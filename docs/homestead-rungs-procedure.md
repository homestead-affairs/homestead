# The rungs procedure — reconstructed

> **RECONSTRUCTED 2026-09-11 from the pack rationales and decision docs in this
> repo; the authoritative text is `docs/homestead-rungs.md` in the
> safe-app-store, not available in this tree. Where a sentence is inferred it
> is marked (reconstructed).**

This document rebuilds, from evidence actually present in `homestead-affairs`,
the sensitivity-ladder model that `homestead/keep/rungs.py` and
`homestead/keep/surfaces.py` implement and repeatedly point back to. Neither
module carries the model's prose — both say in so many words that the prose
lives in `docs/homestead-rungs.md` "in the safe-app-store" (`rungs.py:3-6`,
`surfaces.py:3-5`), a repo this build does not have. What follows is
reconstructed from:

* `homestead/keep/rungs.py` — the `Rung` enum's inline comments (`:145-150`),
  the module docstring's I-11/I-12/I-13/I-14 section (`:1-38`), the `Purpose`
  closed-set docstring and its S4-only lift (`:41-64`, `:156-246`), the
  `_CEILING` table and its validating `_check_crossing()` (`:531-592`), and
  `classify_schema`'s own account of the five-step procedure and what it
  cannot check (`:862-966`).
* `homestead/packs/custody.py` and `homestead/packs/bankruptcy.py` — every
  field's `why` string, which is the two packs' worked application of the
  five-step procedure to real fields, cited "step 1" … "step 5" throughout.
* `docs/PHASE2-SURFACES.md`, `docs/DECISION-cover-re-identification.md`,
  `docs/DECISION-unclassified-field-instrument.md`,
  `docs/DECISION-advisory-matcher.md`, `docs/DECISION-compelled-disclosure.md`,
  `docs/DECISION-redisclosure.md`, `docs/household_safety.md` (the F-findings
  that motivate several rung choices), and `tests/test_invariants_pending.py`
  (which modules are unbuilt and which invariants are still pending).
* `README.md`'s "What is enforced here today" table (I-19/I-20, I-22/I-15,
  I-30/I-26, I-14, I-27/I-28).
* The sibling modules' own docs, read-only: `/home/user/homestead-law/README.md`
  and `/home/user/homestead-ledger/docs/build-plan.md` — the latter is the
  source of the money table in § 6.

Nothing below overrides code. Where this document and `rungs.py` disagree, the
code is the not-yet-adjudicated ground truth and this document is wrong.

---

## 1 · The ladder, L1 → L5

Verbatim from `homestead/keep/rungs.py:145-150` (the `Rung` enum's own inline
comments — these are not paraphrased):

| Rung | One-line definition |
|---|---|
| `L1` | public in this matter's forum |
| `L2` | household — no identity, no protected category |
| `L3` | attributed — names or resolves to a person |
| `L4` | protected — identifies **and** carries a category the law follows |
| `L5` | sealed — never served on any surface |

Higher is more restricted (`rungs.py:3`). Two properties are structural rather
than incidental (`rungs.py:14-33`):

* **I-14 — a rung is a string, never an integer.** `L3`, not `3`. Trust runs
  the *other* direction elsewhere in the stack (ascending privilege), so a
  bare `>=` comparison is right on one scale and silently wrong on the other.
* **I-12 — composition is `max`, everywhere.** A record is the `max` of its
  fields; a projection never lowers a rung. `compose()` (`rungs.py:381ff`) is
  the function this cashes out as.
* **I-11 — absence fails closed, twice.** `compose()` of nothing is `L5`.
  `classify_schema()` refuses an unclassified field at schema-definition time
  — a build failure. A value that reaches `may_render()`/`decide()` with an
  unreadable rung reads `L5` and is not served. A classifier that errors
  denies; it never defaults to `L1`.
* **I-13 — `L5` has no override anywhere, and `L4` never reaches a prompt.**
  Both are checked at import (`_check_crossing`, `rungs.py:540-592`) rather
  than trusted as conditionals someone remembers to write.

