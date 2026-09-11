"""Sync — the operator's own record, copied to the household's own fleet
store, on an explicit per-call act and never in the background.

Decision 5 of the affairs build plan (`docs/PLAN-affairs-face.md` § Wave 4,
`E4-sync-core`): `Purpose.SYNC` (`docs/DECISION-purpose-sync.md`, ratified) is
a word with no sentence until this module writes one. Three things happen
here, in order, and nowhere else:

  * **`SyncScope`** — what the operator named: matters, optionally item
    types, a ceiling, which tables. Empty matters, empty tables, or an `L5`
    ceiling is refused **at construction** (I-40, ratified by the E4-sync-core audit,
    2026-09-11) — there is no
    `"all"` matter.
  * **`compose()`** — scores every candidate on `S4_EGRESS` with
    `Purpose.SYNC`, exactly like `keep/export.py` scores one. A `DENY`
    disposition, or a rung above the scope's own ceiling, is **dropped, not
    derived** (open item 5, `docs/DECISION-sync-envelope-and-consent.md`) —
    freezing what survives into one `Envelope`.
  * **`deliver()`** — exactly one of a URL (through `keep/egress.send`, same
    per-call confirm) or an `O_EXCL` file drop into an absolute directory the
    caller names (`default_drop_dir()` is `exports_dir()/sync/`, the one the
    plan names — offered, never applied, so no envelope ever lands somewhere
    nobody chose). A confirm must return `True`, not merely something truthy.
    A refused confirm ledgers nothing (I-37). A success writes
    **one** `IntegrityLog` row and **one** `VisibleLog` row, both references
    (I-15); a second `deliver` of an already-ledgered envelope is refused
    (I-38 — "ledgered once"). I-37/I-38/I-40 were provisional numbers
    until `docs/DECISION-sync-envelope-and-consent.md` was ratified.

**The chokepoint holds here as it does in `keep/export.py`.** Neither the
gate nor the store: every candidate is handed to `serve()` and only
`Served.value`/`Served.disposition` are read — never `Classified.payload`.
`.derived` is read directly, which is not the payload; it is the stand-in a
classification already made servable, carried for reference even on a
rendered row (`tests/test_invariants_sync.py` scans this file for `.payload`
in addition to the whole-package `tests/test_invariants_chokepoint.py`).

**`HOMESTEAD_FLEET_URL` is not read here.** Where a sync goes is a module
concern (Wave 5) — this function takes `url=`/`drop_dir=` as plain arguments.
A destination is a place to send to, never a permission to send; reading an
environment variable inside the function that ledgers the act would make the
destination ambient rather than something the caller — and the confirm — see.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from . import egress, paths
from .egress import EgressRefused, Wire
from .household import household_id
from .logs import Event, IntegrityLog, VisibleLog
from .rungs import Disposition, Purpose, Rung, Surface, serve
from .rungs import compose as _rung_max
from .store import CANONICAL, SIDECAR, Reader

__all__ = [
    "SCHEMA", "UnnamedScope", "TamperedEnvelope", "AlreadyDelivered",
    "SyncScope", "Envelope", "Receipt", "compose", "deliver", "ledger",
    "default_drop_dir",
]

SCHEMA = "homestead.sync/1"
_TABLES = frozenset({SIDECAR, CANONICAL})


class UnnamedScope(ValueError):
    """A `SyncScope` that names too little to sync anything (I-40,
    ratified): no matters, no tables, an `L5` ceiling, or a table outside
    `{sidecar, canonical}`. A `ValueError`, never a `TypeError` — a scope
    that declines to sync is a refusal on the *value* offered, not a
    malformed call site."""


class TamperedEnvelope(ValueError):
    """An envelope whose bytes do not hash to the id they carry. Raised only
    by `Envelope.from_bytes()` — refused by name (I-11), never repaired."""


class AlreadyDelivered(PermissionError):
    """An envelope already ledgered, or a file drop that already exists
    (I-38 — "ledgered once"). Two mechanisms raise this: the
    `IntegrityLog` check before anything is sent, and the file drop's own
    `O_EXCL` create as the structural backstop if two calls race."""


def _canonical_bytes(obj: dict[str, Any]) -> bytes:
    """Sorted keys, no whitespace — the one encoding `envelope_id` is a hash
    of, and `to_bytes()` freezes. One encoder, not two that can drift
    (`keep/paths.py`'s issue #23)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _envelope_id(fields: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(fields)).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class SyncScope:
    """What the operator named — nothing more, and never "all" (I-40).

    `matters`/`tables` are non-empty tuples; `item_types`, when given,
    narrows which item types are included (`None` = every item type under a
    named matter). `ceiling` bounds a synced row *on top of* whatever
    `S4_EGRESS` itself allows under `Purpose.SYNC` — see `compose()`.

    Refused by `UnnamedScope`: empty `matters`, empty `tables`, `ceiling is
    L5`, or a `tables` entry outside `{"sidecar", "canonical"}`. Refused by
    `TypeError`: any field holding the wrong *kind* of value — a malformed
    call site, not a declined scope.
    """

    matters: tuple[str, ...]
    item_types: tuple[str, ...] | None
    ceiling: Rung
    tables: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.matters, tuple):
            raise TypeError(f"matters must be a tuple, not {type(self.matters).__name__}")
        if self.item_types is not None and not isinstance(self.item_types, tuple):
            raise TypeError(
                f"item_types must be a tuple or None, not {type(self.item_types).__name__}"
            )
        if not isinstance(self.tables, tuple):
            raise TypeError(f"tables must be a tuple, not {type(self.tables).__name__}")
        if not isinstance(self.ceiling, Rung):
            raise TypeError(f"ceiling must be a Rung, not {type(self.ceiling).__name__}")

        if not self.matters:
            raise UnnamedScope(
                "a SyncScope must name at least one matter (I-40) — there is "
                "no 'all' matter"
            )
        if not self.tables:
            raise UnnamedScope("a SyncScope must name at least one table (I-40)")
        if self.ceiling is Rung.L5:
            raise UnnamedScope(
                "a SyncScope's ceiling may not be L5 (I-13, I-40) — L5 has no "
                "override anywhere"
            )
        unknown = sorted(set(self.tables) - _TABLES)
        if unknown:
            raise UnnamedScope(
                f"unknown table(s) {unknown} — must be a subset of {sorted(_TABLES)}"
            )

    def as_dict(self) -> dict[str, Any]:
        """The JSON-shaped form an `Envelope` carries. Never round-tripped
        back through `__init__` — an `Envelope` records what a compose did,
        not a live scope."""
        return {
            "matters": list(self.matters),
            "item_types": list(self.item_types) if self.item_types is not None else None,
            "ceiling": self.ceiling.value,
            "tables": list(self.tables),
        }


