"""The record: a read-only canonical handle, and the sidecar the app writes to.

This is bite 1 of `docs/PLAN-first-runnable.md` — *the store, records survive a
restart* — and the first thing in the package to persist a `Classified` and give
it back. Everything above it was built and connected to nothing; this connects
the classification model to disk without losing what it classified.

Five invariants live here, and each names a failure that happened once:

* **I-6 — the canonical record is read-only, enforced by type.** There are two
  handles, not one with a flag. `Canonical` can only read; it has no `write`,
  `update`, `delete`, `purge`, `remove` or `drop`, so the app *cannot* mutate
  the canonical record even by mistake (I-36 — auto-purging a live matter is
  destroying evidence on a schedule). Writes go to `Sidecar`, a parallel tree.

* **I-7 — one key derivation.** `key(matter, item_type, item_id)` is the only
  place the three components become a path, and read and write both go through
  it. BUG-11 was a literal matter name in one call site and a derived key in
  another, so a record was filed where it could not be found.

* **I-9 — writes never silently overwrite.** `put()` refuses an occupied key, or
  — asked explicitly — reports what it replaced. BUG-8 was a silent clobber.

* **I-11 at the storage boundary.** A stored datum whose rung is missing or
  unreadable reads `L5` on the way out, never `L1`. The rung travels *with* the
  datum or the whole model is decorative on reload: a store that returns a
  payload without its rung has silently declassified it, and there is
  deliberately no path that lowers a rung. `_read_rung` from `rungs` is reused
  rather than re-implemented, so the storage boundary fails closed by the exact
  same rule as the gate — a `bool`, an `int`, `"L9"` and a missing key are all
  refused identically, and refusal means `L5`.

`Canonical` reads the canonical record; `Sidecar` reads and writes its own tree.
The read logic — hydrate a `Classified` from raw JSON, fail closed on a bad rung
— is shared, so the boundary rule cannot hold on one handle and not the other.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import paths
from .rungs import Classified, Rung, _read_rung

__all__ = ["key", "InvalidKey", "Replaced", "Sidecar", "Canonical"]

#: Serializes writes within a process so the exists-check and the create are one
#: act (I-9). Across processes the exclusive create below carries the guarantee;
#: within one, a background thread (an autosave, an indexer) is enough to race a
#: bare exists()/write, which is the TOCTOU the audit reproduced 166 times in
#: 200 — the same lockless read-then-write shape the Phase 0 audit found in
#: SealedLog.
_WRITE_LOCK = threading.Lock()


class InvalidKey(ValueError):
    """A key component that could not be filed, or could escape its tree.

    A key is `(matter, item_type, item_id)`, and each component becomes one path
    segment. A component carrying a separator or a `..` is not a naming choice —
    it is a write trying to land outside its matter's tree, the same escape
    `paths.ensure` refuses for directories. Refused at derivation, before any
    filesystem call, so a malformed key never reaches disk.
    """


def key(matter: str, item_type: str, item_id: str) -> Path:
    """The one place `(matter, item_type, item_id)` becomes a path (I-7).

    Returns a *relative* path — `matter/item_type/item_id.json` — that each
    handle prepends its own tree root to: `Sidecar` under `paths.sidecar_dir()`,
    `Canonical` under `paths.record_dir()`. Read and write cannot disagree about
    where a record lives because they call this and nothing else (BUG-11).

    Every component must be a non-empty string, stripped of surrounding
    whitespace, with no path separator, no `.`/`..`, and no NUL. Those are the
    ways a component stops being a name and becomes a path.
    """
    for name, value in (
        ("matter", matter),
        ("item_type", item_type),
        ("item_id", item_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise InvalidKey(f"{name} must be a non-empty string, not {value!r}")
        if value != value.strip():
            raise InvalidKey(
                f"{name}={value!r} has surrounding whitespace; a key component "
                "is a path segment and must be exactly what it names"
            )
        if "/" in value or "\\" in value or value in (".", "..") or "\x00" in value:
            raise InvalidKey(
                f"{name}={value!r} is not a single path segment. A separator or "
                "a '..' in a key is a write trying to leave its matter's tree — "
                "the escape ensure() refuses for directories, refused here for "
                "records before it reaches disk."
            )
    return Path(matter) / item_type / f"{item_id}.json"


def _hydrate(raw: Any) -> Classified:
    """A `Classified` from raw stored JSON, failing closed on a bad rung (I-11).

    The rung is read with `rungs._read_rung`, the same function the gate uses, so
    a `bool`, an `int`, `"L9"`, or a missing key all read as *unclassified* — and
    unclassified reads `L5`, never `L1`. `L5` needs no derived form (it is served
    on no surface), so the payload rides along and can never be rendered.

    A readable rung that still cannot form a valid `Classified` — an `L3` whose
    derived form was lost, so BUG-5's "shown as excluded, present in the packet"
    could not even be represented — also fails closed to `L5` rather than raising
    or inventing a stand-in. Absence at this boundary is served as nothing.
    """
    payload = raw.get("payload") if isinstance(raw, dict) else None
    rung = _read_rung(raw.get("rung")) if isinstance(raw, dict) else None
    if rung is None:
        return Classified(Rung.L5, payload)
    try:
        return Classified(rung, payload, raw.get("derived"))
    except Exception:
        return Classified(Rung.L5, payload)


def _dump(item: Classified) -> str:
    return json.dumps(
        {"rung": item.rung.value, "payload": item.payload, "derived": item.derived}
    )


def _load(target: Path) -> Classified:
    """Read a stored record from disk, failing closed to L5 on corruption.

    I-11 at the storage boundary is about the *rung*, and `_hydrate` handles a
    missing or unreadable one — but a file that is not even decodable JSON
    (empty, truncated, garbage bytes, an older binary schema) never reaches
    `_hydrate`, and a bare `json.loads` would crash the surface reading it. A
    corrupt row is not an exception a caller should have to catch; it is an
    unreadable datum, and an unreadable datum reads L5 — never L1, never a
    crash. A *missing* file is a different thing (no such record) and is left to
    raise `FileNotFoundError`, which `has()` lets a caller check for first.
    """
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except (UnicodeDecodeError, OSError):
        return Classified(Rung.L5, None)
    try:
        raw = json.loads(text)
    except ValueError:
        return Classified(Rung.L5, None)
    return _hydrate(raw)


@dataclass(frozen=True)
class Replaced:
    """What an explicit overwrite displaced (I-9). Returned by `put(overwrite=True)`
    so a replacement never loses the prior record silently — the caller is handed
    exactly what was there."""

    key: Path
    previous: Classified


class Sidecar:
    """The app's own record tree — the only thing here that writes (I-6).

    Keyed the same way as the canonical record and living beside it under
    `paths.sidecar_dir()`, never inside `record_dir()`. A write refuses an
    occupied key unless overwrite is asked for explicitly (I-9); a read fails
    closed to `L5` on an unreadable rung (I-11).
    """

    def _path(self, matter: str, item_type: str, item_id: str) -> Path:
        return paths.sidecar_dir() / key(matter, item_type, item_id)

    def get(self, matter: str, item_type: str, item_id: str) -> Classified:
        return _load(self._path(matter, item_type, item_id))

    def has(self, matter: str, item_type: str, item_id: str) -> bool:
        return self._path(matter, item_type, item_id).exists()

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
        replacement (I-9). Returns `None` on a first write, a `Replaced` on an
        explicit overwrite.

        Takes a `Classified` and nothing else: an unclassified value has no rung
        to store, and must not acquire one here (I-11). The rung is written with
        the datum, so it comes back with it.

        **The occupied-key check and the write are one act (I-9).** The first
        version tested `exists()` and then wrote, with a window between them —
        two writers both saw an empty slot and both wrote, one clobbering the
        other silently, which the audit reproduced. Now the whole span is under
        `_WRITE_LOCK`, and a first write uses an **exclusive create** (`open`
        mode `"x"`, `O_EXCL`), so even a writer in another process that never
        took the lock cannot clobber — it fails the create and is refused.
        """
        if not isinstance(item, Classified):
            raise TypeError(
                f"put() stores a Classified, not {type(item).__name__} — an "
                "unclassified value has no rung, and the store is not where one "
                "gets invented (I-11)"
            )
        target = self._path(matter, item_type, item_id)
        rel = key(matter, item_type, item_id)
        with _WRITE_LOCK:
            paths.ensure(target.parent)
            if not overwrite:
                try:
                    with open(target, "x", encoding="utf-8") as fh:
                        fh.write(_dump(item))
                except FileExistsError:
                    raise FileExistsError(
                        f"{rel} already exists. A write never silently "
                        "overwrites (I-9, BUG-8): pass overwrite=True to replace "
                        "it, and the prior record is handed back rather than lost."
                    )
                return None
            previous = _load(target) if target.exists() else None
            target.write_text(_dump(item), encoding="utf-8")
            return Replaced(key=rel, previous=previous) if previous is not None else None


class Canonical:
    """A read-only handle over the canonical record (I-6, I-36).

    Read-only *by type*: this class has no `write`, `update`, `delete`, `purge`,
    `remove` or `drop`. The operator's own tools grow the canonical record; the
    app reads it and never edits or deletes it — auto-purging a live matter is
    destroying evidence on a schedule (I-36, F-5, GDPR Art. 17), so retention is
    advisory and lives elsewhere, never as a write path on this handle.

    It shares `key` and `_hydrate` with `Sidecar`, so the storage-boundary rule
    (an unreadable rung reads `L5`) is a property of every read, not just the
    writable one.
    """

    def _path(self, matter: str, item_type: str, item_id: str) -> Path:
        return paths.record_dir() / key(matter, item_type, item_id)

    def get(self, matter: str, item_type: str, item_id: str) -> Classified:
        return _load(self._path(matter, item_type, item_id))

    def has(self, matter: str, item_type: str, item_id: str) -> bool:
        return self._path(matter, item_type, item_id).exists()
