"""I-31 — the resting state reveals nothing (`homestead.app.cover`).

Promoted from `test_invariants_pending.py` when the cover's counts were built as
the Phase-4 re-identification check. The pinned test moved here unmarked — the
fourth occasion of this promotion (dates, surfaces, record, then this) —
`test_pending_liveness` failed the moment `homestead.app.cover` existed and would
not go green again until it was moved and `"homestead.app.cover"` struck from
`UNBUILT`.

`cover_counts(matters, **counts)` returns only the per-category counts that
survive the `L2` re-identification check: a count survives when it clears both
anonymity gates (`K = 2` matters *and* `K = 2` in the count itself), and is
otherwise absent. See `homestead/app/cover.py` and
`docs/DECISION-cover-re-identification.md`.

The one test the pending file pinned is `test_i31_the_cover_survives_re_identification`.
Everything else here is a hard case the pin does not reach — the two gates fired
independently, absence-not-zero, and the survivor rendered as its real number.

**E4-cover-distribution** (bottom of the file) adds `by_matter`, an optional
per-matter distribution. `homestead_law`'s L2c audit found `queue.cover()`
handing this gate the *registered matter types* — identical on every install —
so the matters gate was satisfied by the software's shape rather than the
household's; law now passes the matters that actually hold a deadline, but a
roster of two truthfully open matters still admits a `(2, 0)` distribution
where both counts belong to one of them, and the aggregate-only gate cannot see
that. With `by_matter`, Gate 2 tightens per category to "at least `K` distinct
matters each contribute >= 1" — `(2, 0)` is dropped, `(1, 1)` still survives.
`by_matter=None` (the default) is unchanged behaviour for every prior call.
"""
from __future__ import annotations

import pytest

from homestead.app.cover import K, cover_counts


# ── promoted from test_invariants_pending.py ─────────────────────────────────

def test_i31_the_cover_survives_re_identification():
    """'1 overdue' over a household where one matter has deadlines identifies
    that matter. The L2 check is not theoretical at three matters."""
    counts = cover_counts(matters=["custody"], overdue=1)
    assert "overdue" not in counts


# ── the count gate · k ≥ 2 on the count itself ───────────────────────────────

def test_a_count_of_one_is_dropped_even_across_many_matters():
    """The worked example's own point: 'not about matter-count'. A count of one
    is one item, one item is one matter, and three or ten matters do not launder
    it — the number still resolves to the single matter that holds the item."""
    counts = cover_counts(
        matters=["custody", "workers_comp", "estate", "tenancy"], overdue=1
    )
    assert "overdue" not in counts


def test_a_count_of_two_or_more_survives_when_matters_survive():
    """The other side of the count gate: with ≥2 matters, a count of ≥2 does not
    resolve to a single matter — (2,0), (1,1) and higher spreads are all
    consistent with it — so it crosses, rendered as its real number."""
    counts = cover_counts(matters=["custody", "estate"], overdue=2)
    assert counts == {"overdue": 2}


# ── the matters gate · k ≥ 2 on the matters ──────────────────────────────────

def test_a_single_matter_drops_every_count_however_large():
    """The matters gate, fired alone: a count of 5 clears the count gate, but a
    household of one matter *is* that matter — every count is a fact asserted
    about it, because a number cannot spread across matters that do not exist."""
    counts = cover_counts(matters=["custody"], overdue=5, due_soon=9)
    assert counts == {}


def test_no_matters_shows_nothing():
    """Absence at the root: no open matters, nothing to count, nothing shown —
    the cover rests on 'Nothing is open'."""
    assert cover_counts(matters=[]) == {}
    assert cover_counts(matters=[], overdue=3) == {}


# ── absence, not zero ────────────────────────────────────────────────────────

def test_a_zero_count_is_absent_never_rendered():
    """'0 overdue' over one matter tells the reader that matter has none — a fact
    about the matter. A dropped count leaves no key; it is never a 0 in its
    place. (0 < K, so it fails the count gate regardless.)"""
    counts = cover_counts(matters=["custody", "estate"], overdue=0, due_soon=3)
    assert "overdue" not in counts
    assert counts == {"due_soon": 3}


def test_an_unpassed_category_is_simply_absent():
    """An absent key means 'not shown', never 'shown as none'. A category the
    caller did not pass does not appear as a zero."""
    counts = cover_counts(matters=["custody", "estate"], due_soon=4)
    assert set(counts) == {"due_soon"}
    assert "overdue" not in counts


# ── the survivor is the real number, and several may survive ──────────────────

