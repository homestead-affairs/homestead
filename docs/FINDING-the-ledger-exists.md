# The ledger exists — a cross-repo finding

Status: **A finding, not a decision.** Nothing is proposed for implementation
here and nothing in either repo was changed to write it. It corrects one
argument in `DECISION-compelled-disclosure.md`, and it carries one item back to
another repo that this hand cannot land.

Read against `rudi193-cmd/Nestor` at `be831de` (current state plus the last
thirty commits — not a full history). Nestor is attached to this session
**read-only**; nothing here was written there.

---

## The claim this repo has been making

`rungs.py` § *What it does not do*: *"It does not ledger. `L3` and `L4` on S4
require an explicit act **recorded** in the ledger. This module returns a
decision; it writes nothing."* PR #5 pinned the consequence as an invariant:
*`may_render` gains no safety from membership; the value is auditability, and
that is Phase 3+.*

Every open decision in this series inherits that. `DECISION-agent-retrieval.md`
closes S3's column because the ledger backing the lift *"is Phase 3+ and does not
exist"*. `DECISION-redisclosure.md` and `DECISION-compelled-disclosure.md` both
turn on a vocabulary for a ledger nobody has written a line into.

**"Phase 3+" has been doing the work of "unbuilt". It should stop.**

## What Nestor has

`nestor/ledger.py` and `nestor.cascade.ledger_append` are an append-only,
hash-chained, tamper-evident ledger, in a promoted repo with `dependencies = []`.

- **Chained.** Each line's `prev` is the SHA-256 of the whole previous line, so
  editing any past line breaks the next link. `verify()` walks it and returns
  `(ok, detail)`.
- **Verified rather than merely written.** Nestor's own docstring names the
  failure it was built against: *"a tamper-evident log nobody verifies is just a
  log — Nestor shipped the chain and no verifier."* The walk runs on read and
  boot, and a broken chain is a refusal, not a warning.
- **Correct under concurrency, the hard way.** `ledger_append` holds a
  process-wide lock for threads and an advisory file lock for processes, because
  eight threads appending concurrently once wrote all 160 lines and left a chain
  that `verify()` rejects — *"an audit trail that indicts itself, on a system
  whose whole claim is the trail."*
- **Held by somebody else.** `nestor.frank` mirrors every entry into a ledger the
  local writer cannot reach, each line carrying its own `local_hash`.
- **Injectable.** `set_ledger_path()`; the seam is a path and a function, not a
  framework.

That is the component this repo has been deferring to. It is built, it is
adversarially tested, and it is already the fleet's promotion standard.

## What it changes here — and one argument of mine it refutes

`DECISION-compelled-disclosure.md` § *Which way the deadline runs* concluded:

> **So there is a deadline, and it is not today. It is the first ledger write.**
> That is a fact about Phase 3, not about this brief.

The reasoning holds. **The premise does not.** That section treated the first
ledger write as remote because the ledger was unbuilt. It is not unbuilt; it is
unwired. The distance from here to the first ledger line is an integration
someone could start this week, not a phase.

So the deadline that brief identified is real and much nearer than it priced.
Its recommendation is unchanged in shape — narrow `FILING`'s gloss
unconditionally, decide `COMPELLED_DISCLOSURE` on the product question — but its
*timing* argument inverts. It argued the cost curve is flat, so there is no
hurry. The cost curve is still flat. What is not flat is the window: once
`purpose` starts landing in ledger rows, a compelled production recorded as
`filing` is unrecoverable by inspection or migration, and that window is now
close enough to see.

**Correcting my own brief rather than editing it.** That document is dated and
its argument was sound on what it knew. It should be annotated, not rewritten.

Two smaller consequences:

- **P-1 is half-open.** `DECISION-agent-retrieval.md` § *Reopening* set the bar
  for S3's column at *"S3 carrying a trust tier (P-1), and S4's ledger existing
  to copy."* The second half exists now. The first does not, and it was always
  the load-bearing half — a lift conditioned on a tier this module cannot read is
  a lift conditioned on nothing. **This is not an argument to reopen S3.** It is
  a note that one of the two stated gates has moved, so the next person reading
  that sentence does not have to rediscover it.
