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
(the same validator the household's own `Sidecar.put` runs, I-7), and
~~that `value` is text without a NUL byte~~ **that `value` is something
`json.dumps` can turn into text at all** — see § "Structured values (E7b)",
below, for what that check used to be and why it changed. The audit found
each of those coming out as a bare `KeyError` or a `psycopg.DataError`
traceback instead of a refusal by name, and the `DataError` only after a
connection had been opened. A row missing `matter` **or `value`**, or
~~carrying an integer~~ **carrying something JSON cannot serialize (a
`bytes` object is the planted case), a `float`, or more than 64 KiB of
canonical text**, or a NUL ~~in `value`~~ **in `matter`/`item_type`/
`item_id`**, is not a crash: it is refused by name, naming the field and
never the value (I-15).

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

## § Structured values (E7b)

Status: **Ratified, 2026-09-11**, with the four changes § "What the audit
changed" records.
author: the build seat
verified_by: the audit seat, 2026-09-11 (audit fixes: `1568dda`)

Found by the G5-sync audit (2026-09-11): the ledger's `transfers` pair is an
`L2` served value that is a mapping, `{counterpart, from, to}` — the sample
row in `docs/DECISION-sync-envelope-and-consent.md`'s own § "The envelope"
only ever showed a plain string (`"value":"2026-10-06"`), and `_validate_rows`
took that as the whole contract: it refused any row whose `value` was not a
Python `str`. So a ledger envelope carrying a transfer pair was refused
before the dial, never reaching Postgres at all.

**The contract, settled here: `value` is stored as canonical JSON text, not
`JSONB`.** `keep/sync.py`'s `Envelope`/`envelope_id`/`SCHEMA` are unchanged —
the envelope was already canonical JSON, and the served value inside a row
stays exactly what `serve()` returned (`str`, a mapping, a list, a `bool`,
~~a number~~ an `int`, or `None`; `docs/DECISION-sync-envelope-and-consent.md`
is not amended). What changes is only the fleet's own storage: `store.
canonical_value_text(value)` — sorted keys, no whitespace, unicode kept
literal, `allow_nan=False`, the same shape `sync._canonical_bytes` freezes an
envelope with — is what `PostgresAdapter.insert`/`.write` now put in the
`value` column, and `fleet_cli.decode_value(text, *, value_format)` is the
way back out. A JSON `null` stores as the four-byte text `null`; the `value`
column stays `TEXT NOT NULL`, unchanged.

~~and no migration touches a row already there (every stored value was
already a JSON string literal, which is itself valid canonical JSON text —
`json.loads` of it returns the same Python `str` it always did).~~ **That
sentence was false, and the migration it waved away is § "Rows written
before this" below.**

**Why `TEXT`, not `JSONB`.** Two reasons, both already in the plan's
decision 5. First, the fleet is a mirror, never a judge: nothing on the
engine side queries *into* a value (no `->`, no `@>`, no index on a field
inside one), so `JSONB`'s one real advantage — indexed, in-database
querying — is never asked for here. Second, `TEXT` keeps this adapter
symmetric with `SQLiteAdapter`, whose `value` column is `TEXT` and always
will be (SQLite has no first-class JSON column type); a `JSONB` column on
one backing and not the other would make the two adapters disagree about
what they store, for no capability this codebase uses.

**What `_validate_rows` refuses, restated.** An `L5` or unreadable `rung`
(unchanged). ~~A `value` on a row whose `disposition` is not `"render"`~~
**Any row whose `disposition` is not `"render"`, and any row with no
`value` key at all** — see § "What the audit changed". A `float`. A value
whose canonical text is over `fleet_cli.MAX_VALUE_TEXT` (64 KiB). And
anything `json.dumps` cannot serialize — a Python `bytes` object is the
planted case, a `set`, a circular reference, a structure nested past the
interpreter's limit — which can only reach this function from an `Envelope`
built by hand (every test in this repo, and any future direct
construction), since a row that arrived through `Envelope.from_bytes()`
already round-tripped through JSON and so is always one of the shapes above.

~~It no longer refuses a bare number or a NUL byte inside a string value.~~
Neither is a refusal any more, and neither hazard went away unaddressed: an
`int` is simply a valid JSON value, and a NUL byte inside a JSON string is
escaped to the six characters `\u0000` by `json.dumps` itself —
`canonical_value_text`'s output never contains a literal NUL byte, so the
thing the old check guarded against (Postgres's `TEXT` type rejecting one)
cannot occur through this path at all. Both are pinned by positive tests,
not merely deleted. A *`float`* is a different matter and is refused by
name (below).

## § Rows written before this, and what the audit changed

Status: **Ratified, 2026-09-11.** author: the audit seat.

**Rows written before E7b are not JSON text.** `PostgresAdapter.insert`/
`.write` took an already-serialized blob and passed it straight to the
statement, so every row already in a fleet database holds the served string
*verbatim* — `2026-10-06`, not `"2026-10-06"`. Reading one back with
`json.loads` does not merely fail loudly: on `2026-10-06` it raises, but on
a ledger amount `1450.00` it succeeds and returns the float `1450.0`, and on
`123`, `true`, `null` an `int`, a `bool`, a `None`. A household's money,
silently re-typed by a reader that believed it was decoding. Text alone
cannot tell the two encodings apart, so a guess — try `json.loads`, fall
back on failure — is not enough on its own.

**So the row carries the answer.** `canonical`/`sidecar` gain
`value_format TEXT NOT NULL DEFAULT 'raw'`, added by an idempotent
`ALTER TABLE … ADD COLUMN IF NOT EXISTS` beside the `CREATE TABLE IF NOT
EXISTS` in `ensure_schema()`. That is the whole migration, and it lands the
truth by construction: the rows that predate the column are exactly the raw
ones. Every row written from here on says `json`; an upsert over a raw row
moves its format with its value; `PostgresAdapter.read_value()` selects both
halves; and `fleet_cli.decode_value(text, *, value_format)` has **no
default** for the second argument and returns `Decoded(value, legacy)` — a
`raw` row comes back as the text it is, tagged, never parsed (I-11). The
`value` column itself is untouched, and the `(household, matter, item_type,
item_id)` primary key and both `ON CONFLICT` clauses are unchanged: a
re-ingested identical row is still a no-op on `canonical` and still an
upsert on `sidecar`.

**What the audit changed, beyond that.**

1. ~~A non-`render` row is accepted when its `value` is `None`.~~ **Any
   non-`render` disposition is refused outright**, as it was before E7b.
   The loosening read a `DERIVE` row with `value: null` as a shape the fleet
   should expect; `compose()` says otherwise. It drops every `DENY` and
   above-ceiling row before freezing, and `serve()` on `S4_EGRESS` with a
   declared purpose renders L1–L4 and denies L5 — it never returns `DERIVE`
   at all (`keep/rungs.py`'s `_CEILING`). A non-`render` row is therefore
   forged or hand-built, and under the loosened rule it was written as the
   text `null` into the *insert-only* canonical table, taking that key for
   good so the household's real row could never land. The missing-`value`-key
   refusal is restored on the same ground.
2. **A `float` is refused by name.** No module puts one in a record: money
   is a two-decimal *string* (`homestead_ledger.money.amount_text`), and
   every other served value is text, a mapping, a list, a `bool` or an
   `int`. A float does not round-trip as one text — `1.10` and `1.1` are one
   number and two texts, so one record would sync as two rows — and
   `NaN`/`Infinity` are floats Python's `json` writes as text no other JSON
   reader can parse. `canonical_value_text` passes `allow_nan=False` as the
   structural backstop under the same rule.
3. **Three refusals that were tracebacks.** The serialization guard caught
   `TypeError` only, so a circular reference (`ValueError`) and a 2000-deep
   structure (`RecursionError`) came out of `ingest()` as stack traces.
4. **A size cap, because nothing upstream has one.** `sync.compose()` puts
   no bound on a served value, so a 1 MB row composed, framed and ingested.
   `fleet_cli.MAX_VALUE_TEXT` is 64 KiB, declared at the fleet's own door
   and named in the refusal. The envelope side is unchanged; if a bound
   belongs there too, that is `keep/sync.py`'s bite, not this one.

**The ledger's own floor.** `homestead-ledger`'s `test_the_fleet_refuses_a_
structured_pair_value_by_name` (G5-sync) is written against the *old*
contract, asserting the refusal this bite removes, and is expected to flip
from a pass to a failure the day the ledger's engine floor rises to include
this bite's release — recorded here rather than fixed there, since the
ledger's own floor bump is its bite, not this one's.
