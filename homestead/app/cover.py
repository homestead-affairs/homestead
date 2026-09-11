"""S1 — the cover's counts, and the re-identification check they survive (I-31).

The cover is the resting state of the S1 window (I-21): what the machine shows
with nobody's hand on it, in a room a second person can walk into (F-1). Phase 0
had it right by showing *nothing* — "Nothing is open" — and nothing is still the
answer whenever the check below has no survivor. This file is the narrow thing
Phase 4 adds: it lets the cover show a **count** in exactly the cases where the
number reveals nothing about *which matter* it came from, and drops every count
where it does.

**I-31 — the resting state reveals nothing.** The cover shows counts that survive
the `L2` re-identification check and no more. `L2` is not a property a count is
born with: an aggregate inherits the `max` of its inputs and *becomes* `L2` only
after a check that it cannot be resolved to a person or a single matter (the rung
model, `L2`, and step 2a of the classification procedure). Until it passes, "1
overdue" over a household is not household news — it is *that one matter's* news
wearing a number, and F-5's reader behind the chair reads it as such.

## The rule, and why it is these two gates

A per-category count (`overdue=…`, `due_soon=…`, `drafts_unsent=…`) is shown only
when it survives **both** of these, and is otherwise absent:

* **k ≥ 2 on the count itself.** A count of `1` is one item, and one item lives in
  exactly one matter — so `overdue=1` *resolves to* that matter the instant it is
  read, no matter how many matters the household holds. This is the gate the
  pinned test names, and its worked example is explicit that it "is not about
  matter-count": three matters do not launder a count of one. k-anonymity with
  k = the count; k=1 is re-identifying by arithmetic.

* **k ≥ 2 on the matters.** With a single open matter, the household *is* that
  matter, and every count — `1`, `5`, `50` — is a fact asserted about it. A number
  cannot be spread across matters that do not exist, so a lone matter fails the
  check for the same reason a count of one does: the mapping to a matter is forced.

Both gates are independent and both are live. The pinned case
(`matters=["custody"], overdue=1`) trips both at once; the tests exercise each
alone, because a rule that only ever fires when both conditions hold has not been
shown to need two.

**Absence, not zero.** A dropped count leaves *no key* — never a `0` in its place.
"0 overdue" over one matter still tells the reader that matter has none, which is
a fact about the matter; and a zero is `count < 2`, so it never survives the first
gate anyway. The window drops what it denies without a trace (product decision 2);
the cover keeps that discipline. An absent key means "not shown"; it never means
"shown as none".

## What the number is allowed to be, once it is shown

The real count. A survivor is rendered as itself — `due_soon=4` shows `4` — because
the check is about *whether* a number may cross, not about blurring one that may.
A count that passes both gates does not, on its face, resolve to a single matter:
`overdue=3` over three matters is consistent with (3,0,0), (2,1,0) and (1,1,1), so
the number alone pins no matter. That is the whole content of "survives the check".

## The honest limit — what this file does *not* see

It is handed the aggregate and the roster of matters, and — since I-31 (E4,
`by_matter`) — optionally the per-matter distribution behind that aggregate.
Without a distribution it still cannot certify that a survivor is *actually*
spread across ≥2 matters — only that the number does not *force* a single matter.
`overdue=2` over two matters passes here even if both items are in one matter,
because the cover cannot tell (2,0) from (1,1) and the reader cannot either. That
was a known, deliberate boundary, recorded in
`docs/DECISION-cover-re-identification.md`.

**Closing that gap.** `homestead_law`'s own L2c audit (queue readiness for a
second matter type) found the shape of the gap made concrete: `queue.cover()`
used to hand this gate the *registered matter types* rather than the matters
that actually hold a deadline, so a second pack landing was enough on its own to
satisfy Gate 2 — nothing broke, a number simply started appearing. Law fixed its
caller to pass the matters that actually hold a deadline, but that still leaves
this file blind to *how* an aggregate is spread: a roster of two truthfully open
matters still admits a `(2, 0)` distribution where both items sit in one of
them, and Gate 2 as written cannot see that. When a caller *can* state the
distribution, Gate 2 tightens to read it instead of trusting the roster: a
category survives only when at least `K` distinct matters each contribute at
least one to it. `(2, 0)` fails that even though the raw count and the matter
roster both clear the old gates; `(1, 1)` passes. See `by_matter` below.

## I-29 — the surface calculates nothing beyond this arithmetic

`cover_counts` compares integers and copies matter names. It computes no deadline
(that is `keep/dates`), reads no rung, reaches no `.payload`, and reflects over
nothing — it deals only in matter names and integer counts a caller already
composed. The one thing it *does* is the re-identification arithmetic, which is
the surface's own and lives nowhere else. `test_invariants_chokepoint.py` scans
this file with the rest of `homestead/app/`.
"""
from __future__ import annotations

