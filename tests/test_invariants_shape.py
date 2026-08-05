"""I-30, I-26, I-14, I-27, I-28 — the shape of the thing.

I-30 is the one the self-contained decision buys: nothing binds a port, so the
whole class of exposure Terpsi's three-zone architecture exists to manage is
absent rather than managed.
"""
from __future__ import annotations

import ast
import importlib.metadata as md
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "homestead"

NET = {"socket", "ssl", "urllib", "http", "requests", "httpx",
       "aiohttp", "websockets", "urllib3", "socketserver", "ftplib",
       "telnetlib", "smtplib", "xmlrpc"}


def _modules() -> list[Path]:
    return sorted(p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts)


def _toplevel_imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_i30_i26_nothing_imports_the_network():
    """No network module at import time, anywhere. Not the core, not a surface."""
    offenders = {}
    for mod in _modules():
        hits = NET & _toplevel_imports(ast.parse(mod.read_text()))
        if hits:
            offenders[str(mod.relative_to(ROOT))] = sorted(hits)
    assert not offenders, (
        f"nothing in this application binds or dials. Found: {offenders}"
    )


def test_i30_nothing_listens():
    """No bind/listen/serve call survives review, however it is spelled."""
    # `bind` is deliberately NOT here. tkinter spells event binding
    # `widget.bind(...)`, so banning the bare name would fire on every key
    # handler in the surface layer and the test would be switched off within a
    # week. The real control is the import scan above: nothing binds a socket
    # without importing one. These four names have no GUI meaning.
    banned = {"listen", "serve_forever", "create_server", "ThreadingHTTPServer"}
    offenders = []
    for mod in _modules():
        tree = ast.parse(mod.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in banned:
                    offenders.append(f"{mod.relative_to(ROOT)}:{node.lineno} {name}")
    assert not offenders, f"nothing may listen. Found: {offenders}"


def test_i14_rungs_are_strings_not_integers():
    from homestead.keep.rungs import Rung

    for r in Rung:
        assert isinstance(r.value, str) and r.value.startswith("L")
    assert Rung.L3.value == "L3"
    assert not isinstance(Rung.L3.value, int)


def test_i14_rung_max_composition():
    from homestead.keep.rungs import Rung, compose

    assert compose(Rung.L1, Rung.L4) is Rung.L4
    assert compose(Rung.L2, Rung.L2) is Rung.L2
    assert compose() is Rung.L5, "absence fails closed — nothing is not L1"
    assert compose(Rung.L1, Rung.L5, Rung.L3) is Rung.L5


def test_i27_the_core_needs_nothing_but_the_standard_library():
    """`paths`, `logs` and `rungs` import with nothing installed but stdlib.

    This said "the package" until Phase 1, when `dates` took a dependency on
    `holidays` and made that sentence false. Narrowed rather than deleted: the
    three modules every other module builds on staying stdlib-only is a real
    property worth holding, and it is the one this subprocess actually checks.
    The general claim — *everything imported is declared* — is now
    `test_i27_every_third_party_import_is_declared` below, which is where it
    belonged all along.
    """
    r = subprocess.run(
        [sys.executable, "-c", "import homestead.keep.paths, homestead.keep.logs,"
                               " homestead.keep.rungs; print('ok')"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_i27_every_third_party_import_is_declared():
    """Nothing is imported that `pyproject.toml` does not name.

    The gap this closes: `holidays` pulls in `python-dateutil`, which pulls in
    `six`, so both are importable in a working checkout without being declared
    anywhere. A module that reached for `six` would run fine here and fail on
    someone else's machine the day `holidays` dropped it — an ambient
    dependency, which is exactly the shape I-27 exists to forbid.

    Import names are mapped to distribution names through the installed
    metadata rather than assumed equal, because they routinely differ
    (`dateutil` ships in `python-dateutil`).
    """
    declared_block = re.search(
        r"^dependencies\s*=\s*\[(.*?)\]",
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE | re.DOTALL,
    )
    assert declared_block, "pyproject.toml must have a dependencies list"
    declared = {
        m.lower().replace("_", "-")
        for m in re.findall(r'"([A-Za-z0-9._-]+)', declared_block.group(1))
    }

    dist_of = md.packages_distributions()
    offenders: list[str] = []
    for mod in _modules():
        tree = ast.parse(mod.read_text(encoding="utf-8"))
        for name in _toplevel_imports(tree):
            if name == "homestead" or name in sys.stdlib_module_names:
                continue
            dists = {d.lower().replace("_", "-") for d in dist_of.get(name, [])}
            if not dists & declared:
                offenders.append(
                    f"{mod.relative_to(ROOT)} imports {name!r}"
                    f" (ships in {sorted(dists) or 'nothing installed'})"
                )
    assert not offenders, (
        "every third-party import must be a declared dependency, not one that "
        f"happens to be installed. Found: {offenders}"
    )


def test_i28_no_test_basename_is_shadowed():
    """`_archived/test_case_store.py` shadowing `tests/test_case_store.py` is
    what stopped the promotion gate from ever seeing law-gazelle's suite."""
    names = [p.name for p in ROOT.rglob("test_*.py") if ".git" not in p.parts]
    assert len(names) == len(set(names)), f"duplicate test basenames: {names}"