@dataclass(frozen=True)
class Envelope:
    """What one `compose()` produced — frozen, content-addressed, the only
    thing `deliver()` ever sends.

    `envelope_id` is the sha256 of the canonical JSON of every other field.
    `to_bytes()` returns that same encoding, `envelope_id` included, so a
    byte written or sent is reproducible via `from_bytes()`.
    """

    schema: str
    household: str
    composed_at: str
    head: str
    scope: dict[str, Any]
    rows: tuple[dict[str, Any], ...]
    count: int
    envelope_id: str

    def _identity_fields(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "household": self.household,
            "composed_at": self.composed_at, "head": self.head,
            "scope": self.scope, "rows": list(self.rows), "count": self.count,
        }

    def to_dict(self) -> dict[str, Any]:
        """Every field, `envelope_id` included — what `deliver()` hands
        `egress.send` for the URL leg."""
        out = self._identity_fields()
        out["envelope_id"] = self.envelope_id
        return out

    def to_bytes(self) -> bytes:
        """The frozen canonical bytes — the file leg, and what
        `from_bytes()` re-verifies."""
        return _canonical_bytes(self.to_dict())

    @classmethod
    def from_bytes(cls, data: bytes) -> "Envelope":
        """Rebuild an `Envelope`, refusing a byte that does not hash to the
        id it claims (`TamperedEnvelope`, I-11) rather than trusting it."""
        try:
            raw = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise TamperedEnvelope("not a decodable homestead.sync envelope") from e
        if not isinstance(raw, dict):
            raise TamperedEnvelope("an envelope must be a JSON object")
        try:
            claimed = raw["envelope_id"]
            identity = {
                k: raw[k] for k in
                ("schema", "household", "composed_at", "head", "scope", "rows", "count")
            }
        except KeyError as e:
            raise TamperedEnvelope(f"envelope is missing a required field: {e}") from e
        if not isinstance(claimed, str) or claimed != _envelope_id(identity):
            raise TamperedEnvelope(
                "envelope_id does not match its contents — refused rather than trusted (I-11)"
            )
        # A matching id proves the bytes were not edited *after* composition. It
        # proves nothing about whether they were ever a `homestead.sync/1`
        # envelope: an id computed over rubbish matches its rubbish. Forged
        # envelopes with a correct hash and `count=99` over one row, a `schema`
        # of `homestead.sync/99`, and `rows` as an object rather than a list all
        # verified during the E4-sync-core audit (2026-09-11) — the last of them
        # silently becoming a one-tuple of a dict *key*. So the shape is checked
        # too, and refused by name (I-11) rather than handed back half-read.
        if identity["schema"] != SCHEMA:
            raise TamperedEnvelope(
                f"envelope declares schema {identity['schema']!r}, and this is "
                f"the {SCHEMA} reader — refused rather than read as if it were one"
            )
        if not isinstance(identity["rows"], list):
            raise TamperedEnvelope("an envelope's rows must be a JSON array")
        if identity["count"] != len(identity["rows"]):
            raise TamperedEnvelope(
                f"envelope claims {identity['count']!r} rows and carries "
                f"{len(identity['rows'])} — a count is what the operator is "
                "shown and what the fleet records, so a disagreeing one is "
                "refused, not reconciled"
            )
        return cls(
            schema=identity["schema"], household=identity["household"],
            composed_at=identity["composed_at"], head=identity["head"],
            scope=identity["scope"], rows=tuple(identity["rows"]),
            count=identity["count"], envelope_id=claimed,
        )


