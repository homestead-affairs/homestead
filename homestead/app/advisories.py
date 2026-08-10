"""The advisory content matcher, surfaced — the display model for the pane.

`keep/advise` decides whether content is shaped for a rung higher than the one it
was declared at; `Sidecar.advise` runs that over a stored record, read-only,
handing back `Advisory` objects — a category and two rungs, never the datum
(I-15). This module is the last, thin step between that and a pane: it turns those
advisories into lines a view can draw, and returns nothing to draw when there is
nothing to say.

It is a surface (I-29): it holds no matching logic and reaches no `.payload`. The
matching lives in `keep/advise`; here we only render what the store already
decided, through the same one door (`Sidecar.advise`) — so the chokepoint holds
and no content the advisory withheld can leak back in through the display.

The three conditions the matcher is built to are the three this display keeps:

* **Advisory, never a gate.** `advisory_lines` returns lines and raises nothing;
  the view draws them as a muted note and blocks no open, save, or export.
* **It never echoes what it matched.** An `Advisory` carries the category and the
  rungs, not the matched text, so the line built from it cannot quote the SSN it
  found — the leak the matcher exists to prevent.
* **Silence is not a clean bill.** An empty result renders as *nothing*. There is
  no "clean", no "no issues", no reassuring line — absence is *no pattern matched*
  (I-11's posture), and a surface that dressed it up as a verdict would be
  claiming a safety the matcher never promised.
"""
from __future__ import annotations

from homestead.app.window import Ref
from homestead.keep.record import Sidecar

__all__ = ["advisory_lines"]


def advisory_lines(store: Sidecar, ref: Ref) -> tuple[str, ...]:
    """The lines a detail pane should show for one stored record — one per concern
    the store's advisory check raised, and an **empty tuple** when it raised none.

    Goes through `store.advise(matter, item_type, item_id)`, which returns
    `Advisory` objects (category + rungs, never content), so this reaches no
    payload and does its own matching nowhere: it only formats what `keep/advise`
    already decided. Each advisory becomes its own `message()` — a line naming the
    category and the two rungs, the reference an operator needs to raise the rung,
    and nothing of the datum itself.

    An empty tuple is *no pattern matched*, which the pane renders as nothing at
    all — never a "clean" note. It raises on no advisory; it is advisory all the
    way out.
    """
    matter, item_type, item_id = ref
    advisories = store.advise(matter, item_type, item_id)
    return tuple(advisory.message() for advisory in advisories)
