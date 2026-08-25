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

  - Anyone who edits **both** the log and its anchor. `line_hash` is an unkeyed
    public SHA-256 over plaintext at a predictable path, so a forged chain plus
    a matching anchor verifies clean. **An on-machine anchor detects accident,
    not an adversary** — there is no location on this machine the writer cannot
    reach, which is the same truth as F-5: a shared OS account is not securable
    by an application.
  - The only real closure is `verify(expected_head=...)` with a head the
    operator recorded **off the machine**. `head()` is public so that is
    possible; nothing forces it.

  **There is no encryption and no key** — that is a deliberate **Phase 4** item,
  not an oversight. F-6 recommended hash-chained *and* encrypted; key management
  for a person in crisis is a product decision, and a user who loses the key
  loses the record permanently. Decided 2026-08-04: rename and anchor now,
  encrypt at Phase 4.

  The absence of a `read()` method is a **naming convention, not a control**.
  `_lines()` returns everything and `.path` is public. It shapes the app's own
  habits; it stops nobody with filesystem access.
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

__all__ = ["VisibleLog", "IntegrityLog", "Event", "line_hash"]

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
        self, path: Path | None = None, *, anchor_path: Path | None = None
    ) -> None:
        self.path = path or (paths.logs_dir() / "integrity.jsonl")
        # The anchor defaults to a `.head` file beside the log — unchanged, so
        # every existing caller keeps its behaviour. A caller that wants the
        # head held off the log's own tree (the willow-mcp #280 separation)
        # passes `anchor_path`; `keep/export.py`'s `ledger()` is the one that
        # does, putting it under `paths.anchors_dir()`.
        self.anchor_path = anchor_path or self.path.with_suffix(".head")

    def _read_anchor(self) -> str | None:
        if not self.anchor_path.exists():
            return None
        return self.anchor_path.read_text(encoding="utf-8").strip() or None

    def _write_anchor(self, head: str) -> None:
        # Ensure the anchor's own parent — it may live in a different tree from
        # the log (anchors_dir()), which append() ensures separately for the log.
        paths.ensure(self.anchor_path.parent)
        self.anchor_path.write_text(head + "\n", encoding="utf-8")

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
                    # The anchor is a separate file, so truncating the log
                    # without also editing this is caught by verify().
                    self._write_anchor(line_hash(sealed))
                finally:
                    if _HAVE_FCNTL:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def verify(self, expected_head: str | None = None) -> bool:
        """Walk the chain and check it against the anchor.

        `expected_head`, if given, wins over the on-disk anchor — it is the only
        check that means anything against someone who can write to this machine,
        because they can edit the anchor too. Pass a head the operator recorded
        off the machine.
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

        if expected_head is not None:
            return prev == expected_head

        anchor = self._read_anchor()
        if anchor is not None and prev != anchor:
            return False            # truncated, or the final line was rewritten
        return True