def test_survivors_render_as_their_real_counts():
    """The check is about *whether* a number may cross, not about blurring one
    that may. A survivor is rendered as itself — the operator's own count, not a
    band or a placeholder."""
    counts = cover_counts(
        matters=["custody", "estate", "tenancy"],
        due_soon=4,
        overdue=1,
        drafts_unsent=2,
    )
    # due_soon (4) and drafts_unsent (2) clear both gates; overdue (1) is one
    # item in one matter and is dropped.
    assert counts == {"due_soon": 4, "drafts_unsent": 2}


def test_both_gates_are_needed_at_the_pinned_case():
    """The pinned case (one matter, count of one) trips *both* gates at once —
    which is why the suite exercises each alone above. Neither gate is redundant:
    drop the matters gate and a single-matter count of 5 leaks; drop the count
    gate and 'overdue=1' over three matters leaks."""
    assert cover_counts(matters=["custody"], overdue=1) == {}
    assert cover_counts(matters=["custody"], overdue=5) == {}          # matters gate
    assert cover_counts(matters=["a", "b", "c"], overdue=1) == {}      # count gate


# ── fail closed on a stranger ────────────────────────────────────────────────

def test_a_non_integer_count_fails_closed():
    """The surface renders a survivor; it does not repair a stranger. A count
    that is not a positive integer at or above K is dropped rather than coerced —
    including a bool, which is an int subclass and has no business being a count."""
    assert cover_counts(matters=["a", "b"], overdue="2") == {}
    assert cover_counts(matters=["a", "b"], overdue=None) == {}
    assert cover_counts(matters=["a", "b"], overdue=True) == {}   # True == 1 anyway
    assert cover_counts(matters=["a", "b"], overdue=3.0) == {}    # not an int


def test_the_anonymity_floor_is_two():
    """K is the smallest set in which 'which one?' has no answer. Pinned so the
    two gates cannot be loosened to 1 without a test saying so."""
    assert K == 2


# ── I-31 + E4-cover-distribution: `by_matter` tightens Gate 2 ────────────────
#
# `homestead_law`'s L2c audit found `queue.cover()` handing this gate the
# *registered matter types* — identical on every install — so Gate 2 was
# satisfied by the software's shape rather than the household's. Law fixed its
# caller to pass the matters that actually hold a deadline, but a roster of two
# truthful matters still admits a (2, 0) distribution where both counts belong
# to one matter, because this file was never handed the distribution to check.
# `by_matter` closes that: when given, a category survives only when at least
# `K` distinct matters in the distribution each contribute >= 1 to it.


def test_by_matter_omitted_is_unchanged_for_every_existing_call():
    """`by_matter=None` (the default) must be indistinguishable from every call
    this function answered before the parameter existed — every test above
    calls it with no `by_matter` at all, and this pins the explicit form too."""
    assert cover_counts(matters=["custody"], overdue=1) == cover_counts(
        matters=["custody"], by_matter=None, overdue=1
    )
    assert cover_counts(
        matters=["custody", "estate", "tenancy"],
        due_soon=4,
        overdue=1,
        drafts_unsent=2,
    ) == cover_counts(
        matters=["custody", "estate", "tenancy"],
        by_matter=None,
        due_soon=4,
        overdue=1,
        drafts_unsent=2,
    )


def test_two_zero_across_two_matters_is_absent():
    """The case the old gate could not see: (2, 0) clears both old gates (count
    >= K, matters >= K) but every item sits in one matter — only one matter
    contributes at all, so it is absent under the distribution check."""
    counts = cover_counts(
        matters=["custody", "estate"],
        by_matter={"custody": {"overdue": 2}, "estate": {"overdue": 0}},
        overdue=2,
    )
    assert "overdue" not in counts


def test_one_one_across_two_matters_survives_with_the_real_total():
    """The other side: (1, 1) has >= K matters each contributing >= 1, so it
    survives and renders as the real total, 2 — not either matter's share."""
    counts = cover_counts(
        matters=["custody", "estate"],
        by_matter={"custody": {"overdue": 1}, "estate": {"overdue": 1}},
        overdue=2,
    )
    assert counts == {"overdue": 2}


def test_two_zero_zero_across_three_matters_is_absent():
    """A third matter does not launder it: (2, 0, 0) still has only one matter
    contributing, so a roster of three does not rescue it either."""
    counts = cover_counts(
        matters=["custody", "estate", "tenancy"],
        by_matter={
            "custody": {"overdue": 2},
            "estate": {"overdue": 0},
            "tenancy": {"overdue": 0},
        },
        overdue=2,
    )
    assert "overdue" not in counts


