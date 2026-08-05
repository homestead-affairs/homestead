# P-3 — a build failure for an unclassified field. Decision brief

Status: **Proposed. Nothing done.** No file was changed to write this.

**Proposed here, to be ratified by another hand** — `verified_by ≠ author`, as
with the three briefs before it. This one recommends recording an answer rather
than building anything, which is the kind of recommendation that most needs a
second pair of eyes: "there is nothing to do here" is what a missed question
looks like from the inside.

Raised as P-3 of `docs/audits/phase2_corpus_report.md`, in these terms:

> **P-3 · Is a build failure the right instrument for an unclassified field in a
> matter pack a *user* can add?** I-11 says build failure, and the corpus
> enforces it hard. Right for shipped schemas. Different question for a matter
> type a user or clinic defines later (the deferred D2 case): a build failure is
> not available to them, and the fallback — "reads `L5` and is not served" —
> means their new field silently shows nothing with no explanation. **Decide now
> whether user-defined fields are in scope, because "fail the build" and "fail
> the user" are different products.**

The reasoning is sound and the question is well posed. **Three of its premises
turn out to be already answered, in writing, elsewhere** — two in the spec and
one in a ruling this repo made on 2026-08-05. What is left is real but much
narrower than the framing, and most of it is a Phase 3 build item that is already
on the plan.

---

## The mechanical facts

### 1 · `classify_schema` has no callers, and there is no schema

Grepped rather than assumed. Outside its own definition and `__all__`, nothing in
`homestead/` calls `classify_schema` — the only other hits are the two mutation
harnesses under `docs/audits/`. And there is no schema for it to classify: the
package is five modules (`dates`, `logs`, `paths`, `rungs`, `surfaces`) and none
of them declares a field with a rung.

So the instrument P-3 asks about is not merely unwired — **there is not yet
anything for it to refuse.** The spec says as much in `homestead-rungs.md`:
*"Where does classification live? Schema-definition time, with a manifest and a
test that fails the build on an unclassified field. **Not written.**"*

Worth being exact about what that means for Phase 2's exit criterion, which reads
*"An unclassified field fails the build."* The refusal is implemented and heavily
tested; what does not exist is any schema definition that would invoke it at
import. The criterion is satisfied the way a lock on an empty room is satisfied.
That is not a defect — Phase 3 is *"registry and one matter pack"* — but a reader
should not take the green suite as evidence that a real schema has ever been
classified. None has.

### 2 · "Build failure" is not an instrument this module has

`classify_schema` raises `UnclassifiedField`. That is the whole mechanism.
Whether a raise is a *build* failure is a property of **when it is called**, and
nothing in the module enforces or even prefers import time:

- called from a schema definition at import → the process defining the schema
  dies → a build failure;
- called at runtime on a pack somebody just loaded → the same exception, in a
  caller that can catch it and say something.

**So the module already supports both answers, and neither is favoured.** P-3
reads as a choice between two instruments the code must choose between. It is
not: it is a choice about *who calls the one instrument, and when*, and that
lives entirely in a caller nobody has written. No change to `rungs.py` is implied
by either answer.

This matters for the shape of the eventual decision. "Fail the build" and "fail
the user" are not competing implementations to pick between — they are the same
function invoked from two places, and a product could do both, for different
inputs, with no contradiction.

### 3 · The user-authored pack is not in v1, and the clinic tier is deferred behind counsel

P-3's subject is *"a matter pack a **user** can add"*. Checked against
`safe-app-store/docs/homestead-law-build-plan.md`:

- **Phase 3** — *"registry and one matter pack … then custody only."*
- **Phase 5** — *"the other two packs. Bankruptcy and workers' comp."*

All three packs are authored by the project. **Nothing anywhere in the plan
describes an operator or a clinic authoring one**, and the clinic case is named
in *Deliberately not in v1*: *"No multi-client dimension. D2 (clinic)
reintroduces entitlement edges; Terpsi's model is the reference when it lands."*
`homestead-rungs.md` repeats it — *"Deferred; Terpsi's model is the reference"* —
and the build plan adds a gate that is not an engineering gate at all:
**"Counsel precedes any D2 deployment."**

So the product question P-3 says to decide now — *whether user-defined fields are
in scope* — has an answer on the record for the clinic half: **not in v1, and not
without counsel.** P-3 does not cite these, and reads as though the question were
undecided.

### 4 · The stated harm is partly closed, by decision 2, in the helpful direction

P-3's harm is that the runtime fallback *"means their new field silently shows
nothing with no explanation."* That silence is not a property of `classify_schema`
— it is the indicator question, which **was decided on 2026-08-05** (product
decision 2, `PHASE2-SURFACES.md`):

- on **ambient** surfaces, `serve_all` leaves no trace, and that is now the
  decided behaviour rather than an accident;
