# An eighth member, `SYNC` — decision brief

Status: **Ratified, 2026-09-11.** `Purpose.SYNC = "sync"` is a member; the four
pins are updated; zero cells of `_CEILING` move, measured and pinned. Every
measurement in this brief was re-run independently at ratification and every
one holds exactly — baseline **1885 passed / 9 skipped**, **+83** sweep pickups
with no test rewritten, **+25** from the new test, **29 mutants · 1
pre-existing survivor**. **Four** of its non-measured claims did not hold and
were corrected rather than ratified, and one argument was incomplete and is
finished; all five are marked **Corrected at ratification** or **added at
ratification** where they stand, and listed in § *What the ratification
changed*.
author: the build seat
verified_by: the audit seat, 2026-09-11

*Status as proposed, kept:* **Proposed; ratified by the audit of this bite.** —
which is the proposing hand writing the outcome of a ratification it is not
allowed to perform. `verified_by ≠ author` is not a form to fill in after the
fact; a brief that states its own verdict has already spent the thing the rule
protects. Left standing rather than deleted, because it is what the document
said when it was handed over.

This follows `docs/DECISION-compelled-disclosure.md`'s method exactly — measure
the same four questions it measured, for a different candidate member — because
that brief is the precedent this repo already ratified for how a purpose member
gets added: measure the crossing, find every pin, rename what a count-named
test would otherwise break, and say what the addition costs before proposing it.

Raised by Wave 1 of the affairs build plan (decision 5). The plan lands in this
repo as `docs/PLAN-affairs-face.md` in Wave 7 and is **not** here yet, so the
two citations of it below are forward references rather than links a reader can
follow today — noted at ratification, because a brief that cites a document
nobody can open is asking to be taken on trust. Sync is an
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
- **revocable forward only — added at ratification.** The posture quoted above
  is *operator-authored, scoped, **and revocable***, and the brief as proposed
  argued the first two and let the third go by. The third does not transfer
  whole, and saying so is the point: a sync grant is revocable in the only
  sense a copy can be — the operator can stop syncing, narrow a `SyncScope`, or
  withdraw it before the next envelope — but a **delivered envelope is not
  recallable**. The row is in the fleet store and the household side, which by
  design never holds the DSN (§ Open items 7 of the build plan), cannot reach
  in and unwrite it. That asymmetry is the honest reason the confirm is
  per-call rather than per-grant, and it is an argument *for* the member rather
  than against it: the ledger row `SYNC` will carry is the only record the
  household keeps of a copy it can no longer retrieve.

## Why it is not `EXPORT`

`EXPORT`'s comment is `# the operator taking their own record out` — a file the
operator carries. A sync does not hand the operator anything; it puts a copy of
the household's own record into a store the operator does not open by hand
afterward. The destination is a **store**, not a file the operator carries away.

> **Corrected at ratification.** As proposed, that sentence went on: *"~~on a
> schedule the operator set once and revisits, not once per file~~"*. Struck. A
> schedule the operator sets once is precisely the unattended act the bullet
> above refuses and the one decision 5 forbids in as many words — *sync is an
> operator act, never background*. There is no schedule. Every envelope is
> confirmed on the call that delivers it, and the sentence as written would
> have been the first citation anybody reached for when proposing a daemon.

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
annotate, not this bite's to rewrite.

> **Corrected at ratification.** The sentence that followed — *"~~none of them
> live in this repo's scope for this bite beyond `rungs.py` itself~~"* — is
> wrong, and the distinction it missed is the one this whole method turns on. A
> **dated narrative** ("the set was six, and became seven the same day") stays
> as written, because it records what was believed on a date. A **present-tense
> claim about how the thing works now** is not a dated record; it is either true
> or false. **Twelve** of them were false, in live docstrings and banners that
> no test reads.
>
> Five are about the size of this set, and this bite made each of them two
> members out of date rather than one:
>
> | site | said | now |
> |---|---|---|
> | `homestead/keep/rungs.py` (`_declared`) | "the bare spellings of the **six** members", "**six** magic strings instead of none" | named for the property |
> | `homestead/keep/rungs.py` (`_declared`) | "the ceiling table has two columns, not **seven**" | "two columns, not one per member" |
> | `tests/test_invariants_surfaces.py` ×2 | "two columns rather than **seven**", "Two columns, not **seven**" | same |
> | `tests/test_surfaces_corpus.py` | "the cell sweep is smaller than it was (**7** purposes, not 12)" | counted from the enum, not spelled out |
>
> The other seven are about how many surfaces a purpose is inert on, and they
> were **already false before this bite** — they went stale on 2026-08-05 when
> S3's column closed, and neither that bite nor `COMPELLED_DISCLOSURE`'s caught
> them, which is the cost the precedent predicted arriving exactly where it
> said it would:
>
> | site | said | now |
> |---|---|---|
> | `tests/test_purpose_corpus.py` § 4 banner | "Inert on **three** surfaces, lifting on **two**" | named for `INERT_SURFACES` / `LIFTING_SURFACES` |
> | `tests/test_purpose_corpus.py` (`..._on_an_inert_surface`) | "The **three** surfaces whose ceilings are equal" | same, plus the S3 sentence that was missing |
> | `tests/test_purpose_corpus.py` (`..._accepted_on_all_five_surfaces`) | "on **three** of five surfaces" | "the surfaces where it is inert" |
> | `tests/test_invariants_surfaces.py` (`test_the_detail_pane_needs_no_purpose...`) | "inert on **three**" | "inert on every surface but `S4_EGRESS`" — the next function in the same file is named `..._and_inert_on_four`, so the file contradicted itself |
> | `tests/test_invariants_surfaces.py` (`..._raises_even_where_a_purpose_is_inert`) | "the **two** surfaces where a purpose lifts ... the **three** where it does not" | named for the property |
> | `tests/test_surfaces_corpus.py` module docstring | "the **three** surfaces whose ceilings are equal" | same |
> | `homestead/keep/rungs.py` (`may_render`) | "passing rubbish on **three** surfaces and then carry it to the **two** where it lifts" | named for the property |
>
> All twelve are fixed the way the
> precedent prescribes: *"the fix for a title that lies about a count is not
> renaming it again next time, it is naming it for the property once,
> permanently."* Rewriting a live false sentence is not a breach of
> annotate-don't-rewrite; leaving it standing would have been a breach of
> something worse.
>
> Not fixed, deliberately, and left for `X7-drift-homestead`: a grep guard that
> would keep a count-word out of a live claim about this set. It cannot be
> written without also firing on the dated narratives it must not touch, and
> telling those apart is the drift bite's problem, not this one's.

