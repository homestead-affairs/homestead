"""I-19, I-20 — every path derives from one resolver, in one spelling.

AST scans over the package, in the store's `test_no_inline_vault_root` shape.
Both exist because the failures happened:

  I-19  law-gazelle's documented launcher (`dev.sh:17`) defaulted NEST_SOURCE
        to $HOME/Desktop/Nest, overriding a clean vault default and putting the
        whole case package in the least private directory on a shared machine.
  I-20  `Path(os.path.expanduser("~")) / ".willow" / ...` extracts as bare `~`
        in the store's vault-leak linter and vanishes, while the identical path
        spelled `Path.home() / ...` is correctly flagged.

**Rewritten 2026-08-04 after the Phase 0 audit.** The first version banned call
*names* and substring literals, and an injected
`Path(os.environ["HOME"]) / "Desktop" / "Nest"` — the Desktop leak itself,
in idiomatic pathlib — passed the whole suite. `os.environ[...]` is a
`Subscript`, not a call; `/ "Desktop"` contains no slash. These now scan for
**mechanisms that reach a home directory**, and `test_i19_regression_desktop_leak`
keeps the specific evasion that got through.
"""
from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "homestead"
RESOLVER = PKG / "keep" / "paths.py"

# Every way a module can reach the user's home directory. Names on the left of
# a call, environment keys, and the functions that expand them.
HOME_CALLS = {"expanduser", "expandvars", "getenv"}
HOME_ENV_KEYS = {"HOME", "USERPROFILE", "HOMEPATH", "HOMEDRIVE"}
BANNED_SEGMENTS = {"desktop", "documents", "downloads", "users", "home", "~"}


def _modules() -> list[Path]:
    return sorted(p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts)