- on **the detail pane the operator deliberately opened**, the same disclosure is
  *fine* — *"by exactly the by-widget logic that settled the `L4` question on
  2026-08-04."*

So a field that failed classification does not have to be silent everywhere. In
the pane the operator opened, a Phase 4 caller may say what happened, and saying
so violates nothing already ratified. **The worst version of P-3's harm — the
user gets nothing, anywhere, with no explanation — is already avoidable under
rulings that exist.**

---

## What is actually left

Stripping the three answered premises, the residue is two things, and only one of
them is a decision.

**A build item, already on the plan.** The classification seam — a manifest, a
schema definition, and a test that fails the build — is Phase 3 work and is
listed as such. P-3 is a reason to make sure that seam is *called* from somewhere
at import, because a refusal with no caller is the lock on the empty room. Not a
product decision; a Phase 3 acceptance criterion, and worth writing into Phase 3
explicitly rather than leaving as an exit line from Phase 2.

**A decision, narrower than P-3's.** The clinic is deferred, but P-3 says *"a
user or clinic"* — and the household operator adding a field to their own matter
is **not** the clinic case and is not covered by the D2 deferral. Nothing on the
record says whether a single operator may extend a shipped pack. That is a real
open question, it is small, and it is the only genuinely undecided thing in P-3.

If the answer is no — packs are authored, the operator's records go in the fields
the pack defines — then P-3 closes entirely and the instrument question never
arises in v1.

If the answer is yes, then §2 says the module needs no change, and the decision
is about the caller: an operator-added field with no rung should be refused **at
the moment they add it**, in the pane where they added it, naming the field —
never accepted and then silently absent later. That is the same "loud on type"
asymmetry `rungs.py` already applies to a surface and a purpose, pointed at the
one input a person actually types.

---

## Options

**A — Record P-3 as answered by scope; open the narrow question in its place.**
Note in the corpus report that user-authored packs are not in v1 and that D2 is
deferred behind counsel, and file the one live residue: *may a household operator
extend a shipped pack?* Zero code, zero tests.
**Recommended.**

**B — Also write the Phase 3 acceptance criterion.** Add to the plan that Phase 3
does not exit until a real schema is classified at import and an unclassified
field in it fails the build — so the criterion is met by a lock on a room with
something in it. Zero code now; it constrains Phase 3.
**Recommended, alongside A.** The build plan lives in `safe-app-store`, so this
half is not this repo's to land.

**C — Decide the operator-extends-a-pack question now.**
Available, and cheap in code either way, because §2 shows the module is already
indifferent. But it is a product question about who this application is for, of
exactly the kind the last three briefs kept handing back — and unlike
`COMPELLED_DISCLOSURE` there is no ledger deadline making it urgent.
**Offered, not recommended, unless the operator already knows the answer.**

**D — Build the classification seam now.**
Out of scope; it is Phase 3 and Phase 3 has not started. Listed to be explicit
that P-3 is not a reason to pull it forward — nothing about the instrument
question gets easier by wiring it early, and §2 shows the choice is not in the
module anyway.
**Not recommended.**

## Recommendation

**A + B.** P-3 is not an open product decision so much as a well-aimed question
asked without the two documents that already answer most of it. What it correctly
identified — that a refusal available only to whoever runs the build is no
refusal at all for someone who cannot run one — stays true, and is worth keeping
as the reason the narrow question exists.

**Confirming what P-3 asked for:** the instrument is right for shipped schemas,
which is all v1 has. It is not wrong for anything else, because there is nothing
else yet, and because the module does not actually pick between build time and
runtime — the caller does.

## What is gated on which answer

- **A** — a paragraph in `phase2_corpus_report.md` marking P-3 answered-by-scope
  with the residue named. Under archive-don't-delete it is an annotation beneath
  the original, not a rewrite. Zero tests.
- **B** — a line in `homestead-law-build-plan.md` § Phase 3. **`safe-app-store`,
  not this repo.** Same trip as the 42 CFR Part 2 classification note already
  filed in `PHASE2-SURFACES.md`; they should travel together.
- **C** — needs whoever owns the product. Not startable by this hand, and not
  urgent.
- **Nothing is gated on P-3 for Phase 3 to begin.**

## What I did not do

- **Changed nothing.** This file is the only write.
- **Did not decide whether an operator may extend a pack** — that is C, and it is
  the one thing in P-3 that is genuinely undecided.
- **Did not touch `safe-app-store`.** Both the B line and the earlier Part 2 note
  live there and neither has been written.
- **Did not verify the D2 deferral is still current.** It is stated in two spec
  documents; if either has moved since, §3 moves with it.
- **Did not examine `Classified` or the runtime `L5` fallback for defects.** P-3
  is about the instrument, not the fallback, and the fallback's visibility was
  settled by decision 2.
