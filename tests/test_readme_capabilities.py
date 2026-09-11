"""README's capabilities table names every `keep`/`app` module, or excludes it.

X7-drift-engine, Wave 7's README requirement: one row per engine capability
the affairs build-out plan added, naming the release that shipped it — see
README.md's "Engine capabilities, and what shipped them". That table does not
re-describe Phase 0–2's foundations (the gate, the store, the two logs before
either grew its Wave-5/6 extra, the registry, the citation extractor, the
first two surfaces) — those already have their own "What is enforced here
today" table just above it, unchanged by this bite. So the property this file
holds is not "every module is a capability row"; it is **every module is
accounted for somewhere** — named in the capabilities table, or in this
file's own `FOUNDATION` exclusion tuple, each with a one-line reason. A
module in neither is exactly BUG-6's shape one level up: a thing that exists
and is not enumerated anywhere a reader would think to look.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
PKG = ROOT / "homestead"

#: Modules the capabilities table deliberately does not name, because they
#: are Phase 0–2 foundations the older "What is enforced here today" table
#: already covers, not a build-out-wave capability with a release of its own.
#: Each reason is checked by nothing but a human reader — this tuple exists
#: so a module can leave this list only by being named in the README, never
#: by being quietly forgotten from both.
FOUNDATION: dict[str, str] = {
    "keep/__init__.py": "package marker, not a capability",
    "keep/paths.py": "Phase 0 — the one path resolver (I-19/I-20)",
    "keep/rungs.py": "Phase 0-2 — the gate itself (I-16), predates the build-out plan",
    "keep/record.py": "Phase 0 — the canonical store (I-36), predates the build-out plan",
    "keep/registry.py": "Phase 3 — the one matter enumeration (I-23), predates the build-out plan",
    "keep/surfaces.py": "Phase 2 — the S1-S4 surface table, predates the build-out plan",
    "keep/advise.py": "Phase 0 audit residual — the advisory content matcher (I-18/F-3)",
    "keep/patterns.py": "Phase 2 — the closed-reporter-set citation extractor (I-18)",
    "keep/egress.py": "pre-build-out — no egress without an explicit per-call act (I-17)",
    "keep/export.py": "pre-build-out — the first IntegrityLog/VisibleLog writer (I-15)",
    "keep/nestor_seam.py": "pre-build-out — the one Nestor seam (docs/seam-pattern-cross-reference.md)",
    "app/__init__.py": "package marker, not a capability",
    "app/__main__.py": "the `--smoke`/`--demo` entry point, not a capability itself",
    "app/advisories.py": "Phase 0 audit residual UI — draws keep/advise's output",
    "app/window.py": "Phase 2 — the S1 list/detail composition, predates the build-out plan",
    "app/view.py": "Phase 2 — the tkinter view, predates the build-out plan",
    "app/theme.py": "hoisted shared surface theme, not a capability",
    "app/demo.py": "the `--demo` headless pipeline printer, not a capability",
}

_CODE_SPAN_MODULE = re.compile(r"`((?:keep|app)/[A-Za-z_]+\.py)`")

#: The heading the capabilities table lives under. The scan is scoped to this
#: one section, and that scoping is the point: read over the whole README, a
#: module counted as "named in the capabilities table" merely by being
#: mentioned anywhere else in the file — which is how `keep/paths.py` was
#: simultaneously in `FOUNDATION` *and* satisfying the coverage check from
#: the I-19/I-20 row of a different table (X7-drift audit). The property this
#: file claims is "named in the capabilities table, or excluded with a
#: reason"; a scan that reads the whole file is not checking that claim.
_CAPABILITIES_HEADING = "## Engine capabilities, and what shipped them"


def _capabilities_section(readme_text: str) -> str:
    """The README text under `_CAPABILITIES_HEADING`, up to the next `##`
    heading — and a refusal, never an empty string, if the heading is gone.
    An empty section would make every module unaccounted-for and the failure
    would read as twenty-six missing rows rather than one renamed heading."""
    _, sep, rest = readme_text.partition(_CAPABILITIES_HEADING)
    assert sep, (
        f"README.md has no {_CAPABILITIES_HEADING!r} heading — this file "
        "checks a table that no longer exists under the name it was given"
    )
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _modules_named_in(text: str) -> set[str]:
    """Every `keep/x.py` or `app/x.py` backtick-quoted path in `text`."""
    return set(_CODE_SPAN_MODULE.findall(text))


def _real_engine_modules() -> set[str]:
    """Every module under `homestead/keep/` and `homestead/app/`, as
    `keep/x.py` / `app/x.py` — the same short form the README and
    `FOUNDATION` both use, so the three sets compare directly."""
    modules = set()
    for sub in ("keep", "app"):
        for path in sorted((PKG / sub).glob("*.py")):
            modules.add(f"{sub}/{path.name}")
    return modules


def _unaccounted_for(real_modules: set[str], readme_text: str) -> set[str]:
    """Modules that are neither named in `readme_text` nor in `FOUNDATION` —
    the check both the real test and its plant below share."""
    named = _modules_named_in(_capabilities_section(readme_text)) | set(FOUNDATION)
    return real_modules - named


def test_every_keep_and_app_module_is_named_or_excluded():
    unaccounted = _unaccounted_for(_real_engine_modules(), README.read_text("utf-8"))
    assert not unaccounted, (
        f"these modules are named in neither README.md's capabilities table "
        f"nor this file's FOUNDATION tuple: {sorted(unaccounted)}. Add a row "
        "naming the release that shipped it, or add it to FOUNDATION with a "
        "one-line reason it predates the build-out plan."
    )


def test_foundation_entries_are_real_modules_not_a_stale_list():
    """The other half of BUG-6's lesson: an entry in the exclusion tuple for
    a module that no longer exists is exactly as silent a drift as a module
    missing from it — `FOUNDATION` is checked against the tree, not assumed
    current."""
    real = _real_engine_modules()
    stale = set(FOUNDATION) - real
    assert not stale, f"FOUNDATION names modules that no longer exist: {sorted(stale)}"


def test_the_coverage_guard_fires_on_a_planted_unaccounted_module():
    """A scan that has never fired has not been shown to check anything. A
    fake module named in neither the README text nor `FOUNDATION` must be
    caught, and a real module (already covered, either way) must not be."""
    readme_text = README.read_text("utf-8")
    planted = _real_engine_modules() | {"keep/_planted_uncovered.py"}
    unaccounted = _unaccounted_for(planted, readme_text)
    assert unaccounted == {"keep/_planted_uncovered.py"}

    # the real tree, run through the same helper, must be clean — the plant
    # above is additive, not a relaxation of the real check.
    assert not _unaccounted_for(_real_engine_modules(), readme_text)


def test_the_foundation_exclusions_are_minimal():
    """An exclusion for a module the table names anyway is not an exclusion,
    it is a second, unsynchronised list of the same module — BUG-6's
    mechanism, which is what this whole file is here about. `keep/paths.py`
    sat in both for exactly as long as the coverage scan read the whole
    README instead of the capabilities section (X7-drift audit); with the
    scan scoped, the overlap is checkable, so it is checked."""
    in_table = _modules_named_in(_capabilities_section(README.read_text("utf-8")))
    both = sorted(set(FOUNDATION) & in_table)
    assert not both, (
        f"these modules are in FOUNDATION and in the capabilities table: "
        f"{both}. A module is a capability with a release, or a foundation "
        "with a reason — one list, not two."
    )


def test_the_capabilities_scan_reads_the_section_and_fires_on_a_planted_mention():
    """The plant the scoping needs, both ways round. A module named *only*
    outside the capabilities section must still count as unaccounted — the
    exact false pass the unscoped scan gave — and the same name inside the
    section must count as covered."""
    outside = (
        "# Engine\n\n## What is enforced here today\n\n"
        "`keep/_planted_elsewhere.py` is the only module that may do the thing.\n\n"
        f"{_CAPABILITIES_HEADING}\n\n| capability | shipped by | module(s) |\n"
        "|---|---|---|\n| Something | 0.9.0 | `keep/sync.py` |\n\n## Design\n"
    )
    planted = {"keep/_planted_elsewhere.py", "keep/sync.py"}
    assert _unaccounted_for(planted, outside) == {"keep/_planted_elsewhere.py"}

    inside = outside.replace(
        "| Something | 0.9.0 | `keep/sync.py` |",
        "| Something | 0.9.0 | `keep/sync.py`, `keep/_planted_elsewhere.py` |",
    )
    assert _unaccounted_for(planted, inside) == set()


def test_a_missing_capabilities_heading_refuses_rather_than_reading_empty():
    """Fail closed (I-11): a renamed or deleted heading is a refusal that
    names the heading, not a silent empty section that would report every
    module in the package as missing a row."""
    with pytest.raises(AssertionError, match="Engine capabilities"):
        _capabilities_section("# Engine\n\n## Design\n\nnothing here\n")