def test_inconsistent_distribution_totals_are_refused():
    """A `by_matter` whose per-category totals disagree with the `**counts`
    aggregate is a caller lying to the gate (I-11) — refused, not reconciled or
    silently trusted on one side."""
    with pytest.raises(ValueError):
        cover_counts(
            matters=["custody", "estate"],
            by_matter={"custody": {"overdue": 1}, "estate": {"overdue": 1}},
            overdue=3,  # distributed total is 2, not 3
        )


def test_by_matter_naming_an_unknown_matter_is_refused():
    """`by_matter`'s matters must be a subset of `matters` — a distribution over
    a matter the roster does not contain is refused, not silently accepted."""
    with pytest.raises(ValueError):
        cover_counts(
            matters=["custody", "estate"],
            by_matter={"custody": {"overdue": 1}, "not-on-the-roster": {"overdue": 1}},
            overdue=2,
        )


def test_a_planted_matter_name_never_appears_in_result_or_error_text():
    """I-15: this surface never emits a matter name or a per-matter count, in
    the result or in any error text it raises. Plant a distinctive matter name
    in both the success path and each refusal path and grep for it."""
    planted = "zzz-planted-matter-name-zzz"

    counts = cover_counts(
        matters=["custody", planted],
        by_matter={"custody": {"overdue": 1}, planted: {"overdue": 1}},
        overdue=2,
    )
    assert planted not in counts
    assert planted not in str(counts)

    with pytest.raises(ValueError) as bad_total:
        cover_counts(
            matters=["custody", planted],
            by_matter={"custody": {"overdue": 5}, planted: {"overdue": 5}},
            overdue=1,
        )
    assert planted not in str(bad_total.value)

    with pytest.raises(ValueError) as unknown_matter:
        cover_counts(
            matters=["custody"],
            by_matter={"custody": {"overdue": 1}, planted: {"overdue": 1}},
            overdue=2,
        )
    assert planted not in str(unknown_matter.value)


# ── audit E4: the distribution is checked before it is read ──────────────────
#
# `by_matter` is the gate's *evidence*. Evidence that cannot be reasoned about
# is refused, never partially believed (I-11) — and every refusal names only the
# category, which is a key, never a matter or a share (I-15).


def test_a_negative_share_is_refused_by_category_name():
    """A count is a count of things; below zero there is nothing to count. A
    negative share is refused rather than summed, and the refusal names only the
    category."""
    with pytest.raises(ValueError) as refusal:
        cover_counts(
            matters=["custody", "estate"],
            by_matter={"custody": {"overdue": -1}, "estate": {"overdue": 3}},
            overdue=2,
        )
    assert "overdue" in str(refusal.value)
    assert "custody" not in str(refusal.value)


def test_a_negative_share_cannot_launder_a_single_matter_spread():
    """The reason the sign matters, and not merely the type. `{3, 1, -2}` totals
    2, clears the totals check, and presents *two* contributors — so the old
    code showed `overdue=2` for a spread no household has. Refused now: a term
    that subtracts makes the sum stop being a count."""
    with pytest.raises(ValueError):
        cover_counts(
            matters=["custody", "estate", "tenancy"],
            by_matter={
                "custody": {"overdue": 3},
                "estate": {"overdue": 1},
                "tenancy": {"overdue": -2},
            },
            overdue=2,
        )


def test_a_stranger_share_is_refused_under_every_category():
    """Bools, floats, strings and `None` are all refused by name — including
    under a category whose *aggregate* is itself a stranger and would be dropped
    anyway. The shares are checked before any of them is summed, so a bad
    distribution is never silently skipped on the way to a dropped count."""
    for share in (True, 1.0, "1", None):
        with pytest.raises(ValueError):
            cover_counts(
                matters=["custody", "estate"],
                by_matter={"custody": {"overdue": share}, "estate": {"overdue": 1}},
                overdue=2,
            )
    with pytest.raises(ValueError):
        cover_counts(
            matters=["custody", "estate"],
            by_matter={"custody": {"overdue": 1.5}, "estate": {"overdue": 1}},
            overdue="2",  # a stranger aggregate does not excuse a stranger share
        )


