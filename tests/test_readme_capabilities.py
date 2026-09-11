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
    named = _modules_named_in(readme_text) | set(FOUNDATION)
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
