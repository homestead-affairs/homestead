# The fleet ingest — a receiving act, never a listener — decision brief

Status: **Ratified**, with the amendments recorded below.
`homestead.keep.fleet_cli` and `store.PostgresAdapter` are built,
`tests/test_invariants_fleet.py` and `tests/test_fleet_postgres.py` are
green (the latter against a real `postgresql-16`), and I-39 is promoted out
of `tests/test_invariants_pending.py`, unmarked.

author: the build seat
verified_by: E4-postgres-fleet audit, 2026-09-11

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

## One code path for a row, not two (amended by the audit)

As built, `ingest()` carried its own copy of the sidecar upsert and the
canonical insert rather than calling `PostgresAdapter.insert`/`.write` —
because those opened and committed a connection per call, and the ingest
must be one transaction. The reasoning was right and the result was two
statements that had to agree on seven columns and on both `ON CONFLICT`
clauses, with nothing checking that they did.

`PostgresAdapter.transaction()` removes the reason rather than the
duplicate: inside it, the four methods run on one held connection and commit
nothing, so the transaction owns the commit. `ingest()` now writes every row
through the adapter, and `tests/test_invariants_fleet.py::
test_ingest_carries_no_row_sql_of_its_own` fails the build if a second copy
of either statement reappears. The adapter is ~45 lines longer and the
command is shorter.

What stayed in `ingest()` is the `envelopes` row, the `anchors` upsert and
the re-ingest `SELECT`: those are this command's own bookkeeping, not the
record store's four-method contract, and their table names are literals in
the SQL text, interpolating nothing. `tests/test_fleet_postgres.py::
test_the_adapter_and_the_ingest_write_the_same_row` writes the same row by
both routes into two households and compares the stored columns.

Two smaller consequences, recorded because they are visible: `synced_at` is
now one client-side timestamp per envelope, passed as a parameter, rather
than the server's `now()` evaluated per statement — every row of one
envelope carries the same instant, which is what `PostgresAdapter`'s
signature already took. And the row's own `table` field never reaches the
SQL text at all: `ingest()` passes the module's own `SIDECAR`/`CANONICAL`
constants, and the adapter validates the name again in the method that
builds the statement.

## The anchor only moves forward (amended by the audit)

A *different* envelope composed before the one this household's anchor
points at is **refused by name**: ingesting it would move the anchor
backwards, and an anchor that can go backwards answers "what is the most
recent thing I have" wrongly. `--allow-stale` ingests its rows and its
`envelopes` row, and still leaves the anchor where it is — the rule is not
"the operator may move the anchor backwards", it is "the anchor only moves
forward, and the rows can still come in".

**Ordered by `composed_at`, not by `head`.** `head` is the household
`IntegrityLog`'s chain head — a hash, with no order of its own; two heads
can only be compared by walking a chain the fleet does not hold. The
envelope's own `composed_at` is ordered, and since `sync._now_iso()` writes
one fixed-width UTC format, byte order *is* time order for it — so
`_is_stale()` checks both strings against that anchored shape and then
compares them as text. It does not call `fromisoformat`, which I-1/I-2 ban
package-wide (one date parser, in `keep/dates.py`, and not that one). A
timestamp in any other shape has not been shown to be older *or* newer, so
it is treated as stale: fail closed (I-11), with `--allow-stale` as the
operator's way past it.

**Equal is not stale.** `_now_iso()` has second resolution and two envelopes
composed in the same second are ordinary — the end-to-end test composes
exactly that pair. Only strictly older is stale.

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

`ingest()` also checks every field that reaches a statement — that the row
is an object at all, that `(matter, item_type, item_id)` pass `store.key()`
(the same validator the household's own `Sidecar.put` runs, I-7), and that
`value` is text without a NUL byte. The audit found each of those coming out
as a bare `KeyError` or a `psycopg.DataError` traceback instead of a refusal
by name, and the `DataError` only after a connection had been opened. A row
missing `matter`, or carrying an integer, or a NUL, is not a crash: it is
refused by name, naming the field and never the value (I-15).

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
- **The confirm's redaction is an allow-list, and libpq has two DSN
  forms.** As built, `_redact_dsn` handled the URL form
  (`postgresql://user:pw@host/db`) and handed the keyword/value form
  (`host=h user=u password=pw`) back *whole*, printing the password to
  stdout — found by this audit. The keyword form is now tokenized and
  rebuilt from `host`/`hostaddr`/`port`/`dbname` alone, so a credential
  keyword this does not know about (`passfile`, `sslpassword`,
  `require_auth`, whatever libpq adds next) is dropped rather than shown,
  and a DSN it cannot take apart is described rather than echoed.
- **The driver's own error text is not echoed.** An unreachable host, bad
  credentials or a role without rights to run the DDL ends in a refusal
  naming the exception class and the redacted destination, not a
  `psycopg.OperationalError` traceback and not libpq's message, which is
  built from the conninfo this command is the one place to hold.
- **`ensure_schema()` runs with whatever privileges the DSN's role has** — a
  deployment choice for whoever provisions the fleet's Postgres.