@dataclass(frozen=True)
class Receipt:
    """What a delivery produced — a reference, not content, the same shape
    `export.ExportReceipt` gives an export."""

    envelope_id: str
    household: str
    destination: str
    rows: int
    head: str


def ledger() -> IntegrityLog:
    """The same shared `IntegrityLog` `keep/export.py`'s `ledger()` writes
    to — one hash chain for every act this household ledgers — anchor held
    off the log's own tree (willow-mcp #280)."""
    return IntegrityLog(
        paths.logs_dir() / "integrity.jsonl",
        anchor_path=paths.anchors_dir() / "integrity.head",
    )


def default_drop_dir() -> Path:
    """Where a file drop goes when a caller has no reason to choose otherwise
    — `exports_dir()/sync/`, named by the plan's decision 5.

    A *default a caller can ask for*, not a default `deliver()` applies: a
    destination that appeared because none was given is a destination the
    confirm did not choose and the operator never named. `deliver()` still
    requires exactly one of `url=`/`drop_dir=`; Wave 5's CLI passes this.
    """
    return paths.exports_dir() / "sync"


def _within_ceiling(rung: Rung, ceiling: Rung) -> bool:
    """`rung` at or below `ceiling`, read off the public `rungs.compose`
    (max-of-inputs) rather than a private ordering table — a module outside
    the gate should not reach for a private name to ask a question the gate
    already answers publicly."""
    return _rung_max(rung, ceiling) is ceiling