__all__ = ["cover_counts", "K"]

#: The anonymity floor. A count survives only when at least `K` items *and* at
#: least `K` matters stand behind it — below either, the number resolves to one
#: matter. Two is the smallest set in which "which one?" has no answer.
K = 2


def _contribution(per_matter: dict[str, int], category: str) -> int:
    """One matter's share of `category`, or `0` if it contributes nothing there.

    A share that is not a plain non-bool int cannot be reasoned about at all —
    not "zero", not "ignored" — so it refuses rather than let a stranger value
    flow into a sum (I-11: an unverified distribution is refused, never guessed)."""
    value = per_matter.get(category, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"by_matter holds a non-integer share for {category!r}")
    return value


def cover_counts(
    matters: list[str],
    *,
    by_matter: dict[str, dict[str, int]] | None = None,
    **counts: int,
) -> dict[str, int]:
    """The counts the resting cover may show, and no more (I-31).

    `matters` is the roster of open matters — context for the check, never itself
    emitted. Each keyword is a per-category aggregate (`overdue=1`,
    `due_soon=4`, …). Returns a dict of only the categories that survive the
    re-identification check, each mapped to its real count. A category that does
    not survive is **absent** from the result — there is no zero standing in for
    a dropped count.

    A count survives when it clears both anonymity gates: at least `K` matters
    exist (else the household is one matter and every count is that matter's), and
    the count is itself at least `K` (else it is one item in one matter). Anything
    that is not a positive integer at or above `K` fails closed and is dropped —
    the surface renders a survivor, it does not repair a stranger.

    `by_matter` (matter → category → count) is the distribution behind an
    aggregate, when a caller has one. Passing it does not change any category
    the caller omits, and passing `None` (the default) is byte-identical to
    every call this function answered before it existed — this parameter
    exists because `homestead_law`'s L2c audit found the second gate could be
    satisfied by the roster's *shape* (a second registered matter type) rather
    than by the household's actual spread, so a roster of two truthfully open
    matters still let `(2, 0)` through Gate 2. With `by_matter` supplied, Gate 2
    tightens: a category survives only when at least `K` *distinct matters in
    the distribution* each contribute at least one to it — `(2, 0)` across two
    matters is now dropped, `(1, 1)` still passes. `by_matter`'s matters must be
    a subset of `matters`, and each category's distributed total must equal the
    `**counts` value passed for it — a caller whose distribution disagrees with
    its own aggregate is refused (I-11), never trusted. As everywhere on this
    surface (I-15), no matter name and no per-matter count is ever emitted, in
    the result or in any exception this function raises — only category names,
    which are not identities.
    """
    if by_matter is not None:
        if not set(by_matter) <= set(matters):
            raise ValueError("by_matter names a matter outside the roster it was given")
        categories = set(counts) | {c for per in by_matter.values() for c in per}
        for category in categories:
            claimed = counts.get(category, 0)
            if isinstance(claimed, bool) or not isinstance(claimed, int):
                continue  # not a countable total; the fail-closed pass below drops it
            distributed = sum(
                _contribution(per, category) for per in by_matter.values()
            )
            if distributed != claimed:
                raise ValueError(
                    f"by_matter total for {category!r} does not match its count"
                )

    n_matters = len(matters)
    if n_matters < K:
        # A household of one matter is that matter; no count over it is household
        # news. Nothing survives, and the cover rests on "Nothing is open".
        return {}

    shown: dict[str, int] = {}
    for category, count in counts.items():
        # bool is an int subclass; a boolean count is nonsense, and both True (1)
        # and False (0) fall below K anyway — the isinstance guard keeps one from
        # ever reading as a rung-shaped truth by accident (I-14's shape).
        if isinstance(count, bool) or not isinstance(count, int):
            continue
        if count < K:
            continue
        if by_matter is not None:
            contributors = sum(
                1 for per in by_matter.values() if _contribution(per, category) >= 1
            )
            if contributors < K:
                continue
        shown[category] = count
    return shown
