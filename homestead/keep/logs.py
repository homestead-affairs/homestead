"""Two logs, because one log cannot serve both readers.

F-6 named the tension and it does not dissolve: a supervising attorney, LSC
Part 1636, and any breach-notification clock all require an audit trail — and
the person sharing the machine reads that trail with one keypress. A single log
either fails the lawyer or exposes the user.

So there are two, with different powers:

* **`VisibleLog`** — what the operator can see. It carries **references, never
  content**. F-4: law-gazelle's `add_note` copied the first eighty characters of
  every private note into its activity log, and the last eight rows of that log
  went into every model prompt. Note → log → prompt, and `a` opened it from the
  main screen. `event` is a **closed enum** and `ref` is a tuple of identifiers,
  so there is no parameter anywhere on this class that accepts free text.

* **`IntegrityLog`** — hash-chained, append-only, and **named for what it
  does**. It was called `SealedLog` until the Phase 0 audits pointed out that
  nothing about it was sealed. Renamed rather than defended, because a name is
  a claim and this one outran its mechanism.

  **What it catches** — and this is the whole list:

  - **In-place edits** of any line the chain runs past. Real and tested.
  - **Truncation and tail rewrites**, via the head anchor: the chain tip is
    written to a *separate* file after each append, so shortening the log
    without also editing the anchor is caught.

  **What it does not catch**, stated because the gap is the useful part:

  - ~~Anyone who edits **both** the log and its anchor. `line_hash` is an
    unkeyed public SHA-256 over plaintext at a predictable path, so a forged
    chain plus a matching anchor verifies clean.~~ **Closed 2026-09-11 (E5) for
    a log that opts in.** `IntegrityLog` now takes an optional HMAC-SHA256 key
    at `paths.anchors_dir()/integrity.key` (`homestead integrity init-key`).
    Keyed, `line_hash` is `hmac.new(key, ..., sha256)` instead of a bare
    digest, so a forger who can read and rewrite both the log and the anchor —
    everything on this machine — still cannot produce a valid chain without
    the key file too. Unkeyed logs (no key ever created, or `keyed=False`)
    keep the exact gap described above; nothing about a legacy log's on-disk
    format changes. See `docs/DECISION-integrity-key-management.md`. **An
    on-machine anchor detects accident, not an adversary** — there is no
    location on this machine the writer cannot reach, which is the same truth
    as F-5: a shared OS account is not securable by an application. The key
    changes what "an adversary" means, not where the key can hide: it sits
    beside the anchor, off the log's own tree, never escrowed (Open item 8) —
    an operator who loses it has an unverifiable keyed segment, not an
    unreadable one (sealing that segment is Phase 4, E6).
  - The only real closure for an **unkeyed** log is `verify(expected_head=...)`
    with a head the operator recorded **off the machine**. `head()` is public
    so that is possible; nothing forces it.

  **There is no encryption** — that stays a deliberate **Phase 4** item (E6,
  `keep/sealed.py`), not an oversight. ~~and no key~~ (struck 2026-09-11, E5):
  the key above closes the forged-chain gap; it does not make the log
  unreadable to whoever has filesystem access, which is what sealing is for.
  F-6 recommended hash-chained *and* encrypted; key management for a person in
  crisis is a product decision, and a user who loses the key loses the ability
  to verify (not to read) the record permanently. Decided 2026-08-04: rename
  and anchor first, key next (E5, this bite), encrypt last (E6).

  The absence of a `read()` method is a **naming convention, not a control**.
  `_lines()` returns everything and `.path` is public. It shapes the app's own
  habits; it stops nobody with filesystem access.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from . import paths

try:                                    # advisory file locking is Unix-only
    import fcntl                        # noqa: F401
    _HAVE_FCNTL = True
except ImportError:                     # pragma: no cover - Windows
    _HAVE_FCNTL = False

__all__ = [
    "VisibleLog", "IntegrityLog", "Event", "line_hash",
    "IntegrityKeyError", "init_key", "read_key", "default_key_path",
    "KEY_BYTES", "BOUNDARY_ACT",
]

GENESIS = "genesis"

#: The key file: 32 random bytes, hex-encoded (64 characters), at a fixed
#: location — `paths.anchors_dir()/integrity.key` — never per-log, because one
#: household has one key to lose (Open item 8: no escrow). See
#: `docs/DECISION-integrity-key-management.md`.
KEY_FILENAME = "integrity.key"
KEY_BYTES = 32

#: The tag on the one line that marks where an `IntegrityLog` turned keyed.
#: Lines before it verify unkeyed (the pre-existing chain, untouched); this
#: line and every line after it verify with HMAC. Written once, the first time
#: `append()` runs while a key is present — never by `init-key` itself, which
#: only makes the key and does not touch any log.
BOUNDARY_ACT = "keyed"


class IntegrityKeyError(Exception):
    """Refuse by name (I-11): a key is required and absent, a key file is
    unreadable as a key, or an existing key would be overwritten. Never
    confused with `verify()` returning `False` — that is tamper detection;
    this is "the key needed to even ask the question is missing or broken."
    """


def default_key_path() -> Path:
    return paths.anchors_dir() / KEY_FILENAME


def _decode_key(raw: str, path: Path) -> bytes:
    raw = raw.strip()
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise IntegrityKeyError(
            f"the integrity key at {path} is not valid hex; refusing to use it"
        ) from exc
    if len(key) != KEY_BYTES:
        raise IntegrityKeyError(
            f"the integrity key at {path} is {len(key)} bytes, not {KEY_BYTES}; "
            "refusing to use it"
        )
    return key


def read_key(path: Path | None = None) -> bytes | None:
    """The key at `path` (default `default_key_path()`), or `None` if absent.

    A missing file is not an error — most logs are unkeyed and that is fine.
    A file that exists but is not 64 hex characters IS an error (refused by
    name), because using it anyway would silently produce a chain nothing else
    can ever verify.
    """
    path = path or default_key_path()
    if not path.exists():
        return None
    return _decode_key(path.read_text(encoding="utf-8"), path)


def init_key(path: Path | None = None) -> Path:
    """Create the integrity key: 32 random bytes, hex-encoded, written
    `O_EXCL` so a second call never overwrites the first (there is no escrow —
    Open item 8 — so overwriting would silently orphan whatever was keyed
    under the old one).

    Mode `0o600` on POSIX. Windows has no POSIX permission bits; `os.open`'s
    mode argument is accepted but mostly ignored there, so on Windows this
    relies on the file's ACL inheriting from its parent directory rather than
    on a mode bit — documented in `docs/DECISION-integrity-key-management.md`,
    not silently assumed.
    """
    path = path or default_key_path()
    paths.ensure(path.parent)
    key_hex = secrets.token_hex(KEY_BYTES)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags, 0o600)
    except FileExistsError as exc:
        raise IntegrityKeyError(
            f"an integrity key already exists at {path}; it is never "
            "overwritten — there is no escrow, so losing it is the "
            "operator's to manage"
        ) from exc
    try:
        os.write(fd, key_hex.encode("ascii"))
    finally:
        os.close(fd)
    if os.name == "posix":
        os.chmod(path, 0o600)          # belt-and-suspenders against umask
    return path

# One lock per process covers threads. Module-level rather than per-instance,
# because two SealedLog objects over the same path are the realistic case and
# a per-instance lock would not see the other one.
_APPEND_LOCK = threading.Lock()


class Event(str, Enum):
    """What the visible log may say happened. Closed, so argument one cannot
    become the free-text field the content leaks through (F-4)."""

    NOTE_ADDED = "note_added"
    NOTE_REMOVED = "note_removed"
    FACT_VERIFIED = "fact_verified"
    FACT_REJECTED = "fact_rejected"
    ITEM_RESOLVED = "item_resolved"
    ITEM_SNOOZED = "item_snoozed"
    RECORD_ADDED = "record_added"          # a record was entered by the operator
    RECORD_SYNCED = "record_synced"
    DRAFT_SAVED = "draft_saved"
    EXPORTED = "exported"
    LIVING_REPLACED = "living_replaced"    # a forgetting cell overwrote in place (H-8)


def _canonical(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def line_hash(entry: dict[str, Any], key: bytes | None = None) -> str:
    """The hash a following entry carries as its `prev`.

    `key=None` (the default, and the only form every existing caller uses):
    unkeyed and public — anyone who can read the file can compute it, and
    therefore forge a consistent chain. See the class docstring.

    `key=<32 bytes>`: the same canonical bytes, HMAC-SHA256'd instead of bare
    SHA256'd. Forging a consistent chain now requires the key, not just read
    access to the file. Nothing about the unkeyed branch changed — same
    bytes, same digest — so every pre-existing unkeyed log still verifies.
    """
    canonical = _canonical(entry).encode()
    if key is None:
        return hashlib.sha256(canonical).hexdigest()
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


def _boundary_index(lines: list[dict[str, Any]]) -> int | None:
    """The index of the `{"act": "keyed"}` marker, or `None` if this chain
    has never turned keyed. Lines at or after this index verify keyed; lines
    before it verify unkeyed, whatever the caller's current key is."""
    for i, entry in enumerate(lines):
        if entry.get("act") == BOUNDARY_ACT:
            return i
    return None


