"""S1 — the window's surface state (bite 4).

`Window` is the two S1 panes as a state machine, with no display attached. It
rests on the **cover** (I-21: the record is not drawn before a human asks), and
on request it composes either the **list** (the S1_LIST pane) or the **detail**
(the S1_DETAIL pane). A view — tkinter, in `view.py` — draws whatever the window
is currently holding.

The split is deliberate and it is I-29: **the surface holds no domain logic.**
Everything here composes through `serve()` and calculates nothing — no rung is
compared, no ceiling read, no `.payload` reached. What the window keeps are
`Row`s (a reference, a rung, and a line of already-served text) and a `Served`,
which have been through the gate. That is why the list cannot show an `L4`
payload and the cover cannot show anything: the shape of what the window holds,
not a check in this file.

**A `Row` carries a reference, never a record.** To open an item the surface has
to name it, and the name is its key — `(matter, item_type, item_id)`, a
reference exactly as a log entry is (I-15), never the datum. So the list can be
interactive without a payload ever living on it: a click carries a ref back to
`open_detail`, which re-serves that one record for the pane the operator opened.
The window holds the matter's loaded records as an in-memory working set keyed by
ref, and lets go of them on `close()` — the ground I-32's reveal-timeout builds
on.

The crossing does the rest:

* **list** (`S1_LIST`, ceiling `L3`) — `L1`-`L3` render their payloads, `L4`
  shows its derived form, `L5` is dropped without a trace (product decision 2).
* **detail** (`S1_DETAIL`, ceiling `L4`) — opening it *is* the purpose
  declaration (by widget, 2026-08-04), so an `L4` payload renders; `L5` still
  denies, because `L5` has no override anywhere (I-13).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from homestead.keep.rungs import (
    Classified,
    Disposition,
    Rung,
    Served,
    Surface,
    serve,
)

__all__ = ["Ref", "Row", "Window"]

#: A reference to one record — its key, not its content (I-15). Safe to hold on a
#: surface and to carry back on a click.
Ref = tuple[str, str, str]

_COVER = "cover"
_LIST = "list"
_DETAIL = "detail"


@dataclass(frozen=True)
class Row:
    """One line in the list pane: a reference, a rung, and the served text.

    `text` is what `serve(S1_LIST)` handed back — the payload for `L1`-`L3`, the
    derived form for `L4`. It is never a withheld payload, because an `L5` never
    becomes a `Row` at all. `ref` is the record's key, so a click can open it
    without the payload ever having lived here.
    """

    ref: Ref
    rung: Rung
    text: str


class Window:
    """The S1 surface, resting on the cover until a human asks.

    `state` is one of `"cover"`, `"list"`, `"detail"`. `rows` are the composed
    list; `detail` is the served datum of the open pane. Both are empty at rest —
    the cover draws nothing (I-21).
    """

    def __init__(self) -> None:
        self._state = _COVER
        self._rows: list[Row] = []
        self._detail: Served | None = None
        self._records: dict[Ref, Classified] = {}

    @property
    def state(self) -> str:
        return self._state

    @property
    def rows(self) -> list[Row]:
        """The list pane's rows — a copy, so a view holding them cannot mutate
        the surface's state."""
        return list(self._rows)

    @property
    def detail(self) -> Served | None:
        return self._detail

    def open_list(self, items: Iterable[tuple[Ref, Classified]]) -> list[Row]:
        """Compose the list pane (`S1_LIST`) from a matter's records, each paired
        with its reference. The gate drops `L5`, derives `L4`, and renders the
        rest; a dropped record leaves no row and no trace, so the list cannot
        even count what it withheld. The records are kept keyed by ref so a click
        can open one — the ref is the only handle the list keeps on a payload."""
        self._records = {}
        rows: list[Row] = []
        for ref, record in items:
            self._records[ref] = record
            served = serve(record, Surface.S1_LIST)
            if served.disposition is Disposition.DENY:
                continue
            rows.append(Row(ref=ref, rung=served.rung, text=str(served.value)))
        self._rows = rows
        self._detail = None
        self._state = _LIST
        return self.rows

    def open_detail(self, ref: Ref) -> Served:
        """Open one record in the detail pane (`S1_DETAIL`), named by its ref. The
        act of opening is the purpose declaration, so no purpose is passed — and
        `serve` still denies an `L5`, which no act overrides. The record is
        re-served rather than read from the row, so nothing a `Row` carries is a
        payload."""
        record = self._records[ref]
        self._detail = serve(record, Surface.S1_DETAIL)
        self._state = _DETAIL
        return self._detail

    def close(self) -> None:
        """Back to the cover, letting go of the working set and whatever was
        shown. A reveal does not persist past the act that asked for it."""
        self._state = _COVER
        self._rows = []
        self._detail = None
        self._records = {}
