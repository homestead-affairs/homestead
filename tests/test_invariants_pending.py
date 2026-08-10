"""The invariants later phases must satisfy — written now, failing on purpose.

Every one is `xfail(strict=True)`, which means two things at once:

  * the suite stays green while the phase is unbuilt, so CI is honest; and
  * the moment an implementation makes one of these pass, **the suite fails**
    and forces the test to be promoted out of this file.

So this is not a wish list. It is a set of claims that cannot be quietly
satisfied and cannot be quietly forgotten. Each one names the failure it exists
to prevent, in an app that has already produced that failure once.
"""
from __future__ import annotations

import importlib.util

import pytest

# Every module a pending test reaches for, and the phase that builds it.
UNBUILT = {
    # homestead.keep.dates was Phase 1 and is built. Its three tests moved to
    # tests/test_invariants_dates.py, unmarked — which is what this file is
    # for: test_pending_liveness failed the moment the module existed and would
    # not go green again until they were promoted out.
    #
    # homestead.keep.surfaces was Phase 2 and is built. Its three tests, plus
    # the I-11 test that was mis-attributed to `registry`, moved to
    # tests/test_invariants_surfaces.py, unmarked. Same mechanism, second
    # occasion.
    #
    # **The mis-attribution was not a typo and is worth leaving written down.**
    # `test_i11_unclassified_field_is_a_build_failure` imported
    # `classify_schema` from `homestead.keep.rungs`, which has existed since
    # Phase 0, and was marked `@pending("homestead.keep.registry", ...)`
    # because `rungs` could not be named here: a module in this dict is
    # asserted *not to exist*, and `rungs` did. So a Phase 2 addition to an
    # already-built module had no honest home, and it borrowed a Phase 3 one.
    #
    # That is a real limit of R-6 rather than a slip. This guard is
    # **module-granular** — `importlib.util.find_spec` answers for a module, not
    # for a symbol inside it — so a pending test whose real dependency is a
    # *function* that does not exist yet cannot be tracked by it at all. Two
    # consequences, both live: the reason string can be wrong in a way nothing
    # detects, and such a test goes XPASS-strict when its symbol lands, which is
    # a failure but not one that names the module. Phase 3 adds `registry`
    # and functions to modules that already exist; if it needs symbol-granular
    # pending marks, this dict is the thing to widen.
    #
    # homestead.keep.record was Phase 3 here and is built early, as bite 1 of
    # docs/PLAN-first-runnable.md ("the store — records survive a restart"). The
    # plan re-scoped the record layer forward: it is the seam everything else
    # renders over, so it comes before the registry rather than beside it. Its
    # I-36 test — the canonical handle has no write method — moved to
    # tests/test_invariants_record.py, unmarked, the third occasion of this same
    # promotion (dates, surfaces, then record). test_pending_liveness failed the
    # moment the module existed and would not go green again until it was moved.
    "homestead.keep.registry": "Phase 3",
    # homestead.keep.egress was built after the runnable-path batch: I-17, no
    # network egress by default, refused unless a per-call act is shown exactly
    # what will be sent. Its test moved to tests/test_invariants_egress.py,
    # unmarked.
    "homestead.keep.patterns": "Phase 4",
    # homestead.app.window was built as bite 4 of docs/PLAN-first-runnable.md
    # (the two S1 surfaces). Its I-21 test — a fresh window rests on the cover —
    # moved to tests/test_invariants_window.py, unmarked.
    #
    # homestead.app.cover (the I-31 re-identification counts) was then built:
    # the cover may show a count only where the number reveals nothing about
    # which matter it came from. Its I-31 test moved to
    # tests/test_invariants_cover.py, unmarked — the fourth occasion of this
    # promotion (dates, surfaces, record, then cover). test_pending_liveness
    # failed the moment the module existed and would not go green again until it
    # was moved and struck from this dict.
}


def pending(module: str, why: str):
    """xfail with a reason naming *this* test's module and phase.

    A shared reason string made four different states indistinguishable —
    unbuilt phase, uninstalled package, partial implementation, and a **typo in
    an imported symbol**. The audit demonstrated the last one: a registry
    satisfying I-23 exactly, with the pending test importing `all_matter_types`
    instead of `all_matters`, left the suite green at 13 xfailed. Naming the
    module per test, plus `test_pending_liveness` below, closes that.
    """
    phase = UNBUILT.get(module, "unknown phase")
    return pytest.mark.xfail(strict=True, reason=f"{module} unbuilt ({phase}) — {why}")


def test_pending_liveness():
    """The guard the shared reason string could not provide.

    Asserts exactly which modules are still unbuilt. When a phase lands, this
    fails *first* and by name — so a pending test cannot keep xfailing for a
    reason nobody checked, and cannot be silently dropped because someone
    mistyped a symbol.
    """
    built = sorted(m for m in UNBUILT if importlib.util.find_spec(m) is not None)
    assert not built, (
        f"these modules now exist: {built}. Their pending tests must be "
        "promoted out of this file, and this list updated — do not leave them "
        "xfailing."
    )


# ── Phase 3 · the registry ───────────────────────────────────────────────────

@pending("homestead.keep.registry", "i23 the registry is the only enumeration")
def test_i23_the_registry_is_the_only_enumeration():
    """BUG-6: workers' comp — one of three advertised matter types — was
    structurally absent from the urgent queue, because three types were
    enumerated by hand in three places."""
    from homestead.keep.registry import REGISTRY, all_matters

    assert set(all_matters()) == set(REGISTRY)


# I-36 (`homestead.keep.record`) was promoted to tests/test_invariants_record.py
# when the store was built as bite 1 of docs/PLAN-first-runnable.md.


# ── Phase 4 · surfaces ───────────────────────────────────────────────────────

# I-21 (`homestead.app.window`) was promoted to tests/test_invariants_window.py
# when the two S1 surfaces were built as bite 4 of docs/PLAN-first-runnable.md.


# I-31 (`homestead.app.cover`) was promoted to tests/test_invariants_cover.py
# when the cover's re-identification counts were built.


# I-17 (`homestead.keep.egress`) was promoted to tests/test_invariants_egress.py
# when network egress was built after the runnable-path batch.


@pending("homestead.keep.patterns", "i18 extraction patterns reject pii")
def test_i18_extraction_patterns_reject_pii():
    """F-3: the citation regex matched `1420 Maple 87501` and missed
    `347 F.3d 1120`, and the path POSTed what it matched."""
    from homestead.keep.patterns import CITATION

    assert CITATION.findall("347 F.3d 1120")
    assert not CITATION.findall("1420 Maple 87501")
    assert not CITATION.findall("88 Ridgeline 90210")
