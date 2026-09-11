"""`homestead-fleet ingest` — the fleet side's own dial, never the
household's.

Decision 5 of the affairs build plan, `E4-postgres-fleet` (depends on
`E4-sync-core`): `keep/sync.py` composes and delivers an `Envelope`; this
module is the *other end* — the operator runs it by hand, on the machine
that holds the fleet's own Postgres, to bring one delivered envelope in.
Nothing here runs unattended.

**The household side never holds a DSN (open item 7).** `keep/sync.py`
delivers to a URL or a file drop; it never dials Postgres. This CLI is a
separate program behind a separate extra (`fleet`), run by whoever operates
the fleet store — possibly not the household's own operator at all. See
`docs/DECISION-fleet-ingest.md`.

**Never listens (I-30); `psycopg` is lazy (I-27, I-39).** One file read, one
dial out to `--dsn`/`HOMESTEAD_FLEET_DSN`, then exit — no server mode.
`psycopg` is imported only inside `_connect()`, after the envelope has
already been read and validated — and `_connect` is the *one* place in this
process that reaches for it: `store.PostgresAdapter`, which does the row
writes, is handed this function rather than importing its own.

**Refusals, checked in order, each by name and never echoing a value
(I-15):** (1) the file does not read as a `homestead.sync/1` envelope
(`Envelope.from_bytes`'s `TamperedEnvelope`); (2) `envelope.schema` is not
`SCHEMA`; (3) `--household` was given and disagrees; (4) any row's `rung` is
`L5`/unreadable, or its `disposition` is not `render`, or its `value` is
missing, a `float`, unserializable, or over `MAX_VALUE_TEXT` — belt and
braces, since `compose()` never emits such a row, and one bad row refuses
the **whole** envelope (I-11) rather than a silent per-row skip;
(5) `envelope.envelope_id` is already in the fleet's `envelopes` table — a
re-ingest, checked before a single row is written; (6) the envelope was
composed *before* the one this household's anchor points at — ingesting it
would move the anchor backwards, so it is refused unless `--allow-stale`,
which ingests the rows and still leaves the anchor where it is. The anchor
only ever moves forward.

**A row's `value` may be `str`, a mapping, a list, a `bool`, an `int`, or
`None` (E7b, 2026-09-11).** `keep/store.canonical_value_text` is what turns
whichever one arrived into the JSON text `PostgresAdapter.insert`/`.write`
actually store, beside a `value_format` column saying that that is what the
text is — see `docs/DECISION-fleet-ingest.md` § "Structured values". A
`float` is not on the list: money is a decimal string, and a float neither
round-trips as one text nor stays finite. `decode_value` below is the
reverse, and it takes the `value_format` too, because rows the fleet wrote
*before* E7b hold the served string verbatim rather than JSON text and no
amount of parsing can tell the two apart.

**Sidecar rows upsert; canonical rows insert-only** — the fleet's own copy
of I-6's read-only canonical record: an existing key is counted as skipped,
never overwritten. **One transaction**: every row, the `envelopes` row, and
the `anchors` upsert commit together or not at all. **Interactive confirm**
(unless `--yes`, which skips only the prompt, never a refusal) prints the
destination host (password stripped) and the envelope id/row count — never a
row.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .store import (
    CANONICAL,
    SIDECAR,
    InvalidKey,
    VALUE_FORMAT_JSON,
    VALUE_FORMAT_RAW,
    MissingFleetExtra,
    PostgresAdapter,
    canonical_value_text,
    key as _record_key,
)
from .sync import SCHEMA, Envelope, TamperedEnvelope

__all__ = [
    "main", "ensure_schema", "ingest", "IngestRefused", "IngestResult",
    "decode_value", "Decoded", "MAX_VALUE_TEXT", "MAX_VALUE_DEPTH",
]

_TABLES = (CANONICAL, SIDECAR)
_READABLE_RUNGS = {"L1", "L2", "L3", "L4"}   # L5, or anything else, is refused

#: The largest canonical value text one row may carry, in bytes. Nothing
#: upstream caps a served value's size — `sync.compose()` frames whatever
#: `serve()` hands it — so the bound is declared here, at the fleet's own
#: door, and named in the refusal (E7b audit, 2026-09-11).
MAX_VALUE_TEXT = 64 * 1024

#: How deep a served value may nest. Python 3.12 stopped counting the json
#: encoder's C recursion against `sys.getrecursionlimit()`, so a 2000-deep
#: list that raised `RecursionError` on 3.10/3.11 serializes on 3.12 and
#: would have reached the dial. The bound is the fleet's own, named in the
#: refusal, and does not depend on which interpreter runs the ingest
#: (E7b, CI finding 2026-09-11). No module serves anything nested past two.
MAX_VALUE_DEPTH = 32


def _depth(value: Any) -> int:
    """Nesting depth of a JSON-shaped value, iteratively (so measuring a
    hostile value never recurses)."""
    deepest = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        node, level = stack.pop()
        if level > deepest:
            deepest = level
        if level > MAX_VALUE_DEPTH:
            return level
        if isinstance(node, dict):
            stack.extend((child, level + 1) for child in node.values())
        elif isinstance(node, (list, tuple)):
            stack.extend((child, level + 1) for child in node)
    return deepest


class IngestRefused(ValueError):
    """One of the five refusals in the module docstring. Raised before any
    row is written; the message never carries a record value, only
    references (a row's `item_id`, an envelope id, a rung name — I-15)."""


@dataclass(frozen=True)
class IngestResult:
    """What one successful ingest did — counts only, by reference, never a
    row (I-15)."""

    written: int
    skipped: int
    #: Whether this ingest moved the household's anchor. `False` only for an
    #: `--allow-stale` ingest of an envelope composed before the anchored
    #: one — the anchor never moves backwards.
    anchor_moved: bool = True


#: The only libpq keywords the confirm may echo back. An allow-list, not a
#: `password`-shaped deny-list: libpq spells a credential in more than one
#: keyword (`password`, `passfile`, `sslpassword`, `sslkey`, `require_auth`)
#: and gains more between releases, so anything not named here is dropped.
_SHOWABLE_KEYWORDS = ("host", "hostaddr", "port", "dbname")


def _redact_dsn(dsn: str) -> str:
    """Host, port and database only — never the password or username. What
    the interactive confirm may show.

    **libpq takes two DSN forms and this must redact both.** The URL form
    (`postgresql://user:pw@host:5432/db`) carries the password in the
    userinfo, and `urlsplit` strips it. The keyword/value form
    (`host=h port=5432 dbname=d user=u password=pw`) is not a URL at all:
    `urlsplit` returns it whole, with no scheme, as the path — so the first
    version of this function handed the confirm an unredacted `password=`
    and printed it to stdout (E4-postgres-fleet audit, 2026-09-11). The
    keyword form is now tokenized and rebuilt from `_SHOWABLE_KEYWORDS`
    alone, so an unrecognized keyword is dropped rather than shown.

    Fails closed: a DSN this cannot take apart is described, never echoed.

    `urllib.parse` is imported here, not at module load: `urllib` is on the
    package-wide network-import blocklist even though `urlsplit`/`urlunsplit`
    touch no network — the scan is conservative by name, the same way
    `keep/egress.py`'s default transport imports `urllib.request` inside a
    function rather than earning an exception to the rule."""
    import shlex
    from urllib.parse import urlsplit, urlunsplit

    try:
        parts = urlsplit(dsn)
    except ValueError:
        return "<a dsn that does not parse>"
    if parts.scheme.lower() in ("postgres", "postgresql"):
        netloc = parts.hostname or ""
        if parts.port:
            netloc += f":{parts.port}"
        # The query string goes too: `?passfile=` and `?sslpassword=` are
        # both credentials, and none of it is the destination.
        return urlunsplit((parts.scheme, netloc, parts.path, "", ""))

    try:
        tokens = shlex.split(dsn)
    except ValueError:
        return "<a dsn that does not parse>"
    shown = [
        t for t in tokens
        if "=" in t and t.split("=", 1)[0].strip().lower() in _SHOWABLE_KEYWORDS
    ]
    return " ".join(shown) if shown else "<a dsn with no host to show>"


def _now_iso() -> str:
    """One timestamp for the whole ingest, so every row of an envelope
    carries the same `synced_at`. Was `now()` in the SQL text, which is the
    server clock and a different value per statement; a parameter is also
    what `PostgresAdapter.insert/write` take, which is what lets `ingest()`
    use them instead of a second copy of their SQL."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate_rows(envelope: Envelope) -> None:
    """Belt and braces: `keep/sync.py`'s `compose()` never emits an `L5` or
    non-`render` row (they are dropped before the envelope is frozen), and
    this refuses to trust that promise without checking it again here, on
    the receiving end. One bad row refuses the whole envelope (I-11) —
    never a silent per-row skip."""
    for n, row in enumerate(envelope.rows, 1):
        if not isinstance(row, dict):
            raise IngestRefused(
                f"row {n} of this envelope is not a JSON object — refused by "
                "name rather than read as if it were one"
            )
        table = row.get("table")
        if table not in _TABLES:
            raise IngestRefused(
                f"row {row.get('item_id')!r} names table {table!r}, not one "
                f"of {_TABLES} — refused by name"
            )
        rung = row.get("rung")
        if rung not in _READABLE_RUNGS:
            raise IngestRefused(
                f"row {row.get('item_id')!r} carries rung {rung!r} — L5 or "
                "unreadable rows are never accepted by the fleet (I-39)"
            )
        disposition = row.get("disposition")
        if disposition != "render":
            # **Any** non-`render` disposition, not just one that also
            # carries a value. E7b first loosened this to "a non-render row
            # is fine as long as its `value` is `None`", on the reading that
            # a `DERIVE` row is a normal shape the fleet should accept; the
            # E7b audit read `compose()` and found it is not. `compose()`
            # drops every `DENY` row and every above-ceiling row before the
            # envelope is frozen, and `serve()` on `S4_EGRESS` with a
            # declared purpose renders L1–L4 and denies L5 — it never
            # returns `DERIVE` at all. So no envelope this codebase composes
            # has a non-`render` row in it, and one that has is forged or
            # hand-built. The loosened rule let such a row through to be
            # written as the text `null`, which on the canonical table is
            # insert-only: it would take that key permanently and the real
            # row could never land. Fail closed (I-11).
            raise IngestRefused(
                f"row {row.get('item_id')!r} carries disposition "
                f"{disposition!r}, not 'render' — refused by name"
            )
        # Every field that reaches a statement, checked before one is built.
        # A forged envelope hashes correctly over whatever it likes, so a row
        # can be missing `matter` entirely, or carry a NUL byte inside an
        # identifier psycopg refuses outright — each of which came out of
        # `ingest()` as a bare `KeyError`/`DataError` traceback before the
        # E4-postgres-fleet audit (2026-09-11) rather than a refusal by name
        # (I-11). `store.key()` is the same validator the household side's own
        # `Sidecar.put` runs (I-7), so the fleet accepts exactly the keys the
        # household could have written.
        try:
            _record_key(row.get("matter"), row.get("item_type"), row.get("item_id"))
        except InvalidKey as e:
            raise IngestRefused(
                f"row {n} of this envelope is not keyed by a usable "
                f"(matter, item_type, item_id): {e} — refused by name"
            ) from e
        # `value` may be `str`, a mapping, a list, a `bool`, an `int`, or
        # `None` (E7b, 2026-09-11) — anything `serve()` can return. The key
        # must be *present*: a row without one is a row this fleet cannot
        # know the value of, and reading a missing key as JSON `null` would
        # store a row saying the household holds nothing there (the refusal
        # the E4-postgres-fleet audit added, kept).
        if "value" not in row:
            raise IngestRefused(
                f"row {row.get('item_id')!r} carries no 'value' key at all — "
                "refused by name rather than stored as if the household held "
                "nothing there"
            )
        value = row["value"]
        # **A `float` is refused by name.** No module puts one in a record —
        # money is a two-decimal *string* through
        # `homestead_ledger.money.amount_text`, precisely because binary
        # floats are not amounts — and a float does not round-trip as one
        # text (`1.10` and `1.1` are one number and two texts, so one record
        # would sync as two rows). `NaN`/`Infinity` are floats too, which
        # Python's `json` writes as text no other JSON reader can parse.
        if isinstance(value, float):
            raise IngestRefused(
                f"row {row.get('item_id')!r} carries a float value — a "
                "float is not an amount (money is a decimal string) and does "
                "not round-trip as one text, so it is refused by name, and "
                "the value itself is not echoed (I-15)"
            )
        # Beyond that: anything `json.dumps` cannot turn into text at all —
        # a `bytes` or a `set` (`TypeError`), a circular reference
        # (`ValueError`), a structure nested past the interpreter's limit
        # (`RecursionError`, a backstop: the depth cap above refuses first,
        # since 3.12 no longer raises it). Only a hand-built `Envelope` can carry one,
        # and each came out of here as a bare traceback (not the middle two
        # only) until the E7b audit.
        if _depth(value) > MAX_VALUE_DEPTH:
            raise IngestRefused(
                f"row {row.get('item_id')!r} carries a value nested deeper "
                f"than {MAX_VALUE_DEPTH} levels — refused by name, and the "
                "value itself is not echoed (I-15)"
            )
        try:
            text = canonical_value_text(value)
        except (TypeError, ValueError, RecursionError) as e:
            raise IngestRefused(
                f"row {row.get('item_id')!r} carries a value json cannot "
                "serialize as canonical text — refused by name, and the "
                "value itself is not echoed (I-15)"
            ) from e
        # A cap, because nothing upstream has one: `sync.compose()` puts no
        # bound on a served value's size, so a 1 MB row composes, frames and
        # ingests today. 64 KiB is far above every record shape in the three
        # modules and far below what makes one row a problem to read.
        if len(text.encode("utf-8")) > MAX_VALUE_TEXT:
            raise IngestRefused(
                f"row {row.get('item_id')!r} carries a value whose canonical "
                f"text is over {MAX_VALUE_TEXT} bytes — refused by name, and "
                "the value itself is not echoed (I-15)"
            )


@dataclass(frozen=True)
class Decoded:
    """One fleet row's `value`, read back, and whether it had to be read as
    a pre-E7b row. `legacy` is `True` when the row's text was stored
    verbatim rather than as canonical JSON, in which case `value` is that
    text exactly as it is — never a guess at what JSON it might have been.
    """

    value: Any
    legacy: bool


def decode_value(text: str, *, value_format: str) -> Decoded:
    """The reverse of `store.canonical_value_text` — a fleet row's stored
    `value` column, read back as the JSON it started as (`str`, a mapping, a
    list, a `bool`, an `int`, or `None`). Nothing in `ingest()` itself calls
    this (a household's own record is never read back through the fleet); it
    is here for whoever does read a row off the fleet's own Postgres, so
    that reader is not left to re-derive the rule on their own.

    **`value_format` has no default, and that is the point (E7b audit,
    2026-09-11).** Rows written before E7b hold the served *string* stored
    verbatim, not JSON text — `2026-10-06`, not `"2026-10-06"` — because
    `PostgresAdapter.insert`/`.write` took an already-serialized blob and
    passed it straight to the statement. `json.loads` on such a row does not
    merely fail loudly: on `2026-10-06` it raises, but on a ledger amount
    `1450.00` it *succeeds* and returns the float `1450.0`, and on `123`,
    `true`, `null` the `int`, the `bool`, the `None` — a household's money
    silently re-typed. Text alone cannot tell the two encodings apart, so
    this is told instead, from the row's own `value_format`
    (`store.PostgresAdapter.read_value` selects both halves together);
    anything but `VALUE_FORMAT_JSON` comes back as the text it is, tagged.

    A `VALUE_FORMAT_JSON` row that will not parse comes back tagged too:
    the column and the text disagreeing is an answer for the caller, not a
    traceback (I-11).
    """
    if value_format != VALUE_FORMAT_JSON:
        return Decoded(text, legacy=True)
    try:
        return Decoded(json.loads(text), legacy=False)
    except ValueError:
        return Decoded(text, legacy=True)


def ensure_schema(conn: Any) -> None:
    """Idempotent DDL for the fleet's four tables — run at the top of every
    ingest so a fresh Postgres just works.

    `canonical`/`sidecar`: `(household, matter, item_type, item_id, value,
    value_format, envelope, synced_at)`, primary key on the first four.
    `value` is `TEXT`, never `JSONB` — the fleet is a mirror, not a judge
    (nothing here queries *into* a value), and `TEXT` keeps this DDL
    symmetric with `SQLiteAdapter`'s own `value TEXT` column; what it holds
    is canonical JSON text (`store.canonical_value_text`), not necessarily a
    bare string (E7b, 2026-09-11 — `docs/DECISION-fleet-ingest.md` §
    "Structured values"). `envelopes`: one row per ingested envelope,
    primary key `(household, envelope)` — the re-ingest check. `anchors`:
    one row per household, `head` set to the most recently ingested
    envelope's `head`, and only ever moved forward.

    **The `value_format` column is the E7b migration, and it is the whole of
    it (E7b audit, 2026-09-11).** Every row written before E7b holds the
    served string verbatim, which is *not* JSON text, so nothing can be read
    back by parsing alone. `ADD COLUMN IF NOT EXISTS … DEFAULT 'raw'` is
    idempotent, needs no table rewrite on any Postgres this ships against,
    and lands the truth in the existing rows by construction: they are the
    ones that were there before the column, and they are exactly the ones
    that are `raw`. Every row `PostgresAdapter.insert`/`.write` writes from
    here on says `json`. `fleet_cli.decode_value` requires the column's
    value and has no default for it.

    Commits its own DDL, so it is not part of the envelope's transaction: a
    rolled-back ingest can be re-run against tables that are still there.
    Every table name here is a module constant and every column name a
    literal — nothing in this function comes from an envelope.
    """
    with conn.cursor() as cur:
        for table in _TABLES:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {table} ("
                " household TEXT NOT NULL,"
                " matter TEXT NOT NULL,"
                " item_type TEXT NOT NULL,"
                " item_id TEXT NOT NULL,"
                " value TEXT NOT NULL,"
                f" value_format TEXT NOT NULL DEFAULT '{VALUE_FORMAT_RAW}',"
                " envelope TEXT NOT NULL,"
                " synced_at TIMESTAMPTZ NOT NULL,"
                " PRIMARY KEY (household, matter, item_type, item_id))"
            )
            cur.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
                f"value_format TEXT NOT NULL DEFAULT '{VALUE_FORMAT_RAW}'"
            )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS envelopes ("
            " household TEXT NOT NULL,"
            " envelope TEXT NOT NULL,"
            " head TEXT NOT NULL,"
            " composed_at TEXT NOT NULL,"
            " scope JSONB NOT NULL,"
            " row_count INTEGER NOT NULL,"
            " ingested_at TIMESTAMPTZ NOT NULL,"
            " PRIMARY KEY (household, envelope))"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS anchors ("
            " household TEXT PRIMARY KEY,"
            " head TEXT NOT NULL,"
            " envelope TEXT NOT NULL,"
            " updated_at TIMESTAMPTZ NOT NULL)"
        )
    conn.commit()


def _connect(dsn: str):
    """The one place this file reaches for `psycopg` — inside a function,
    never at module load (I-27, I-39)."""
    try:
        import psycopg
    except ImportError as e:
        raise MissingFleetExtra(
            "the 'fleet' extra is not installed — "
            'pip install "homestead-affairs[fleet]" to run homestead-fleet'
        ) from e
    return psycopg.connect(dsn)


def _anchor_composed_at(cur: Any, household: str) -> str | None:
    """When the envelope the household's anchor currently points at was
    composed, or `None` if there is no anchor yet. Joined rather than stored
    twice: `envelopes` already holds every `composed_at`, and a second copy
    on `anchors` is a second thing that can disagree."""
    cur.execute(
        "SELECT e.composed_at FROM anchors a JOIN envelopes e "
        "ON e.household = a.household AND e.envelope = a.envelope "
        "WHERE a.household = %s",
        (household,),
    )
    got = cur.fetchone()
    return got[0] if got is not None else None


#: Exactly what `sync._now_iso()` writes — `YYYY-MM-DDTHH:MM:SS+00:00`,
#: fixed width, always UTC. Anchored, so nothing is matched in the middle of
#: a longer string.
_COMPOSED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$")


def _is_stale(composed_at: str, anchored_at: str) -> bool:
    """Whether ingesting an envelope composed at `composed_at` would move
    the household's anchor *backwards* past `anchored_at`.

    **Ordered by `composed_at`, not by `head`.** `head` is the household
    `IntegrityLog`'s chain head — a hash, which has no order at all; two
    heads can only be compared by walking a chain the fleet does not have.
    `composed_at` is the same envelope's own ISO timestamp and is ordered,
    so it is what the anchor rule reads.

    **Compared as text, not parsed.** `sync._now_iso()` writes one
    fixed-width UTC format, and for that format byte order *is* time order —
    so this asks whether both strings are in that format and then compares
    them, rather than reaching for `fromisoformat`, which I-1/I-2 ban
    package-wide (`tests/test_invariants_dates.py`: one date parser, in
    `keep/dates.py`, and not that one). A string in any other shape has not
    been shown to be older *or* newer, so it is treated as stale — fail
    closed (I-11), and `--allow-stale` is the operator's way past it.

    **Equal is not stale.** `_now_iso()` has second resolution, and two
    envelopes composed in the same second are ordinary (the end-to-end test
    composes exactly that pair). Only strictly older is stale.
    """
    if not (
        isinstance(composed_at, str) and isinstance(anchored_at, str)
        and _COMPOSED_AT.match(composed_at) and _COMPOSED_AT.match(anchored_at)
    ):
        return True
    return composed_at < anchored_at


def ingest(
    envelope: Envelope,
    dsn: str,
    *,
    household: str | None = None,
    allow_stale: bool = False,
) -> IngestResult:
    """Ingest one already-parsed `Envelope`. Validates, then does the whole
    write — every row, the `envelopes` row, the `anchors` upsert — inside
    one transaction. See the module docstring for the refusal order.

    The rows go in through `store.PostgresAdapter`'s own `insert`/`write`,
    held open by `adapter.transaction()`, rather than through a second copy
    of their SQL here: the two copies had to agree on the columns *and* on
    both `ON CONFLICT` clauses, with nothing checking that they did
    (E4-postgres-fleet audit, 2026-09-11). The `envelopes` and `anchors`
    statements stay here — they are this command's own bookkeeping, not the
    record store's contract, and their table names are literals.
    """
    if envelope.schema != SCHEMA:
        raise IngestRefused(
            f"envelope declares schema {envelope.schema!r}, not {SCHEMA!r} "
            "— refused by name"
        )
    if household is not None and envelope.household != household:
        raise IngestRefused(
            "envelope household does not match --household — refused by "
            "name rather than ingested into the wrong household's rows"
        )
    _validate_rows(envelope)

    # Every statement below is scoped to this household: the adapter carries
    # it on each row, and the two bookkeeping statements pass it explicitly.
    adapter = PostgresAdapter(dsn, household=envelope.household, connect=_connect)
    synced_at = _now_iso()
    with adapter.transaction() as conn:
        # The DDL commits on its own, *inside* the block and before any data
        # statement, and that is deliberate: idempotent table creation is not
        # part of what this envelope did, and it is what lets a rolled-back
        # ingest be re-run against tables that are still there. Everything
        # after this line is the one unit that commits or does not.
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM envelopes WHERE household=%s AND envelope=%s",
                (envelope.household, envelope.envelope_id),
            )
            if cur.fetchone() is not None:
                raise IngestRefused(
                    f"envelope {envelope.envelope_id} is already ingested — "
                    "an envelope is ingested once, exactly as it is "
                    "delivered once (I-38's shape, at the fleet end)"
                )
            anchored_at = _anchor_composed_at(cur, envelope.household)

        stale = anchored_at is not None and _is_stale(envelope.composed_at, anchored_at)
        if stale and not allow_stale:
            raise IngestRefused(
                f"envelope {envelope.envelope_id} was composed before the "
                "one this household's anchor points at — ingesting it would "
                "move the anchor backwards, so it is refused by name. Pass "
                "--allow-stale to ingest its rows anyway; the anchor still "
                "does not move."
            )

        written = skipped = 0
        for row in envelope.rows:
            ref = (row["matter"], row["item_type"], row["item_id"])
            # The table is the module's own constant, never the row's own
            # string: `_validate_rows` has already refused anything but
            # these two, and the adapter validates again where it builds the
            # statement.
            if row["table"] == SIDECAR:
                adapter.write(
                    SIDECAR, ref, row["value"],
                    envelope=envelope.envelope_id, synced_at=synced_at,
                )
                written += 1
            elif row["table"] == CANONICAL:   # insert-only, the fleet's I-6
                if adapter.insert(
                    CANONICAL, ref, row["value"],
                    envelope=envelope.envelope_id, synced_at=synced_at,
                ):
                    written += 1
                else:
                    skipped += 1
            else:
                # Unreachable while `_validate_rows` runs first, and spelled
                # out anyway: an `else` that fell through to the canonical
                # table would write an unrecognized table's row into it.
                raise IngestRefused(
                    "a row names a table that is neither the sidecar nor the "
                    "canonical record — refused by name"
                )

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO envelopes (household, envelope, head, "
                "composed_at, scope, row_count, ingested_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (envelope.household, envelope.envelope_id, envelope.head,
                 envelope.composed_at, json.dumps(envelope.scope),
                 envelope.count, synced_at),
            )
            if not stale:
                cur.execute(
                    "INSERT INTO anchors (household, head, envelope, updated_at) "
                    "VALUES (%s,%s,%s,%s) "
                    "ON CONFLICT (household) DO UPDATE SET head=excluded.head, "
                    "envelope=excluded.envelope, updated_at=excluded.updated_at",
                    (envelope.household, envelope.head, envelope.envelope_id,
                     synced_at),
                )

    return IngestResult(written=written, skipped=skipped, anchor_moved=not stale)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(
        prog="homestead-fleet",
        description="The fleet side's own ingest — dials Postgres on the "
                     "operator's own act, never listens.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_ingest = sub.add_parser(
        "ingest", help="ingest one delivered homestead.sync/1 envelope"
    )
    p_ingest.add_argument("envelope", help="path to the envelope JSON file")
    p_ingest.add_argument(
        "--dsn", default=None,
        help="Postgres DSN; else HOMESTEAD_FLEET_DSN"
    )
    p_ingest.add_argument(
        "--household", default=None,
        help="the expected household id — refuses a mismatch by name"
    )
    p_ingest.add_argument(
        "--yes", action="store_true",
        help="skip the interactive confirm (never skips a refusal)"
    )
    p_ingest.add_argument(
        "--allow-stale", action="store_true",
        help="ingest an envelope composed before the anchored one; the "
             "anchor still does not move backwards"
    )
    args = parser.parse_args(argv)

    dsn = args.dsn or os.environ.get("HOMESTEAD_FLEET_DSN")
    if not dsn:
        print(
            "refused: no --dsn given and HOMESTEAD_FLEET_DSN is not set — "
            "the fleet side is never guessed at",
            file=sys.stderr,
        )
        return 2

    try:
        data = Path(args.envelope).read_bytes()
    except OSError as e:
        print(f"refused: cannot read {args.envelope}: {e}", file=sys.stderr)
        return 2

    try:
        envelope = Envelope.from_bytes(data)
    except TamperedEnvelope as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1

    if not args.yes:
        print(f"destination: {_redact_dsn(dsn)}")
        print(
            f"envelope: {envelope.envelope_id} "
            f"({envelope.count} rows) for household {envelope.household}"
        )
        answer = input("ingest? [y/N] ")
        if answer.strip().lower() != "y":
            print("refused: not confirmed at the preview")
            return 1

    try:
        result = ingest(
            envelope, dsn,
            household=args.household, allow_stale=args.allow_stale,
        )
    except (IngestRefused, MissingFleetExtra) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    except Exception as e:   # noqa: BLE001 — see below
        # Anything the driver raises — unreachable host, bad credentials, a
        # role without rights to run `ensure_schema`'s DDL — is a refusal to
        # the operator, not a traceback: before the E4-postgres-fleet audit
        # (2026-09-11) a mistyped `--dsn` ended the command in a
        # `psycopg.OperationalError` stack. The exception *class* is named
        # and the driver's own message is deliberately not echoed: libpq
        # error text is built from the conninfo, and this is the one code
        # path holding a credential. The destination is the already-redacted
        # form. Nothing was ingested — `ingest()` rolled back.
        print(
            f"refused: {type(e).__name__} from the fleet database at "
            f"{_redact_dsn(dsn)} — nothing was ingested",
            file=sys.stderr,
        )
        return 1

    print(f"rows written / skipped / refused: {result.written} / {result.skipped} / 0")
    if not result.anchor_moved:
        print(
            "note: --allow-stale — this envelope was composed before the "
            "anchored one, so the anchor was left where it is"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