def _dotted(node: ast.AST) -> str:
    """`Path.home` from a `Path.home()` call; `paths.home` from `paths.home()`."""
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}".lstrip(".")
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _docstring_ids(tree: ast.AST) -> set[int]:
    """Docstrings are excluded from the literal scan — a docstring cannot create
    a path, and this file caught `paths.py`'s own docstring on its first run,
    where the banned pattern appears precisely because it is documented as
    forbidden. A scanner that fires on its own documentation gets switched off."""
    ids: set[int] = set()
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if isinstance(node, holders) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _home_reaches(tree: ast.AST) -> list[tuple[int, str]]:
    """Every construct in this tree that reaches a home directory."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        # Path.home(), os.path.expanduser(...), os.getenv("HOME"),
        # os.path.expandvars("$HOME"), and any aliased binding of them.
        if isinstance(node, ast.Call):
            dotted = _dotted(node.func)
            leaf = dotted.rsplit(".", 1)[-1]
            if leaf == "home" and dotted != "paths.home":
                hits.append((node.lineno, dotted or "home"))
            elif leaf in HOME_CALLS:
                hits.append((node.lineno, dotted or leaf))
        # os.environ["HOME"] / environ.get("HOME") — a Subscript, not a call,
        # which is exactly how the Desktop leak walked through the first version.
        elif isinstance(node, ast.Subscript):
            if "environ" in _dotted(node.value):
                key = getattr(node.slice, "value", None)
                if isinstance(key, str) and key.upper() in HOME_ENV_KEYS:
                    hits.append((node.lineno, f"environ[{key!r}]"))
    return hits


def test_resolver_exists():
    assert RESOLVER.exists(), "homestead/keep/paths.py is the only path resolver"


def test_i19_i20_only_the_resolver_reaches_home():
    """No module but `keep/paths.py` may reach a home directory, by any means.

    `paths.home()` is explicitly permitted — the resolver exports it, and the
    first version banned calling the very function it published, so the
    invariant would have fired on correct code the moment Phase 1 needed the
    root.
    """
    offenders = []
    for mod in _modules():
        if mod == RESOLVER:
            continue
        for lineno, how in _home_reaches(ast.parse(mod.read_text())):
            offenders.append(f"{mod.relative_to(PKG.parent)}:{lineno} {how}")
    assert not offenders, (
        "only keep/paths.py may resolve a home directory, and only via "
        f"Path.home(). Found: {offenders}"
    )


def test_i20_the_invisible_spelling_is_banned_everywhere():
    """`expanduser` is invisible to the store's vault-leak linter, so it is
    banned even inside the resolver."""
    offenders = []
    for mod in _modules():
        for node in ast.walk(ast.parse(mod.read_text())):
            if isinstance(node, ast.Call) and _dotted(node.func).rsplit(".", 1)[-1] == "expanduser":
                offenders.append(f"{mod.relative_to(PKG.parent)}:{node.lineno}")
    assert not offenders, f"expanduser() is invisible to the linter. Found: {offenders}"


def _path_context_strings(tree: ast.AST) -> list[tuple[int, str]]:
    """String literals used to *build a path*, rather than every string.

    Scoped deliberately. A whole-string check fired on `"home"` inside
    `__all__` — a symbol name, not a path — which is the same family of false
    positive as the docstring hit, and the same lesson: a scan broad enough to
    catch its own vocabulary gets switched off. Two contexts count:

      * an operand of `/` — `root / "Desktop" / "Nest"`, which is how the
        Desktop leak evaded the substring version; and
      * an argument to `Path(...)`.

    Plus any string carrying a separator, wherever it appears, since
    `"~/Desktop"` is unambiguous on its own.
    """
    out: list[tuple[int, str]] = []
    skip = _docstring_ids(tree)

    def note(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in skip:
            out.append((node.lineno, node.value))

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            note(node.left)
            note(node.right)
        elif isinstance(node, ast.Call) and _dotted(node.func).rsplit(".", 1)[-1] == "Path":
            for arg in node.args:
                note(arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in skip:
            if "/" in node.value or "\\" in node.value:
                out.append((node.lineno, node.value))
    return out


def test_i19_no_user_directory_literals():
    """Segment-wise and in path context.

    The first version matched `"~/"` and `"/Desktop"` as substrings, so a path
    assembled a segment at a time — `/ "Desktop" / "Nest"` — contained no slash
    and was invisible.
    """
    offenders = []
    for mod in _modules():
        for lineno, value in _path_context_strings(ast.parse(mod.read_text())):
            segments = {s.strip().lower() for s in value.replace("\\", "/").split("/")}
            hit = segments & BANNED_SEGMENTS
            if hit:
                offenders.append(
                    f"{mod.relative_to(PKG.parent)}:{lineno} {value!r} ({sorted(hit)})"
                )
    assert not offenders, f"user-directory literals are forbidden. Found: {offenders}"


def test_i19_regression_desktop_leak(tmp_path):
    """The exact evasion that passed the first version of this suite.

    Injected into the package, `Path(os.environ["HOME"]) / "Desktop" / "Nest"`
    left 19 tests green. It is F-1 — the worst safety finding in the
    predecessor — reintroduced in idiomatic pathlib. Both scans must catch it.
    """
    leak = tmp_path / "leaky.py"
    leak.write_text(
        "import os\n"
        "from pathlib import Path\n"
        '_LEAK = Path(os.environ["HOME"]) / "Desktop" / "Nest"\n'
    )
    tree = ast.parse(leak.read_text())

    assert _home_reaches(tree), "the mechanism scan must catch os.environ['HOME']"

    caught = [
        v for _, v in _path_context_strings(tree)
        if {s.lower() for s in v.split("/")} & BANNED_SEGMENTS
    ]
    assert caught, "the literal scan must catch a bare 'Desktop' segment"


def test_root_is_env_overridable_and_defaults_under_home(tmp_path, monkeypatch):
    from homestead.keep import paths

    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path / "elsewhere"))
    assert paths.home() == tmp_path / "elsewhere"

    monkeypatch.delenv("HOMESTEAD_HOME", raising=False)
    assert paths.home().name == ".homestead"


def test_every_path_helper_sits_under_the_root(tmp_path, monkeypatch):
    from homestead.keep import paths

    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    root = paths.home()
    for name in paths.__all__:
        if name in ("home", "ensure"):     # `ensure` has side effects; tested below
            continue
        fn = getattr(paths, name)
        if not callable(fn):
            continue
        got = fn("demo") if fn.__code__.co_argcount else fn()
        assert isinstance(got, Path)
        assert root in got.parents or got == root, f"{name}() escaped the root: {got}"


# ── ensure() — the one function carrying a security check ────────────────────

def test_ensure_refuses_traversal(tmp_path, monkeypatch):
    """`.parents` is lexical. Before this was resolved, `ensure(home()/'..'/'..')`
    created a directory at the filesystem root."""
    from homestead.keep import paths

    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path / "root"))
    import pytest
    with pytest.raises(ValueError):
        paths.ensure(Path("..") / ".." / "escaped")


def test_ensure_refuses_absolute_outside(tmp_path, monkeypatch):
    from homestead.keep import paths
    import pytest

    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path / "root"))
    with pytest.raises(ValueError):
        paths.ensure(Path(tmp_path) / "outside")


def test_ensure_refuses_a_symlink_out(tmp_path, monkeypatch):
    from homestead.keep import paths
    import pytest

    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape").symlink_to(outside)
    monkeypatch.setenv("HOMESTEAD_HOME", str(root))
    with pytest.raises(ValueError):
        paths.ensure(Path("escape") / "x")


def test_ensure_creates_under_the_root(tmp_path, monkeypatch):
    from homestead.keep import paths

    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path / "root"))
    got = paths.ensure(Path("logs") / "sub")
    assert got.is_dir() and paths.home().resolve() in got.parents
