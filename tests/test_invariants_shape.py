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


def _dotted(node: ast.AST) -> str:
    """`urllib.request.urlopen` for the attribute chain that spells it, and
    `""` for anything that is not a plain dotted name."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        root = _dotted(node.value)
        return f"{root}.{node.attr}" if root else ""
    return ""


def _any_network_import(tree: ast.Module) -> set[str]:
    """Network modules imported *anywhere* in the file, nested imports
    included. `_toplevel_imports` deliberately reads only `tree.body` — I-30
    is about import time — so a lazily imported dialler is invisible to it.
    This is the wider reading, used for the two checks below that are about
    what the code *does* rather than what it costs to import."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names & NET


def _label(mod: Path) -> str:
    """A path in a message or a dict key, spelled the one way Windows and
    posix agree on (CI runs both)."""
    return mod.relative_to(ROOT).as_posix() if mod.is_relative_to(ROOT) else mod.name


#: The one module allowed to *spell* a network call, and only in the call-chain
#: half of the scan below. `keep/egress.py` is the sanctioned door: I-17 says
#: nothing leaves without a per-call act that shows the operator the `Wire`,
#: and the send that act reaches has to name `urllib` somewhere. Its own
#: module docstring, `test_invariants_egress.py` and
#: `test_egress_imports_no_network_at_module_load` hold the rest of the
#: promise; what stays banned for it, like everything else, is the *import*
#: at module load. Same shape as the chokepoint's allowance for `keep/rungs.py`
#: to reach a `.payload`: one named door, not a category.
_DIAL_ALLOWED = {("keep", "egress.py")}


def _network_import_offenders(paths: list[Path]) -> dict[str, list[str]]:
    """Every path, among `paths`, that imports a network module at the top
    level, **or** spells a call on one whatever the import looked like.

    Factored out (X7-drift) so the real package scan and its
    planted-violation test below run the identical check — this scan had
    never fired before that test existed. The audit leg then added the
    second half: `_toplevel_imports` reads `tree.body` only, so
    `urllib.request.urlopen(...)` reached through an import inside a function
    passed the whole scan. The call chain is caught by its root name, which
    is the same word in either spelling.
    """
    offenders: dict[str, list[str]] = {}
    for mod in paths:
        tree = ast.parse(mod.read_text())
        hits = NET & _toplevel_imports(tree)
        if mod.parts[-2:] not in _DIAL_ALLOWED:
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                dotted = _dotted(node.func)
                root = dotted.split(".")[0]
                if dotted and "." in dotted and root in NET:
                    hits = hits | {root}
        if hits:
            offenders[_label(mod)] = sorted(hits)
    return offenders


def test_i30_i26_nothing_imports_the_network():
    """No network module at import time, anywhere. Not the core, not a surface."""
    offenders = _network_import_offenders(_modules())
    assert not offenders, (
        f"nothing in this application binds or dials. Found: {offenders}"
    )


def test_i30_i26_the_network_import_scan_fires_on_a_planted_import(tmp_path):
    """A scan that has never fired has not been shown to check anything
    (X7-drift): this file had no planted violation for either network scan
    until the builder's leg, and the builder's plant was one line —
    `import socket` — which is the one spelling nobody would use to hide a
    dial. Four spellings now, three of them import forms the scan has to
    normalise (`from X import y`, `import x.y as z`) and one of them the
    hole the audit found: the import moved inside a function, where
    `_toplevel_imports` cannot see it, and only the call chain is left.
    """
    bare = tmp_path / "bare.py"
    bare.write_text("import socket\n\ndef dial():\n    return socket.socket()\n")
    assert _network_import_offenders([bare]) == {"bare.py": ["socket"]}

    from_import = tmp_path / "from_import.py"
    from_import.write_text(
        "from urllib import request\n\ndef dial(url):\n    return request.urlopen(url)\n"
    )
    assert _network_import_offenders([from_import]) == {"from_import.py": ["urllib"]}

    aliased = tmp_path / "aliased.py"
    aliased.write_text(
        "import http.client as h\n\ndef dial():\n    return h.HTTPConnection('x')\n"
    )
    assert _network_import_offenders([aliased]) == {"aliased.py": ["http"]}

    lazy = tmp_path / "lazy.py"
    lazy.write_text(
        "def dial(url):\n"
        "    import urllib.request\n"
        "    return urllib.request.urlopen(url).read()\n"
    )
    assert _network_import_offenders([lazy]) == {"lazy.py": ["urllib"]}, (
        "a dial whose import hides inside the function is still a dial — the "
        "call chain names the module whatever the import looked like"
    )

    # The sanctioned door is exempt from the call-chain half and from nothing
    # else: a `keep/egress.py` that imported urllib at module load would still
    # be caught, which is the half of I-26 the allowance does not touch.
    door = tmp_path / "keep"
    door.mkdir()
    (door / "egress.py").write_text(
        "def send(url):\n"
        "    import urllib.request\n"
        "    return urllib.request.urlopen(url)\n"
    )
    assert _network_import_offenders([door / "egress.py"]) == {}

    (door / "egress.py").write_text(
        "import urllib.request\n\ndef send(url):\n    return urllib.request.urlopen(url)\n"
    )
    assert _network_import_offenders([door / "egress.py"]) == {"egress.py": ["urllib"]}


