"""The sensitivity ladder. `L1`–`L5`, and higher is more restricted.

See `docs/homestead-rungs.md` in the safe-app-store for the full model and its
provenance (adapted from terpsi-music's SENSITIVITY.md, whose own crossing
table was written in the shape of law-gazelle's permission table).

Two rules live here rather than in prose:

* **I-14 — a rung is a string, never an integer.** `L3`, not `3`. Trust runs
  the *other* direction (`Rookie → Steady → Veteran`, ascending privilege), so
  `if level >= 3` is correct against one scale and catastrophic against the
  other, and it reads perfectly in review either way.

* **Absence fails closed.** `compose()` of nothing is `L5`, not `L1`. An
  unclassified field is a build failure; if one reaches runtime anyway it reads
  `L5` and is not served. A classifier that errors denies.
"""
from __future__ import annotations

from enum import Enum

__all__ = ["Rung", "compose"]


class Rung(str, Enum):
    L1 = "L1"   # public in this matter's forum
    L2 = "L2"   # household — no identity, no protected category
    L3 = "L3"   # attributed — names or resolves to a person
    L4 = "L4"   # protected — identifies AND carries a category the law follows
    L5 = "L5"   # sealed — never served on any surface


_ORDER = {Rung.L1: 1, Rung.L2: 2, Rung.L3: 3, Rung.L4: 4, Rung.L5: 5}


def compose(*rungs: Rung) -> Rung:
    """The `max` of its inputs — records, joins, chronologies, drafts, and a
    model prompt over its whole context window.

    With no inputs the answer is `L5`. Composing nothing is not composing
    something harmless.
    """
    if not rungs:
        return Rung.L5
    return max(rungs, key=lambda r: _ORDER[r])
