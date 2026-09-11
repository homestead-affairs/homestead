# An eighth member, `SYNC` — decision brief

Status: **Proposed; ratified by the audit of this bite.**
author: the build seat
verified_by:

This follows `docs/DECISION-compelled-disclosure.md`'s method exactly — measure
the same four questions it measured, for a different candidate member — because
that brief is the precedent this repo already ratified for how a purpose member
gets added: measure the crossing, find every pin, rename what a count-named
test would otherwise break, and say what the addition costs before proposing it.

Raised by Wave 1 of `docs/PLAN-affairs-face.md` (decision 5): sync is an
operator act, never background, and it needs a word in the ledger vocabulary
before `keep/sync.py` (Wave 4) writes the first line that uses it — the same
shape `COMPELLED_DISCLOSURE` was in before Phase 3's ledger existed.

---

## The mechanical facts, measured

### 1 · An eighth member changes no answer. Zero cells, out of twenty-five.

`may_render` reads *whether* a purpose was declared and never *which*
(`rungs.py:_declared`). Fired over the whole grid, in the working tree with
`SYNC` added:

```
cells compared:                       25
cells where SYNC differs from EXPORT:  0
```

A dedicated test asserts this rather than only inferring it from the general
interchangeability sweep:
`tests/test_purpose_corpus.py::test_sync_lifts_exactly_what_export_lifts_on_s4_and_nothing_elsewhere`
compares `decide(rung, surface, purpose=Purpose.SYNC)` against
`decide(rung, surface, purpose=Purpose.EXPORT)` for every rung and every
surface — 25 parametrised cells, all passing. `EXPORT` is the comparison
point rather than `FILING` or any other member because it is the nearest
neighbour in *kind*: both are the operator moving their own record somewhere,
which is exactly the distinction this brief has to explain is not identity
(§ *Why not `EXPORT`*, below).

The general sweep,
`tests/test_purpose_corpus.py::test_all_members_are_interchangeable_at_the_decision_function`,
also holds with eight members, unmodified — it iterates `tuple(Purpose)` and
was never written against a count.

### 2 · That one surface is S4, and only S4

Unchanged from every prior member. `_CEILING` gives `S4_EGRESS` a `(L2, L4)`
ceiling and every other surface a ceiling a purpose does not move
(`S3_AGENT` closed 2026-08-05; see `docs/DECISION-agent-retrieval.md`). `SYNC`
lifts nothing anywhere else, by the same structural argument
`test_l5_is_refused_structurally_rather_than_member_by_member` and
`test_a_purpose_changes_no_answer_on_an_inert_surface` already make for every
member, `SYNC` included because they parametrise over `Purpose`.

### 3 · So `SYNC` buys a word, not a capability

Exactly `COMPELLED_DISCLOSURE`'s finding, restated for this member: "a call
site that wants `L4` on `S4_EGRESS` today declares `Purpose.EXPORT` and gets
it. An eighth member is not one more call site that can unlock `L4`; it is the
same call site with a different word in it." The set being closed bounds the
**vocabulary**, not the **capability**.

### 4 · Therefore this is a ledger question, and the ledger for sync does not
### exist yet either

`keep/sync.py` is Wave 4 and unbuilt (`docs/PLAN-affairs-face.md` § Wave 4,
`E4-sync-core`). So `SYNC` added now is, again, a word added to a vocabulary in
which no sentence has yet been written — see § *What this deliberately does
not include*.

---

## Why `SYNC` is a purpose individuated by posture

The set's membership rule, as `docs/DECISION-compelled-disclosure.md` restated
it after finding `COMPELLED_DISCLOSURE`'s and `SUBJECT_ACCESS`'s common shape:
**an act, individuated by the legal or operational posture that says who it
answers to and where it goes**, not by what the bytes do differently at the
gate.

A sync is that shape. It is:

- **operator-authored** — an explicit act, never a default and never
  background. `docs/DECISION-connection-consent.md` settles the general
  version of this for every cross-boundary reach in the house: *"Connections
  between modules are the household's to make — operator-authored, scoped,
  and revocable. Modules are independent by default; a connection is an
  explicit, visible, consented grant, never a designer's choice and never a
  default."* A sync to the household's own fleet store is the same shape one
  level out — the fleet is not another module in the same process, but the
  posture is identical: nothing reaches it without the operator naming the
  scope and confirming the act, per call, every time (`E4-sync-core`'s
  `SyncScope` and per-call `confirm`).
