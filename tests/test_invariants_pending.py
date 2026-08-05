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
    "homestead.keep.dates": "Phase 1",
    "homestead.keep.surfaces": "Phase 2",
    "homestead.keep.registry": "Phase 3",
    "homestead.keep.record": "Phase 3",
    "homestead.keep.egress": "Phase 4",
    "homestead.keep.patterns": "Phase 4",
    "homestead.app.window": "Phase 4",
    "homestead.app.cover": "Phase 4",
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


# ── Phase 1 · dates ──────────────────────────────────────────────────────────

@pending("homestead.keep.dates", "i1 i2 strict parse or refuse")
def test_i1_i2_strict_parse_or_refuse():
    """BUG-1: `_days_until` sliced to 10 chars before trying the long-form
    formats it declared, so every `"July 1, 2026"` returned None — and the
    failure was data-dependent, because `"May 5 2026"` is exactly 10."""
    from homestead.keep.dates import parse_deadline

    assert parse_deadline("2026-08-10").iso == "2026-08-10"
    assert parse_deadline("July 1, 2026").iso == "2026-07-01"
    assert parse_deadline("May 5, 2026").iso == "2026-05-05"
    for junk in ("2026", "June", "30", "next week", "", "not a date"):
        with pytest.raises(ValueError):
            parse_deadline(junk)


@pending("homestead.keep.dates", "i3 overdue never disagrees with days until")
def test_i3_overdue_never_disagrees_with_days_until():
    """BUG-3: `overdue` string-compared the raw value while `days_until`
    parsed it, so one item carried days_until=-91 and overdue=False at once."""
    from homestead.keep.dates import Deadline

    d = Deadline.from_text("May 5, 2026", today="2026-08-04")
    assert d.days_until == -91
    assert d.overdue is True


@pending("homestead.keep.dates", "i5 no free text dates reach storage")
def test_i5_no_free_text_dates_reach_storage():
    """BUG-4: snooze took free text and `is_snoozed` compared it to today as a
    string, so `"next week"` hid an item until 2099 and `"08/11/2026"` did
    nothing at all — and there was no un-snooze anywhere in the codebase."""
    from homestead.keep.dates import parse_deadline

    with pytest.raises(ValueError):
        parse_deadline("next week")


# ── Phase 2 · rungs ──────────────────────────────────────────────────────────

@pending("homestead.keep.registry", "classify_schema is Phase 2")
def test_i11_unclassified_field_is_a_build_failure():
    from homestead.keep.rungs import classify_schema

    with pytest.raises(Exception):
        classify_schema({"body": None})  # no rung declared


@pending("homestead.keep.surfaces", "i13 l5 has no override on any surface")
def test_i13_l5_has_no_override_on_any_surface():
    """BUG-5: `_fact_blocked` tested only `needs_source`, so `do_not_use` —
    the *stronger* rejection — still flowed into the drafting packet and the
    model prompt, while the screen said 'Excluded from drafting'."""
    from homestead.keep.rungs import Rung, may_render
    from homestead.keep.surfaces import Surface

    for surface in Surface:
        assert may_render(Rung.L5, surface, purpose="anything") is False


@pending("homestead.keep.surfaces", "i35 the list pane cannot render an l4 payload")
def test_i35_the_list_pane_cannot_render_an_l4_payload():
    from homestead.keep.rungs import Rung, may_render
    from homestead.keep.surfaces import Surface

    assert may_render(Rung.L4, Surface.S1_LIST, purpose=None) is False
    assert may_render(Rung.L4, Surface.S1_LIST, purpose="medical") is False
    assert may_render(Rung.L4, Surface.S1_DETAIL, purpose=None) is True


@pending("homestead.keep.surfaces", "i13 l4 never reaches a model prompt")
def test_i13_l4_never_reaches_a_model_prompt():
    from homestead.keep.rungs import Rung, may_render
    from homestead.keep.surfaces import Surface

    assert may_render(Rung.L4, Surface.S2_PROMPT, purpose="medical") is False


# ── Phase 3 · the registry ───────────────────────────────────────────────────

@pending("homestead.keep.registry", "i23 the registry is the only enumeration")
def test_i23_the_registry_is_the_only_enumeration():
    """BUG-6: workers' comp — one of three advertised matter types — was
    structurally absent from the urgent queue, because three types were
    enumerated by hand in three places."""
    from homestead.keep.registry import REGISTRY, all_matters

    assert set(all_matters()) == set(REGISTRY)


@pending("homestead.keep.record", "i36 nothing deletes canonical data")
def test_i36_nothing_deletes_canonical_data():
    from homestead.keep.record import Canonical

    for forbidden in ("delete", "purge", "remove", "drop", "write", "update"):
        assert not hasattr(Canonical, forbidden)


# ── Phase 4 · surfaces ───────────────────────────────────────────────────────

@pending("homestead.app.window", "i21 the app does not render on start")
def test_i21_the_app_does_not_render_on_start():
    from homestead.app.window import Window

    assert Window().state == "cover"


@pending("homestead.app.cover", "i31 the cover survives re identification")
def test_i31_the_cover_survives_re_identification():
    """'1 overdue' over a household where one matter has deadlines identifies
    that matter. The L2 check is not theoretical at three matters."""
    from homestead.app.cover import cover_counts

    counts = cover_counts(matters=["custody"], overdue=1)
    assert "overdue" not in counts


@pending("homestead.keep.egress", "i17 no egress without an explicit per call act")
def test_i17_no_egress_without_an_explicit_per_call_act():
    from homestead.keep.egress import send

    with pytest.raises(PermissionError):
        send("https://example.invalid/", payload={"x": 1})


@pending("homestead.keep.patterns", "i18 extraction patterns reject pii")
def test_i18_extraction_patterns_reject_pii():
    """F-3: the citation regex matched `1420 Maple 87501` and missed
    `347 F.3d 1120`, and the path POSTed what it matched."""
    from homestead.keep.patterns import CITATION

    assert CITATION.findall("347 F.3d 1120")
    assert not CITATION.findall("1420 Maple 87501")
    assert not CITATION.findall("88 Ridgeline 90210")
