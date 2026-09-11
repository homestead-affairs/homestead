# The fleet ingest — a receiving act, never a listener — decision brief

Status: **Proposed.** `homestead.keep.fleet_cli` and `store.PostgresAdapter`
are built, `tests/test_invariants_fleet.py` is green, and I-39 is promoted
out of `tests/test_invariants_pending.py`, unmarked.

author: the build seat
verified_by:

`E4-postgres-fleet` (Wave 4, decision 5), depends on `E4-sync-core`. That
bite's own brief (`docs/DECISION-sync-envelope-and-consent.md`) composes and
delivers one `Envelope`; its "What this deliberately does not include" named
`store.PostgresAdapter`/`keep/fleet_cli.py` as `E4-postgres-fleet`'s job.
This is that bite.

## What the household side never holds (open item 7)

`homestead-fleet ingest` is a **separate program**, installed by a
**separate extra** (`fleet`), run **by hand** on whichever machine holds the
fleet's own Postgres — not necessarily the household's own operator.
`keep/sync.py` never reads a DSN, never imports `psycopg`, and never dials
Postgres; it delivers to a URL or writes a file. The household's own
checkout runs forever without the `fleet` extra installed at all.

This is `keep/egress.py`'s own shape: the permission to dial is per call and
spent on the call, never an ambient credential sitting where code that runs
unattended could read it. Keeping a fleet DSN out of the household's own
process is not a convenience — there is no code path in that checkout that
could leak a credential it never holds.

## Why the canonical table is insert-only at the fleet, too

The household's own `Canonical` reader has no `put` (I-6, I-36): read-only
*by type*. The fleet's own copy keeps the same shape the same way — not a
permission check but the statement itself: `INSERT … ON CONFLICT DO
NOTHING`. A canonical row already there at the fleet is counted as
**skipped**, never overwritten — a number, not which row it was. The
sidecar table is the opposite on purpose (the household's own editable
record), so `ingest()` upserts it — `PostgresAdapter.write()` vs
`.insert()`, picked by the row's own `table` field, which `compose()`
already set from `scope.tables`.

## Why there is an anchor

`anchors (household PRIMARY KEY, head, envelope, updated_at)` — one row per
household, the most recently ingested envelope's `head` (the household's
`IntegrityLog` head *at compose time*, carried inside the envelope). It lets
the fleet answer "what is the most recent thing I have, and against what
chain-state" without walking `envelopes`. It is descriptive, not
authoritative: nothing on the household side reads it back, and it is not a
second source of truth for the household's own chain — `anchors/
integrity.head` (`keep/paths.py`) stays that.

## Why the CLI never listens (I-39, promoted)

One file read, one dial out, then exit — no server mode. Not merely
unbuilt: `tests/test_invariants_fleet.py`'s AST scan (banned listen calls,
banned top-level `import psycopg`, each with a planted-violation test)
fails the build if it grows one. **The listener is Willow's** (the plan's
own decision 5); a second one here, even informally, would put a second
network-reachable thing in an application whose whole `homestead` side is
I-30's *"nothing here listens"*.

## Belt and braces: the fleet does not trust `compose()`'s own promise

`compose()` already drops any `DENY`-disposed or above-ceiling row before
freezing an envelope, so a well-formed one never carries an `L5` row, an
unreadable rung, or a non-`render` disposition. `ingest()` checks anyway,
refusing the **whole** envelope before any row is written, for two reasons:
the envelope crossed a boundary (a forged one that hashes correctly could
still carry a row `compose()` would never produce — `Envelope.from_bytes()`
only proves the bytes weren't edited *after* composition, not that they
were ever a genuine one); and a future `compose()` regression should fail
here loudly, at ingest time, rather than let an `L5` datum land in a shared
store because the one thing standing between it and Postgres assumed the
upstream promise still held. The whole envelope refuses on one bad row —
never a silent per-row skip — the same fail-closed shape `_hydrate()` gives
a corrupt field (I-11): a partial, silently-incomplete copy is worse than a
loud refusal, and the operator can compose a fresh envelope once the cause
is fixed.

## What this deliberately does not include

- **No retry, no batching, no partial ingest.** One transaction — every
  row, the `envelopes` row, and the `anchors` upsert commit together or not
  at all; a crash midway leaves the fleet's prior state untouched, and a
  retry either re-runs cleanly or is refused as a re-ingest.
- **No schema migration tooling.** `ensure_schema()` is idempotent DDL, run
  at the top of every ingest.
- **No listener, ever** — see above.

## Residuals recorded, not fixed

- **A DSN on the command line is visible in shell history and process
  listings.** `HOMESTEAD_FLEET_DSN` avoids the process-listing half; shell
  history is the shell's own residual, shared by every CLI that takes a
  credential argument. The confirm strips the password before printing
  anything, but cannot reach a shell's history file.
- **`ensure_schema()` runs with whatever privileges the DSN's role has** — a
  deployment choice for whoever provisions the fleet's Postgres.