## 2 · The five-step classification procedure

`classify_schema`'s own docstring (`rungs.py:895-902`) and its refusal message
(`rungs.py:961-965`) state the procedure directly, and both packs' `why`
strings apply it field by field, citing the step number inline. Reassembled
here as five steps (step numbering per the packs; this doc's prose around each
step is (reconstructed) except where quoted):

**Step 1 — is it public in this matter's forum?** → `L1`. A court's identity,
a hearing date posted on the calendar, a docket number that's public through
PACER — all `L1` because the *forum*, not the content, is public. Both packs
cite this explicitly: `custody.py:51-61` (`courthouse`, `hearing_date`) and
`bankruptcy.py:32-64` (`courthouse`, `filing_date`, `case_number`, `chapter`,
`trustee`, `creditor_meeting_date`, `discharge_date` — an entire matter's
`L1` set, all "step 1").

**Step 2 — does it resolve to a person?** → at least `L3`. Naming a co-parent
(`custody.py:75-79`, "step 2 yes, step 3 no") or a debtor's income
(`bankruptcy.py:78-83`, "step 2 yes, step 3 no") resolves to a person without
(yet) carrying a protected category, and lands at `L3`.

An **aggregate** does not inherit `L3` from its ingredients automatically —
and it does not become `L2` for free either. `compose` is `max` (I-12), so an
aggregate starts at the `max` of what it aggregates; it is demoted to `L2`
only *after* a re-identification check confirms it cannot be resolved to a
person or to a single matter. `homestead/app/cover.py:11-15` names this
directly as "step 2a of the classification procedure": *"`L2` is not a
property a count is born with: an aggregate inherits the `max` of its inputs
and becomes `L2` only after a check that it cannot be resolved to a person or
a single matter."* `docs/DECISION-cover-re-identification.md` specifies that
check as two independent gates, both required, `K = 2`:

* **Gate 1 — k ≥ 2 on the count itself.** A count of `1` is one item, and one
  item lives in exactly one matter — `overdue=1` resolves to that matter the
  instant it is read, regardless of how many matters exist.
* **Gate 2 — k ≥ 2 on the matters.** With one open matter, the household *is*
  that matter, so every count is a fact about it, no matter its size.