### Callers — **Corrected at ratification**

As proposed this section read: *"~~**There are none**, verified the same way
the prior brief verified it for `COMPELLED_DISCLOSURE`: no call to
`may_render`, `decide`, `serve`, `serve_all` or `ambient_rows` exists anywhere
in `homestead/` outside `rungs.py`.~~"* That is false in this tree, and it was
inherited rather than measured: the prior brief measured it on 2026-08-05, when
it was true, and it stopped being true at `371bfb2` — *"wire the chokepoint —
one door to a payload"*. Measured here, `serve()` has four callers:
`homestead/app/window.py:112` and `:128`, `homestead/keep/store.py:332`,
`homestead/keep/export.py:196`.

**The conclusion survives; only the evidence was wrong**, and the replacement
is narrower and is the thing that was actually load-bearing all along: **no
module in `homestead/` enumerates the purpose set.** `export.py` imports the
*type* and renders `[p.value for p in Purpose]` into its refusal text — both
derived from the enum, both still true the day it grows. No call site spells
the members out, so a new member cannot make one of them silently short. That
is the claim, and it is now a test with a planted violation rather than a
sentence:
`tests/test_purpose_corpus.py::test_no_module_hardcodes_a_list_of_purpose_values`
and `::test_the_hardcoded_purpose_scan_catches_a_planted_enumeration`.

`keep/sync.py` — the first module that will *name* a member — does not exist.
Naming one member is a call site and is what the set is for; the guard above is
careful not to forbid it. This bite adds the enum member, its tests, and (at
ratification) that guard.

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

---

## What the ratification changed

Read by the audit seat against `docs/DECISION-compelled-disclosure.md` as the
precedent, on a cold venv, 2026-09-11.

**Re-measured and holding, independently:**

| claim | re-measured |
|---|---|
| baseline 1885 passed / 9 skipped | 1885 / 9, at `f121b1e` |
| +83 from the sweeps, no test rewritten | 1968 / 9 with the new test deselected; 1968 − 1885 = **83** |
| +25 from the new dedicated test → 1993 / 9 | 25 collected, **1993 / 9** total |
| zero `_CEILING` cells move | pinned by `test_the_ceiling_table_matches_an_independent_transcription`, which sweeps `SYNC`; a planted `S3_AGENT: (L2, L4)` fails 43 cases |
| 29 mutants · 1 pre-existing survivor | identical, `docs/audits/purpose_corpus_mutate.py` |
| the four pins are the only membership pins | confirmed by grep; no test *name* asserts a purpose count (the precedent's rename did that job) |
| `"sync"` passes `_check_the_str_enums_cannot_be_confused` | disjoint from `L1`–`L5` and `S1_LIST`–`S4_EGRESS` |
| `"sync"` passes `test_there_is_no_catch_all_purpose` | `SYNC` matches no banned stem, and names an act rather than a category, a surface or an instrument |
| `VALID_PURPOSES` is 9 | `(None,) + tuple(Purpose)` — the ninth is `None`, "nobody declared one", which is not an error and is the reason the sweep is complete |

The new test is not a never-fired guard: planting `if purpose is Purpose.SYNC:
return False` in `_declared` fails it at `[L3-S4_EGRESS]` and `[L4-S4_EGRESS]`.

**Corrected rather than ratified:** the status line (a brief may not record its
own verdict); § *Callers* (false, and inherited rather than measured — replaced
with the narrower claim that was load-bearing, now a test with a plant); the
`EXPORT` section's "a schedule the operator set once" (contradicts decision 5
and this brief's own *never background* bullet); and § *Doc sites*'s claim that
no live count outside `rungs.py` was stale — twelve were (two of them inside
`rungs.py`), five about the size of this set and seven about the surfaces, the
latter already false since 2026-08-05.

**Added rather than corrected:** the *revocable forward only* bullet. The
posture this brief borrows from `docs/DECISION-connection-consent.md` has three
parts and the brief argued two.
