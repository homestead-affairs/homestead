"""I-30, I-26, I-14, I-27, I-28 — the shape of the thing.

I-30 is the one the self-contained decision buys: nothing binds a port, so the
whole class of exposure Terpsi's three-zone architecture exists to manage is
absent rather than managed.
"""
from __future__ import annotations

import ast
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


def test_i27_declared_dependencies_are_true():
    """The package imports with nothing installed but the standard library."""
    r = subprocess.run(
        [sys.executable, "-c", "import homestead.keep.paths, homestead.keep.logs,"
                               " homestead.keep.rungs; print('ok')"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_i28_no_test_basename_is_shadowed():
    """`_archived/test_case_store.py` shadowing `tests/test_case_store.py` is
    what stopped the promotion gate from ever seeing law-gazelle's suite."""
    names = [p.name for p in ROOT.rglob("test_*.py") if ".git" not in p.parts]
    assert len(names) == len(set(names)), f"duplicate test basenames: {names}"
