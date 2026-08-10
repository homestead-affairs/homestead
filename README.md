# homestead

The seat of **Homestead · Affairs** — *the affairs you handle yourself.*

This repository holds **`homestead.keep`**: the shared record, deadline,
evidence and log core that every module on the face pins. It is the base repo,
and on this face the base repo is **not optional** — a module cannot pin an
engine that does not exist.

> **Phase 0 was audited, and the findings are fixed.** Suite: **30 passed / 13
> xfailed**. The path scans now catch the Desktop leak that walked through the
> first version, `IntegrityLog.append()` takes a lock, `ensure()` resolves
> before it checks, and CI builds and smoke-runs the artifact on three
> platforms. Encryption of the integrity log is a named **Phase 4** item.
> History below, kept rather than edited away.
>
> **Phase 0 did not meet its exit criteria.** Two independent audits
> (`docs/audits/`) found the implementations roughly right and **the enforcement
> theatre** — the path scans miss the Desktop leak they were written to prevent,
> `SealedLog.append()` has no lock and breaks its own chain under concurrent use,
> `ensure()`'s containment check is lexical, and the packaged artifact crashes on
> startup. Nothing below should be trusted as enforced until
> **`docs/PHASE0-REMEDIATION.md`** is worked. The list is written down; the fixes
> are not made.

**Status: Phase 0, audited and remediated.** The resolver, the two logs, the rung type, a window that
opens and shows nothing, and the invariant suite. Deadline arithmetic is built
(`keep/dates`), and so now is the **record layer** — `keep/record`, bite 1 of
`docs/PLAN-first-runnable.md`: a read-only canonical handle and the sidecar the
app writes to, keyed once (I-7), refusing silent overwrites (I-9), and failing
closed to `L5` when a stored rung is missing or unreadable (I-11 at the storage
boundary). The first matter pack — **custody** (`packs/custody`, bite 2) — is
authored and classified at import: a closed schema whose every field declares a
rung, its matter and its jurisdiction, so an unclassified field fails the build
naming itself (I-11), on a real schema rather than a synthetic one. The
authorization **chokepoint** is wired ahead of the surfaces that will use it
(bite 3): a payload may be reached only in the gate (`keep/rungs`) and the store
(`keep/record`), and a reach past `serve()` on any surface is a build failure
(I-16). The two **S1 surfaces** now render through that gate (bite 4,
`app/window`): a `Window` that rests on the cover until a human asks (I-21), a
**list** that shows `L1`–`L3` payloads, the *derived* form for `L4`, and drops
`L5` without a trace, and a **detail** pane that shows the `L4` payload and still
refuses `L5` — the surface calculating nothing itself (I-29), only asking
`ambient_rows`/`serve`. And the **logs now have a writer** (bite 5,
`keep/export`): an export — the operator taking their own record out, gated
through `serve(…, S4_EGRESS, purpose=…)`, since nothing here dials — writes the
content to `exports/`, one `IntegrityLog` entry naming the declared purpose, and
one `VisibleLog` `EXPORTED` act, both carrying **references and never content**
(I-15). `Event.EXPORTED` had a name and no writer; it has one now. The head that
vouches for the ledger is held off the log's own tree in `anchors/` (the
willow-mcp #280 separation), and `export_record` returns it so the operator can
record it off the machine — the only closure against someone who edits both. The
tkinter view that draws a `Window`, and loading a matter's records from the store
into it, are the remaining wiring.

**Bites 1–3 were then audited adversarially and remediated**
(`docs/audits/bites-1-3-remediation.md`). The audit earned its keep: the
chokepoint was theatre — `getattr(record, "payload")` in a surface reached a
sealed `L5` payload and passed the suite, because the scan matched the *spelling*
`.payload` rather than the property. It now bans reflection in the surface layer
outright, and its regression runs the real scan over every bypass the audit
found. The store's `put` was made race-safe (I-9) and corruption-safe (a corrupt
row reads `L5`, not a crash), the canonical tree closed to every module but the
store, and two custody rungs aligned to the spec.

There is no matter registry yet. Nothing here is installable by anyone who is not
building it.

## The method

Every invariant is written as a test **before** the code that satisfies it, and
each one is traceable to a failure that actually happened in the predecessor.
`tests/test_invariants_pending.py` holds the invariants for phases not yet
built, as `xfail(strict=True)` — so the suite stays green while a phase is
unbuilt, and **fails the moment an implementation quietly satisfies one**,
forcing the test to be promoted rather than forgotten.

```bash
pip install pytest && pip install -e .
pytest -q          # bare, from a cold checkout. No out-of-band install step.
```

## What is enforced here today

*Each row was audited and, where it fell short, fixed. `docs/audits/` holds the
findings; `docs/PHASE0-REMEDIATION.md` holds what changed.*

| | |
|---|---|
| **I-19 / I-20** | One resolver, one spelling. `keep/paths.py` is the only module that may reach a home directory, and `expanduser()` is banned outright — it is invisible to the store's vault-leak linter, so the identical path in that spelling vanishes from the report. |
| **I-22 / I-15** | Two logs, and a writer for them. `VisibleLog` takes a **closed `Event` enum** and a reference tuple — there is no free-text parameter in any position. `IntegrityLog` is hash-chained, locked against concurrent appends, and anchored: truncation and tail rewrites are caught. An **export** (`keep/export`) is the first thing to write either — one integrity entry and one visible act per export, both references, never content. The head anchor is held off the log's own tree (`anchors/`) and returned to the operator to record off the machine. It is **not** encrypted and does **not** withstand someone who edits both the log and its anchor; the docstring says so and a test asserts it. |
| **I-30 / I-26** | Nothing imports the network and nothing listens. The self-contained shape removes the problem rather than managing it. |
| **I-14** | A rung is a string. `L3`, never `3` — trust runs the other direction, and `if level >= 3` reads perfectly either way while being right on one scale and catastrophic on the other. |
| **I-27 / I-28** | Declared dependencies are true (there are none), and bare `pytest -q` works. |

## Design

Lives in the safe-app-store: `docs/homestead-law-build-plan.md` (the 36
invariants and the phase order), `docs/homestead-rungs.md` (the `L1`–`L5`
model), `docs/homestead-affairs-face.md` (the face), `docs/die-rules.md`.

MIT.
