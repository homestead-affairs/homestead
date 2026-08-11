# Homestead · Health — module three (a plan, not a commitment)

Status: **A plan, not a commitment. Nothing here is built.** Where this document
decides rather than plans, the decision is **proposed for ratification**
(`verified_by ≠ author`, the `DECISION-cover-re-identification.md` posture).
Drafted 2026-08-11, prompted by the operator.

One thing for the record, since the prompt arrived wrapped in a rumor: nothing
in this module was ever waiting on a model-policy change. The restricted end of
biology is pathogen work; a household's shot card is not near it and never was.
The module was already named, in as many words, in the face doc — *"Later
modules, same shape: household records and renewals, maintenance history,
property, **family health records**. Each is a module; none is a new face."*
This plan is that sentence, worked.

---

## What it is

**Module three on Homestead · Affairs**, sibling to `homestead-law` and
`homestead-ledger`: the household's own health records, held by the household.
Who got which shot and when. What medication, at what dose, since when. Which
provider, and what is due next. A sibling repo — `homestead-health` — pinning
**`homestead.keep`** the way every module on the face pins it: the record
layer, the gate, the two logs, the deadline arithmetic. The module brings a
domain; it brings no second engine.

The two-level rule from the face doc governs the internal shape too:
**modules** are sibling repos on the org; **packs** live inside a module and
belong to a registry. Law's packs are kinds of legal matter (custody,
bankruptcy, workers' comp). Health's packs are kinds of health record —
immunizations, medications, conditions, allergies, providers, insurance — and
they belong to an enumeration held to I-23's discipline: one registry, packs
discovered on disk and cross-checked at import, a pack authored and left out a
build failure. Whether that enumeration *is* `keep.registry` or a sibling of it
is an open question at the end of this file; the discipline is not open.

## What it is not

Four exclusions, each with a reason, because every one of them is a thing this
module will be mistaken for:

1. **Not a new face.** The face doc already ruled: a module, sibling to law and
   ledger. Health overlaps every face the way "life" does, and the argument
   that killed `Life` as a face name kills `Health` as one too. It is a domain
   of a household's affairs — the part you handle yourself, which is this
   face's whole edge.

2. **Not the health-almanac.** `almanac-data/health-almanac` is face 3: a
   public catalog of public data — CDC WONDER, BRFSS, the WHO GHO — pointers,
   never bytes, maintained in the open. This module is the opposite object on
   every axis: private records, held locally, never published, never dialed
   for. The two touch at exactly one seam (H-5 below): reference data such as
   an immunization schedule is *public* data, so the catalog of where it lives
   is the almanac's job, and this module carries a **pinned snapshot** of what
   it needs — versioned, dated, updated only by an operator's act — and never
   resolves a link at runtime (I-17).

3. **Not the health fields inside legal matters.** `custody.diagnosis` and the
   workers' comp IME already have a home and a rung; they stay with their
   matters. A health datum that exists *because a legal matter needs it* is the
   matter's record, governed by the matter's pack. This module holds the
   household's health record *outside* any matter — and if a matter later needs
   a fact this module holds, that is a cross-reference travelling through the
   gate, never a copy. Two copies of a diagnosis with one rung each is BUG-6's
   drift with worse stakes.

4. **Not medical advice.** I-25 says the app never authors a fact and never
   applies law to facts; the health analog is load-bearing enough to be its own
   invariant (H-2). The module records what happened and surfaces what is due.
   It never recommends care, doses, interprets a result, or triages a symptom.
   The law module's standing line — *"no forms-and-instructions product, at any
   version"* — has an exact counterpart here: **no symptom-checker product, at
   any version.** Unauthorized practice is a bar with a medical spelling too.

---

## The premise that cracks here, named before it bites

The rung model's founding simplification: *"A household has one operator, no
relay, and no untrusted server. Those edges mostly collapse."* The question is
never *which person may see this*; it is *what crosses a boundary*. That
premise built five modules' worth of correct behavior, and health is the first
module where it meets a lawful exception, so the exception gets named here
rather than discovered later:

**Health records are per person, and the household has several.** The operator,
a spouse, children. For minors the operator is guardian and holds the file —
the premise holds. But minor-consent care exists: in this pack's jurisdiction
(US-CA), a minor of twelve or older may consent to certain care — and for that
care, the *parent is not entitled to the record*. That is an entitlement edge
**inside the household**, the exact structure the model said collapses, and no
rung expresses it: rungs score surfaces, not principals.

