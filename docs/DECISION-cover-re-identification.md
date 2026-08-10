# The cover's re-identification check — decision brief (I-31)

Status: **Proposed. Built and green, awaiting ratification by another hand** —
`verified_by ≠ author`, as with `DECISION-agent-retrieval.md` and
`DECISION-redisclosure.md`. This brief and the code it describes were written by
the same hand; the rule below is a product judgement about what a resting screen
may reveal, and one author grading their own arithmetic is exactly the shape
`§0.2` forbids. This recommends; the operator ratifies.

The invariant, unchanged: **the resting state reveals nothing** — the cover shows
counts that survive the `L2` re-identification check and no more (I-31, F-5, the
rung model's `L2` and step 2a).

---

## The question

Phase 0 kept the cover count-less — "Nothing is open" — and that was correct: no
count can leak what no count exists. I-31 asks the harder thing, which is to make
counts *possible* on the cover in exactly the cases where the number reveals
nothing about **which matter** it came from, and to drop the rest. The clear case
the pending test pins: `cover_counts(matters=["custody"], overdue=1)` must not
show the overdue count. The brief is about everything the pin does not reach.

The rung model states the check but does not implement it (`PHASE2-SURFACES.md`:
*"The re-identification check itself is not implemented … I-31 is Phase 4"*). This
is that implementation, at the surface, over aggregate counts.

## What the surface is handed, and what it is not

`cover_counts(matters, **counts)` receives the **roster of open matters** and a
set of **per-category aggregate counts** (`overdue=1`, `due_soon=4`, …). It is
*not* handed the per-matter distribution — it does not know whether `overdue=3`
is `(3,0,0)` or `(1,1,1)` across the matters. That boundary is load-bearing for
the rule and is stated as a limit below rather than hidden.

## The rule: two independent anonymity gates, `K = 2`

A per-category count is shown **only when it clears both**, and is otherwise
**absent** (never a `0` in its place):

**Gate 1 — k ≥ 2 on the count itself.** A count of `1` is one item, and one item
lives in exactly one matter, so `overdue=1` *resolves to* that matter the instant
it is read. The worked example is explicit that this "is not about matter-count":
a household of three matters does not launder a count of one, because the count
still points at the single matter holding the single item. k-anonymity with
k = the count; k = 1 is re-identifying by arithmetic.

**Gate 2 — k ≥ 2 on the matters.** With one open matter, the household *is* that
matter, so every count — `1`, `5`, `50` — is a fact asserted about it. A number
cannot be spread across matters that do not exist, so the mapping to a matter is
forced exactly as it is for a count of one.

Both gates fire independently. The pinned case (`["custody"]`, `overdue=1`) trips
both at once, which is precisely why each must be tested alone:

- drop Gate 2 and `cover_counts(["custody"], overdue=5)` leaks "5 overdue" onto a
  screen a second person can read, naming the sole matter's state;
- drop Gate 1 and `cover_counts(["a","b","c"], overdue=1)` leaks a count that
  names whichever matter holds the one overdue item.

## Why "absence, not zero"

A dropped count leaves **no key**. "0 overdue" over one matter still tells the
reader *that matter has none* — a fact about the matter, F-1's reader again — and
a zero is `count < K`, so it fails Gate 1 regardless. This is the same discipline
the window already keeps: `serve_all` drops what it denies without a placeholder,
count, or ordering gap (product decision 2). An absent key means "not shown"; it
never means "shown as none".

## What a survivor is rendered as — the real number

A count that clears both gates is shown **as itself** (`due_soon=4` → `4`), not
banded or blurred. The check is about *whether* a number may cross, not about
softening one that may: a survivor does not, on its face, resolve to a single
matter — `overdue=3` over three matters is consistent with `(3,0,0)`, `(2,1,0)`
and `(1,1,1)`, so the number pins no matter. Rendering the truth is the point of
having passed.

## The honest limit — the distribution the cover cannot see

Gates 1 and 2 certify that the number does **not force** a single matter. They do
**not** certify that a survivor is *actually spread* across ≥2 matters, because
the surface is not handed the distribution: `overdue=2` over two matters passes
here even if both items sit in one matter, since the cover cannot tell `(2,0)`
from `(1,1)` — and neither can the reader, from the number alone. This is a
deliberate boundary, of the same kind as `DECISION-compelled-disclosure.md`'s
"known, open gap": the aggregate is the honest unit the cover has.

**If a later bite wants the stronger guarantee** — show a count only when it
demonstrably spans ≥2 matters — the caller must pass the per-matter distribution
and Gate 2 tightens to read it (a count survives when ≥2 matters each contribute
≥1). That is a widening of the input, not a change to the rule's direction, and
it is left for when a distribution exists to check. Recorded here so the next
seat finds the boundary named rather than re-deriving it.

## What this is *not*

- **Not a rung computation.** `cover_counts` compares integers and copies matter
  names; it reads no `Rung`, reaches no `.payload`, and reflects over nothing
  (I-29, enforced by `test_invariants_chokepoint.py` over `homestead/app/`). The
  re-identification arithmetic is the surface's own and lives nowhere else.
- **Not a declassifier.** It lowers no rung. A count that fails the check is not
  *made* `L2`; it is simply not shown. `L2` is what an aggregate *is* after it
  passes, and passing is the whole of the check (rung model, `L2`).
- **Not the matter-count itself.** Whether the cover may show *"3 matters open"*
  (the number of matters, once ≥2) is a separate product call. It is not a
  per-matter-derived count — it points at no single matter — so the same k≥2
  logic would permit it at ≥2 matters; but the pending test does not ask for it,
  and emitting an unrequested key is its own small surprise. **Left out on
  purpose**, noted for ratification: if wanted, it is a one-line addition and its
  own test.

## What a second hand should ratify

1. **The two gates and `K = 2`** — that a count of one, *and* a household of one
   matter, each independently withhold every count; and that `K = 2` is the floor
   (loosening either gate to 1 must fail a test, and does).
2. **Absence, not zero** — that a dropped or unpassed category is an absent key,
   never a rendered `0`.
3. **The survivor renders as its real number**, not a band.
4. **The distribution limit** — that certifying "does not force one matter" (not
   "provably spread across ≥2") is the right line for an aggregate-only surface,
   and that tightening it is correctly deferred to when a distribution is passed.
5. **Leaving the matter-count out** — that not surfacing `len(matters)` by
   default is the right default, or a request to add it.

## Files

- `homestead/app/cover.py` — the module and its docstring.
- `tests/test_invariants_cover.py` — the promoted I-31 test plus the hard cases
  (each gate alone, absence-not-zero, real-number survivor, fail-closed on a
  non-integer).
- `tests/test_invariants_pending.py` — `homestead.app.cover` struck from
  `UNBUILT`, the pending test removed, a promotion note left in its place.
- `README.md` — one status sentence.