#: `bind` is deliberately NOT an unconditional ban. tkinter spells event
#: binding `widget.bind(...)`, so banning the bare name would fire on every
#: key handler in the surface layer and the test would be switched off within
#: a week. It is banned *conditionally* below, in a file that has a network
#: module in scope, where `bind` has only one meaning. The rest have no GUI
#: meaning at all: `HTTPServer`/`ThreadingHTTPServer` construct a listener,
#: `start_server` is asyncio's, `create_server` is asyncio's and ssl's.
_LISTEN_BANNED = {
    "listen",
    "serve_forever",
    "create_server",
    "start_server",
    "HTTPServer",
    "ThreadingHTTPServer",
    "TCPServer",
    "ThreadingTCPServer",
}

#: Banned only where a network module is in scope — see above.
_LISTEN_BANNED_NEAR_A_SOCKET = {"bind"}


def _listen_offenders(paths: list[Path]) -> list[str]:
    """Every bind/listen/serve call, however it is spelled, among `paths`.
    Factored out (X7-drift) for the same reason `_network_import_offenders`
    was: the real scan and its plant must run one check, not two. The audit
    leg widened the banned set — `HTTPServer(...)` and
    `asyncio.start_server(...)` are listeners the four original names walked
    straight past — and added the conditional `bind`."""
    offenders: list[str] = []
    for mod in paths:
        tree = ast.parse(mod.read_text())
        conditional = (
            _LISTEN_BANNED_NEAR_A_SOCKET if _any_network_import(tree) else set()
        )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            root = _dotted(f).split(".")[0]
            if name in _LISTEN_BANNED or name in conditional or (
                name in _LISTEN_BANNED_NEAR_A_SOCKET and root in NET
            ):
                offenders.append(f"{_label(mod)}:{node.lineno} {name}")
    return offenders


def test_i30_nothing_listens():
    """No bind/listen/serve call survives review, however it is spelled."""
    offenders = _listen_offenders(_modules())
    assert not offenders, f"nothing may listen. Found: {offenders}"


def test_i30_the_listen_scan_fires_on_a_planted_call(tmp_path):
    """The plant this scan never had (X7-drift), widened by the audit to the
    four spellings a listener actually arrives in. `socket.bind` is the one
    the original scan could not take at all — `bind` is tkinter's word too —
    so it is caught by its company: a `bind` in a file with a socket in
    scope is not a key handler."""
    served = tmp_path / "served.py"
    served.write_text("def run(server):\n    server.serve_forever()\n")
    assert _listen_offenders([served]) == ["served.py:2 serve_forever"]

    bound = tmp_path / "bound.py"
    bound.write_text(
        "import socket\n\n"
        "def run():\n"
        "    s = socket.socket()\n"
        "    s.bind(('127.0.0.1', 0))\n"
        "    s.listen(1)\n"
    )
    assert _listen_offenders([bound]) == ["bound.py:5 bind", "bound.py:6 listen"]

    http_server = tmp_path / "http_server.py"
    http_server.write_text(
        "from http.server import HTTPServer, BaseHTTPRequestHandler\n\n"
        "def run():\n"
        "    return HTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)\n"
    )
    assert _listen_offenders([http_server]) == ["http_server.py:4 HTTPServer"]

    aio = tmp_path / "aio.py"
    aio.write_text(
        "import asyncio\n\n"
        "async def run(handler):\n"
        "    return await asyncio.start_server(handler, '127.0.0.1', 0)\n"
    )
    assert _listen_offenders([aio]) == ["aio.py:4 start_server"]


def test_the_listen_scan_does_not_fire_on_a_tkinter_key_handler(tmp_path):
    """The negative control the conditional `bind` needs, and the reason the
    ban was never unconditional: `widget.bind("<Key>", handler)` in a file
    with no network module in scope is a key handler, and a scan that fires
    on it is a scan somebody switches off."""
    view = tmp_path / "view.py"
    view.write_text(
        "import tkinter as tk\n\n"
        "def wire(widget, handler):\n"
        "    widget.bind('<Return>', handler)\n"
    )
    assert _listen_offenders([view]) == []


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
