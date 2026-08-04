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

* **`SealedLog`** — hash-chained and append-only.

  **Read the limits before trusting it.** The Phase 0 audits established what
  this does and does not do, and the docstring is written to the code rather
  than to the ambition:

  - It detects **in-place edits of a non-final line**. That is real and tested.
  - It does **not** withstand a determined local adversary. `line_hash` is an
    unkeyed public SHA-256 over a plaintext JSONL file at a predictable path,
    so truncating the tail, rewriting the last line, or deleting the file and
    forging a fresh chain from `genesis` all verify clean. Passing
    `expected_head` from somewhere this process cannot reach is the only thing
    that closes the suffix hole, and nothing does that yet.
  - There is **no encryption and no key.** F-6 recommended hash-chained *and*
    encrypted; only the chain was built. An earlier version of this docstring
    described the cost of losing a key that does not exist — that sentence is
    removed rather than quietly corrected, because it is the exact failure this
    project keeps finding elsewhere: a claim that outran its mechanism.
  - The absence of a `read()` method is a **naming convention, not a control**.
    `_lines()` returns everything and `.path` is public. It shapes the app's own
    habits; it stops nobody with filesystem access.

  Whether that is enough — and whether this should be renamed, anchored, or
  encrypted — is the one open decision in `docs/PHASE0-REMEDIATION.md`.
"""
from __future__ import annotations

import hashlib
import json
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

__all__ = ["VisibleLog", "SealedLog", "Event", "line_hash"]

GENESIS = "genesis"

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
    RECORD_SYNCED = "record_synced"
    DRAFT_SAVED = "draft_saved"
    EXPORTED = "exported"


def _canonical(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def line_hash(entry: dict[str, Any]) -> str:
    """The hash a following entry carries as its `prev`.

    Unkeyed and public: anyone who can read the file can compute it, and
    therefore forge a consistent chain. See the class docstring.
    """
    return hashlib.sha256(_canonical(entry).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ref(parts: Iterable[str]) -> str:
    parts = [str(p) for p in parts]
    if not parts:
        raise ValueError("a reference needs at least one part")
    for p in parts:
        if "/" in p or "\\" in p or "\n" in p:
            raise ValueError(f"reference parts are separator-free, got {p!r}")
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


class SealedLog:
    """Append-only and hash-chained. Read the module docstring for its limits."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (paths.logs_dir() / "sealed.jsonl")

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
        return line_hash(lines[-1]) if lines else GENESIS

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
        """
        paths.ensure(self.path.parent)
        with _APPEND_LOCK:
            with self.path.open("a", encoding="utf-8") as fh:
                if _HAVE_FCNTL:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                try:
                    sealed = dict(entry)
                    sealed["at"] = _now()
                    sealed["prev"] = self.head()   # re-read inside the lock
                    fh.write(_canonical(sealed) + "\n")
                    fh.flush()
                finally:
                    if _HAVE_FCNTL:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def verify(self, expected_head: str | None = None) -> bool:
        """Walk the chain. A broken chain is a refusal, not a warning.

        Catches an in-place edit of any line that something follows. Does **not**
        catch truncation, a rewritten final line, or a forged chain — pass
        `expected_head` from storage this process cannot reach to close the
        suffix hole. Nothing does that yet; see the module docstring.
        """
        prev = GENESIS
        try:
            lines = self._lines()
        except json.JSONDecodeError:
            return False            # a partial final line from a crash mid-write
        for entry in lines:
            if entry.get("prev") != prev:
                return False
            prev = line_hash(entry)
        if expected_head is not None and prev != expected_head:
            return False
        return True
