# Next modules — the running list

Status: **A list, not a commitment.** Each entry is a candidate sibling repo
under Homestead · Affairs — the shape of what it would hold, why it belongs on
this face, and what would need to be true before a `PLAN-<name>.md` is written
against it and a bite lands. A candidate is not a promise: the list is where
proposals live before ratification chooses which to build, and the order below
is not the build order.

The three existing siblings — `homestead-law`, `homestead-ledger`,
`homestead-health` — each pin `homestead.keep` and bring a domain. A new
sibling belongs on this face when it holds records the household keeps for
itself, and its domain does not already fit inside one of the three.

## Candidates

### `homestead-people` — the household's own persons register

**Prompted by 2026-08-24 review of the intake modules.** Law tracks parties on
a matter, ledger tracks merchants/payees, health tracks providers and holds a
`roster` for household members (whose immunization records these are). Each
resolves entities inside its own lane, through Nestor's `EntityResolver`, with
no shared spine. So "the humans of this household" — the people whose records
the modules keep — has three partial answers and no canonical one. A child who
appears on a health record, a parent who signs a court filing, an account
holder on a bill: today each module names them in its own store, and there is
no place a rename or a status change reaches once.

The module would hold the persons the household keeps records *for* — the
household roster itself — and let the sibling modules pin to it the way they
pin to `homestead.keep`. What each module continues to hold: the party / payee
/ provider entity as it appears in *its* record (a signed filing names one
party, a receipt names one payee), resolved through Nestor as today. What this
module would hold: the household's own members, their identifiers as the
household uses them (a legal name, a preferred name, a role in the household),
and the joins from module-scoped entities back to a household person where one
exists. A merchant is not a household member; a household member can be the
account holder on a merchant's account, and that is the join.

**Open before writing a PLAN:**

- **Does health's `roster` become the seed?** The health module already ships
  `roster add|list` for household members, scoped to health. If the persons
  register is a separate module, health's roster narrows to *whose health
  record this is* — a join, not the definition. If it stays health-scoped, law
  and ledger grow their own rosters and the fleet has three. The move
  ratification calls: extract the seed, or leave the seed where it is and let
  the three grow parallel until the join earns the extraction. `stores/`
  Article IV governs the extraction either way.
- **What discipline holds the identifiers?** A household roster is the exact
  shape of data whose "person id" outlives every module that quotes it and
  reaches the log lines those modules leave. `keep.logs`' key discipline (H-1
  applied to persons: the log carries the ref, never the identifying content)
  is where this starts, and any surface that renders a person's name is on
  the rungs the way a record's contents are.
- **What does not belong.** Not a contacts app: an outside person referenced by
  the household (a doctor, a lawyer, a landlord) stays where each module names
  them, resolved through Nestor. This module holds the *household's own*
  people, not everyone the household has ever transacted with.

*Would become bite 1 when written:* the seat — `homestead-people` scaffolded,
pinning `homestead.keep`, with a single `Household.member(id)` primitive and
the module's own `P-1…P-N` invariants (the persons analogue of `H-1…H-8`) as
strict `xfail`s the day the repo exists. No sibling module changes until the
seat is green.

<!-- Next candidates land below. Each earns its own subsection here before a
PLAN-<name>.md is written; when the PLAN exists, this section becomes a
pointer to it. -->
