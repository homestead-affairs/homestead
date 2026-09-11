"""The meta-scan — X7-drift-engine, Wave 7's drift-and-closure sweep.

Phase 0's lesson, restated by every AST/grep guard this suite has grown
since: **a scan that has never fired has not been shown to check anything.**
`test_invariants_chokepoint.py`'s own history is the proof — the first
version of the payload ban matched the *spelling* `.payload` and an audit
walked straight past it with `getattr(record, "payload")`, green the whole
way. Every guard built after that carries its own planted violation.

This file turns that rule on `tests/` itself, and it has to do so
**structurally**, because the two ways of getting it wrong are both easy:

* **Discovery too narrow.** The first version of this file counted a helper
  as a scan only if it called `ast.walk`/`ast.parse`. A guard that greps
  (`re.search` over a file's text) or that reads a file and asks "is this
  sentence still in it" is the same kind of check with the same failure
  mode, and was invisible to it. `_owners_named_in`, `_fields_missing_step`,
  `_modules_named_in`, `_leaks`, `live` — five real guards, none of them
  AST-shaped, none of them swept. Discovery here is therefore three shapes,
  not one (`_scan_kinds` below), and there is no leading-underscore rule:
  `_strikethrough.live` is a scan with a public name.
* **The plant test judged by its name.** The first version asked whether the
  *file* contained a test whose name carried a plant-ish word. A file with
  five scans and one plant passed; so would a file whose plant tested
  something else entirely. What makes a plant a plant is that it **runs the
  scan** — so `_planted_scans` walks the module's own call graph from each
  plant test and keeps only the scans it actually reaches, directly or
  through the module's helpers (and across modules for a helper imported
  from another file in `tests/`, which is how `_strikethrough.live` is
  planted by `test_invariants_registry.py` and `test_docs_drift.py`).

**The naming convention is pinned from the repo, not invented.** Reading
every existing planted-violation test's name turns up four words —
`plant`/`planted` (`test_i39_planted_listeners_are_caught`,
`test_ast_guard_plant_a_bare_equality_and_watch_it_fire`), `fires`
(`test_the_structural_guard_fires_on_a_planted_enumeration`), `catches`
(`test_anchor_catches_truncation`) — and one more that the first three miss:
`regression` (`test_i19_regression_desktop_leak`), this project's word for
"the exact bug, replayed." A fifth shape exists too and no name covers it:
`test_invariants_sync.py::test_sync_and_household_reach_no_payload` composes
a violation inline — a local variable literally called `planted` — with no
marker in the test's own name. So a test qualifies as a plant if its *name*
carries one of the four words, or its own *source* contains "planted"; and
then it only counts for the scans it is shown to call.

**What this sweep found, X7-drift-engine, 2026-09-11:**

* the builder's leg, with the AST-only discovery: `test_invariants_shape.py`'s
  `test_i30_i26_nothing_imports_the_network` and `test_i30_nothing_listens`
  were both real, both correct, and neither had ever been run against a
  violation. Both scan bodies are now factored into
  `_network_import_offenders`/`_listen_offenders`, each with its own plant.
* the audit's leg, with discovery widened and the plant tied to a call:
  `test_invariants_pack_contract.py`'s `_derived_of_source` (the AST half of
  the `derived_of` reflection guard — its file had plants, but none of them
  ran *that* scan) and `test_invariants_logs.py`'s `_latest_released_version`
  (a `re.search` over `CHANGELOG.md` that decides which half of the
  deprecation-window assertion runs, and had never been shown to read a
  changelog at all). Both are planted in their own files.

Inline scans — a `for node in ast.walk(...)` written in the body of a
`test_*` function — are out of this sweep's reach by construction: a test is
not a helper, and a test that scans inline *is* its own only caller, so
"does a plant call it" has no answer. The remedy is the one both legs above
used: factor the scan into a helper, which puts it in this sweep, and plant
it.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

#: This file, excluded from its own sweep — see the planted fixtures below
#: for the meta-scan's own violations, run against synthetic files rather
#: than against itself, so a passing sweep here can never be "this file
#: plants nothing and also declines to check that."
SELF = Path(__file__).resolve()

#: The repo's own naming convention for a planted-violation test, read off
#: the tests that already exist (see the module docstring) rather than
#: guessed. Checked against the test *name*; the "planted" body/docstring
#: check below is the second, independent way a test can qualify.
NAME_MARKERS = ("plant", "fires", "catches", "regression")

#: `re` functions that answer "does this text match a pattern". `sub`/`split`
#: are not here as bare names — `str` has both — but they *are* reached as
#: methods of a name this module can see was bound by `re.compile`, which is
#: how `_strikethrough.live`'s `_STRUCK.sub(...)` is counted.
PATTERN_FUNCTIONS = ("search", "findall", "finditer", "match", "fullmatch", "compile")

#: Reading a file's text is half of the third shape; the other half is an
#: `in`/`not in` question asked about what came back.
READ_CALLS = ("read_text", "read_bytes")


def _is_fixture(node: ast.FunctionDef) -> bool:
    """A `@pytest.fixture` is scaffolding, not a scan: it hands other tests a
    tree or a temp file and asserts nothing of its own."""
    return any("fixture" in ast.dump(d) for d in node.decorator_list)


def _compiled_pattern_names(node: ast.AST) -> set[str]:
    """Names bound to `re.compile(...)` anywhere under `node` — module-level
    constants (`_STRUCK`, `_OWNER_NAMED`, `_CODE_SPAN_MODULE`) and locals
    alike. Knowing them is what lets `_scan_kinds` count `_STRUCK.sub(...)`
    as pattern matching without counting every `str.split` in the suite."""
    names: set[str] = set()
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Assign):
            continue
        value = inner.value
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "compile"
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "re"
        ):
            names |= {t.id for t in inner.targets if isinstance(t, ast.Name)}
    return names


def _scan_kinds(node: ast.FunctionDef, compiled: set[str]) -> list[str]:
    """Why this function is a scan, or `[]` if it is not — the three shapes
    every guard in this suite takes:

    * **walks source** — `ast.parse`/`ast.walk` (`_payload_reaches`,
      `_matter_name_enumerations`, `_listen_offenders`);
    * **matches a pattern** — `re.search`/`findall`/`finditer`/`match`/
      `fullmatch`/`compile`, a method of a name bound by `re.compile`, or a
      bare `compile(...)` (`_owners_named_in`, `_fields_missing_step`,
      `_latest_released_version`, `live`);
    * **reads text and asks membership** — a `read_text`/`read_bytes` call
      and an `in`/`not in` question in the same body (the grep guards that
      never touch `re` at all).
    """
    walks = matches = reads = membership = False
    for inner in ast.walk(node):
        if isinstance(inner, ast.Compare) and any(
            isinstance(op, (ast.In, ast.NotIn)) for op in inner.ops
        ):
            membership = True
        if not isinstance(inner, ast.Call):
            continue
        func = inner.func
        if isinstance(func, ast.Attribute):
            receiver = func.value.id if isinstance(func.value, ast.Name) else None
            if func.attr in ("walk", "parse") and receiver == "ast":
                walks = True
            if func.attr in PATTERN_FUNCTIONS and receiver == "re":
                matches = True
            if receiver is not None and receiver in compiled:
                matches = True
            if func.attr in READ_CALLS:
                reads = True
        elif isinstance(func, ast.Name) and func.id == "compile":
            matches = True
    kinds = []
    if walks:
        kinds.append("walks source")
    if matches:
        kinds.append("matches a pattern")
    if reads and membership:
        kinds.append("reads text and asks membership")
    return kinds


def _module_facts(path: Path) -> dict:
    """Everything one file in `tests/` contributes to the sweep: its
    module-level functions, which of them are scans, which of its tests are
    plants, and what it imported from its neighbours."""
    source = path.read_text("utf-8")
    tree = ast.parse(source, filename=str(path))
    compiled = _compiled_pattern_names(tree)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    scans: dict[str, list[str]] = {}
    plants: list[str] = []
    for name, node in functions.items():
        if name.startswith("test_"):
            body = ast.get_source_segment(source, node) or ""
            if any(marker in name for marker in NAME_MARKERS) or "planted" in body.lower():
                plants.append(name)
            continue
        if _is_fixture(node):
            continue
        kinds = _scan_kinds(node, compiled | _compiled_pattern_names(node))
        if kinds:
            scans[name] = kinds

    imported: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            # `from _strikethrough import live` and `from tests.x import y`
            # both resolve to the neighbouring file's stem.
            origin = node.module.split(".")[-1]
            for alias in node.names:
                imported[alias.asname or alias.name] = (origin, alias.name)

    return {
        "path": path,
        "functions": functions,
        "scans": scans,
        "plants": plants,
        "imported": imported,
    }


def _called_names(node: ast.AST) -> set[str]:
    """Every name this function calls, by the last segment — `helper()` and
    `module.helper()` both count, which is what lets a plant reach a helper
    it imported under its own name."""
    called: set[str] = set()
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        func = inner.func
        if isinstance(func, ast.Name):
            called.add(func.id)
        elif isinstance(func, ast.Attribute):
            called.add(func.attr)
    return called


def _planted_scans(facts: dict[str, dict]) -> set[tuple[str, str]]:
    """`{(module stem, scan name)}` reachable from some plant test by calls —
    the whole point of this rewrite. A plant that never calls the scan is a
    word in a name, not evidence."""
    reached: set[tuple[str, str]] = set()
    frontier = [(stem, plant) for stem, mod in facts.items() for plant in mod["plants"]]
    while frontier:
        stem, name = frontier.pop()
        if (stem, name) in reached:
            continue
        reached.add((stem, name))
        mod = facts.get(stem)
        if mod is None or name not in mod["functions"]:
            continue
        for called in _called_names(mod["functions"][name]):
            if called in mod["functions"]:
                frontier.append((stem, called))
            elif called in mod["imported"]:
                origin, original = mod["imported"][called]
                if origin in facts:
                    frontier.append((origin, original))
    return reached


def unplanted_scans(paths: list[Path]) -> dict[str, list[str]]:
    """`{"<file>::<helper>": [why it is a scan]}` for every scan no plant
    test reaches. Keyed by `.name`, never a full path — these are
    single-segment file names, so no Windows/posix separator can get into a
    key or a message."""
    facts = {p.stem: _module_facts(p) for p in paths if p.resolve() != SELF}
    planted = _planted_scans(facts)
    return {
        f"{mod['path'].name}::{name}": kinds
        for stem, mod in facts.items()
        for name, kinds in mod["scans"].items()
        if (stem, name) not in planted
    }


def test_every_scan_in_tests_has_a_planted_violation_test():
    """The meta-scan, run for real: every helper in `tests/` that walks a
    source tree, matches text with a pattern, or reads a file and asks a
    membership question must be *called* by a test that plants a violation
    against it. Not vacuous: the day it was widened from "AST only" to these
    three shapes and from "the file has a plant-ish name" to "a plant calls
    it", it named two more real, never-fired scans."""
    offenders = unplanted_scans(sorted(TESTS_DIR.glob("*.py")))
    assert not offenders, (
        f"these scans are never run against a violation: {offenders}. Add a "
        f"test that calls the scan on a planted violation — name it with one "
        f"of {NAME_MARKERS}, or call the composed value 'planted' (this "
        "repo's two conventions). A scan that has never fired has not been "
        "shown to check anything."
    )