def test_a_malformed_by_matter_is_refused_not_crashed():
    """A `by_matter` that is not a mapping of matter to share table is refused by
    name (I-11), not left to raise whatever `TypeError` the arithmetic happens to
    hit — a refusal is a decision, an `AttributeError` is an accident."""
    with pytest.raises(ValueError):
        cover_counts(matters=["custody", "estate"], by_matter=["custody"], overdue=2)
    with pytest.raises(ValueError):
        cover_counts(matters=["custody"], by_matter={"custody": 2}, overdue=2)
    with pytest.raises(ValueError):
        cover_counts(matters=["custody"], by_matter={"custody": "two"}, overdue=2)


def test_a_category_distributed_but_never_counted_is_refused():
    """The totals check runs over the *union* of the two sides. A category the
    distribution knows and the aggregate does not is an inconsistency in itself —
    including when its shares are all zero, where arithmetic alone (0 == 0) would
    have waved it through."""
    with pytest.raises(ValueError) as nonzero:
        cover_counts(
            matters=["custody", "estate"],
            by_matter={"custody": {"due_soon": 1}, "estate": {"due_soon": 1}},
            overdue=2,
        )
    assert "due_soon" in str(nonzero.value)

    with pytest.raises(ValueError):
        cover_counts(
            matters=["custody", "estate"],
            by_matter={"custody": {"due_soon": 0}, "estate": {"due_soon": 0}},
            overdue=0,
        )


def test_a_counted_category_the_distribution_omits_is_refused():
    """The other side of the union: an aggregate with no shares behind it is a
    distribution that does not cover its own count."""
    with pytest.raises(ValueError) as refusal:
        cover_counts(
            matters=["custody", "estate"],
            by_matter={"custody": {"overdue": 1}, "estate": {"overdue": 1}},
            overdue=2,
            due_soon=5,
        )
    assert "due_soon" in str(refusal.value)


# ── the roster is a set of matters, not a list of spellings ──────────────────


def test_one_matter_named_twice_is_still_one_matter():
    """The matters gate counts *distinct* matters. A roster that repeats a name
    is one matter wearing two spellings, and the household is still that matter —
    counting the list would show '5 overdue' about the only matter there is."""
    assert cover_counts(matters=["custody", "custody"], overdue=5) == {}
    assert cover_counts(matters=["custody", "custody", "custody"], overdue=9) == {}
    # and the same roster with a genuine second matter still passes
    assert cover_counts(matters=["custody", "custody", "estate"], overdue=5) == {
        "overdue": 5
    }


# ── I-15, again, over every path a matter name can reach ─────────────────────


def test_no_matter_name_or_share_reaches_any_exception_surface():
    """A planted matter name and a planted share (7919 — findable, and no
    count this suite otherwise uses) must appear in neither `str`, `args` nor
    `__notes__` of any refusal, on every refusal path there is. An exception
    built from a dict `repr` would fail this."""
    planted = "zzz-planted-matter-name-zzz"
    share = 7919

    def caught(**kwargs):
        with pytest.raises(Exception) as raised:
            cover_counts(**kwargs)
        error = raised.value
        surface = " ".join(
            [str(error), repr(error.args), repr(getattr(error, "__notes__", None))]
        )
        assert planted not in surface, surface
        assert str(share) not in surface, surface
        return error

    caught(  # outside the roster
        matters=["custody"],
        by_matter={planted: {"overdue": share}},
        overdue=share,
    )
    caught(  # totals disagree
        matters=["custody", planted],
        by_matter={"custody": {"overdue": share}, planted: {"overdue": 1}},
        overdue=3,
    )
    caught(  # a stranger share
        matters=["custody", planted],
        by_matter={"custody": {"overdue": float(share)}, planted: {"overdue": 1}},
        overdue=3,
    )
    caught(  # a negative share
        matters=["custody", planted],
        by_matter={"custody": {"overdue": -share}, planted: {"overdue": 1}},
        overdue=1,
    )
    caught(  # a share table that is not a mapping
        matters=["custody", planted],
        by_matter={"custody": {"overdue": 1}, planted: planted},
        overdue=1,
    )
    caught(  # a category the aggregate never counted
        matters=["custody", planted],
        by_matter={"custody": {"drafts_unsent": 1}, planted: {"drafts_unsent": share}},
        overdue=2,
    )


def test_the_result_carries_counts_and_never_a_matter():
    """The survivor path: the returned mapping is category → int. No matter name
    reaches its keys, and its values are the aggregate — never a share."""
    planted = "zzz-planted-matter-name-zzz"
    counts = cover_counts(
        matters=["custody", planted],
        by_matter={"custody": {"overdue": 4}, planted: {"overdue": 3}},
        overdue=7,
    )
    assert counts == {"overdue": 7}
    assert all(isinstance(value, int) for value in counts.values())
    assert planted not in repr(counts)
