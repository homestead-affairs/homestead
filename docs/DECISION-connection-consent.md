# Connections are the household's — decision brief

Status: **Decided by the operator, in session (2026-08-17).** This is the rarer
shape: not a hand proposing for another to ratify, but the operator ruling and the
session transcribing. `verified_by ≠ author` still holds and is the point —
**author: the session; verified_by: the operator** — but the substance was the
operator's judgement, made in conversation, not a model's recommendation. What
remains is the *formal* seal into the decision record (`stores/decisions/` + a
Nestor entry), a separate human act, deferred here only because Nestor is not
reachable in this cloud session. Until that seal lands, this brief is the faithful
record of the ruling, awaiting the operator's confirmation that it reads true.

The invariant is homestead-wide (face-level, not module-local); whether it takes an
`I-*` number is ratification's call, not this file's.

---

## The question

Homestead is a family of independent modules over one engine — law, ledger, health,
and the kitchen table among them. They are useful together: an allergy the health
module holds is a fact the kitchen wants; a diagnosis a legal matter needs is a fact
health holds. **So who decides which module may ask which other module for what?**

The question arrived through the kitchen's allergy gate (the worked instance below),
but it is not about allergies. It is about every cross-module seam in the house, and
it has exactly three candidate answers: the *designer* wires them, they are wired *by
default*, or the *household* wires them.

## The decision

**Connections between modules are the household's to make — operator-authored,
scoped, and revocable. Modules are independent by default; a connection is an
explicit, visible, consented grant, never a designer's choice and never a default.**

- **Independent by default.** `CLAUDE.md §6` lane isolation is not a limitation to
  route around — it is the ground state. A module reaches another module's data
  only through a connection the operator made. Absent one, the wall stands.
- **The operator decides what connects to what.** One household wires the kitchen to
  health's allergies and never types shellfish twice; another keeps them walled
  because the person who cooks is not the person who holds the health file. Both are
  correct *for that household*. The design picks neither.
- **A connection is a first-class, revocable grant.** It is made, it is seen, it is
  pulled. It is not a dependency compiled into the modules.

## Why

The reason is the fleet's oldest one, one level up from where it usually sits:
**authority is the person's.** The house already holds that a model may propose but
only a person may verify, rule, seal, or publish (`§0.2`); the household analogue is
that only the household may decide how its own rooms connect. A designer choosing the
seams for everyone is the paternalism the whole house is built against — *"mirror,
not judge."* One family's right answer is not another's, and a wall the household did
not ask for is a reach it did not consent to. Sovereignty over one's own information
architecture is what "local-first, yours to keep" means when taken past storage and
into *shape*.

## The rails that bind even a consented connection

"The household decides" is not "the household may wire anything." Consent operates
*within* the safety discipline, never around it. Three rails hold regardless of what
the operator asks for:

- **No silent live-join (H-3, authored-not-computed).** A connection may never
  become a computed card — a query one module runs live into another's records and
  surfaces as if it were its own. The health plan already ruled this for the
  emergency card: *"a computed card is a query someone else effectively wrote, run at
  the worst possible moment."* A connection the operator cannot see is not a consented
  connection.
- **No silent second copy (exclusion 3, BUG-6).** A connection that copies a fact
  from one module into another creates two copies with one rung each, which drift. A
  copy is permitted only as an act the operator authored and can see — never as a
  quiet background sync.
- **Scoped — one connection never implies another.** Wiring the kitchen to health's
  *allergies* grants nothing about health's *conditions*. This is the sealed
  precedent exactly (`granting testimony_publication never implies kb_promotion`):
  one consent must never quietly stand in for another.

So the operator chooses among **safe, visible modes** — a *check-against* (one module
asks another's gate a question and surfaces the answer, copying nothing) or a
*confirmed seed* (a copy the operator explicitly authorized and can see) — and never
an invisible join. The household decides *what connects*; the house still decides
*that a connection can never be invisible*. That line is what keeps "let the user
choose" from becoming "let the user footgun."

## What it makes real — the connection-consent layer

The decision names a primitive the box does not yet have. `libs/subject-consent`
governs *who may hold whose records*; this governs *which modules may ask each other
what* — a sibling. It is the surface where the operator sees every live connection,
its mode (check-against / seed), its scope, and pulls any of them. A connection is a
grant with a reason and a revocation, held where the household can read it, the same
posture the decision record holds for the fleet's own decisions.

Building it is not in this brief. Naming it as the decision's consequence is.

## The instance that produced it — the kitchen's allergy gate

Recorded so the reason stays legible. The kitchen wants to flag a dish unsafe for
the household. Two designs were weighed — *seed* the kitchen's no-serve set from
health's allergy pack (convenient; risks the BUG-6 two-copies drift) versus *re-enter*
it by hand (safe; redundant, and the two can silently disagree). The attempt to pick
one in the architecture is what surfaced this decision: **the pick is not the
designer's.** A household that shares a cook and a record-holder seeds; a household
that separates them re-enters. The gate offers both safe modes and the operator
chooses — and, per the rails, is never offered the silent live-join that started the
analysis. (Full derivation:
`safe-app-store/apps/the-table/docs/homestead-kitchen-vision.md`, the allergy-gate
section — including that the k≥2 privacy cover was the wrong lens, since allergies are
already H-3 export-nature.)

## Closed doors

- **The designer picks the seams for everyone** — rejected: paternalism, and one
  household's right answer is not another's; it is the `mirror, not judge` violation
  at the architecture level. *reopen_when:* never — this is the decision's core.
- **Modules connected by default** — rejected: violates `§6` default-deny and the
  sovereignty the decision rests on; a connection nobody chose is a reach nobody
  consented to. *reopen_when:* never.
- **The operator may authorize a silent live-join / computed card** — rejected: `H-3`
  and `BUG-6`; a connection the household cannot see is not one it consented to.
  *reopen_when:* never — this is a safety rail, not a default.

## Reopen when

The decision itself reopens only if a genuinely necessary connection is found that
**cannot** be expressed as an authored, visible, scoped grant in one of the safe
modes — i.e., if the rails are shown to forbid something a household truly needs.
Then the question is whether a new safe mode exists, not whether the household stops
deciding.

## Related

- `CLAUDE.md §6` — the lane-isolation default this decision makes load-bearing
- `homestead/docs/PLAN-homestead-health.md` — H-3 (authored not computed), exclusion 3 (BUG-6), the three-postures extension
- `safe-app-store/apps/the-table/docs/homestead-kitchen-vision.md` — the allergy gate that produced the question
- `libs/subject-consent` — the sibling primitive; consent over subjects, where this is consent over connections
- `stores/decisions/README.md` — the decision-record contract this brief awaits a seal into