def compose(readers: Mapping[str, Reader], scope: SyncScope) -> Envelope:
    """Score every candidate on `S4_EGRESS` under `Purpose.SYNC`, and freeze
    what survives into an `Envelope`.

    `readers` maps a table name (`"sidecar"`, `"canonical"`) to the `Reader`
    (`store.Sidecar()`/`store.Canonical()`) every other consumer already
    uses — this function never touches a `StorageAdapter` or a raw blob.

    For each table in `scope.tables`, each matter in `scope.matters`, every
    record `reader.records(matter)` returns is served on `S4_EGRESS` with
    `Purpose.SYNC` (I-16 — through `serve()`, never `.payload`). A row is
    **dropped entirely** — not marked, not derived — when either is true:

      * `served.disposition is Disposition.DENY` (the datum is `L5`, or
        unclassified and so read as `L5`); or
      * `served.rung` is above `scope.ceiling` — the scope's own, stricter
        bound, checked *in addition to* what `S4_EGRESS` permits. Decision
        5: a rung above the sync ceiling is dropped, not derived. In
        practice `S4_EGRESS` with a declared purpose never returns `DERIVE`
        (its with-purpose ceiling is `L4`, the highest rung below `L5`), so
        `scope.ceiling` is what actually lets an operator hold a sync to,
        say, `L1` even though the surface itself would render up to `L4`.

    A surviving row is `{table, matter, item_type, item_id, rung,
    disposition, value, derived}` — `value` is `Served.value`; `derived` is
    the record's own `Classified.derived`, `None` where none was needed.
    """
    rows: list[dict[str, Any]] = []
    for table in scope.tables:
        reader = readers[table]
        for matter in scope.matters:
            for ref, classified in reader.records(matter):
                item_type, item_id = ref[1], ref[2]
                if scope.item_types is not None and item_type not in scope.item_types:
                    continue
                served = serve(classified, Surface.S4_EGRESS, purpose=Purpose.SYNC)
                if served.disposition is Disposition.DENY:
                    continue
                if not _within_ceiling(served.rung, scope.ceiling):
                    continue
                rows.append({
                    "table": table, "matter": matter, "item_type": item_type,
                    "item_id": item_id, "rung": served.rung.value,
                    "disposition": served.disposition.value,
                    "value": served.value, "derived": classified.derived,
                })

    # Sorted, so the id is addressed by *content* and nothing else. Row order
    # was the store's iteration order, which is not one order: `FileAdapter`
    # sorts `<item_id>.json` filenames and `SQLiteAdapter` sorts `item_id`
    # columns, and they disagree wherever a `.` or a `-` is in an id — `a`,
    # `a-1`, `a.1` came back in two different orders during the E4-sync-core
    # audit (2026-09-11), so one store composed twice through two backings gave
    # two envelope ids for identical rows, and `AlreadyDelivered` could not see
    # the second was the first. Scope order stays the operator's: `scope` is
    # what they named, in the order they named it, and it is consent, not data.
    rows.sort(key=lambda r: (r["table"], r["matter"], r["item_type"], r["item_id"]))

    identity = {
        "schema": SCHEMA, "household": household_id(), "composed_at": _now_iso(),
        "head": ledger().head(), "scope": scope.as_dict(),
        "rows": rows, "count": len(rows),
    }
    return Envelope(
        schema=identity["schema"], household=identity["household"],
        composed_at=identity["composed_at"], head=identity["head"],
        scope=identity["scope"], rows=tuple(rows), count=identity["count"],
        envelope_id=_envelope_id(identity),
    )


