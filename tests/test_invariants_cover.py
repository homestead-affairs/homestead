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
"""
from __future__ import annotations

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