- **`REDISCLOSURE`'s defence gets more concrete.** `DECISION-redisclosure.md`
  argues the member earns its place by naming an act no other member truthfully
  names, in a ledger that does not yet exist. The ledger it was arguing about is
  a real file format with a real row shape.

## What runs the other way, and it is the sharper half

Nestor's ledger rows carry a `kind`. **It is a free string, and nothing validates
it.** Twenty kinds are in use — `seal`, `unseal`, `seal_replaced`,
`seal_override`, `reject_match`, `reject_pair`, `reject_segment`, `restore`,
`entity_seal`, `entity_resolve`, `baseline_seal`, `baseline_replaced`,
`reconcile`, `corpus_seed`, `seed_conflict`, `seed_rejected`, `bundle_import`,
`proposal`, `passage`, `segment_sealed` — grown one call site at a time. There is
no enum, no membership check, and no test pinning the set; grepping for one finds
nothing. `nestor/frank.py` coerces whatever it is handed:

```python
kind = str(entry.get("kind") or "entry").strip() or "entry"
```

so an unknown kind is not an error, it is an event type.

**This repo has already fixed that defect twice, and wrote down why both times.**

- **R-7** — `VisibleLog.record`'s first argument was a free string, that is where
  note content leaked, and it became a closed enum.
- **`Purpose`** — a purpose was any non-blank string, so `"x"` bought the same
  lift as `"medical"`. I-13 calls a declared purpose a *control*, and *a control
  nothing can check is a label*.

The field that records **why a boundary was crossed** is the field that must not
be free text. That is this project's most-repeated sentence, and it is the
sentence Nestor's `kind` has not heard.

Two things follow, and they are not the same size:

1. **Homestead is not only a consumer here.** The closed-set discipline is the
   more mature design, and it is the thing the better-built component is missing.
   If `purpose` ever lands in a Nestor row, it arrives as a closed enum inside a
   row whose own type field is not one.
2. **This is Nestor's decision, not ours.** Twenty organically-grown kinds with
   live call sites is a different and larger change than six members with none —
   the cheapest-moment argument that applied to S3 applies here in reverse, and
   badly. It should be raised there as a finding, with this repo's two precedents
   attached, and decided by whoever owns that ledger.

## One limit to inherit along with the component

A hash chain vouches for every line **except the newest** — nothing follows it,
so editing the last line leaves the walk passing. Nestor states this plainly
rather than letting it be discovered, and closes it two ways: `verify(
expected_head=...)` for a caller who kept the tip somewhere the writer cannot
reach, and FRANK for the general case.

If this repo ever ledgers an S4 egress, the newest line is the one that just
recorded why an `L4` payload left the machine. **The most recent decision being
the editable one is a strange thing for an audit trail to leave unsaid**, and it
is not a defect to fix on adoption — it is a property to carry the fix for.

## What is not proposed

- **No wiring.** Nothing here proposes that homestead depend on Nestor. That is
  an integration with a ratification of its own, and the injected-seam direction
  matters: the host imports the component, never the reverse.
- **No change to either open brief's recommendation.** Only the timing argument
  in one of them is corrected, and that correction argues for deciding sooner,
  not for deciding differently.
- **No reopening of S3.** One gate moved; the other did not.
- **Nothing written to Nestor.** It is attached read-only and the `kind` finding
  is not this hand's to land. If it is raised there, it should be raised as a
  question with the two precedents attached, not as a patch.

## What is gated on what

- **The `FILING` gloss** — free, and unaffected by any of this. Still the
  smallest true thing available.
- **`COMPELLED_DISCLOSURE`** — still the product question about whether these
  households field discovery. What changed is that deferring it *"to Phase 3"* is
  no longer deferring it far.
- **Any homestead↔Nestor integration** — needs its own decision, and would set
  the row shape that both open briefs are arguing about the vocabulary for. It
  should be decided **before** the vocabulary is frozen, not after.
- **Nestor's `kind`** — theirs. Raise, do not patch.
