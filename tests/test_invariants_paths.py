"""I-19, I-20 — every path derives from one resolver, in one spelling.

These are the store's `test_no_inline_vault_root` shape: AST scans over the
package, not behavioural tests. They exist because the failures they prevent
were both found in the field:

  I-19  law-gazelle's documented launcher (`dev.sh:17`) defaulted NEST_SOURCE
        to $HOME/Desktop/Nest, overriding a clean vault default and putting the
        whole case package in the least private directory on a shared machine.
  I-20  `Path(os.path.expanduser("~")) / ".willow" / ...` extracts as bare `~`
        in the store's vault-leak linter and vanishes, while the identical path
        spelled `Path.home() / ...` is correctly flagged. One spelling is
        visible to the tooling; the other is not.
"""
from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "homestead"
RESOLVER = PKG / "keep" / "paths.py"


def _modules() -> list[Path]:
    return sorted(p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts)


def _calls(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def test_resolver_exists():
    assert RESOLVER.exists(), "homestead/keep/paths.py is the only path resolver"


def test_i20_expanduser_appears_nowhere():
    """The spelling the store's linter cannot see is banned outright."""
    offenders = []
    for mod in _modules():
        tree = ast.parse(mod.read_text())
        for call in _calls(tree):
            if _call_name(call) == "expanduser":
                offenders.append(f"{mod.relative_to(PKG.parent)}:{call.lineno}")
    assert not offenders, (
        "expanduser() is invisible to the store's vault-leak linter — use "
        f"Path.home(), and only in paths.py. Found: {offenders}"
    )


def test_i19_only_the_resolver_reaches_home():
    """`Path.home()` appears in exactly one module."""
    offenders = []
    for mod in _modules():
        if mod == RESOLVER:
            continue
        tree = ast.parse(mod.read_text())
        for call in _calls(tree):
            if _call_name(call) == "home":
                offenders.append(f"{mod.relative_to(PKG.parent)}:{call.lineno}")
    assert not offenders, (
        f"only keep/paths.py may resolve a home directory. Found: {offenders}"
    )


def _docstring_ids(tree: ast.AST) -> set[int]:
    """Docstrings are excluded from the literal scan.

    Not a loophole — a docstring cannot create a filesystem path, and this file
    caught `paths.py`'s own docstring on its first run, where the banned
    `expanduser("~")` pattern appears precisely because it is being documented
    as forbidden. A scanner that fires on its own documentation gets switched
    off, and a switched-off scanner is worse than none.
    """
    ids: set[int] = set()
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if isinstance(node, holders) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def test_i19_no_fixed_user_paths():
    """No literal home-rooted or shared-directory path in executable code."""
    banned = ("~/", "/Desktop", "\\Desktop", "/Users/", "/home/", "C:\\Users")
    offenders = []
    for mod in _modules():
        tree = ast.parse(mod.read_text())
        skip = _docstring_ids(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in skip:
                if any(b in node.value for b in banned):
                    offenders.append(
                        f"{mod.relative_to(PKG.parent)}:{node.lineno} {node.value!r}"
                    )
    assert not offenders, f"fixed user paths are forbidden. Found: {offenders}"


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
        fn = getattr(paths, name)
        if name == "home" or not callable(fn):
            continue
        try:
            got = fn("demo") if fn.__code__.co_argcount else fn()
        except TypeError:
            continue
        assert isinstance(got, Path)
        assert root in got.parents or got == root, f"{name}() escaped the root: {got}"