- **a copy, not a disclosure to a stranger** — the destination is the
  household's own fleet store (Postgres behind the `fleet` extra,
  `E4-postgres-fleet`), which the same household controls. It shares
  `EXPORT`'s and `SYNC`'s common ancestor — *the operator moving their own
  record* — but not `EXPORT`'s destination, which is the reason it is not
  `EXPORT` (next section).
- **never background** — `rungs.py`'s own words for the danger a session
  cache would create ("a session cache would turn the set into one hardcoded
  string per call site... after which L4 on S4 is unlocked unconditionally")
  are the same danger a background sync process would be: an unattended act
  wearing a purpose that was declared once and never re-confirmed. Wave 4's
  design refuses that shape structurally — `deliver(envelope, *, confirm, ...)`
  ledgers nothing on a refused confirm (I-37, provisional) — and the purpose
  member's whole value is naming that this is the act being confirmed.

## Why it is not `EXPORT`

`EXPORT`'s comment is `# the operator taking their own record out` — a file the
operator carries. A sync does not hand the operator anything; it puts a copy of
the household's own record into a store the operator does not open by hand
afterward, on a schedule the operator set once and revisits, not once per
file. The destination is a **store**, not a file the operator carries away.

That is the identical distinction the compelled-disclosure brief drew between
`FILING` and `COMPELLED_DISCLOSURE` — same operation, different party in
motion — turned sideways: here it is the same *party* (the operator, acting)
but a different **destination shape** (a store the household maintains, versus
a file the operator holds). Declaring `EXPORT` for a sync would be false in a
ledger for the same reason `docs/DECISION-redisclosure.md` gives for not
collapsing `REDISCLOSURE` into `EXPORT`: *"a tautology in a ledger line is
uninformative; a falsehood in a ledger line is worse than uninformative,
because it reads as evidence."* A fleet operator reading a `SYNC` row and an
`EXPORT` row should be able to tell, from the word alone, that one produced a
file handed to the operator and the other produced a database write the
operator will never see rendered — and `_declared`'s indifference to *which*
member fired means that distinction has nowhere else to live except the word.

## Its meaning is entirely in the ledger row not yet written

Exactly as `COMPELLED_DISCLOSURE`'s meaning waited on Phase 3's ledger, `SYNC`'s
meaning waits on `keep/sync.py` (Wave 4, `E4-sync-core`). That module is
specified (`docs/PLAN-affairs-face.md` § Wave 4) to write, per delivered
envelope: one `IntegrityLog` row
`{act: "record_synced", household, envelope, purpose, scope, rows,
destination}` and one `VisibleLog` `RECORD_SYNCED` reference row
`(household, envelope_id)` — references only, per I-15, never content. `SYNC`
is the value that row's `purpose` field will hold. Until that module exists,
this member is a word with no sentence, which is the honest and stated
condition of every member added ahead of its ledger (§ next).

---

## The cost, measured

Baseline, this tree, cold venv: **1885 passed / 9 skipped** — matching the
wave's stated baseline exactly.

### Adding the member and updating every pin

**One member in `rungs.py`; four assertion sites across three test files**,
the same three files `docs/DECISION-compelled-disclosure.md` found and no
others (verified by grep for `len(Purpose)`, `len(VALID_PURPOSES)`, and the
name/value pin dict — nothing outside `tests/test_invariants_surfaces.py`,
`tests/test_purpose_corpus.py`, `tests/test_surfaces_corpus.py` pins
membership):

| test | file | what moved |
|---|---|---|
| `test_the_members_are_exactly_those_that_were_ratified` | `tests/test_purpose_corpus.py` | name/value list + `len({...}) == 8` |
| `test_this_corpus_has_not_been_hollowed_out` | `tests/test_purpose_corpus.py` | `len(Purpose) == 8`, `len(VALID_PURPOSES) == 9` |
| `test_the_corpus_has_not_been_hollowed_out` | `tests/test_surfaces_corpus.py` | same two counts |
| `test_the_purpose_enum_is_the_set_that_was_ratified` | `tests/test_invariants_surfaces.py` | membership dict, `SYNC` added |

No test needed **renaming** this time — the count-named tests
(`..._is_the_six_that_were_published`, `..._the_six_members_are_exactly_the_six...`,
`..._all_six_members_are_interchangeable...`) were already renamed off their
counts by the `COMPELLED_DISCLOSURE` bite
(`test_the_purpose_enum_is_the_set_that_was_ratified`,
`test_the_members_are_exactly_those_that_were_ratified`,
`test_all_members_are_interchangeable_at_the_decision_function`), which is
that ratification's pin doing its second job: the fix for a title that lies
about a count is not renaming it again next time, it is naming it for the
property once, permanently.

### One test added, not required by any pin

`test_sync_lifts_exactly_what_export_lifts_on_s4_and_nothing_elsewhere`
(`tests/test_purpose_corpus.py`) — 25 parametrised cells, all rungs by all
surfaces, `decide(..., purpose=SYNC)` against `decide(..., purpose=EXPORT)`.
Not required to make the suite pass; required by this bite's brief, and a
useful third proof alongside the whole-table interchangeability sweep and the
structural `L5`-reach test, because it names the specific comparison a reader
asking "is `SYNC` really inert relative to `EXPORT`" would want answered
directly rather than inferred from a general property.

### Result

**1993 passed / 9 skipped**, from 1885 / 9 — **+108**: +83 from the sweeps
picking the eighth member up with no test rewritten (identical to
`COMPELLED_DISCLOSURE`'s measured +83), +25 from the new dedicated test. Zero
migrations, zero renames, zero failures introduced. `pyflakes` clean on every
file touched.

### Mutation score: unchanged

`python docs/audits/purpose_corpus_mutate.py`, run against the working tree
with `SYNC` added:

```
mutants: 29 · survivors: ['the agent surface loses its lift — L4 is unservable on S3']
```

**Identical to the previous brief's finding** — one pre-existing survivor,
`S3_AGENT`'s column already being closed makes the "S3 loses its lift" mutant
a no-op the corpus cannot distinguish from the unmutated tree. An eighth
member neither opens nor closes a hole in the corpus.

### Doc sites, not counted above

`homestead/keep/rungs.py`'s `Purpose` class docstring still narrates "the set
was six... became seven the same day" in its `COMPELLED_DISCLOSURE` paragraph.
Under archive-don't-delete and annotate-don't-rewrite that paragraph is left as
the dated record it is; a new paragraph naming `SYNC` and this document is
appended after it rather than folded into the old count. Same treatment
`docs/DECISION-compelled-disclosure.md` gave the eleven `PHASE2-SURFACES.md`
lines that said "six" — they are the operator's or the ratifying hand's to
annotate, not this bite's to rewrite, and none of them live in this repo's
scope for this bite beyond `rungs.py` itself, where the new member's own
comment and one new docstring paragraph are the addition.

### Callers

**There are none**, verified the same way the prior brief verified it for
`COMPELLED_DISCLOSURE`: no call to `may_render`, `decide`, `serve`,
`serve_all` or `ambient_rows` exists anywhere in `homestead/` outside
`rungs.py`. `keep/sync.py` does not exist. This bite adds only the enum
member and its tests.

---

## What this deliberately does not include

- **No caller declares `Purpose.SYNC` yet.** `keep/sync.py` is Wave 4
  (`E4-sync-core`), not this bite. That is the documented acceptable state —
  the same one `docs/DECISION-compelled-disclosure.md` left
  `COMPELLED_DISCLOSURE` in after its own ratification, with the same
  reasoning: a member ahead of its caller is a vocabulary word with nothing
  written in it yet, which is not nothing (a reader can see the word coming
  and design around it) but is exactly and only that much.
- **No ledger write.** `homestead.keep` still does not ledger (`rungs.py`'s
  own *What it does not do*). The `IntegrityLog` and `VisibleLog` rows this
  member's meaning depends on are Wave 4's to write.
- **No `SyncScope`, no envelope, no fleet adapter.** Those are
  `E4-sync-core` and `E4-postgres-fleet`, both out of this bite's scope and
  both depending on an engine release this bite does not cut.
- **No decision about ranking `SYNC` against other members.** Exactly
  `docs/DECISION-compelled-disclosure.md`'s option E: unavailable and
  unneeded. `_declared` returns a `bool`; ranking needs a trust tier and a
  ledger, neither of which exists, and inventing one here would be inventing
  an authority `rungs.py:444` already refuses to invent for any member.
- **No change to any `_CEILING` cell.** Measured at zero moves (§ 1); this
  bite is not a crossing decision and does not propose to become one.