**The v1 answer is scope, not architecture.** The module holds what the
household lawfully holds: records the operator received as guardian, records
adults handed in about themselves. A minor-consent record is **out of scope**,
written down as such, and its absence is not rendered — by the *"a refusal is
information at the rung of the thing refused"* rule, a surface that said
"something about this child is withheld" would disclose the category it exists
to protect. The full answer is D2-adjacent (Terpsi's `guardian_of` edges are
the reference when it lands) and is this plan's largest open decision. What
this plan refuses to do is pretend the one-operator premise survives contact
with this domain unmodified, and then find out the way BUG-6 was found out.

**The subject dimension is new, and it touches the logs.** `keep`'s key is
`(matter, item_type, item_id)` — no person in it, because legal matters never
needed one. Health records need a subject, and the naive spelling —
`("health:mara", ...)` — puts a name in a key, and keys are exactly what the
logs carry (I-15: references, never content). A reference that *is* the datum
defeats the split. So: **subjects are opaque ids** (`subj-01`), the roster that
maps id → person is itself a classified record served through the gate, and a
log line about a subject carries the id and nothing else. That is H-1, and it
is the module's first real design obligation rather than an ornament.

---

## The packs

| Pack | What it holds | Phase | The work it brings |
|---|---|---|---|
| **immunizations** | doses received, next due | **v1 — the one pack** | deadlines, the first purposed egress, minors' data |
| medications | current and past, dose, since when | later | Part 2 rows (the L4/L5 procedure, not the regime shortcut) |
| conditions | diagnoses, onset, status | later | the highest-stakes rungs; nothing new structurally |
| allergies | reactions, severity | later | the emergency card (H-3), and the tension worked below |
| providers | who, where, relationship | later | specialty-as-category (the advisory matcher's shape) |
| insurance | carrier, plan, member ids | later | key material — member ids are `L5`, the SSN posture |

**v1 builds immunizations and nothing else** — *"one pack proves the seam;
three prove nothing that one does not"* is standing, and the later packs are
this module's Phase 5: inventing stubs for them now would be the hand-kept
phantom I-23 forbids. Immunizations is first on merit, not modesty: it is the
one pack that exercises **every seam the law packs proved, plus the new one**.
Real deadlines (`keep/dates`), a real egress with a legible purpose (the school
form — the rare health disclosure that is routine, expected, and bounded),
minors' data (`L4` work that is real, on the least dangerous content in the
domain), and the subject dimension end to end. If the seam is wrong,
immunizations finds out at the lowest stakes on the table.

## The immunizations pack, classified

The custody pack's shape exactly: a closed schema, every field a mapping
carrying `rung`, record type, jurisdiction, and the sentence that justifies the
rung against the five-step procedure — classified at **import**, so an authored
field with no rung stops the build naming itself (I-11). Rungs are declared,
never inferred from field names; these are the declarations this plan proposes,
and the pack file is where they become real.

| Field | Rung | Why (the five steps) |
|---|---|---|
| `subject` | `L3` | The opaque subject id. Resolves to a person — that is its purpose — with no category carried by the id itself (step 2 yes, step 3 no). It **is** the derived form of the person: what a log or a list row may carry where a name may not. |
| `vaccine` | `L4` | Names a medical act attached to a person (step 3): health is the first of `L4`'s familiar four. Uniform across vaccines on purpose — some names carry more than others (a travel vaccine says travel; HPV says age), and a per-vaccine ladder invites classifying by column name, which is the wrong that opened the rungs doc. Over-classifying fails closed, and the derived serving mode keeps it livable. |
| `dose_date` | `L2` | A date, naming nobody by itself (step 2 no). The *record* still composes to `L4` — I-12's `max` — so nothing renders a dose date beside a subject on an ambient surface; the declaration is per-field, the protection is per-record. |
| `next_due` | `L2` | Same posture as `dose_date`: a parsed `Deadline` (I-1), never a string. What Today renders is derived from the record and gated by I-31 — see the worked example below. |
| `provider` | `L3` | Names a business, not a person — but a care relationship resolves to the household (step 2), and a specialty-bearing name can carry the category in a proper noun: *a pediatric oncology clinic is a diagnosis wearing a business name.* Declared `L3`; content shaped hotter is the advisory matcher's case — argued **up**, never down. |
| `lot_number` | `L2` | Operational; carries no identity and no category. Kept at all because recalls are keyed on it. |
| `source` | `L3` | How this dose is known — the clinic card, a portal printout, the operator's memory (H-4). Provenance resolves to who was there (step 2), no category. |
| `notes` | `L4` | Free operator text, same decision and same residual as `custody.notes` — kept at `L4` **by that decision** (2026-08-10), the advisory matcher as the guard, synthetic-data-only until the residual closes. Not re-argued here; a second copy of that argument could drift from the first. |

