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
set of **per-category aggregate counts** (`overdue=1`, `due_soon=4`, …). ~~It is
*not* handed the per-matter distribution — it does not know whether `overdue=3`
is `(3,0,0)` or `(1,1,1)` across the matters.~~ (struck 2026-09-11, E4: it is now
handed the distribution when a caller has one — `cover_counts(matters, *,
by_matter=None, **counts)`. Without one, every sentence above still holds, and
that is still the default.) That boundary is load-bearing for the rule and is
stated as a limit below rather than hidden — see *The honest limit* and the
struck paragraph that closes it.

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

~~**If a later bite wants the stronger guarantee** — show a count only when it
demonstrably spans ≥2 matters — the caller must pass the per-matter distribution
and Gate 2 tightens to read it (a count survives when ≥2 matters each contribute
≥1). That is a widening of the input, not a change to the rule's direction, and
it is left for when a distribution exists to check. Recorded here so the next
seat finds the boundary named rather than re-deriving it.~~

> **Struck 2026-09-11 — the boundary is closed.** That later bite landed
> (E4-cover-distribution): `cover_counts` now takes an optional keyword-only
> `by_matter` (matter → category → share), and when it is given Gate 2 tightens
> exactly as predicted — a category survives only when at least `K` **distinct
> matters in the distribution** each contribute at least one to it. `(2, 0)` is
> dropped where `(1, 1)` passes. The widening was of the input, not of the
> rule's direction, as this paragraph forecast. `by_matter=None` — the default,
> and every call written before the parameter existed — is byte-identical to the
> aggregate-only behaviour described above, so the limit in the paragraph above
> this one still describes what a caller *without* a distribution gets. The
> paragraph is struck because it described its own future as open, and a
> decision brief that does that is a stale claim, not a record.
>
> Two things the widening settled that the forecast did not name:
>
> * **The distribution is evidence, and evidence is checked before it is read**
>   (I-11). `by_matter` must be a mapping of matter to share table; its matters
>   must be a subset of the roster; every share must be a plain non-bool,
>   **non-negative** `int`; every category it distributes must be one the caller
>   also counted (the totals check runs over the union of both sides); and each
>   category's distributed total must equal the aggregate passed for it.
>   Anything else is refused by category name, never repaired. The sign is
>   load-bearing and was found on audit: without it `{a: 3, b: 1, c: -2}` totals
>   `2`, clears the totals check and presents *two* contributors for a spread no
>   household has — a negative term makes a sum stop being a count.
> * **The roster is a set.** The matters gate counts *distinct* matters, so
>   `["custody", "custody"]` is one matter and shows nothing. This was wrong in
>   the aggregate-only code from the start — it is the same failure law's L2c
>   audit found one layer up, a gate satisfied by the *shape* of the list handed
>   to it rather than by the household — and it is fixed here rather than left
>   for the caller to avoid.

### What the tightening itself publishes

Tightening a gate is not free, and this brief should not pretend it is. A
published count now carries one bit the aggregate-only gate did not publish:
that ≥`K` matters contribute to it. Run the rule backwards at the floor —
exactly `K` matters on the roster, a count of exactly `K` — and the reader lands
on `(1, 1)` exactly. So "2 overdue" over two matters, under the distribution
gate, does tell a reader who knows the rule that each matter holds one.

That is **inside** I-31's threat model, not a hole in it. The model asks that the
resting number not resolve to *which* matter the news belongs to (F-5's reader
behind the chair, the rung model's `L2`, step 2a). `(1, 1)` is the one
distribution perfectly symmetric across the roster: it singles nobody out, and
there is no "which one?" left to answer. Compare the case the tightening
*removes* — `(2, 0)`, where the news is entirely one matter's and the old gate
showed it anyway. The trade is strictly in the model's direction.

Nor does it reach further than the floor. At three matters, `overdue=6` with
`{a: 5, b: 1, c: 0}` publishes only "at least two of the three contribute";
`(4,1,1)`, `(2,2,2)` and `(3,2,1)` are all still consistent, and an observer who
separately knows `c` is clean learns `a + b = 6` — which is the aggregate over
the matters that have news, the honest unit this brief has argued for
throughout. The gate that avoids even the floor inference is "show nothing",
which is Phase 0.

**For ratification:** that the floor inference (`K` matters, count `K` ⇒ each
contributes one) is an acceptable price for dropping `(2, 0)`, or a request to
raise `K`, which is a one-line change and its own test.

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
   ~~and that tightening it is correctly deferred to when a distribution is
   passed.~~ (struck 2026-09-11: no longer deferred — E4 passed a distribution
   and tightened it.) and that it remains the right line for the `by_matter=None`
   calls that are still the default.
5. **Leaving the matter-count out** — that not surfacing `len(matters)` by
   default is the right default, or a request to add it.
6. **(E4, 2026-09-11) The tightened Gate 2 and what it publishes** — that
   "≥`K` distinct matters each contribute ≥1" is the right stronger rule when a
   distribution exists; that its floor inference (see *What the tightening
   itself publishes*) is an acceptable price; and that a distribution which
   cannot be checked — non-mapping, a matter off the roster, a negative or
   non-`int` share, a category distributed but never counted, a total that
   disagrees with its aggregate — is **refused by category name**, not repaired
   and not quietly downgraded to the aggregate-only gate.
7. **(E4, 2026-09-11) The roster read as a set** — that `["custody", "custody"]`
   is one matter and shows nothing; this corrects the original code, which
   counted list entries and would have shown a lone matter's counts on a
   duplicated roster.

## Files

- `homestead/app/cover.py` — the module and its docstring.
- `tests/test_invariants_cover.py` — the promoted I-31 test plus the hard cases
  (each gate alone, absence-not-zero, real-number survivor, fail-closed on a
  non-integer), and — since E4 — the distribution cases: `(2,0)` dropped and
  `(1,1)` kept, `by_matter=None` byte-identical to the old behaviour, each
  refusal above with its violation planted, the duplicated roster, and a planted
  matter name and share asserted absent from `str`, `args` and `__notes__` of
  every refusal.
- `tests/test_invariants_pending.py` — `homestead.app.cover` struck from
  `UNBUILT`, the pending test removed, a promotion note left in its place.
- `README.md` — one status sentence.
- `docs/homestead-rungs-procedure.md` — the I-31 row, widened (struck, dated).
- `homestead_law`'s `queue.cover()` calls its *own* vendored copy of this
  function (`homestead_law/app/cover.py`), not this one, so nothing in law
  changed with E4 and nothing in law can. Law's copy still takes
  `(matters, **counts)`; the Wave-5 caller that means to pass a distribution has
  to widen that copy too, or import this module.