def _hash_at(entry: dict[str, Any], idx: int, boundary: int | None, key: bytes | None) -> str:
    """`line_hash` for the entry at position `idx`, keyed or not depending on
    where it falls relative to the boundary — never on whether a key happens
    to be in hand right now. A keyed position without a key refuses by name
    (I-11): returning an unkeyed hash there would silently accept a chain a
    forger built without the key, which is exactly the gap keying exists to
    close."""
    if boundary is not None and idx >= boundary:
        if key is None:
            raise IntegrityKeyError("this log is keyed; the key is absent")
        return line_hash(entry, key)
    return line_hash(entry)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ref(parts: Iterable[str]) -> str:
    """Join reference parts into the log's ``ref`` string.

    Each part is validated through `paths.component` — the same validator
    `export._segment` uses — so the two cannot disagree on what a component
    may contain. Before the fix for issue #23 these were two independently
    written checks (`_segment` allowed embedded ``\\n``, this rejected it),
    and the drift turned a rejection into a partial write on the export path.
    """
    parts = [str(p) for p in parts]
    if not parts:
        raise ValueError("a reference needs at least one part")
    for p in parts:
        paths.component(p, name="ref part")
    return "/".join(parts)


class VisibleLog:
    """Operator-readable. References only — never the content of anything."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (paths.logs_dir() / "visible.jsonl")

    def record(self, event: Event, *, ref: tuple[str, ...]) -> None:
        """Record that something happened, and to what.

        `event` must be an `Event`. There is deliberately no parameter for a
        body, a summary, a preview or a note — adding one re-creates F-4, and
        so does widening `event` back to a free string.
        """
        if not isinstance(event, Event):
            raise TypeError(
                f"event must be an Event, not {type(event).__name__} — a free "
                "string here is where note content leaked last time (F-4)"
            )
        paths.ensure(self.path.parent)
        entry = {"at": _now(), "event": event.value, "ref": _ref(ref)}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(entry) + "\n")

    def read(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(x) for x in lines[-limit:] if x.strip()]


class IntegrityLog:
    """Append-only and hash-chained, with an off-file head anchor.

    Read the module docstring for exactly what it catches and what it does not.
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        anchor_path: Path | None = None,
        key: bytes | None = None,
        keyed: bool | None = None,
    ) -> None:
        """`keyed` controls whether this instance uses the HMAC key, in three
        states — pick one, don't guess from context:

        * `None` (default) — **auto**. Keyed iff `default_key_path()` exists
          and reads as a valid key; otherwise unkeyed. This is why a checkout
          that has never run `homestead integrity init-key` behaves exactly as
          before E5: no key file, no change.
        * `True` — **require** the key. Missing or invalid key file:
          `IntegrityKeyError` at construction, not a silent fall-back to
          unkeyed (I-11).
        * `False` — **force unkeyed**, even if a key file exists. For a caller
          that has a specific reason to read or write the pre-key segment of a
          log without needing the key on hand.

        `key`, if given, is the raw 32-byte key to use directly (skipping the
        file) — the same value `read_key()` would have returned. Mainly for
        tests that want a known key without touching `anchors_dir()`.
        Contradicts `keyed=False` (a key was handed over on purpose) and that
        combination is refused rather than silently resolved either way.
        """
        self.path = path or (paths.logs_dir() / "integrity.jsonl")
        # The anchor defaults to a `.head` file beside the log — unchanged, so
        # every existing caller keeps its behaviour. A caller that wants the
        # head held off the log's own tree (the willow-mcp #280 separation)
        # passes `anchor_path`; `keep/export.py`'s `ledger()` is the one that
        # does, putting it under `paths.anchors_dir()`.
        self.anchor_path = anchor_path or self.path.with_suffix(".head")
        self.key = self._resolve_key(key, keyed)

    @staticmethod
    def _resolve_key(key: bytes | None, keyed: bool | None) -> bytes | None:
        if key is not None:
            if keyed is False:
                raise IntegrityKeyError(
                    "an explicit key was given together with keyed=False; "
                    "that is a contradiction, not a choice to resolve"
                )
            if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_BYTES:
                raise IntegrityKeyError(
                    f"an explicit key must be {KEY_BYTES} raw bytes"
                )
            return bytes(key)
        if keyed is False:
            return None
        if keyed is True:
            found = read_key()
            if found is None:
                raise IntegrityKeyError(
                    f"this log requires a key, and none is at "
                    f"{default_key_path()} — run `homestead integrity "
                    "init-key` first, or pass keyed=False if that is the "
                    "intent"
                )
            return found
        return read_key()          # keyed is None: auto — None if no key file

    @property
    def keyed(self) -> bool:
        return self.key is not None

    def _read_anchor(self) -> tuple[str, bool] | None:
        """The stored `(digest, is_keyed)`, or `None` if there is no anchor
        yet. A keyed anchor is written `hmac:<hex>` (item 6) so a reader — the
        CLI included — can say which kind it is without needing the key."""
        if not self.anchor_path.exists():
            return None
        raw = self.anchor_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        if raw.startswith("hmac:"):
            return raw[len("hmac:"):], True
        return raw, False

    def _write_anchor(self, head: str, *, keyed: bool = False) -> None:
        # Ensure the anchor's own parent — it may live in a different tree from
        # the log (anchors_dir()), which append() ensures separately for the log.
        paths.ensure(self.anchor_path.parent)
        text = f"hmac:{head}" if keyed else head
        self.anchor_path.write_text(text + "\n", encoding="utf-8")

    def _lines(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                out.append(json.loads(raw))
        return out

    def head(self) -> str:
        lines = self._lines()
        if not lines:
            return GENESIS
        boundary = _boundary_index(lines)
        return _hash_at(lines[-1], len(lines) - 1, boundary, self.key)

    def _ensure_boundary(self, fh) -> None:
        """Write the `{"act": "keyed"}` boundary row, once — the first time
        this log is appended to while a key is present. `init-key` itself
        never touches a log; this is where a log actually turns keyed, lazily,
        on its own next write. Idempotent: a log that already has a boundary
        (this call or an earlier one) is left alone, so a mixed log's already
        recorded turning point never moves.
        """
        if _boundary_index(self._lines()) is not None:
            return
        marker = {"act": BOUNDARY_ACT, "at": _now(), "prev": self.head()}
        fh.write(_canonical(marker) + "\n")
        fh.flush()
        self._write_anchor(line_hash(marker, self.key), keyed=True)

    def append(self, entry: dict[str, Any]) -> None:
        """Append one entry, reading the tail and writing under one lock.

        Read-then-write is not atomic, and the consequence is not a lost line
        but a **broken chain**: eight threads appending concurrently wrote all
        160 lines and left 72 duplicate `prev` links, so `verify()` returned
        False — an audit trail that indicts itself. That is
        `nestor/cascade.py:ledger_append`'s documented failure, reproduced here
        before this lock existed.

        Two locks, because there are two kinds of concurrent writer. The
        threading lock covers threads in this process. An advisory file lock
        covers separate processes — the app and an MCP entry point against the
        same log is not exotic — and is best-effort: where `fcntl` is absent the
        threading lock still holds, and a file lock is a lock, not a guarantee
        about other software.

        When `self.key` is set, the first call also writes the boundary row
        (see `_ensure_boundary`) before the entry itself, so every entry this
        call writes from here on is unambiguously on the keyed side.
        """
        paths.ensure(self.path.parent)
        with _APPEND_LOCK:
            with self.path.open("a", encoding="utf-8") as fh:
                if _HAVE_FCNTL:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                try:
                    if self.key is not None:
                        self._ensure_boundary(fh)
                    sealed = dict(entry)
                    sealed["at"] = _now()
                    sealed["prev"] = self.head()   # re-read inside the lock
                    fh.write(_canonical(sealed) + "\n")
                    fh.flush()
                    # The anchor is a separate file, so truncating the log
                    # without also editing this is caught by verify().
                    keyed_now = self.key is not None
                    head_hash = line_hash(sealed, self.key) if keyed_now else line_hash(sealed)
                    self._write_anchor(head_hash, keyed=keyed_now)
                finally:
                    if _HAVE_FCNTL:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def verify(self, expected_head: str | None = None) -> bool:
        """Walk the chain and check it against the anchor.

        `expected_head`, if given, wins over the on-disk anchor — it is the only
        check that means anything against someone who can write to this machine,
        because they can edit the anchor too. Pass a head the operator recorded
        off the machine.

        Every comparison against a hash — the chain link and the final anchor
        or expected head — uses `hmac.compare_digest`, never `==`/`!=`
        (I-11's fail-closed spirit applied to timing, not just to defaults;
        see `tests/test_invariants_integrity_keyed.py`'s AST guard). A keyed
        segment encountered without the key raises `IntegrityKeyError` — that
        is "cannot tell," refused by name, never reported as `False` ("tamper
        found"), which is a different answer to a different question.
        """
        prev = GENESIS
        try:
            lines = self._lines()
        except json.JSONDecodeError:
            return False            # a partial final line from a crash mid-write
        boundary = _boundary_index(lines)
        for i, entry in enumerate(lines):
            prev_field = entry.get("prev")
            if not isinstance(prev_field, str) or not hmac.compare_digest(prev_field, prev):
                return False        # missing/wrong-typed prev is a mismatch, not a crash
            prev = _hash_at(entry, i, boundary, self.key)

        if expected_head is not None:
            return hmac.compare_digest(prev, expected_head)

        anchor = self._read_anchor()
        if anchor is None:
            return True
        anchor_hex, anchor_keyed = anchor
        if anchor_keyed and self.key is None:
            raise IntegrityKeyError(
                f"the anchor at {self.anchor_path} is keyed; the key is absent"
            )
        # truncated, or the final line was rewritten, if this does not match
        return hmac.compare_digest(prev, anchor_hex)
