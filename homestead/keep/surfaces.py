"""The four surfaces a render can happen on — and the five members that takes.

See `docs/homestead-rungs.md` in the safe-app-store for the model and its
provenance. Adapted from `terpsi-music/docs/SENSITIVITY.md`, whose crossing
table was itself written in the shape of `law-gazelle`'s permission table.

Terpsi scores its ladder against **principals** — six populations across an
untrusted relay, with `guardian_of` / `judge_at` / `staff_of` edges between
them. A household has one operator, no relay and no untrusted server, so those
edges collapse. What replaces them is this: **the question is not who may see
it, it is what crosses a boundary.** So the ladder is scored against surfaces.

## The four, and why they are five members

| Member | Surface | What it is |
|---|---|---|
| `S1_LIST` | S1 · the operator's own screen | The **list** pane. Ambient — it draws things the operator did not ask for one at a time. |
| `S1_DETAIL` | S1 · the operator's own screen | The **detail** pane. Opened deliberately, one record at a time. |
| `S2_PROMPT` | S2 · a model prompt | Anything placed in a local LLM's context window. |
| `S3_AGENT` | S3 · agent retrieval | The MCP entry point, over stdio, invoked as a subprocess. Never a listening port (I-30). |
| `S4_EGRESS` | S4 · egress | Drafts, exports, filings, commit manifests — anything that leaves. |

**S1 is one surface and two members because the difference between its panes is
the whole of I-35.** The list cannot render an `L4` payload — not by policy but
because its ceiling is below `L4` and the ambient row type has nowhere to put
one. The detail pane can, and takes no `purpose` argument to do it: *the
deliberate act of opening it is the purpose declaration*, decided 2026-08-04
"by widget, not by dialog", so a person in crisis pays no ceremony tax.

**S2 is a rendering.** This is the point most easily missed. A prompt is not
"internal processing"; it is a surface with a reader that summarizes, caches,
and produces text a human acts on. `intelligence.py` was governed as plumbing
and that is how eight lines of activity log — including 80 characters of every
private note — reached a model (F-3/F-4). Under this model it is a render path.

## What this module holds, and what it does not

It holds the **members** and the facts that are true of a surface on its own:
what it is, whether it is ambient, whether it leaves the machine.

It does **not** hold the crossing — which rung may be served here, and on what
condition. That lives in `homestead.keep.rungs` with `may_render()` and
`decide()`, in one place, because the rung model says it lives in one place. If
you are looking for the ceiling table, it is `rungs._CEILING`, and `rungs`
checks at import that every member of this enum appears in it.

## What it does not cover

* **No trust tier.** The crossing table also carries WillowGate tiers —
  S3 needs `≥ Rookie` for `L1`/`L2`, `≥ Steady` for `L3`, `≥ Veteran` for `L4`.
  None of that is represented here or enforced anywhere in this package. A
  surface answering `may_render` has not checked who is asking.
* **No ledgering.** `L3` and `L4` on S4 require an explicit act *recorded in the
  ledger*. The ledger seam is Phase 3+; nothing here writes to it, and nothing
  here refuses to serve because a write did not happen.
* **No widget.** These are not windows. Phase 4 builds the windows and must
  route every render through `rungs.decide()`; nothing in this module can make
  it. That chokepoint is I-16 and it is not built — a gate wired to one entry
  point is not a gate, and at Phase 2 it is wired to none.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["Surface", "SurfaceFacts", "FACTS", "facts"]


class Surface(str, Enum):
    """Every render happens on exactly one of these, and is scored against it.

    A `str` enum for the same reason a `Rung` is (I-14): the value that ends up
    in a log line, a manifest or an error message should read as itself.

    That is *all* it is for. The decision functions in `rungs` take the member
    and refuse the bare spelling — a surface is code, not data, and R-7's lesson
    is that a free string in the first argument of a permission call is where
    the leak goes. Being readable in a log is not a licence to be accepted in a
    gate.
    """

    S1_LIST = "S1_LIST"
    S1_DETAIL = "S1_DETAIL"
    S2_PROMPT = "S2_PROMPT"
    S3_AGENT = "S3_AGENT"
    S4_EGRESS = "S4_EGRESS"


@dataclass(frozen=True)
class SurfaceFacts:
    """What is true of a surface without reference to any rung.

    `ambient` — the surface draws things the operator did not ask for one at a
    time. The list pane is one; the cover (I-31) will be another. `rungs`
    refuses at import to give an ambient surface a ceiling of `L4` or above,
    which is I-35 held as a property of the table rather than as a rule someone
    has to remember when they add the next surface.

    `leaves_the_machine` — the rendered value is outside the operator's own
    disk when it is done. Only S4. S2 is a *local* model and S3 is a stdio
    subprocess; both are still renderings, and both are still governed, but
    neither of them is a network.
    """

    what: str
    ambient: bool
    leaves_the_machine: bool


FACTS: dict[Surface, SurfaceFacts] = {
    Surface.S1_LIST: SurfaceFacts(
        what="the operator's own screen, list pane — ambient",
        ambient=True,
        leaves_the_machine=False,
    ),
    Surface.S1_DETAIL: SurfaceFacts(
        what="the operator's own screen, detail pane — opened deliberately",
        ambient=False,
        leaves_the_machine=False,
    ),
    Surface.S2_PROMPT: SurfaceFacts(
        what="a local model's context window",
        ambient=False,
        leaves_the_machine=False,
    ),
    Surface.S3_AGENT: SurfaceFacts(
        what="agent retrieval over MCP stdio",
        ambient=False,
        leaves_the_machine=False,
    ),
    Surface.S4_EGRESS: SurfaceFacts(
        what="egress — a draft, an export, a filing, a manifest",
        ambient=False,
        leaves_the_machine=True,
    ),
}


# BUG-6 was three matter types enumerated by hand in three places, one of which
# had two. A surface added to the enum and forgotten here is the same shape, so
# it is an ImportError rather than a `KeyError` on the day someone renders to it.
_missing = sorted(s.value for s in Surface if s not in FACTS)
if _missing:
    raise RuntimeError(
        f"surfaces without facts: {_missing}. Every member of Surface must "
        "appear in FACTS — a surface nothing knows anything about is a surface "
        "nothing can score a rung against."
    )
_extra = sorted(str(s) for s in FACTS if not isinstance(s, Surface))
if _extra:
    raise RuntimeError(f"FACTS has keys that are not surfaces: {_extra}")
del _missing, _extra


def facts(surface: Surface) -> SurfaceFacts:
    """The facts for a surface member. `KeyError` for anything that is not one.

    Strict for the same reason `rungs._read_surface` is: a caller holding a
    string has skipped a step somewhere upstream, and this is a cheaper place to
    find that out than a render path.
    """
    if not isinstance(surface, Surface):
        raise KeyError(f"{surface!r} is not a Surface member")
    return FACTS[surface]