def _write(path: Path, *lines: str) -> Path:
    path.write_text("\n".join(lines) + "\n", "utf-8")
    return path


def test_the_meta_scan_fires_on_a_planted_ast_scan_under_a_public_name(tmp_path):
    """Plant 1 of 3 — the AST shape, deliberately named *without* a leading
    underscore. The first version of this file swept `_`-prefixed helpers by
    habit; `_strikethrough.live` is a real scan with a public name, so a
    public name must not be a way out."""
    planted = _write(
        tmp_path / "test_fake_public_ast_scan.py",
        "import ast",
        "",
        "def hardcoded_constants(tree):",
        "    return [n.lineno for n in ast.walk(tree)]",
        "",
        "def test_nothing_is_hardcoded():",
        "    assert not hardcoded_constants(ast.parse('x = 1'))",
    )
    assert unplanted_scans([planted]) == {
        "test_fake_public_ast_scan.py::hardcoded_constants": ["walks source"]
    }


def test_the_meta_scan_fires_on_a_planted_grep_shaped_scan(tmp_path):
    """Plant 2 of 3 — the shape the AST-only discovery could not see at all:
    a guard that greps. `_owners_named_in` and `_latest_released_version` are
    the real ones; this is that shape in miniature."""
    planted = _write(
        tmp_path / "test_fake_grep_scan.py",
        "import re",
        "from pathlib import Path",
        "",
        "_BANNED = re.compile(r'TODO')",
        "",
        "def banned_words_in(path):",
        "    return _BANNED.findall(Path(path).read_text('utf-8'))",
        "",
        "def sentence_is_still_claimed(path):",
        "    return 'the old claim' in Path(path).read_text('utf-8')",
        "",
        "def test_no_banned_words(tmp_path):",
        "    assert not banned_words_in(tmp_path / 'x.txt')",
    )
    assert unplanted_scans([planted]) == {
        "test_fake_grep_scan.py::banned_words_in": ["matches a pattern"],
        "test_fake_grep_scan.py::sentence_is_still_claimed": [
            "reads text and asks membership"
        ],
    }


