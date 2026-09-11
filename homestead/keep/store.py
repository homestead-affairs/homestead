"""The record store — one contract, swappable backings (the adapter seam).

`homestead.keep.record` proved the record layer on JSON files; `homestead-law`
proved it on SQLite. The two agreed on everything that matters — the *invariants*
— and differed only in how a blob is written and read back. So the invariants are
the **contract**, and the storage is an **adapter**: I-26's *"adapters live
outside the core"* made real.

  * **I-6 — the canonical record is read-only, by type.** `Canonical` reads and
    has no `put`; `Sidecar` writes. Both sit on the same adapter, different
    tables.
  * **I-7 — one key.** `key(matter, item_type, item_id)` is computed once and
    shared by read and write; the adapter never derives a key of its own.
  * **I-9 — writes never silently overwrite.** `Sidecar.put` refuses an occupied
    key via the adapter's atomic `insert` (O_EXCL on files, the primary key on
    SQL); an explicit overwrite reports what it displaced.
  * **I-11 at the storage boundary — absence fails closed to `L5`.** The store
    serializes a `Classified` to a blob and hydrates it back, and *that* is where
    a missing or unreadable rung, or an undecodable blob, reads `L5` — once, in
    the contract, so every backing fails closed by the same rule and no adapter
    re-implements it.

**The adapter stores an opaque blob.** It never sees a rung or a payload — it
`read`s and `write`s a string keyed by `(matter, item_type, item_id)`. So a new
backing (a Postgres adapter for the shared fleet engine) implements four small
methods and inherits every invariant above; and the store — the one place a raw
payload is reached (the chokepoint) — is backing-independent.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

#: Serializes directory creation in the file adapter. Not for the file write —
#: that is O_EXCL and race-safe on its own — but for `paths.ensure`, whose
#: `resolve()`-based containment check is fooled on Windows when one thread is
#: creating a deep path while another resolves it (the `\\?\` extended-length
#: prefix appears mid-creation, and the containment check spuriously fails). One
#: ensure at a time keeps the tree in a consistent state for the check.
_DIR_LOCK = threading.Lock()

from . import paths
from .rungs import (
    Classified,
    Disposition,
    Rung,
    Surface,
    _read_rung,
    serve,
)

__all__ = [
    "key", "InvalidKey", "RecordExists", "Replaced", "Due",
    "StorageAdapter", "FileAdapter", "SQLiteAdapter",
    "InvalidTable", "MissingFleetExtra", "PostgresAdapter",
    "Reader", "Sidecar", "Canonical",
]

Ref = tuple[str, str, str]

SIDECAR = "sidecar"
CANONICAL = "canonical"
DEADLINE = "deadline"


class InvalidKey(ValueError):
    """A key component that is not a usable identifier — empty, whitespace-only,
    or carrying a separator or NUL. A key is `(matter, item_type, item_id)`, and
    each component is an identifier, not a path."""


class RecordExists(Exception):
    """A write refused because the key is occupied (I-9)."""


@dataclass(frozen=True)
class Replaced:
    """What an explicit overwrite displaced (I-9)."""

    key: Ref
    previous: Classified


@dataclass(frozen=True)
class Due:
    """One deadline, read out of the store and already through the gate. `iso` is
    the parsed date (or `None` for a gap — an unparseable date, surfaced not
    dropped, I-8); `shown` is the gated display (the date for `L1`–`L3`, the
    derived instruction for `L4`). A sealed (`L5`) deadline never becomes a
    `Due`."""

    ref: Ref
    iso: str | None
    rung: Rung
    shown: str
    gap: bool


def key(matter: str, item_type: str, item_id: str) -> Ref:
    """Validate and return the key (I-7). Read and write both call this."""
    for name, value in (("matter", matter), ("item_type", item_type), ("item_id", item_id)):
        if not isinstance(value, str) or not value.strip():
            raise InvalidKey(f"{name} must be a non-empty string, not {value!r}")
        if value != value.strip():
            raise InvalidKey(f"{name}={value!r} has surrounding whitespace")
        if "/" in value or "\\" in value or value in (".", "..") or "\x00" in value:
            raise InvalidKey(
                f"{name}={value!r} is not a single identifier — a separator, a "
                "'..', or a NUL is not part of a key"
            )
    return (matter, item_type, item_id)


# ── serialize / hydrate — the invariant boundary (I-11), backing-independent ──

def _serialize(item: Classified) -> str:
    return json.dumps({"rung": item.rung.value, "payload": item.payload, "derived": item.derived})


def _hydrate(blob: str) -> Classified:
    """A `Classified` from a stored blob, failing closed to `L5` (I-11).

    An undecodable blob, a missing or unreadable rung (`bool`, `int`, `"L9"`), or
    a readable rung that cannot form a valid `Classified` (an `L3` whose derived
    form is gone) all read `L5` — never `L1`, never a crash. This is the *one*
    place the fail-closed rule lives; every adapter inherits it.
    """
    try:
        raw = json.loads(blob)
    except (ValueError, TypeError):
        return Classified(Rung.L5, None)
    if not isinstance(raw, dict):
        return Classified(Rung.L5, None)
    payload = raw.get("payload")
    rung = _read_rung(raw.get("rung"))
    if rung is None:
        return Classified(Rung.L5, payload)
    try:
        return Classified(rung, payload, raw.get("derived"))
    except Exception:
        return Classified(Rung.L5, payload)


# ── the adapter contract ─────────────────────────────────────────────────────

class StorageAdapter(ABC):
    """Raw blob storage keyed by `(table, ref)`. An adapter never sees a rung or a
    payload — it stores and returns opaque strings. Four methods, and every
    record invariant lives above them in the store."""

    @abstractmethod
    def read(self, table: str, ref: Ref) -> str | None:
        """The blob at `ref`, or `None` if there is no record there."""

    @abstractmethod
    def read_matter(self, table: str, matter: str) -> list[tuple[Ref, str]]:
        """Every `(ref, blob)` under `matter`, ordered stably."""

    @abstractmethod
    def insert(self, table: str, ref: Ref, blob: str) -> bool:
        """Write only if `ref` is free. Return `True` on success, `False` if the
        key is already occupied — **atomically** (I-9); no check-then-write gap."""

    @abstractmethod
    def write(self, table: str, ref: Ref, blob: str) -> None:
        """Write unconditionally (the overwrite path)."""


class FileAdapter(StorageAdapter):
    """Blobs as JSON files under the `/.homestead` root — `sidecar/` for the
    app's writes, `record/` for the canonical record. The format `keep.record`
    already wrote, so existing files read back unchanged."""

    _DIRS = {SIDECAR: "sidecar", CANONICAL: "record"}

    def _path(self, table: str, ref: Ref) -> Path:
        return paths.home() / self._DIRS[table] / ref[0] / ref[1] / f"{ref[2]}.json"

    def read(self, table: str, ref: Ref) -> str | None:
        target = self._path(table, ref)
        try:
            return target.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (UnicodeDecodeError, OSError):
            return "corrupt"   # an unreadable file — hydrates to L5 (I-11)

    def read_matter(self, table: str, matter: str) -> list[tuple[Ref, str]]:
        base = paths.home() / self._DIRS[table] / matter
        out: list[tuple[Ref, str]] = []
        if not base.is_dir():
            return out
        for type_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            for f in sorted(type_dir.glob("*.json")):
                blob = self.read(table, (matter, type_dir.name, f.stem))
                if blob is not None:
                    out.append(((matter, type_dir.name, f.stem), blob))
        return out

    def insert(self, table: str, ref: Ref, blob: str) -> bool:
        target = self._path(table, ref)
        with _DIR_LOCK:
            paths.ensure(target.parent)
        try:
            with open(target, "x", encoding="utf-8") as fh:   # O_EXCL — atomic (I-9)
                fh.write(blob)
        except FileExistsError:
            return False
        return True

    def write(self, table: str, ref: Ref, blob: str) -> None:
        target = self._path(table, ref)
        with _DIR_LOCK:
            paths.ensure(target.parent)
        target.write_text(blob, encoding="utf-8")


class SQLiteAdapter(StorageAdapter):
    """Blobs in a SQLite table, keyed by `(matter, item_type, item_id)` — the
    primary key that makes `insert` atomic (I-9). The value is one opaque column;
    a backing that wants to gate by rung (the Postgres fleet store) adds its own
    indexed column, but the contract does not require it."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db = Path(db_path) if db_path is not None else paths.home() / "homestead.db"

    @contextmanager
    def _connect(self, table: str) -> Iterator[sqlite3.Connection]:
        paths.ensure(self._db.parent)
        conn = sqlite3.connect(self._db)
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "  matter TEXT NOT NULL, item_type TEXT NOT NULL, item_id TEXT NOT NULL,"
            "  value TEXT NOT NULL, PRIMARY KEY (matter, item_type, item_id))"
        )
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def read(self, table: str, ref: Ref) -> str | None:
        with self._connect(table) as conn:
            row = conn.execute(
                f"SELECT value FROM {table} WHERE matter=? AND item_type=? AND item_id=?",
                ref,
            ).fetchone()
        return row[0] if row is not None else None

    def read_matter(self, table: str, matter: str) -> list[tuple[Ref, str]]:
        with self._connect(table) as conn:
            rows = conn.execute(
                f"SELECT item_type, item_id, value FROM {table} WHERE matter=? "
                "ORDER BY item_type, item_id",
                (matter,),
            ).fetchall()
        return [((matter, it, ii), value) for it, ii, value in rows]

    def insert(self, table: str, ref: Ref, blob: str) -> bool:
        with self._connect(table) as conn:
            try:
                conn.execute(
                    f"INSERT INTO {table} (matter, item_type, item_id, value) VALUES (?,?,?,?)",
                    (*ref, blob),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def write(self, table: str, ref: Ref, blob: str) -> None:
        with self._connect(table) as conn:
            conn.execute(
                f"INSERT INTO {table} (matter, item_type, item_id, value) VALUES (?,?,?,?) "
                "ON CONFLICT(matter, item_type, item_id) DO UPDATE SET value=excluded.value",
                (*ref, blob),
            )


class InvalidTable(ValueError):
    """A table name that is not `{SIDECAR, CANONICAL}`. `PostgresAdapter`
    builds its statements with an f-string for the table name — `psycopg`
    cannot parameterize an identifier — so this is the guard between a
    caller's string and the SQL text; every value stays a `%s` placeholder.
    Refused before a cursor is ever opened. Planted at `"sidecar; DROP TABLE
    envelopes"` and `"sidecar "` (a trailing space is a real, different
    identifier) during the E4-postgres-fleet build."""


class MissingFleetExtra(ImportError):
    """`psycopg` is not installed. `PostgresAdapter` is reached only by the
    fleet's own `homestead-fleet ingest`, behind the optional `fleet` extra,
    and imports `psycopg` lazily, inside this constructor and nowhere at
    module load (I-27, I-39) — a checkout without the extra still imports
    this whole module. Refused by name rather than a bare
    `ModuleNotFoundError` a caller has to guess the fix for."""


_FLEET_TABLES = frozenset({SIDECAR, CANONICAL})


class PostgresAdapter:
    """The fleet's own backing — a shared Postgres database one household's
    record is copied *to*, on `homestead-fleet ingest`'s own act
    (`keep/fleet_cli.py`). Never constructed by `Sidecar`/`Canonical` on the
    household side, which never holds a DSN (open item 7;
    `docs/DECISION-fleet-ingest.md`).

    The same four-method shape `StorageAdapter` documents — `read`,
    `read_matter`, `insert`, `write` — scoped to one `household` fixed at
    construction, so every statement carries it. Does not literally
    subclass `StorageAdapter`'s ABC: `insert`/`write` here also take the
    envelope id and synced-at timestamp the fleet's own columns carry, and
    `insert` returns the affected row count rather than a bare bool, so a
    caller can tell "already there" (`0`) from "written" (`1`) without a
    second read — `keep/fleet_cli.py`'s canonical insert-only count depends
    on it.

    `psycopg` is imported inside `__init__`, never at module load — the one
    caller that ever needs it already needs the extra. Table names are
    validated against `{SIDECAR, CANONICAL}` **in the method that builds the
    statement**, not by a caller who promises to have checked earlier — see
    `InvalidTable`.

    `transaction()` makes the four methods composable: inside it they run on
    one connection and commit nothing, so a caller that must write several
    rows and its own bookkeeping as a unit uses *these* statements rather
    than writing a second copy of them (E4-postgres-fleet audit, 2026-09-11
    — `keep/fleet_cli.py`'s `ingest()` had duplicated both `ON CONFLICT`
    clauses for exactly that reason).
    """

    def __init__(self, dsn: str, *, household: str, connect: Any = None) -> None:
        """`connect` is the seam `keep/fleet_cli.py` passes its own
        `_connect()` through, so one process has exactly one place that
        reaches for `psycopg`. A caller that supplies it has already taken
        responsibility for opening a connection, so this constructor does
        not import `psycopg` at all — which is what lets the no-database
        tests drive `ingest()` on a fake connection with the `fleet` extra
        uninstalled."""
        if connect is None:
            try:
                import psycopg
            except ImportError as e:
                raise MissingFleetExtra(
                    "the 'fleet' extra is not installed — "
                    'pip install "homestead-affairs[fleet]" to use PostgresAdapter'
                ) from e
            self._open = lambda: psycopg.connect(dsn)
        else:
            self._open = lambda: connect(dsn)
        self._dsn = dsn
        self._household = household
        #: The connection an open `transaction()` holds, or `None`. Every
        #: statement below runs on it while it is set, and commits nothing
        #: — the transaction owns the commit.
        self._conn: Any = None

    def _connect(self):
        return self._open()

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """One connection, one transaction, for a caller that must write
        several rows *and* its own bookkeeping as a single unit.

        `keep/fleet_cli.py`'s `ingest()` is that caller: every row, the
        `envelopes` row and the `anchors` upsert commit together or not at
        all. Without this it had to duplicate `insert`/`write`'s SQL —
        because those commit per call — and two copies of an `ON CONFLICT`
        clause are two things that can drift apart. Inside the block,
        `read`/`read_matter`/`insert`/`write` run on this connection and
        commit nothing; the yielded connection is there for the statements
        the adapter contract does not cover (the fleet's own `envelopes`
        and `anchors` tables, whose names are literals).

        Commits on a clean exit, rolls back on any exception — including
        `KeyboardInterrupt`, which is the one an operator running an ingest
        by hand is most likely to produce.
        """
        if self._conn is not None:
            raise RuntimeError(
                "PostgresAdapter.transaction() does not nest — one adapter "
                "holds at most one open transaction"
            )
        conn = self._connect()
        self._conn = conn
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            self._conn = None
            conn.close()

    @contextmanager
    def _cursor(self) -> Iterator[Any]:
        """A cursor on the open `transaction()` if there is one — which
        then owns the commit — or one on a connection of this call's own,
        committed and closed here."""
        if self._conn is not None:
            with self._conn.cursor() as cur:
                yield cur
            return
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _table(table: str) -> str:
        if table not in _FLEET_TABLES:
            raise InvalidTable(
                f"table {table!r} is not one of {sorted(_FLEET_TABLES)} — "
                "refused before it reaches any SQL text"
            )
        return table

    def read(self, table: str, ref: Ref) -> str | None:
        table = self._table(table)
        matter, item_type, item_id = ref
        with self._cursor() as cur:
            cur.execute(
                f"SELECT value FROM {table} WHERE household=%s AND matter=%s "
                "AND item_type=%s AND item_id=%s",
                (self._household, matter, item_type, item_id),
            )
            row = cur.fetchone()
        return row[0] if row is not None else None

    def read_matter(self, table: str, matter: str) -> list[tuple[Ref, str]]:
        table = self._table(table)
        with self._cursor() as cur:
            cur.execute(
                f"SELECT item_type, item_id, value FROM {table} "
                "WHERE household=%s AND matter=%s ORDER BY item_type, item_id",
                (self._household, matter),
            )
            rows = cur.fetchall()
        return [((matter, it, ii), value) for it, ii, value in rows]

    def insert(self, table: str, ref: Ref, blob: str, *, envelope: str, synced_at: str) -> int:
        """`INSERT … ON CONFLICT DO NOTHING`, returning the row count. `0`
        means the key was already there — canonical rows are append-only,
        and `keep/fleet_cli.py` counts a `0` here as skipped, never
        overwritten."""
        table = self._table(table)
        matter, item_type, item_id = ref
        with self._cursor() as cur:
            cur.execute(
                f"INSERT INTO {table} "
                "(household, matter, item_type, item_id, value, envelope, synced_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (household, matter, item_type, item_id) DO NOTHING",
                (self._household, matter, item_type, item_id, blob, envelope, synced_at),
            )
            count = cur.rowcount
        return count

    def write(self, table: str, ref: Ref, blob: str, *, envelope: str, synced_at: str) -> None:
        """Upsert — the sidecar's shape: a later sync of the same key
        replaces it (never used for the canonical table, which is
        insert-only at the fleet too)."""
        table = self._table(table)
        matter, item_type, item_id = ref
        with self._cursor() as cur:
            cur.execute(
                f"INSERT INTO {table} "
                "(household, matter, item_type, item_id, value, envelope, synced_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (household, matter, item_type, item_id) DO UPDATE SET "
                "value=excluded.value, envelope=excluded.envelope, "
                "synced_at=excluded.synced_at",
                (self._household, matter, item_type, item_id, blob, envelope, synced_at),
            )


def _default_adapter() -> StorageAdapter:
    """The shipped app is self-contained on SQLite. A caller passes `FileAdapter()`
    or a Postgres adapter explicitly when it wants another backing."""
    return SQLiteAdapter()


# ── the store — the invariants, over any adapter ─────────────────────────────

class Reader:
    """The read half — `get`, `has`, `records`, `advise`, `deadlines` — over one
    table of one adapter. `Canonical` and `Sidecar` differ only in the table and
    whether they can also write."""

    _table: str

    def __init__(self, adapter: StorageAdapter | None = None) -> None:
        self._adapter = adapter if adapter is not None else _default_adapter()

    def get(self, matter: str, item_type: str, item_id: str) -> Classified:
        blob = self._adapter.read(self._table, key(matter, item_type, item_id))
        if blob is None:
            raise KeyError(f"{matter}/{item_type}/{item_id}: no such record")
        return _hydrate(blob)

    def has(self, matter: str, item_type: str, item_id: str) -> bool:
        return self._adapter.read(self._table, key(matter, item_type, item_id)) is not None

    def records(self, matter: str) -> list[tuple[Ref, Classified]]:
        key(matter, "_probe_", "_probe_")
        return [(ref, _hydrate(blob)) for ref, blob in self._adapter.read_matter(self._table, matter)]

    def advise(self, matter: str, item_type: str, item_id: str) -> tuple:
        from .advise import advise as _advise

        record = self.get(matter, item_type, item_id)
        return _advise(record.rung, record.payload)

    def deadlines(self, matter: str) -> list[Due]:
        """This matter's deadlines, parsed and gated. The store is the payload
        boundary, so the date is parsed and the display served *here*. An
        unparseable date is a gap (I-8), a sealed deadline is dropped."""
        from .dates import UnparseableDate, parse_deadline

        out: list[Due] = []
        for ref, record in self.records(matter):
            if ref[1] != DEADLINE:
                continue
            served = serve(record, Surface.S1_LIST)
            if served.disposition is Disposition.DENY:
                continue
            try:
                iso: str | None = parse_deadline(record.payload).iso
                gap = False
            except UnparseableDate:
                iso, gap = None, True
            out.append(Due(ref=ref, iso=iso, rung=record.rung, shown=str(served.value), gap=gap))
        return out


class Canonical(Reader):
    """A read-only handle over the canonical record (I-6, I-36) — no write method
    of any kind."""

    _table = CANONICAL


class Sidecar(Reader):
    """The app's own record table — the only handle that writes (I-6)."""

    _table = SIDECAR

    def put(
        self,
        matter: str,
        item_type: str,
        item_id: str,
        item: Classified,
        *,
        overwrite: bool = False,
    ) -> Replaced | None:
        """Persist a `Classified`. Refuse an occupied key, or report the
        replacement (I-9). A `Classified` and nothing else — an unclassified
        value has no rung and must not acquire one here (I-11)."""
        if not isinstance(item, Classified):
            raise TypeError(
                f"put() stores a Classified, not {type(item).__name__} — an "
                "unclassified value has no rung (I-11)"
            )
        ref = key(matter, item_type, item_id)
        blob = _serialize(item)
        if not overwrite:
            if not self._adapter.insert(self._table, ref, blob):
                raise RecordExists(
                    f"{ref[0]}/{ref[1]}/{ref[2]} already exists. A write never "
                    "silently overwrites (I-9): pass overwrite=True to replace it."
                )
            return None
        prior = self._adapter.read(self._table, ref)
        previous = _hydrate(prior) if prior is not None else None
        self._adapter.write(self._table, ref, blob)
        return Replaced(key=ref, previous=previous) if previous is not None else None
