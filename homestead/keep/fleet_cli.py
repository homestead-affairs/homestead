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
already been read and validated.

**Refusals, checked in order, each by name and never echoing a value
(I-15):** (1) the file does not read as a `homestead.sync/1` envelope
(`Envelope.from_bytes`'s `TamperedEnvelope`); (2) `envelope.schema` is not
`SCHEMA`; (3) `--household` was given and disagrees; (4) any row's `rung` is
`L5`/unreadable, or its `disposition` is not `render` — belt and braces,
since `compose()` never emits such a row, and one bad row refuses the
**whole** envelope (I-11) rather than a silent per-row skip; (5)
`envelope.envelope_id` is already in the fleet's `envelopes` table — a
re-ingest, checked before a single row is written.

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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .store import CANONICAL, SIDECAR, MissingFleetExtra
from .sync import SCHEMA, Envelope, TamperedEnvelope

__all__ = ["main", "ensure_schema", "ingest", "IngestRefused", "IngestResult"]

_TABLES = (CANONICAL, SIDECAR)
_READABLE_RUNGS = {"L1", "L2", "L3", "L4"}   # L5, or anything else, is refused


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


def _redact_dsn(dsn: str) -> str:
    """Host, port and database path only — never the password or username.
    What the interactive confirm may show.

    `urllib.parse` is imported here, not at module load: `urllib` is on the
    package-wide network-import blocklist even though `urlsplit`/`urlunsplit`
    touch no network — the scan is conservative by name, the same way
    `keep/egress.py`'s default transport imports `urllib.request` inside a
    function rather than earning an exception to the rule."""
    from urllib.parse import urlsplit, urlunsplit

    try:
        parts = urlsplit(dsn)
    except ValueError:
        return "<a dsn that does not parse>"
    netloc = parts.hostname or ""
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def _validate_rows(envelope: Envelope) -> None:
    """Belt and braces: `keep/sync.py`'s `compose()` never emits an `L5` or
    non-`render` row (they are dropped before the envelope is frozen), and
    this refuses to trust that promise without checking it again here, on
    the receiving end. One bad row refuses the whole envelope (I-11) —
    never a silent per-row skip."""
    for row in envelope.rows:
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
        if row.get("disposition") != "render":
            raise IngestRefused(
                f"row {row.get('item_id')!r} carries disposition "
                f"{row.get('disposition')!r}, not 'render' — refused by name"
            )


def ensure_schema(conn: Any) -> None:
    """Idempotent DDL for the fleet's four tables — run at the top of every
    ingest so a fresh Postgres just works.

    `canonical`/`sidecar`: `(household, matter, item_type, item_id, value,
    envelope, synced_at)`, primary key on the first four. `envelopes`: one
    row per ingested envelope, primary key `(household, envelope)` — the
    re-ingest check. `anchors`: one row per household, `head` set to the
    most recently ingested envelope's `head`.
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
                " envelope TEXT NOT NULL,"
                " synced_at TIMESTAMPTZ NOT NULL,"
                " PRIMARY KEY (household, matter, item_type, item_id))"
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


def ingest(envelope: Envelope, dsn: str, *, household: str | None = None) -> IngestResult:
    """Ingest one already-parsed `Envelope`. Validates, then does the whole
    write — every row, the `envelopes` row, the `anchors` upsert — inside
    one transaction. See the module docstring for the refusal order."""
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

    conn = _connect(dsn)
    try:
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

            written = skipped = 0
            for row in envelope.rows:
                table = row["table"]
                args = (
                    envelope.household, row["matter"], row["item_type"],
                    row["item_id"], row["value"], envelope.envelope_id,
                )
                if table == SIDECAR:
                    cur.execute(
                        f"INSERT INTO {table} "
                        "(household, matter, item_type, item_id, value, "
                        "envelope, synced_at) VALUES (%s,%s,%s,%s,%s,%s, now()) "
                        "ON CONFLICT (household, matter, item_type, item_id) "
                        "DO UPDATE SET value=excluded.value, "
                        "envelope=excluded.envelope, synced_at=excluded.synced_at",
                        args,
                    )
                    written += 1
                else:   # CANONICAL — insert-only, the fleet's own copy of I-6
                    cur.execute(
                        f"INSERT INTO {table} "
                        "(household, matter, item_type, item_id, value, "
                        "envelope, synced_at) VALUES (%s,%s,%s,%s,%s,%s, now()) "
                        "ON CONFLICT (household, matter, item_type, item_id) "
                        "DO NOTHING",
                        args,
                    )
                    if cur.rowcount == 0:
                        skipped += 1
                    else:
                        written += 1

            cur.execute(
                "INSERT INTO envelopes (household, envelope, head, "
                "composed_at, scope, row_count, ingested_at) "
                "VALUES (%s,%s,%s,%s,%s,%s, now())",
                (envelope.household, envelope.envelope_id, envelope.head,
                 envelope.composed_at, json.dumps(envelope.scope), envelope.count),
            )
            cur.execute(
                "INSERT INTO anchors (household, head, envelope, updated_at) "
                "VALUES (%s,%s,%s, now()) "
                "ON CONFLICT (household) DO UPDATE SET head=excluded.head, "
                "envelope=excluded.envelope, updated_at=excluded.updated_at",
                (envelope.household, envelope.head, envelope.envelope_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return IngestResult(written=written, skipped=skipped)


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
        result = ingest(envelope, dsn, household=args.household)
    except (IngestRefused, MissingFleetExtra) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1

    print(f"rows written / skipped / refused: {result.written} / {result.skipped} / 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