def test_the_meta_scan_fires_on_a_plant_that_only_names_itself_one(tmp_path):
    """Plant 3 of 3, and the reason this file was rewritten: a file whose
    plant-named test does not *call* the scan. Under the first version —
    "does this file contain a test named for the convention" — this passed,
    and so did `test_invariants_pack_contract.py`, whose four plant-named
    tests all ran a different scan from the one that had never fired."""
    planted = _write(
        tmp_path / "test_fake_name_only_plant.py",
        "import ast",
        "",
        "def _reflection_reaches(tree):",
        "    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)]",
        "",
        "def _something_else(value):",
        "    return value * 2",
        "",
        "def test_the_guard_fires_on_a_planted_violation():",
        "    assert _something_else(1) == 2",
    )
    assert unplanted_scans([planted]) == {
        "test_fake_name_only_plant.py::_reflection_reaches": ["walks source"]
    }


def test_the_meta_scan_does_not_fire_on_a_plant_that_calls_the_scan(tmp_path):
    """Negative control 1: the identical helper, this time called by a test
    named for the convention, must NOT be flagged — a meta-scan that passed
    by calling every file guilty would not be a check, it would be an
    opinion. Transitivity is pinned here too: the plant calls a wrapper,
    which calls the scan."""
    clean = _write(
        tmp_path / "test_fake_fired_scan.py",
        "import ast",
        "",
        "def _reflection_reaches(tree):",
        "    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)]",
        "",
        "def _offenders(source):",
        "    return _reflection_reaches(ast.parse(source))",
        "",
        "def test_the_guard_fires_on_a_planted_call():",
        "    assert _offenders('f()')",
    )
    assert unplanted_scans([clean]) == {}


def test_the_meta_scan_does_not_fire_on_a_fixture_or_an_unnamed_plant(tmp_path):
    """Negative control 2, two ways at once. A `@pytest.fixture` that parses
    a tree is scaffolding, not a guard, and must not be swept; and a test
    with no marker word in its *name* still counts as a plant if it composes
    the violation in its body — the fifth shape the module docstring names,
    whose real precedent is `test_invariants_sync.py::test_sync_and_
    household_reach_no_payload`."""
    clean = _write(
        tmp_path / "test_fake_fixture_and_unnamed_plant.py",
        "import ast",
        "import pytest",
        "",
        "@pytest.fixture",
        "def parsed():",
        "    return ast.parse('x = 1')",
        "",
        "def _constants(tree):",
        "    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant)]",
        "",
        "def test_nothing_is_hardcoded(parsed):",
        "    assert not _constants(ast.parse('pass'))",
        "    planted = ast.parse('x = 1')",
        "    assert _constants(planted)",
    )
    assert unplanted_scans([clean]) == {}
