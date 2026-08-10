"""S1 — the window's surface state (bite 4).

`Window` is the two S1 panes as a state machine, with no display attached. It
rests on the **cover** (I-21: the record is not drawn before a human asks), and
on request it composes either the **list** (`ambient_rows`, the S1_LIST pane) or
the **detail** (`serve` against `S1_DETAIL`, the pane the operator opened). A
view — tkinter, in `__main__` — draws whatever the window is currently holding.

The split is deliberate and it is I-29: **the surface holds no domain logic.**
Everything here composes and stores; nothing calculates a rung. `Window` never
compares a rung, never reads the ceiling table, and never reaches a `.payload` —
it asks `ambient_rows`/`serve` and keeps back `AmbientRow.text` and
`Served.value`, which have already been through the gate. That is why the list
cannot show an `L4` payload and the cover cannot show anything: not a check in
this file, but the shape of the objects this file is handed.

The crossing does the rest, and it is worth stating what the panes then show:

* **list** (`S1_LIST`, ceiling `L3`) — `L1`–`L3` render their payloads, `L4`
  shows its derived form, `L5` is dropped without a trace (product decision 2).
* **detail** (`S1_DETAIL`, ceiling `L4`) — opening it *is* the purpose
  declaration (by widget, 2026-08-04), so an `L4` payload renders; `L5` still
  denies, because `L5` has no override anywhere (I-13).
"""
from __future__ import annotations

from typing import Iterable

from homestead.keep.rungs import (
    AmbientRow,
    Classified,
    Served,
    Surface,
    ambient_rows,
    serve,
)

__all__ = ["Window"]

_COVER = "cover"
_LIST = "list"
_DETAIL = "detail"


class Window:
    """The S1 surface, resting on the cover until a human asks.

    `state` is one of `"cover"`, `"list"`, `"detail"`. `rows` are the composed
    ambient rows of the list; `detail` is the served datum of the open pane. Both
    are empty at rest — the cover draws nothing (I-21).
    """

    def __init__(self) -> None:
        self._state = _COVER
        self._rows: list[AmbientRow] = []
        self._detail: Served | None = None

    @property
    def state(self) -> str:
        return self._state

    @property
    def rows(self) -> list[AmbientRow]:
        """The list pane's rows — a copy, so a view cannot mutate the surface's
        state by holding onto them."""
        return list(self._rows)

    @property
    def detail(self) -> Served | None:
        return self._detail

    def open_list(self, records: Iterable[Classified]) -> list[AmbientRow]:
        """Compose the list pane (`S1_LIST`). The gate drops `L5`, derives `L4`,
        and renders the rest; this only asks and keeps the answer."""
        self._rows = ambient_rows(records)
        self._detail = None
        self._state = _LIST
        return self.rows

    def open_detail(self, record: Classified) -> Served:
        """Open one record in the detail pane (`S1_DETAIL`). The act of opening
        is the purpose declaration, so no purpose is passed — and `serve` still
        denies an `L5`, which no act overrides."""
        self._detail = serve(record, Surface.S1_DETAIL)
        self._state = _DETAIL
        return self._detail

    def close(self) -> None:
        """Back to the cover, letting go of whatever was shown. A reveal does not
        persist past the act that asked for it (the ground I-32's timeout builds
        on)."""
        self._state = _COVER
        self._rows = []
        self._detail = None
