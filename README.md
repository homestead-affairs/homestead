# homestead

The seat of **Homestead · Affairs** — *the affairs you handle yourself.*

This repository holds **`homestead.keep`**: the shared record, deadline,
evidence and log core that every module on the face pins. It is the base repo,
and on this face the base repo is **not optional** — a module cannot pin an
engine that does not exist.

**Status: Phase 0.** The resolver, the two logs, the rung type, a window that
opens and shows nothing, and the invariant suite. There is no record layer, no
deadline arithmetic and no matter registry yet. Nothing here is installable by
anyone who is not building it.

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

| | |
|---|---|
| **I-19 / I-20** | One resolver, one spelling. `keep/paths.py` is the only module that may reach a home directory, and `expanduser()` is banned outright — it is invisible to the store's vault-leak linter, so the identical path in that spelling vanishes from the report. |
| **I-22 / I-15** | Two logs. `VisibleLog` carries **references, never content** — it has no parameter for a note body, so the failure is a `TypeError` rather than a leak. `SealedLog` is hash-chained and has **no read method at all**; a test asserts the absence. |
| **I-30 / I-26** | Nothing imports the network and nothing listens. The self-contained shape removes the problem rather than managing it. |
| **I-14** | A rung is a string. `L3`, never `3` — trust runs the other direction, and `if level >= 3` reads perfectly either way while being right on one scale and catastrophic on the other. |
| **I-27 / I-28** | Declared dependencies are true (there are none), and bare `pytest -q` works. |

## Design

Lives in the safe-app-store: `docs/homestead-law-build-plan.md` (the 36
invariants and the phase order), `docs/homestead-rungs.md` (the `L1`–`L5`
model), `docs/homestead-affairs-face.md` (the face), `docs/die-rules.md`.

MIT.
