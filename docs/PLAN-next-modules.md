# Next modules — the running list

Status: **A list, not a commitment.** Each entry is a candidate sibling repo
under Homestead · Affairs — the shape of what it would hold, why it belongs on
this face, and what would need to be true before a `PLAN-<name>.md` is written
against it and a bite lands. A candidate is not a promise: the list is where
proposals live before ratification chooses which to build, and the order below
is not the build order.

A sibling belongs on this face when it holds records the household keeps for
itself, and its domain does not already fit inside one of the three existing
modules — `homestead-law`, `homestead-ledger`, `homestead-health`. That is a
narrow test on purpose. A candidate that could sit inside one of the three
as a **pack** — a domain-specific record type inside a module's registry, as
defined in [`PLAN-homestead-health.md`](PLAN-homestead-health.md) (§ *What it
is*: "modules are sibling repos on the org; packs live inside a module and
belong to a registry") — is a *pack*, not a sibling.

## Open candidates

*(None right now — see below.)*

## Considered and ruled out (for now)

Kept here because the next seat should not re-propose them from scratch: the
reasoning is the point of the record.

### `homestead-people` — a household persons register

*Proposed and ruled out 2026-08-24.* Three modules resolve entities inside
their own lanes today (parties, payees, providers), and health also holds a
household `roster` for whose immunization records these are. A shared persons
register looked like a clean fourth sibling — until the privacy test.

**Why it doesn't earn a sibling.** A persons register is inherently the *join
key* across every other module, which is exactly the shape the rest of the
suite is architected against:

1. **It makes cross-module inference easy.** Today law names a party, ledger
   names a payee, health names a subject, each in its own store — joinable
   only through a deliberate act. A persons module is an ambient index over
   all of them, which is what H-1 was written against ("the log carries the
   ref, never the identifying content"): the *ref* is fine; the
   *joinability of refs* is what leaks.
2. **The existence of the store leaks structure.** "There are four rows in
   the roster" tells an attacker the household size before any record is
   opened.
3. **It centralizes identity.** Every other module holds records *about*
   people, not the people themselves — so a compromise of one lane doesn't
   compromise identity. A persons store consolidates the identity graph into
   one lane, which is the opposite of the containment the fleet builds
   toward.

**What survives the test.** A *naming primitive* — just "this opaque ref is
one of ours," no attributes, no queries, no joins pulled from it. Each module
keeps naming its own subjects; the primitive only marks which refs are
household members. At that size, it belongs inside `homestead.keep` as a
small addition to key discipline (an "ours-vs-outside" bit on a ref), not as
its own repo. If it grows past that, the same three concerns come back.

**Reopen condition.** A concrete need that (a) can't be met by each module
naming its own subjects through Nestor's `EntityResolver`, and (b) does not
recreate the ambient join graph the three concerns above name. Health's
`roster` is not that need: it is scoped to health, and the join to law's
parties or ledger's payees stays a deliberate act.

### `homestead-home` — the physical property

*Proposed and ruled out 2026-08-24.* Property records — appliance serials,
warranties, HVAC / roof / plumbing service history, permits — are the
artifacts of *ownership*, and ownership is a shape ledger already holds. A
payment produces an asset; the asset has a warranty, a serial, a service log;
those attach to the asset ledger already knows about because ledger has the
purchase. The right shape is a `homestead-ledger` pack — call it `Asset`,
carrying `(kind, serial, warranty_until, service_log[])` — rather than a
sibling. Utility service accounts are the same argument: an account is a
ledger concept.

**Reopen condition.** A body of household-property records that survives
without being attached to a ledger transaction — a thing the household holds
that ledger doesn't and shouldn't know about. If that appears, the sibling
question is worth revisiting.

### Vehicles, school, work

*Considered 2026-08-24 alongside people and home; ruled out as siblings.*
Each looked like a sibling and turned out to spread cleanly across the
existing three:

- **Vehicles.** Title / registration deadlines → law (deadlines are law's
  shape, and titles are legal documents). Insurance / maintenance / gas →
  ledger. Recall notices → law again. The "vehicle as a thing" has no
  orphan data once you split the deadlines from the money.
- **School.** Enrollment paperwork → law. Tuition → ledger. Required
  immunizations already live in health. Everything else (report cards,
  IEPs, teacher contacts) is *about a person* — the same H-1-H-8 subject
  discipline health already runs, and lands as a health pack.
- **Work.** Employment contracts → law. Pay stubs / W-2s → ledger (income
  is a transaction, same shape as an outbound bill). Benefits enrollment
  spans ledger + health; PTO is small enough to sit in ledger.

**Reopen condition.** A case where one of these needs cross-module discipline
that a pack in one lane can't provide (e.g. a vehicle-scoped subject-key
discipline that neither law nor ledger holds).

<!-- Next candidates land under ## Open candidates. Each earns its own
subsection there before a PLAN-<name>.md is written; when the PLAN exists,
the entry becomes a pointer to it. -->