No `ssn`, no member id, no insurance field in this pack — key material belongs
to the insurance pack when it exists, at `L5`, and importing one field of it
early would be exactly the two-homes drift exclusion 3 refuses.

> *Worked example — the Today line.* The record holds *"subj-02 · MMR · dose 2
> of 2 · due 2026-09-01."* A two-child household's Today renders **"2
> immunizations due this month."** A one-child household renders **nothing** —
> *"1 immunization due"* over one child names the child, which is I-31's k ≥ 2
> check biting at exactly the scale the cover decision said it would, and a
> dropped count is an absent key, never a rendered zero. Opening the queue
> (a deliberate act — the S1 detail posture) shows *"MMR · due Sep 1"* against
> the subject; the schedule reasoning behind it, if any, cites the pinned
> snapshot and its version date (H-5).

**Deadlines here are calendar days, and that is a check, not an assumption.**
`keep/dates` grew up on court time — `court_days`, FRCP roll-forward. A booster
interval does not skip weekends, and a health due date rolled forward by court
rules is BUG-1's cousin wearing a stethoscope. The bite below carries a *done
when* that a Saturday due date stays Saturday.

## The rung work that is health's own

**The emergency card — the one artifact whose purpose is to leave.** Allergies,
current medications, blood type: the point of the datum is that a stranger
reads it in the worst minute. The wrong answer is lowering the rung —
usefulness does not declassify any more than time does. The right answer is
already built: the card is an **export**. `serve(…, S4_EGRESS, purpose=…)`
through `keep/export`, one `IntegrityLog` entry and one `EXPORTED` act, both
references, head anchor off-tree — and the operator carries the paper. The
card's field set is **authored, never computed** (H-3): the operator chooses
what the card holds, field by field, and no code path assembles "everything
relevant" — a computed card is a query someone else effectively wrote, run at
the worst possible moment to be surprised.

**Turning eighteen.** *"A child turning eighteen changes who may hold the file,
not what the data is"* — the rungs doc already ruled, and this module is where
the ruling gets a mechanism: **export-and-handoff**. A purposed S4 export of
the subject's record, ledgered like any other, handed to the person it is
about. Never a deletion — I-36 has no write path to lose, and the module adds
none. What remains behind remains the household's own record of what it did as
guardian, at the rungs it always had.

**Part 2, when medications lands.** Substance-use treatment rows get the
procedure, not the regime: step 3 puts them at `L4` by category, step 4 asks
about sealing orders case by case, and the generalisation *"Part 2 material is
`L5`"* stays refuted where `DECISION-redisclosure.md` left it. Recorded now
because the medications pack is exactly where someone will re-derive the
shortcut.

---

## The module invariants, proposed

Numbered `H-1…` and module-local; whether any joins the face's `I-*` ledger is
ratification's call, not this file's. Each is written to be a test.

| | | Traceable to |
|---|---|---|
| **H-1** | **A subject is opaque everywhere but the roster and the detail pane.** Keys, log lines, list rows, and derived text carry the subject id; the roster mapping id → person is itself a classified record served through the gate. A name is never a key, and a log carrying a reference never thereby carries a name. | I-15, the subject dimension |
| **H-2** | **The app never advises care.** It records acts and surfaces due dates; it does not recommend, dose, interpret, or triage. No symptom-checker product, at any version. Structural where possible (no code path composes a recommendation), tested at the surfaces regardless. | I-25's analog |
| **H-3** | **The emergency card is authored, not computed.** A closed, operator-chosen field set; no path auto-includes by relevance. Adding a field to the card is an act on the card's own record. | I-13, F-4's lesson |
| **H-4** | **A dose is a fact with a source.** Every dose records how it is known — card, printout, memory — and *memory renders as memory*. An undated or unsourced dose is a recorded gap (I-8), never dropped, never silently promoted to certainty. | I-24's analog, BUG-10 |
| **H-5** | **Reference data is pinned, never fetched.** The immunization schedule ships as a versioned snapshot showing its own date; updating it is an operator's act, ledgered like one. The module never dials — I-17 has no health exception, and the catalog of where public health data lives is the almanac's job, not this repo's. | I-17, I-26, the face-3 seam |

## The bites, in order

Each independently landable, each with a check rather than a claim. The order
wires the gate and the subject discipline **before** there is much to render —
the law module's order, kept because it worked.

