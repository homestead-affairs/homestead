"""The export act — the operator taking their own record out, and the ledger.

Bite 5 of `docs/PLAN-first-runnable.md`: *wire the logs, and the ledger with
them.* `keep/logs.py` built the two logs and connected them to nothing; this is
the first thing that writes to either. `Event.EXPORTED` had a name and no writer
(the plan's own words) — it has one now.

**An export is not a socket.** Nothing on this face binds or dials (I-17, I-30);
the network `send()` is a *different* act on this same surface and stays pending
under `homestead.keep.egress`. An export is the operator taking their record out
as a written artifact, on their own machine, for a reason they state — the S4
spec row, *"explicit act + purpose + ledgered."* Three writes and a refusal:

  * the **artifact** — the record leaving — to `paths.exports_dir()`. This is
    the only place the content goes.
  * one **`IntegrityLog`** entry — the provable record — naming the declared
    `Purpose`, and carrying a **reference**, never content (I-15): the matter,
    the item, the purpose, the rung and the disposition. No payload, no derived.
  * one **`VisibleLog`** entry — `Event.EXPORTED` and a reference tuple. A closed
    enum member (R-7), no free-text field, no content.
  * an `L5` datum, or an undeclared purpose, is **refused before either log is
    touched** — a refused export is not an export, and is not ledgered as one.

**The chokepoint holds here.** This module is neither the gate nor the store, so
`tests/test_invariants_chokepoint.py` forbids it a `.payload` reach. It has none:
it hands an item to `serve()` and receives `Served.value` already scored, exactly
like every other consumer. The content it writes to the artifact is that served
value, never a payload it reached for.

**The head anchor is held off the log's own tree** — `paths.anchors_dir()`, via
`ledger()`. See `docs/DECISION-export-and-the-anchor.md`: the willow-mcp #280
separation is that the head is not stored beside the chain it vouches for, so a
truncation is caught rather than cleared with it. That is not a wall the app
cannot climb (F-5 — a shared account has no such wall); the real closure is
`verify(expected_head=…)` with a head the operator recorded off the machine, and
`export_record()` returns that head in the receipt so there is somewhere to keep
it. #280's mistake was having nowhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import paths
from .logs import Event, IntegrityLog, VisibleLog
from .rungs import (
    Classified,
    Disposition,
    Purpose,
    Rung,
    Surface,
    serve,
)

__all__ = ["ExportReceipt", "ExportRefused", "export_record", "ledger"]


class ExportRefused(PermissionError):
    """An export that did not happen — and therefore was not ledgered.

    Raised before either log is written, for the two reasons an export must not
    proceed: no purpose was declared (an export is an explicit, purposeful act,
    so `None` is refused *here* even though the gate treats it as the ordinary
    no-purpose read), or the datum may not cross the egress surface at all (`L5`
    denies — `serve()` returns `DENY`, `Served.value` is `None`, nothing crosses).

    A `PermissionError` for the same reason the network `send()` is one: the act
    was not permitted, and the caller must be able to tell that apart from a
    programmer error like a malformed purpose (which stays `UndeclaredPurpose`,
    raised by the gate).
    """


@dataclass(frozen=True)
class ExportReceipt:
    """What an export produced — a reference, not content.

    `head` is the value worth keeping: the `IntegrityLog` head after this export,
    the one thing the operator should record somewhere this machine cannot reach,
    so that `verify(expected_head=…)` means something later. `artifact` is where
    the record itself was written (the content leaving); the logs hold neither.
    """

    ref: str
    purpose: Purpose
    rung: Rung
    disposition: Disposition
    artifact: Path
    head: str


def ledger() -> IntegrityLog:
    """The export ledger, with its head anchor held off the log's own tree.

    The chain lives in `logs_dir()`; the anchor lives in `anchors_dir()`. That
    separation is the whole of the willow-mcp #280 decision — the head is not
    stored beside the thing it vouches for, so truncating the log, or wiping the
    export tree, does not clear the witness in the same stroke. The one place
    that relocates the anchor, so every other `IntegrityLog` keeps its default
    `.head`-beside-the-log behaviour.
    """
    return IntegrityLog(
        paths.logs_dir() / "integrity.jsonl",
        anchor_path=paths.anchors_dir() / "integrity.head",
    )


def _segment(name: str, value: str) -> str:
    """One reference component, validated as a single path segment.

    A separator or a `..` in a component is a write trying to leave its tree —
    the same escape `record.key` and `ensure()` refuse. Refused here before it
    reaches the artifact path or a log reference, so a malformed key never lands
    on disk or in the ledger.
    """
    if not isinstance(value, str) or not value.strip():
        raise ExportRefused(f"{name} must be a non-empty string, not {value!r}")
    if value != value.strip():
        raise ExportRefused(
            f"{name}={value!r} has surrounding whitespace; a reference component "
            "is exactly what it names"
        )
    if "/" in value or "\\" in value or value in (".", "..") or "\x00" in value:
        raise ExportRefused(
            f"{name}={value!r} is not a single segment — a separator or a '..' "
            "in a reference is a write trying to leave its tree"
        )
    return value


def _write_artifact(
    where: Path, matter: str, item_type: str, item_id: str, value: object
) -> Path:
    """Write the served value — the record leaving — under `exports_dir()`.

    This is the one place the content goes. Keyed the same way the store keys a
    record, plus the timestamp of this export, so a second export of the same
    record never silently clobbers the first (the I-9 posture, applied to the
    export tree). An exclusive create makes that structural rather than hopeful.
    """
    import json  # local: keeps the module's import surface stdlib-and-siblings
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = paths.ensure(where / matter / item_type) / f"{item_id}-{stamp}.json"
    body = json.dumps(
        {
            "ref": f"{matter}/{item_type}/{item_id}",
            "exported_at": stamp,
            "content": value,
        },
        sort_keys=True,
        ensure_ascii=False,   # the artifact is the record leaving — keep it readable
    )
    with open(target, "x", encoding="utf-8") as fh:      # O_EXCL — never clobber
        fh.write(body)
    return target


def export_record(
    item: Classified,
    matter: str,
    item_type: str,
    item_id: str,
    *,
    purpose: Purpose | None,
    integrity: IntegrityLog | None = None,
    visible: VisibleLog | None = None,
    exports: Path | None = None,
) -> ExportReceipt:
    """Take one record out, on S4, and ledger the act.

    Gated through `serve(item, Surface.S4_EGRESS, purpose=…)` — the one door
    (I-16). Requires a declared `Purpose`: an export is an explicit, purposeful
    act, so `purpose=None` is refused *here* (`ExportRefused`) even though the
    gate treats `None` as the ordinary no-purpose read; a malformed purpose still
    raises `UndeclaredPurpose` from the gate. An `L5` datum denies at the gate and
    is refused before either log is touched.

    On success: writes the artifact (the content, to `exports_dir()`), **one**
    `IntegrityLog` entry (a reference and the purpose, never content), and **one**
    `VisibleLog` entry (`Event.EXPORTED` and a reference tuple). Returns the
    receipt, whose `head` is the value to record off the machine.
    """
    if purpose is None:
        raise ExportRefused(
            "an export must name a purpose — it is an explicit, purposeful act "
            f"({[p.value for p in Purpose]}). None is the gate's ordinary "
            "no-purpose read, but there is no such thing as a purposeless export."
        )
    matter = _segment("matter", matter)
    item_type = _segment("item_type", item_type)
    item_id = _segment("item_id", item_id)

    # The one door. `serve` type-checks the item (a bare value raises TypeError)
    # and the purpose (a non-member raises UndeclaredPurpose), then scores it.
    served = serve(item, Surface.S4_EGRESS, purpose=purpose)
    ref = f"{matter}/{item_type}/{item_id}"

    if served.disposition is Disposition.DENY or served.value is None:
        raise ExportRefused(
            f"{ref}: {served.rung.value} may not cross S4 egress — nothing "
            "crossed, so nothing is exported and nothing is ledgered as one."
        )

    # The content leaves in the artifact and nowhere near a log.
    artifact = _write_artifact(
        exports or paths.exports_dir(), matter, item_type, item_id, served.value
    )

    # Exactly one provable entry — a reference and the purpose, never content.
    log = integrity or ledger()
    log.append(
        {
            "act": Event.EXPORTED.value,
            "matter": matter,
            "item_type": item_type,
            "item_id": item_id,
            "purpose": purpose.value,
            "rung": served.rung.value,
            "disposition": served.disposition.value,
        }
    )
    head = log.head()

    # The operator-visible act — a closed Event and a reference, no content.
    (visible or VisibleLog()).record(
        Event.EXPORTED, ref=(matter, item_type, item_id)
    )

    return ExportReceipt(
        ref=ref,
        purpose=purpose,
        rung=served.rung,
        disposition=served.disposition,
        artifact=artifact,
        head=head,
    )