def _already_delivered(log: IntegrityLog, envelope_id: str) -> bool:
    """Whether this envelope already has a `record_synced` row.

    Routed through `IntegrityLog.read_entries()` (E6; given its public name
    in E7 — it was `_entries()`) rather than a bare `json.loads` over the
    file: a sealed log's lines are AES-256-GCM ciphertext wrappers on disk,
    and `read_entries()` is the one place that decrypts them and skips the
    boundary rows — a direct read here would see `{"sealed": 1, ...}` and
    never find the `act` it is looking for, sync'd or not. No `.payload`; a
    ledger line is JSON, not a `Classified`.

    Named refusals from that reader propagate on purpose — `IntegritySealError`
    (no key, no extra) and, since the E7 audit, `IntegrityIncompleteError` (the
    ledger is shorter than its anchor says). Both mean the same thing here: the
    row that would say "already delivered" may be one of the ones this read
    could not see, and answering `False` on the strength of that is how the
    same envelope goes out twice. Only a bare `JSONDecodeError`, which is not a
    refusal by name, is translated below."""
    if not log.path.exists():
        return False
    try:
        for entry in log.read_entries():
            if entry.get("act") == Event.RECORD_SYNCED.value and entry.get("envelope") == envelope_id:
                return True
    except json.JSONDecodeError as e:
        # A log this cannot read is a log that cannot be shown not to hold
        # this envelope already. Fail closed by name (I-11) rather than
        # letting a `JSONDecodeError` out of `deliver` — `IntegrityLog`
        # itself takes the same partial-final-line crash seriously
        # (`verify()` returns False for it).
        raise EgressRefused(
            f"{log.path} does not read as a ledger, so whether this "
            "envelope was already synced cannot be established — refused "
            "rather than delivered twice (I-11, I-38)"
        ) from e
    return False


Confirm = Callable[[Wire], bool]


