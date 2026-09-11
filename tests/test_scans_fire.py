"""The meta-scan — X7-drift-engine, Wave 7's drift-and-closure sweep.

Phase 0's lesson, restated by every AST/grep guard this suite has grown
since: **a scan that has never fired has not been shown to check anything.**
`test_invariants_chokepoint.py`'s own history is the proof — the first
version of the payload ban matched the *spelling* `.payload` and an audit
walked straight past it with `getattr(record, "payload")`, green the whole
way. Every guard built after that carries its own planted violation.

This file turns that rule on `tests/` itself: every helper function in this
suite that walks a source tree with `ast.walk`/`ast.parse` looking for a
banned or required shape is a scan of exactly that kind, and this meta-scan
asserts each one is exercised by at least one test that plants a violation
and watches it fire — the same property, one level up.

**The naming convention is pinned from the repo, not invented.** Reading
every existing planted-violation test's name turns up four words —
`plant`/`planted` (`test_i39_planted_listeners_are_caught`,
`test_ast_guard_plant_a_bare_equality_and_watch_it_fire`), `fires`
(`test_the_structural_guard_fires_on_a_planted_enumeration`), `catches`
(`test_anchor_catches_truncation`) — and one more that the first three miss:
`regression` (`test_i19_regression_desktop_leak`,
`test_i16_regression_every_bypass_the_audit_found_is_caught`), this
project's word for "the exact bug, replayed." A fifth shape exists too and no
name covers it: `test_invariants_sync.py::test_sync_and_household_reach_no_
payload` composes a violation inline — a local variable literally called
`planted` — and asserts the scan catches it, with no marker in the test's own
name at all. So this meta-scan checks two things, either of which is enough:
the test's *name* carries one of the four words above, or the test's own
*source* (body and docstring) contains the word "planted" — which is what
that fifth shape always does even when its name does not.

**What this sweep found and fixed, X7-drift-engine, 2026-09-11:**
`test_invariants_shape.py`'s `test_i30_i26_nothing_imports_the_network` and
`test_i30_nothing_listens` were both real, both correct, and neither had ever
been run against a violation — the exact "enforcement theatre" Phase 0 was
audited for, still possible one level up from the code it audits. Both scan
bodies are now factored into `_network_import_offenders`/`_listen_offenders`
and each has a planted-violation test calling that same helper, so the real
scan and its plant cannot drift into checking two different things.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

#: This file, excluded from its own sweep — see `test_the_meta_scan_fires_
#: on_a_planted_omission` and its negative control below for the meta-scan's
#: own planted violation, run against a synthetic fixture rather than against
#: itself, so a passing sweep here can never be "this file plants nothing and
#: also declines to check that."
SELF = Path(__file__).resolve()

#: The repo's own naming convention for a planted-violation test, read off
#: the tests that already exist (see the module docstring) rather than
#: guessed. Checked against the test *name*; the "planted" body/docstring
#: check below is the second, independent way a test can qualify.
NAME_MARKERS = ("plant", "fires", "catches", "regression")


def _ast_scan_helpers(tree: ast.Module) -> list[str]:
    """Module-level, non-`test_*` function defs whose body calls
    `ast.walk(...)` or `ast.parse(...)` anywhere inside it — the shape every
    AST-based package scan in this suite takes (`_payload_reaches`,
    `_matter_name_enumerations`, `_offenders`, `_network_import_offenders`,
    …). A function that only *receives* an already-parsed tree and never
    calls `ast.walk`/`ast.parse` itself (`_digest_named`, a predicate over one
    node) is not counted — it has no scan of its own to plant against; the
    function that walks the tree and calls it does.
    """
    helpers: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("test_"):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Attribute)
                and inner.func.attr in ("walk", "parse")
                and isinstance(inner.func.value, ast.Name)
                and inner.func.value.id == "ast"
            ):
                helpers.append(node.name)
                break
    return helpers


def _test_sources(tree: ast.Module, source: str) -> dict[str, str]:
    """`{test function name: its own source text}` — body and docstring both,
    since the fifth shape in the module docstring plants inside the body with
    no marker in the name."""
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            out[node.name] = ast.get_source_segment(source, node) or ""
    return out


def _has_a_planted_violation_test(path: Path) -> bool:
    """True if some test in `path` is named for the convention, or plants a
    violation in its own body without saying so in its name."""
    source = path.read_text("utf-8")
    tree = ast.parse(source, filename=str(path))
    for name, body in _test_sources(tree, source).items():
        if any(marker in name for marker in NAME_MARKERS):
            return True
        if "planted" in body.lower():
            return True
    return False


def _files_with_unfired_scans(paths: list[Path]) -> dict[str, list[str]]:
    """`{file name: [helper names]}` for every file that defines at least one
    AST-scanning helper but carries no planted-violation test by the
    convention above. Keyed by `.name` rather than a full path — these are
    always single-segment file names, never a path a Windows/posix suffix
    comparison could disagree about."""
    offenders: dict[str, list[str]] = {}
    for path in paths:
        if path.resolve() == SELF:
            continue
        source = path.read_text("utf-8")
        tree = ast.parse(source, filename=str(path))
        helpers = _ast_scan_helpers(tree)
        if helpers and not _has_a_planted_violation_test(path):
            offenders[path.name] = helpers
    return offenders


def test_every_ast_scan_helper_in_tests_has_a_planted_violation_test():
    """The meta-scan, run for real: every `tests/*.py` file that defines an
    AST-walking package scan must carry a test that plants a violation
    against it and watches it fire. Vacuous the day `test_invariants_
    chokepoint.py` was the only such file; not vacuous the day someone adds a
    ninth scan and forgets the ninth plant — which is exactly what had
    already happened, twice, in `test_invariants_shape.py` before this bite.
    """
    offenders = _files_with_unfired_scans(sorted(TESTS_DIR.glob("*.py")))
    assert not offenders, (
        f"these test files scan the package with an AST helper but plant no "
        f"violation against it: {offenders}. Add a test whose name contains "
        f"one of {NAME_MARKERS}, or whose body composes a violation and "
        "calls the scan on it (the repo's convention: name the composed "
        "value 'planted')."
    )


def test_the_meta_scan_fires_on_a_planted_omission(tmp_path):
    """The meta-scan's own plant, per the plan's own instruction for this
    bite ("itself planted"). A synthetic file carrying a real AST-walking
    helper and zero planted-violation tests must be caught — run against a
    fixture, never against this file itself, so the sweep this file performs
    for real above cannot be satisfied by this test happening to pass."""
    unfired = tmp_path / "test_fake_unfired_scan.py"
    unfired.write_text(
        "import ast\n\n"
        "def _hardcoded_thing(tree):\n"
        "    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant)]\n\n"
        "def test_nothing_is_hardcoded():\n"
        "    assert not _hardcoded_thing(ast.parse('x = 1'))\n",
        "utf-8",
    )
    assert _files_with_unfired_scans([unfired]) == {
        "test_fake_unfired_scan.py": ["_hardcoded_thing"]
    }


def test_the_meta_scan_does_not_fire_on_a_properly_planted_file(tmp_path):
    """The negative control the plant above needs: the identical helper, this
    time with a test named for the convention, must NOT be flagged —
    otherwise this meta-scan would pass just as easily by asserting every
    file is guilty, which is not a check, it is an opinion."""
    fired = tmp_path / "test_fake_fired_scan.py"
    fired.write_text(
        "import ast\n\n"
        "def _hardcoded_thing(tree):\n"
        "    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant)]\n\n"
        "def test_the_hardcoded_scan_fires_on_a_planted_constant():\n"
        "    assert _hardcoded_thing(ast.parse('x = 1'))\n",
        "utf-8",
    )
    assert _files_with_unfired_scans([fired]) == {}


def test_the_meta_scan_accepts_an_unnamed_plant_that_says_so_in_its_body(tmp_path):
    """The fifth shape (module docstring): a test with no marker word in its
    *name* still qualifies if it plants a violation in its own body — the
    real precedent is `test_invariants_sync.py::test_sync_and_household_
    reach_no_payload`, reproduced here in miniature so this file's own
    behaviour is pinned rather than only described."""
    unnamed_plant = tmp_path / "test_fake_unnamed_plant.py"
    unnamed_plant.write_text(
        "import ast\n\n"
        "def _hardcoded_thing(tree):\n"
        "    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant)]\n\n"
        "def test_nothing_is_hardcoded():\n"
        "    assert not _hardcoded_thing(ast.parse('x = 1'))\n"
        "    planted = ast.parse('x = 1')\n"
        "    assert _hardcoded_thing(planted)\n",
        "utf-8",
    )
    assert _files_with_unfired_scans([unnamed_plant]) == {}
