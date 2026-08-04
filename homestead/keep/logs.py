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
  main screen. This log physically cannot hold a note body; `record()` takes no
  free-text parameter, so the failure is a `TypeError` rather than a leak.

* **`SealedLog`** — hash-chained, append-only, and **it has no read method at
  all**. The application appends; nothing renders it. That is not an oversight
  to be filled in later, and a test asserts the absence: the moment this class
  grows a `read()`, the audit trail becomes available to exactly the reader it
  was built to withstand.

The cost is stated plainly in F-6 and is real: the sealed half is worthless to
a user who loses the key, and there are two write paths to keep correct.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import paths

__all__ = ["VisibleLog", "SealedLog", "line_hash"]

GENESIS = "genesis"


def _canonical(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def line_hash(entry: dict[str, Any]) -> str:
    """The hash a following entry carries as its `prev`."""
    return hashlib.sha256(_canonical(entry).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ref(parts: Iterable[str]) -> str:
    parts = [str(p) for p in parts]
    if not parts or any("/" in p for p in parts):
        raise ValueError(f"a reference is slash-free parts, got {parts!r}")
    return "/".join(parts)


class VisibleLog:
    """Operator-readable. References only — never the content of anything."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (paths.logs_dir() / "visible.jsonl")

    def record(self, event: str, *, ref: tuple[str, ...]) -> None:
        """Record that something happened, and to what.

        There is deliberately no parameter for a body, a summary, a preview or
        a note. Adding one re-creates F-4.
        """
        paths.ensure(self.path.parent)
        entry = {"at": _now(), "event": event, "ref": _ref(ref)}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(entry) + "\n")

    def read(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(x) for x in lines[-limit:] if x.strip()]


class SealedLog:
    """Append-only, hash-chained, and unreadable by design.

    No `read`, `tail`, `entries`, `all`, `render` or `show`. `verify()` returns
    a boolean and never content.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (paths.logs_dir() / "sealed.jsonl")

    def _lines(self) -> list[dict[str, Any]]:
        """Private. The chain walk needs it; nothing outside this class does."""
        if not self.path.exists():
            return []
        return [json.loads(x) for x in
                self.path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def head(self) -> str:
        lines = self._lines()
        return line_hash(lines[-1]) if lines else GENESIS

    def append(self, entry: dict[str, Any]) -> None:
        paths.ensure(self.path.parent)
        sealed = dict(entry)
        sealed["at"] = _now()
        sealed["prev"] = self.head()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(sealed) + "\n")

    def verify(self) -> bool:
        """Walk the chain. A broken chain is a refusal, not a warning.

        Note the limit, stated because it is easy to assume away: this vouches
        for every line except the last, which nothing follows.
        """
        prev = GENESIS
        for entry in self._lines():
            if entry.get("prev") != prev:
                return False
            prev = line_hash(entry)
        return True