def deliver(
    envelope: Envelope,
    *,
    confirm: Confirm | None,
    url: str | None = None,
    drop_dir: Path | None = None,
    integrity: IntegrityLog | None = None,
    visible: VisibleLog | None = None,
) -> Receipt:
    """Deliver one composed `Envelope`, exactly once, on an explicit act.

    Exactly one of `url`/`drop_dir` — neither or both is a `ValueError`, a
    call-site mistake rather than a declined act.

    `url`: sent through `egress.send(url, envelope.to_dict(),
    confirm=confirm)` — same per-call confirm, same `EgressRefused` for no
    confirmation or a declined one.

    `drop_dir`: an **absolute** directory — `default_drop_dir()` is the one
    the plan names, and a caller that wants it passes it. A relative one is a
    `ValueError`: `paths.ensure` resolves a relative path against
    `paths.home()` while `open()` resolves it against the process's cwd, so a
    relative `drop_dir` created one directory and wrote into another (or into
    nothing) — found by the E4-sync-core audit. The path the ledger records
    must be the path the bytes went to, and only an absolute one is that in
    every cwd. `paths.ensure` also keeps the drop inside `paths.home()`; a
    drop outside it is refused there, not widened here.

    It is shown a `Wire(method="FILE", url=<path>, body=<byte count>)` — the
    destination and the size, never a row (the content was already composed
    and is the caller's to have inspected before calling `deliver`). A
    refused or missing `confirm` raises `EgressRefused`, writes nothing and
    creates nothing — not even the directory. Approved, the write is `O_EXCL`
    — `<envelope_id>.json` under `drop_dir` — so a repeat, a file already at
    that name, or a symlink planted there, is `AlreadyDelivered` rather than
    overwritten or followed (I-9's shape, applied to a sync).

    `confirm` must return **`True`**, on either leg, and is called exactly
    once. Truthiness is not consent: `lambda w: input("send? [y/N] ")`
    returns `"n"`, which is truthy, and would have sent. `deliver` normalises
    its own confirm to `is True` before handing it to `egress.send`, which is
    why the URL leg gets the same rule without `keep/egress.py`'s own
    contract (I-17's, older and with other callers to come) being redefined
    from here.

    Either way, before anything is sent or written, the `IntegrityLog` is
    consulted for this `envelope_id`; already there, `deliver` refuses with
    `AlreadyDelivered` before showing anything to `confirm` (I-38 —
    "ledgered once").

    On success: **one** `IntegrityLog` row — `{act: "record_synced",
    household, envelope, purpose, scope, rows, destination}`, references
    only (I-15) — and **one** `VisibleLog` row, `Event.RECORD_SYNCED` with
    `ref=(household, envelope_id)`.
    """
    if (url is None) == (drop_dir is None):
        raise ValueError(
            "deliver needs exactly one of url= or drop_dir= — a sync goes to "
            "exactly one destination per call, never both and never neither"
        )

    if drop_dir is not None and not drop_dir.is_absolute():
        raise ValueError(
            f"drop_dir must be an absolute directory, not {drop_dir!r} — a "
            "relative one names one directory to paths.ensure (under "
            "paths.home()) and another to open() (under the cwd), and the "
            "ledger can only honestly record one of them. Resolve it at the "
            "call site, or pass default_drop_dir()."
        )

    log = integrity or ledger()
    if _already_delivered(log, envelope.envelope_id):
        raise AlreadyDelivered(
            f"envelope {envelope.envelope_id} is already ledgered as synced "
            "— an envelope is delivered once (I-38); compose a fresh one if "
            "the record has changed"
        )

    # `True`, not truthy — see the docstring. Wrapping rather than re-deciding
    # keeps the confirm called exactly once on both legs: this is a pass-through.
    approved: Confirm | None = None if confirm is None else (lambda wire: confirm(wire) is True)

    if url is not None:
        egress.send(url, envelope.to_dict(), confirm=approved)
        destination = url
    else:
        # Normalised *before* the Wire is built, so the path the operator is
        # shown, the path the bytes go to and the path the ledger records are
        # one string. The only assert-free way to say "this is not None here"
        # is to use it, and `.resolve()` on an absolute path does that.
        drop = drop_dir.resolve()   # type: ignore[union-attr]  # the exactly-one guard above
        body = envelope.to_bytes()
        target = drop / f"{envelope.envelope_id}.json"
        wire = Wire(method="FILE", url=str(target), body=f"{len(body)} bytes",
                    content_type="text/plain")
        if approved is None:
            raise EgressRefused(
                "no sync without an explicit per-call act (I-37). Nothing "
                "here writes by default; pass confirm=, shown the "
                "destination and the size, and it must return True."
            )
        if not approved(wire):
            raise EgressRefused(
                f"sync declined at the preview: {wire.method} {wire.url} was "
                "shown and not approved, so nothing was written."
            )
        # Only now — a refused act leaves no directory behind either.
        # `paths.ensure` is also the containment check: a drop outside
        # `paths.home()` is refused there, by the rule that predates this bite.
        paths.ensure(drop)
        try:
            with open(target, "xb") as fh:   # O_EXCL — never overwrite or follow a drop
                fh.write(body)
        except FileExistsError as e:
            raise AlreadyDelivered(
                f"{target} already exists — an envelope is dropped once (I-38)"
            ) from e
        destination = str(target)

    # Order: destination first, then the IntegrityLog, then the VisibleLog. A
    # crash between the first two leaves an envelope delivered and unledgered
    # — the residual, ruled on in `docs/DECISION-sync-envelope-and-consent.md`
    # § "The crash window". The other order would leave one ledgered and never
    # sent, which is the worse lie for a log whose whole job is to prove what
    # left; and a two-row pending/finalise scheme would break the one-row
    # shape I-38 pins.
    log.append({
        "act": Event.RECORD_SYNCED.value, "household": envelope.household,
        "envelope": envelope.envelope_id, "purpose": Purpose.SYNC.value,
        "scope": envelope.scope, "rows": envelope.count, "destination": destination,
    })
    head = log.head()
    (visible or VisibleLog()).record(
        Event.RECORD_SYNCED, ref=(envelope.household, envelope.envelope_id)
    )
    return Receipt(
        envelope_id=envelope.envelope_id, household=envelope.household,
        destination=destination, rows=envelope.count, head=head,
    )