### 1 · The seat — a module that pins the engine

Scaffold `homestead-health`: pyproject pinning `homestead.keep`, import-pure,
no network module at import, bare `pytest -q` from a cold checkout. The
module's `UNBUILT` file starts full: H-1 through H-5 land as
`xfail(strict=True)` the day the repo exists, so a quiet implementation
promotes a test rather than escaping one.

*Done when:* cold clone, `pip install -e .`, suite green; grepping the package
for network imports, `expanduser`, and a second path resolver all come back
empty (I-19/I-20/I-26/I-27/I-28).

### 2 · The roster — subjects before records

Opaque ids, the id → person mapping stored through `keep/record` like anything
else, roster names declared `L4` where the subject is a minor. This is H-1's
bite, and it comes before any health datum exists because every later record
references it.

*Done when:* a subject survives a restart; a log line about a subject carries
the id and nothing else, held by a test that greps the rendered log the way the
chokepoint test greps the surface layer.

### 3 · The pack — `classify_schema` on health's first schema

The immunizations schema above, classified at import, in the custody pack's
exact shape.

*Done when:* the pack imports, and deleting one field's rung fails the build
with that field named (I-11) — the custody check, on the second real schema.

### 4 · Due onto Today — calendar days and k ≥ 2

`next_due` through `keep/dates` on calendar arithmetic; the derived line
through the cover's re-identification gate.

*Done when:* a Saturday due date stays Saturday; a one-child household renders
no count while a two-child household renders "2 due" (I-31, both directions).

### 5 · The school form — health's first purposed egress

Export one subject's immunization history: `serve(…, S4_EGRESS, purpose=…)`,
`keep/export` writing both logs, references only, head anchor off-tree.

*Done when:* the export file exists and reads correctly; both log entries carry
references and no content (I-15); `verify(expected_head)` catches a
hand-edited entry.

---

## What this plan deliberately does not include

- **The five later packs.** The second pack proves the seam only after the
  first has landed; before that it proves nothing and can still drift.
- **Portal import, FHIR, wearables.** Every one of them dials, and portal
  credentials are key material the module has no business holding. If import
  ever lands it is file-shaped, offline, and walks through the same gate.
- **Minor-consent records.** Out of scope by the section above, and the
  absence is not rendered. The open decision is named below, not smuggled.
- **The clinic / D2 case.** A household is not a practice; Terpsi's
  entitlement model is the reference when that question is real.
- **Anything that advises care.** H-2 is an invariant, not a roadmap item.

## Open

- **The minor-consent decision.** Scope rule now; architecture later. The
  moment it is revisited, Terpsi's `guardian_of` edges are the prior art, and
  the answer must survive the *"refusal is information"* rule.
- **Whose registry.** Health record types held to I-23's discipline — but in
  `keep.registry` (which enumerates *matters*), or a sibling enumeration inside
  the module? Leaning module-local: a health record type is not a matter, and
  overloading the matter enumeration to avoid a second registry trades a
  category error for a convenience. Ratification's call.
- **The snapshot's chain of custody.** H-5 pins the schedule; *updating* the
  pin is an operator act with a date — but from what source, verified how, and
  is the almanac entry (face 3) the named source of record? The seam exists;
  its ceremony is unwritten.
- **Adult subjects who are not the operator.** A spouse's records, entered by
  the operator: the household holds them today on consent that is real but
  unrecorded. Whether consent becomes a recorded act (it is one, in Part 2's
  world) is open.

## What I did not do

- **Built none of it.** This file is the only write.
- **Did not create the `homestead-health` repo**, nor its packs, nor a stub in
  this repo's registry — a matter name with no pack behind it is the phantom
  I-23 forbids, and a *module* stub would be the same phantom one level up.
- **Did not decide minor-consent.** Scoped it out and named it.
- **Did not touch `homestead.keep`.** The calendar-day check in bite 4 may
  surface work there; the bite finds out, this file does not presume it.

## Related

- `safe-app-store/docs/homestead-affairs-face.md` — the face; the sentence this plan works
- `safe-app-store/docs/homestead-rungs.md` — the ladder, the surfaces, the procedure
- `docs/PLAN-first-runnable.md` — the bite discipline this plan copies
- `docs/DECISION-cover-re-identification.md` — k ≥ 2, which bites hardest here
- `docs/DECISION-redisclosure.md` — the Part 2 procedure the medications pack will need
- `homestead/packs/custody.py` — the pack shape, field for field
