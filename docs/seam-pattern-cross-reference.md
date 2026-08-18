# Soft-Nestor dependency with local path resolution — a cross-reference

Status: **A finding, not a decision.** Two independently built repos arrived
at the same seam shape for consuming Nestor. Nothing here proposes changing
either implementation; it records that the pattern is now proven twice.

**The pattern:** treat Nestor as optional at import time, resolve every path
Nestor needs yourself (never through Nestor's own resolver), pin Nestor to a
tag, and degrade to a no-memory / no-recognition mode rather than crash when
Nestor is absent or unbound.

## Where it lives

- **homestead** — `homestead/keep/nestor_seam.py`
- **Forge** — `forge/checkpoint_memory.py` (soft-import) +
  `forge/checkpoint.py:473-486` (the degrade decision)

Built independently, for different products (a legal-affairs household vs. a
builder-checkpoint memory), with no shared code between them.

## What each does

**homestead** — explicit `bind()`, fail-closed. `nestor_seam.bind(root)`
computes `<root>/keep/ledger.jsonl` via homestead's own `keep/paths.py` (the
one module allowed to resolve a home directory, I-19/I-20) and hands it to
`nestor.cascade.set_ledger_path()` explicitly — never calling Nestor's own
household resolver. `resolver_for()`/`verify_ledger()` raise
`SeamNotBoundError` if `bind()` has not run: unbound, the ledger would
otherwise write to `data/ledger.jsonl` relative to cwd. Nestor is imported
lazily inside `bind()`, so a checkout without the `entity` extra still
imports the seam cleanly. Pinned at `v0.2.0`, a tag (fleet rule R14).

**Forge** — `nestor_available()` gate, degrade to full-Socratic.
`checkpoint_memory._nestor()` imports Nestor lazily, caching success only;
`nestor_available()` calls it and returns `True`/`False`, never raising.
`checkpoint.py` checks that first, before anything else in the module, and
when `False` skips memory entirely — `_full_socratic()`,
`memory_available=False` — rather than let `open_checkpoint_memory()` raise
partway through a flow. Once Nestor is available, `open_checkpoint_memory()`
points Nestor's ledger at `<root>/ledger.jsonl` itself, the same
resolve-it-yourself move homestead makes.

## The shared shape

| | homestead | Forge |
|---|---|---|
| Import-time posture | soft (lazy import inside `bind()`) | soft (lazy import inside `_nestor()`) |
| Availability check | `SeamNotBoundError` on first unbound call | `nestor_available()`, checked first |
| Ledger/path resolution | homestead's `keep/paths.py`, never Nestor's | Forge's own `root`, never Nestor's cwd default |
| Absent-Nestor behavior | refuse (fail closed) once a call is attempted | degrade to full-Socratic (never attempted) |
| Pin | `v0.2.0`, tag | git SHA at promotion (unset in dev) |

They differ on *when* Nestor's absence is allowed to surface — homestead
refuses at the call site, Forge decides upstream and never calls — but both
refuse Nestor's own path defaults and neither crashes a Nestor-less caller.

## Proven drift resilience

homestead's seam has already paid for this once. At the pinned `v0.2.0`,
Nestor's own resolver (`nestor.homestead_paths.home()`) happened to agree
with homestead's `paths.home()`. Nestor later renamed that module to
`nestor.home_paths` and gave itself an independent root
(`$NESTOR_HOME`/`~/.nestor`) — the two no longer agree. Nothing in
`nestor_seam.py` changed, because it never called Nestor's resolver at all.
The seam absorbed the rename silently — the coincidence it declined to
depend on was exactly what would have broken had it depended on it.

## Lesson for future builds

Any homestead module (or Forge module) that next wants Nestor should copy
this shape, not reinvent it:

1. **Pin Nestor** to a tag or SHA, never a branch.
2. **Resolve paths yourself.** Nestor's own household/root resolver is a
   second resolver that can drift from yours — one resolver per side.
3. **Degrade, don't crash.** Import Nestor lazily; expose an availability
   check (`nestor_available()`) or a fail-closed guard (`SeamNotBoundError`)
   so a Nestor-less caller gets "feature absent," not an `ImportError` at
   module load.