A count that fails either gate is **absent**, never rendered as `0` — a
dropped `0` still says "this matter has none," which is a fact about the
matter (the cover decision's "absence, not zero," citing F-1's reader-over-
the-shoulder). A survivor renders as its real number, not a band — the check
is about *whether* a number may cross, not about softening one that may.
`docs/DECISION-cover-re-identification.md` is explicit about the boundary:
the gates certify a number does not *force* one matter; they do not certify
it is *actually* spread across ≥2 (the surface isn't handed the distribution),
and a later stronger guarantee (E4-cover-distribution in the build-out plan,
provisional) would need the per-matter distribution passed in.

**Step 3 — does it carry a category the law follows?** → `L4`. `classify_schema`'s
refusal message states this as "a category the law follows → L4"
(`rungs.py:962-963`). The categories this tree evidences by name, each with a
citation:

* **minor** — `custody.py:80-84`: "names a person who is a minor. A minor is a
  category the law follows (step 3 yes)."
* **medical** — `custody.py:94-98` (`diagnosis`): "a medical category attached
  to a person (step 3). 'Medical' belongs to the rung..."
* **substance use** — `custody.py:99-115` (`notes`) names "substance use" among
  the categories a free-text note routinely carries, and
  `docs/DECISION-redisclosure.md:140-143` quotes the (unavailable)
  `homestead-rungs.md` itself (at that document's own `:108`–`:112`) naming
  "substance-use records (42 CFR Part 2)" as an `L4` category by definition.
* **financial / money** — the same quoted passage
  (`docs/DECISION-redisclosure.md:140-143`) gives: "Health, money, discipline,
  likeness are the familiar four"; the ledger's own money table (§ 6) makes
  `amount` `L4` for the same reason.
* **immigration** — named in the same quoted passage
  (`docs/DECISION-redisclosure.md:140-143`).

**(reconstructed, unconfirmed in this tree)** — the plan that commissioned
this document also lists **religion**, **union** (membership), and
**criminal** (history) as step-3 categories. This tree has **zero** hits for
any of those three terms anywhere under `homestead/` or `docs/`. The nearest
verified text — the quoted `homestead-rungs.md` passage above — instead names
"discipline," "likeness," and "privileged communications" alongside health,
money, minors, substance-use and immigration. Whether religion/union/criminal
are additional categories the real document lists elsewhere, or a
misremembering in the plan, cannot be settled from this tree. Treat the
religion/union/criminal trio as **unverified** until `homestead-rungs.md` is
read directly.

**Step 4 — key material, a refusal, privilege, or a sealing order?** → `L5`,
and `L5` has no override anywhere (I-13). `classify_schema`'s refusal message
gives this as a four-clause test, quoted directly (`rungs.py:963-965`):
*"would rendering reveal a refusal, expose privileged strategy, disclose key
material or breach a sealing order → L5."* Both packs' `ssn` field cites this
verbatim as "step 4": `custody.py:117-121`, `bankruptcy.py:96-101` — "key
material — sealed, and L5 has no override anywhere (step 4)."

Step 3 and step 4 are sequenced, not merged: a field can pass step 2 or 3 and
still not clear step 4. Both packs say this explicitly of `case_number`: "step
2, then step 4 does not raise it" (`custody.py:62-68`, `bankruptcy.py:72-77`
for `creditors`) — resolving to a person, or carrying financial content, does
not by itself reach `L5` unless one of the four step-4 clauses is also true.

**Step 5 — record the matter and the jurisdiction alongside the rung.** The
*same field name* takes a different rung depending on the matter it is filed
in, and neither the matter nor the rung is derivable from the field's name
alone (`rungs.py:895-899`, `rungs.py:826-827`). The canonical example, cited
by both packs against each other:

* `bankruptcy.py:41-45` — `case_number` is **`L1`**: "the docket number —
  public through PACER in a bankruptcy (step 1). This is the model's worked
  example: L1 here, L3 in a family matter where records are commonly sealed."
* `custody.py:62-68` — `case_number` is **`L3`**: "resolves to the parties, no
  protected category. The model's worked example: L1 in a bankruptcy where
  the docket is public, L3 in a family matter where records are commonly
  sealed (step 2, then step 4 does not raise it)."

Both packs' `_field()` helper (`custody.py:42-43`, `bankruptcy.py:27-28`)
bakes `matter` and `jurisdiction` into every declaration precisely so step 5's
answer travels with the rung rather than living only in a reviewer's head.
`classify_schema` itself does **not** check that step 5 was applied
correctly — it "checks that a rung was declared, not that it was declared
well" (`rungs.py:109-112`, `custody.py:24-28`) — which is why the registry
(I-23, "Phase 3" per the module) is named as the thing that will eventually
hold a matter to its own declared fields.

## 3 · The crossing table — surfaces × ceilings

`homestead/keep/surfaces.py` defines five surface members over four "S"
groups (`surfaces.py:69-86`); `homestead/keep/rungs.py`'s `_CEILING` gives each
surface two ceilings — the highest rung whose **payload** renders with no
purpose declared, and the highest with one declared (`rungs.py:497-500,
531-537`):

| Surface | What it is | Ceiling, no purpose | Ceiling, purpose declared |
|---|---|---|---|
| `S1_LIST` | the operator's own screen, list pane — ambient | `L3` | `L3` (no lift) |
| `S1_DETAIL` | the operator's own screen, detail pane — opened deliberately | `L4` | `L4` (no lift; opening the pane *is* the declaration) |
| `S2_PROMPT` | a local model's context window | `L2` | `L2` (no lift) |
| `S3_AGENT` | agent retrieval over MCP stdio, never a listening port (I-30) | `L2` | `L2` (no lift) |
| `S4_EGRESS` | egress — drafts, exports, filings, manifests; the only surface that leaves the machine | `L2` | `L4` |

**A purpose lifts on `S4` and nowhere else.** This is stated directly:
*"S3's column was closed on 2026-08-05 ... A purpose lifts on S4 alone"*
(`rungs.py:50-56`), and the `_CEILING` comment repeats it per row
(`rungs.py:502-530`): S1 list, S1 detail, S2 and S3 all show the same ceiling
in both columns; only `S4_EGRESS` moves, from `L2` to `L4`. `_check_crossing()`
(`rungs.py:540-592`) enforces four properties of this table at import, so a
future surface cannot silently violate them:

1. every `Surface` member has a `_CEILING` entry (no BUG-6-shaped gap);
2. every ceiling is a `Rung`, never a bare integer (I-14);
3. **no ceiling is ever `L5`** — I-13, structurally, not by convention;
4. a purpose-declared ceiling never sits *below* the plain one;
5. an **ambient** surface (`S1_LIST`) may never carry an `L4`+ ceiling in
   either column — I-35, because the ambient path (a list row) "has nothing
   to put" an `L4` payload in.

`L5` is refused on every surface not because five rows say "never," but
because no ceiling in the table is `L5` — a threshold comparison makes the
refusal universal by arithmetic (`rungs.py:78-83`).

**Purpose is a closed, per-call set** (`Purpose`, `rungs.py:156-246`): **seven**
members today — `DRAFTING`, `FILING`, `COMPELLED_DISCLOSURE`, `EXPORT`,
`SUBJECT_ACCESS`, `REDISCLOSURE`, `ANSWERING` (`rungs.py:240-246`) — none ranked
against another, each spent on the one call that declares it and forgotten on
the next (`rungs.py:617-619`, "per-call, never per-session").
`docs/DECISION-compelled-disclosure.md`'s status line says
`COMPELLED_DISCLOSURE` is *"Ratified and done, 2026-08-05"* — it was added,
`FILING`'s gloss was narrowed to *voluntarily*, and the suite moved from
1621/6 xfailed to 1704/6 with no test rewritten by hand, purely from sweeps
picking the new member up. **This is a live docstring/code drift, worth
flagging on its own terms:** the `Purpose` class docstring still reads
*"these six are acts"* (`rungs.py:186`) and *"the set still has no member for
a compelled disclosure"* (`rungs.py:228-233`) — both now false against the
seven-member enum sitting directly beneath that same docstring. The decision
doc itself predicts this exact failure mode (*"a title asserting a number
goes false every time the thing it guards legitimately changes"*), and the
class docstring is an instance of it that nothing caught because a docstring
is not an assertion. `docs/DECISION-redisclosure.md` is the other ratified
adjustment to this set: `REDISCLOSURE`'s gloss was narrowed to stop implying
it is scoped to 42 CFR Part 2 specifically. The plan's E1-purpose-sync bite
adds an **eighth** member, `Purpose.SYNC`, and is explicitly scoped to update
"the count-named pins" the same way this ratification did — i.e., to not
repeat the stale-docstring/stale-title failure this section just found.

## 4 · The derived-form rule

An `L3` or `L4` field must carry a **derived sentence** — a true statement
that stands in for the payload wherever the payload itself may not render.
`Classified.__post_init__` (`rungs.py:694-706`) enforces this mechanically:
`derived` is *required* for every rung in `_NEEDS_DERIVED`, which
`_check_crossing()` computes as everything strictly between the lowest ceiling
any surface has and `L5` (`rungs.py:585-592`) — today that computes to `{L3,
L4}`. A rung needing a derived form and not carrying one is a build failure
(`rungs.py:702-706`), citing BUG-5 by name: *"a withheld payload with nothing
in its place is the screen saying 'Excluded from drafting' over a packet that
still contains the fact."*

**What "derived" means in practice, from the packs' own worked examples**
(reconstructed synthesis of `rungs.py:664-678` and the pack `why` strings): a
derived sentence restates neither

* **the value itself** — `custody.py:85-93`'s `parenting_time` (`L3`) is not
  rendered to a model prompt as the schedule; the doc's own worked example,
  quoted in the field's `why`, is *"a recurring parenting-time obligation on
  Tue/Thu"* — a shape, not the schedule;
* **a name** — `diagnosis` and `notes` (`L4`, `custody.py:94-115`) never reach
  a prompt or an agent; their derived forms say a category exists ("a
  substance-use treatment record exists in this matter," quoted at
  `docs/DECISION-redisclosure.md:95`) without naming who;
* **a date** — no worked derived form in this tree includes a date; the
  parenting-time example replaces a specific schedule with a recurrence shape;
* **nor a magnitude** — the derived form for a financial field states that an
  obligation or category exists, not its amount.

`Classified.__post_init__` checks only that a derived string is present and
non-blank (`rungs.py:702-704`); it explicitly does **not** check that the
sentence is *safe* — *"nothing here can tell whether 'a recurring
parenting-time obligation on Tue/Thu' leaks less than the schedule it
replaces — that is the re-identification judgement the spec puts on a human at
classification time"* (`rungs.py:674-678`). The stronger, mechanical version of
this rule — every `L3`/`L4` field's derived form contains no digits — is a
**planned** test (the build-out plan's E1-pack-contract bite), not a check
this tree enforces today. This document states the rule the packs already
follow by hand; it does not claim the rule is machine-checked yet.

## 5 · The advisory content matcher — argues a rung up, never down

`docs/DECISION-advisory-matcher.md` documents `keep/advise.py` (built,
tested), which closes part of the gap classify_schema leaves: it cannot know
a field is declared *well*, only that it is declared. `advise(declared,
content)` flags content shaped for a higher rung than its field's declared
rung — nine anchored, PII-tested patterns (`ssn`→`L5`; `credit_card`, `dob`,
`bank`→`L4`; `phone`, `email`, `ein`→`L3`) — and:

1. may only argue a rung **up**, never down (uses `compose`, so it cannot
   disagree with the gate about which is higher);
2. is advisory, never a gate (`put()` never consults it);
3. its silence is never a clean bill (no `is_clean`, no boolean verdict).

It is the guard `custody.py:106-114` leans on for keeping `notes` at `L4`
rather than `L5`, against an earlier audit that argued for `L5`
(`docs/audits/bites-1-3-remediation.md`).

## 6 · The money table (ledger)

Read-only from `/home/user/homestead-ledger/docs/build-plan.md:55` ("Settled
decisions," item 5), which states the ledger's rungs as settled in its bite 1:

| Field | Rung | Why |
|---|---|---|
| `amount` | `L4` | a money category — step 3 |
| `account_number` (and SSN) | `L5` | key material — step 4 |
| `date` (posting date) | `L2` | household activity, *not* a public record the way a court date is — explicitly **not** `L1` |
| `description` / `payee` | `L3` | resolves to a party — step 2 |

The same source states these are "declared at schema-definition time;
unclassified fails the build" — the same I-11 build-failure discipline as the
law packs, applied to money fields. `/home/user/homestead-law/README.md:79`
independently confirms the general rule this table is an instance of: *"I-11
— absence fails closed to L5 at the storage boundary. A row whose rung is
missing, unreadable, or whose payload will not decode reads L5 on the way
out — never L1."*

Note the contrast with the law packs' `case_number` (step 5, § 2 above): a
transaction's `date` is `L2` specifically *because* a household ledger entry
is not the public-forum fact a court date is — the same "resolves to
household activity, not the forum" reasoning that puts `courthouse` and
`hearing_date` at `L1` in custody does the opposite work here, landing
ordinary dates at `L2` rather than `L1`.

## 7 · Invariants I-1 … I-36, one line each

Each tagged with its source. "(reconstructed)" marks a one-liner synthesized
from surrounding text rather than quoted from a single named line.

| # | One-line meaning | Source |
|---|---|---|
| I-1 | One `Deadline` type, parsed once, at the edge — nothing downstream re-parses a date string. | `homestead/keep/dates.py:7-9` |
| I-2 | Parse strictly or refuse — every date pattern is anchored to the whole string, no `[:10]` slice. | `homestead/keep/dates.py:11-16` |
| I-3 | One source for every derived fact — `overdue` and `days_until` cannot disagree because there is only one of them. | `homestead/keep/dates.py:18-22` |
| I-4 | FRCP 6(a) counting rules; an unknown jurisdiction is refused, never silently treated as federal. | `tests/test_dates_corpus.py:593-594, 784-787` |
| I-5 | No free text for a date/snooze — an unreadable date is a visible refusal, never a guess or a silent `None`. | `homestead/keep/dates.py:24-28` |
| I-6 | The canonical record is read-only, enforced by type (`Canonical` has no write/update/delete). | `homestead/keep/record.py:13-19` |
| I-7 | One key derivation — `key(matter, item_type, item_id)` is the only place those three become a path. | `homestead/keep/record.py:21-24` |
| I-8 | An unparseable or sealed deadline becomes a recorded gap, never dropped or defaulted. | `homestead/keep/store.py:93-95, 325` |
| I-9 | Writes never silently overwrite — `put()` refuses an occupied key or reports what it replaced. | `homestead/keep/record.py:26-27` |
| I-10 | **Unknown in this tree.** Zero references anywhere under `homestead/` or `docs/`. | — |
| I-11 | Absence fails closed, twice: an unclassified field is a build failure; an unreadable rung reads `L5` at runtime. | `homestead/keep/rungs.py:24-29`, `classify_schema` (`:862-966`) |
| I-12 | Composition is `max`, everywhere — a projection never lowers a rung. | `homestead/keep/rungs.py:19-23` |
| I-13 | `L5` has no override anywhere; `L4` never reaches a prompt. Checked at import, not trusted as a conditional. | `homestead/keep/rungs.py:30-33`, `_check_crossing` (`:540-592`) |
| I-14 | A rung is a string, never an integer — `L3`, not `3`. | `homestead/keep/rungs.py:14-17, 145-150` |
| I-15 | References, never content, in logs and errors — an advisory or log names a field, never echoes an L3+ value. | `homestead/keep/advise.py` (per `docs/DECISION-advisory-matcher.md`), `README.md`'s I-22/I-15 row |
| I-16 | One chokepoint — a payload may be reached only by the gate and the store; any other reach is a build failure, enforced by AST scan. | `homestead/keep/rungs.py:95-104`, `tests/test_invariants_chokepoint.py` |
| I-17 | No network egress by default — `send()` refuses unless a per-call act is shown exactly what will go. | `homestead/keep/egress.py:1-16` |
| I-18 | Any pattern that could match PII is anchored and tested against PII negatives (F-3's lesson — an address must not wear a citation's shape). | `homestead/keep/patterns.py:1-16` |
| I-19 | One path resolver — only `keep/paths.py` may reach a home directory. | `homestead/keep/paths.py:8-15` |
| I-20 | `expanduser()` is banned outright — it is invisible to the vault-leak linter under that spelling. | `homestead/keep/paths.py:16-20` |
| I-21 | A fresh window rests on the cover — the record is not drawn before a human asks. | `homestead/app/window.py:4, 79` |
| I-22 | Two logs (`VisibleLog`, `IntegrityLog`) and a writer for them — closed `Event` enum, no free-text parameter. | `README.md`'s I-22/I-15 row; `homestead/keep/nestor_seam.py:16` |
| I-23 | The registry is the only enumeration — a matter pack that exists but is unregistered is a build failure (BUG-6's fix). | `homestead/keep/registry.py:1-20` |
| I-24 | (reconstructed) A dose/fact must record how it is known and stay traceable to its source — named only as an "analog" in the health plan, not defined standalone in this tree. | `docs/PLAN-homestead-health.md:229` ("I-24's analog, BUG-10") |
| I-25 | The app never authors a fact and never applies law to facts — no advice, no recommendation, structural where possible. | `docs/PLAN-homestead-health.md:76-77, 227` |
| I-26 | Nothing here imports the network — the core has no networking dependency, checked by scan. | `homestead/keep/nestor_seam.py:59`, `homestead/keep/store.py:6` |
| I-27 | Declared dependencies are true, and reads only `dependencies` (not extras) — an optional-extra import must be lazy. | `homestead/keep/nestor_seam.py:237`, `README.md`'s I-27/I-28 row |
| I-28 | Bare `pytest -q` works from a cold checkout — no out-of-band install step. | `README.md`'s I-27/I-28 row; `tests/test_invariants_shape.py:1` |
| I-29 | The surface holds no domain logic — it calculates nothing itself, only asks `serve`. | `homestead/app/__init__.py:1`, `homestead/app/window.py:9` |
| I-30 | Nothing here listens — no bound port anywhere, including the MCP stdio surface. | `homestead/keep/export.py:8`, `homestead/keep/nestor_seam.py:59` |
| I-31 | The cover's resting state reveals nothing — a count is shown only after it clears the k≥2 re-identification check on both the count and the matters. | `homestead/app/cover.py:1-15`, `docs/DECISION-cover-re-identification.md` |
| I-32 | A reveal, once shown, expires back to derived after a timeout — pending, not yet built. | `homestead/app/window.py:23`, `tests/test_surfaces_corpus.py:410` |
| I-33 | One rung indicator per pane — a list row shows one indicator, not the rung of every field composited into it. | `homestead/app/theme.py:28, 64` |
| I-34 | **Unknown in this tree.** Zero references anywhere under `homestead/` or `docs/`. | — |
| I-35 | An ambient surface (the list pane) can never carry an `L4`+ ceiling — it has nowhere to put a withheld payload's stand-in. | `homestead/keep/rungs.py:503, 577-583` |
| I-36 | The canonical record must never be auto-purged — that is destroying evidence on a schedule. | `homestead/keep/paths.py:53`, `homestead/keep/record.py:13` |

**I-10 and I-34 are not referenced anywhere in this tree.** A repo-wide grep
for `I-10` and `I-34` (word-bounded, across every `.py` and `.md` file) returns
zero hits, in contrast to every other number 1–36, each of which has at least
two independent hits. Both are left as **unknown in this tree** rather than
guessed at; whoever holds `docs/homestead-law-build-plan.md` (the plan the
build-out references as holding "the 36 invariants and the phase order," per
`README.md`'s Design section) can fill them in.

**I-24 and I-25** are a weaker case than I-10/I-34 but short of the others:
both are *named* (in `docs/PLAN-homestead-health.md` only), each cited once as
the thing a health-module invariant (`H-2`, `H-4`) is "the analog of," but
neither is defined standalone anywhere in this tree the way I-1…I-23 and
I-26…I-36 are. The one-liners above for I-24/I-25 are reconstructed from what
their *analogs* say, not from a direct definition of I-24/I-25 themselves.

## 8 · Provisional invariants I-37 … I-45 — reserved for the build-out

Per the build-out plan's decision 10 ("Provisional invariant numbers I-37…I-45
are ratified by audit; the reconstruction doc says so") — this section is that
notice. None of these exist in code yet; they are reserved numbers with
provisional one-line meanings, copied from the plan that reserves them, and
are **not ratified**. An auditor ratifies each as its bite lands.

| # | Provisional one-liner | Landing bite (per the plan) |
|---|---|---|
| I-37 | A refused sync confirmation ledgers nothing — sync is an operator act, never background. | E1-pending (seeded); E4-sync-core (built) |
| I-38 | A sync envelope is ledgered exactly once, and only as references — never content. | E1-pending (seeded); E4-sync-core (built) |
| I-39 | Fleet ingest never listens, and its optional Postgres dependency (`psycopg`) is lazy-imported. | E1-pending (seeded); E4-postgres-fleet (built) |
| I-40 | An unnamed or empty sync scope syncs nothing — `SyncScope` refuses empty or `L5`. | E1-pending (seeded); E4-sync-core (built) |
| I-41 | **Reserved — no provisional meaning assigned in the plan.** | unassigned |
| I-42 | Jurisdiction is a per-instance `L1` fact; deadline arithmetic reads it through the gate and refuses when absent. | L2b-instances |
| I-43 | The per-transaction `account_number` record is no longer written once account instances exist; the fingerprint carries the number only inside the store's allowed boundary. | G2b-account-instances |
| I-44 | No `Purpose.DRAFTING`/`FILING` anywhere in the law or ledger packages — this face models, and does not draft or file (AST guard). | L3-bankruptcy-ch13, G4-schedules-export |
| I-45 | **Reserved — no provisional meaning assigned in the plan.** | unassigned |

## 9 · What this reconstruction cannot vouch for

* **Two fields' `why` strings were completed, not merely read, while writing
  this document.** `tests/test_rungs_procedure.py::test_every_pack_field_why_names_a_step`
  checks that every field's `why` cites a step, and two custody fields
  (`docket`, `notes`) did not, before this bite, in the tree this document
  reconstructs from — a real, small, pre-existing gap, not a defect in the
  test. Each `why` gained a one-clause step citation making an already-true
  classification explicit (`docket` was already `L3` for the same reason
  `case_number` is; `notes` was already `L4` for the reason `diagnosis` is);
  neither field's `rung` value changed. This is disclosed here because a
  reconstruction that quietly patches its own sources to make its claims true
  would be worse than one that says so.
* **It is not `docs/homestead-rungs.md`.** Every quoted line above is quoted
  from *this repo's* code, tests, and decision docs — several of which
  themselves quote fragments of the real document (`docs/DECISION-
  redisclosure.md` quotes three passages with their original line numbers,
  `:108-112`, `:138-144`, `:151`). Those quoted fragments are trustworthy as
  far as they go; the document's full structure, its complete class→rung
  table, and its exact "Classifying a new field" section heading are not
  reproduced here because they are not available in this tree.
* **The step-3 category list is incomplete and partly unverified.** Only
  minor, medical, substance use, financial/money and immigration are backed by
  a direct quote or a pack's `why` string in this tree. Religion, union, and
  criminal — named in the plan that commissioned this document — have zero
  hits anywhere in this repo and are flagged unverified in § 2.
* **I-10, I-34, I-24 and I-25 are gaps, not settled facts.** I-10 and I-34 are
  wholly unattested; I-24 and I-25 are attested only as "analogs," never
  defined on their own terms.
* **I-37…I-45 are provisional by the plan's own admission**, copied here
  verbatim from the plan document rather than derived from any implementation,
  because none of the modules that would define them (`keep.sync`,
  `keep.household`, `keep.fleet_cli`, the account-instance and bankruptcy
  packs) exist in this tree yet. I-41 and I-45 have no provisional meaning
  anywhere in the plan text this reconstruction had access to — they are
  reserved slots in the numeric range, nothing more.
* **The derived-form "no digits, no name" rule (§ 4) is this document's own
  synthesis** of what the packs' worked derived examples do, not a rule
  `classify_schema` or `Classified` mechanically enforces today — only
  presence and non-blankness are checked in code (`rungs.py:702-706`). Do not
  read § 4 as describing an existing runtime guard; it describes an
  established practice a future guard (planned, not built) could formalize.
* **The money table (§ 6) is read from a sibling module's docs, not this
  engine's code.** `homestead-ledger` has no packs in this engine's own
  `homestead/packs/`; the table is transcribed from that module's own
  build-plan doc as a documented decision, not verified against a ledger
  schema this repo can import.
* **No page count, section heading, or table row of the real
  `docs/homestead-rungs.md` is asserted here as exact** unless it is inside a
  quotation mark and cited to a file in *this* tree that itself quotes it.
  Anything else in this document that reads like a direct quotation of the
  safe-app-store document is, in fact, this repo's paraphrase of that
  document, one hand removed, and should be treated accordingly until someone
  with access to the safe-app-store confirms it.
