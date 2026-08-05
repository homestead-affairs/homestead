"""The sensitivity ladder, the crossing to surfaces, and the decision function.

`L1`–`L5`, and higher is more restricted. See `docs/homestead-rungs.md` in the
safe-app-store for the full model and its provenance (adapted from
terpsi-music's SENSITIVITY.md, whose own crossing table was written in the shape
of law-gazelle's permission table).

This module is `workflow._fact_blocked`'s successor. That function was a single
boolean over one status value; this is `(rung, surface, purpose) → render |
derive | deny`.

Four rules live here rather than in prose:

* **I-14 — a rung is a string, never an integer.** `L3`, not `3`. Trust runs
  the *other* direction (`Rookie → Steady → Veteran`, ascending privilege), so
  `if level >= 3` is correct against one scale and catastrophic against the
  other, and it reads perfectly in review either way.

* **I-12 — composition is `max`, everywhere.** A record is the `max` of its
  fields, a chronology of its events, a draft of every fact it cites, and **a
  prompt is the `max` of its whole context window**, retrieved neighbours
  included. A projection never lowers a rung.

* **I-11 — absence fails closed, twice over.** `compose()` of nothing is `L5`.
  `classify_schema()` refuses a field with no rung, at schema-definition time,
  which is a **build failure**. If an unclassified value reaches `may_render()`
  or `decide()` anyway it reads `L5` and is not served. A classifier that errors
  denies; it never returns `L1`.

* **I-13 — `L5` has no override anywhere, and `L4` never reaches a prompt.**
  Both are properties of the ceiling table below rather than cases in a
  conditional, and both are checked when this module is imported.

## The crossing, and why it is ten numbers rather than twenty-five

`_CEILING` gives each surface **two** rungs: the highest whose *payload* may be
rendered there with no purpose declared, and the highest with one. `may_render`
is a threshold comparison against that ceiling and nothing else.

That shape is deliberate, and it is BUG-5's answer. BUG-5 was a hand-written
guard that tested `status == "needs_source"` and therefore let `do_not_use` —
the **stronger** rejection — walk straight past it into the drafting packet and
the model prompt, while the screen said "Excluded from drafting". A guard
checked a weaker condition and the stronger case was the one that did not work.
A twenty-five-cell table is where that hides, because every cell is an
independent thing an author can get wrong.

Against a threshold it is unrepresentable: **if a rung is refused on a surface,
every higher rung is refused on that surface**, by arithmetic, for every surface
at once, without anyone remembering to check. `L5` is refused everywhere
because no ceiling is `L5` — not because five rows say `never`.

## What it does not do

* **It does not know who is asking.** The crossing table in the spec also
  carries WillowGate trust tiers (S3 needs `≥ Veteran` for `L4`). Nothing here
  reads a tier, and `may_render() is True` is not an authorization.
* **It does not ledger.** `L3` and `L4` on S4 require an explicit act *recorded*
  in the ledger. This module returns a decision; it writes nothing and refuses
  nothing on the grounds that a write did not happen.
* **It is not a chokepoint.** I-16 wants one authorization point covering every
  surface. `serve()` and `ambient_rows()` are the *shape* of one, but nothing
  compels a caller to use them: a Phase 4 renderer that reads
  `Classified.payload` directly is not stopped by anything in this file. A gate
  wired to one entry point is not a gate, and at Phase 2 it is wired to none.
* **It does not declassify, and there is deliberately no function that does.**
  Declassification is an act with a name and a date, recorded in the ledger.
  Nothing here lowers a rung by inertia, on a schedule, or as a side effect of
  aggregation — `compose` is `max`, so aggregation can only raise.
* **It does not know what a field is about.** `classify_schema` checks that a
  rung was declared, not that it was declared *well*. Step 5 of the spec's
  classification procedure — record the matter type and jurisdiction, because
  a case number is `L1` in a bankruptcy and `L3` in a family matter — needs the
  registry, which is Phase 3.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .surfaces import FACTS, Surface

__all__ = [
    "Rung",
    "Surface",
    "Disposition",
    "compose",
    "context_rung",
    "classify_schema",
    "UnclassifiedField",
    "UnknownSurface",
    "may_render",
    "decide",
    "Classified",
    "Served",
    "AmbientRow",
    "serve",
    "serve_all",
    "ambient_rows",
]


class Rung(str, Enum):
    L1 = "L1"   # public in this matter's forum
    L2 = "L2"   # household — no identity, no protected category
    L3 = "L3"   # attributed — names or resolves to a person
    L4 = "L4"   # protected — identifies AND carries a category the law follows
    L5 = "L5"   # sealed — never served on any surface


_ORDER = {Rung.L1: 1, Rung.L2: 2, Rung.L3: 3, Rung.L4: 4, Rung.L5: 5}


class Disposition(str, Enum):
    """What a surface may be handed for one datum.

    `DERIVE` and `DENY` are not the same thing and conflating them is BUG-5's
    other half. `DERIVE` means *serve the instruction instead of the datum* —
    "Medical records response due Aug 15", which is everything the operator
    needs in order to act. `DENY` means **nothing at all, including the
    instruction**, because at `L5` the existence of a refusal is itself the
    thing that must not be rendered.
    """

    RENDER = "render"     # the payload itself
    DERIVE = "derive"     # the instruction that stands in for the payload
    DENY = "deny"         # nothing — not the payload, not a stand-in, not a count


class UnclassifiedField(ValueError):
    """A field that reached the classifier without a rung it could read.

    Raised at schema-definition time, which is import time, which makes it a
    **build failure** (I-11). It is deliberately not a return value: a
    classifier that can answer "I don't know" is a classifier whose answer gets
    defaulted to something, and the default that gets chosen is never `L5`.
    """


class UnknownSurface(TypeError):
    """Anything in the surface slot that is not a `Surface` member.

    Unlike an unreadable *rung*, this raises rather than denying, and it is
    strict about the type rather than about the spelling.

    **A rung is data.** It comes out of a record, a schema declares it as the
    string `"L3"` (I-14), and it can legitimately be missing — so absence there
    must fail closed to `L5` and be *served as nothing*, which is what the spec
    says in as many words.

    **A surface is code.** The call site is a render path; it knows which one it
    is, and it has no reason to hold a string. `Surface` is a `str` enum so that
    its value reads as itself in a log line, not so that a permission check will
    accept a bare string in the argument that decides what may cross a boundary.
    R-7 is the precedent: `VisibleLog.record`'s first argument was a free string
    and that is where the note content leaked, so it became a closed enum.

    A mistyped surface that quietly returned `False` would draw an empty pane
    with no cause, and an empty pane with no cause gets "fixed" by deleting the
    check. It is a `TypeError` because that is what it is.
    """


# ── composition ──────────────────────────────────────────────────────────────

def compose(*rungs: Rung) -> Rung:
    """The `max` of its inputs — records, joins, chronologies, drafts, and a
    model prompt over its whole context window.

    With no inputs the answer is `L5`. Composing nothing is not composing
    something harmless.
    """
    if not rungs:
        return Rung.L5
    return max(rungs, key=lambda r: _ORDER[r])


def context_rung(items: Iterable[Any]) -> Rung:
    """The rung of a whole context window (I-12).

    A prompt is not scored per fragment. It is the `max` of everything that
    ends up in it — the record, the chronology, the draft, **and the neighbours
    a semantic search pulled in without anyone choosing them one at a time.**
    That last clause is the one that gets skipped, and it is the one that turns
    a retrieval seam into an `L4` leak.

    Accepts `Rung`s, `Classified`s, or anything `_read_rung` can read. Anything
    it cannot read counts as `L5`, so an unclassified neighbour raises the whole
    window rather than being quietly skipped. An empty window is `L5` for the
    same reason `compose()` of nothing is.
    """
    rungs = []
    for item in items:
        rung = item.rung if isinstance(item, Classified) else _read_rung(item)
        rungs.append(rung if rung is not None else Rung.L5)
    return compose(*rungs)


# ── reading a rung, and reading a surface ────────────────────────────────────

def _read_rung(value: Any) -> Rung | None:
    """A `Rung` from a value, or `None` if this is not one.

    `None` means *unclassified*, and every caller turns that into `L5`. It is
    never turned into `L1`.

    `True` is an `int` and `Rung` is a `str`, so the isinstance order matters:
    booleans and integers are refused before anything tries to look them up.
    An integer rung is I-14's catastrophe arriving as data instead of as code.
    """
    if isinstance(value, Rung):
        return value
    if isinstance(value, bool) or not isinstance(value, str):
        return None
    try:
        return Rung(value)
    except ValueError:
        return None


def _read_surface(value: Any) -> Surface:
    if isinstance(value, Surface):
        return value
    raise UnknownSurface(
        f"{value!r} is not a Surface. Every render happens on exactly one of "
        f"{[s.name for s in Surface]}, the caller is the one that knows which, "
        "and it passes the member — not its spelling. A string here is the "
        "shape argument one of `log_activity(event_type, summary)` had."
    )


def _declared(purpose: Any) -> bool:
    """Whether a purpose was actually declared.

    `None`, `""`, `"   "` and anything that is not text are all *no purpose*.
    A purpose is an explicit act by a person; a blank string is the absence of
    one arriving in the shape of one, and it must not lift a ceiling. Nothing
    here validates that the purpose is a *good* one — see the module docstring.
    """
    return isinstance(purpose, str) and not isinstance(purpose, bool) and bool(purpose.strip())


# ── the crossing ─────────────────────────────────────────────────────────────

#: Per surface: (highest rung whose PAYLOAD renders with no purpose declared,
#: highest with one). Transcribed from the crossing table in
#: `docs/homestead-rungs.md`, which is the only place the mapping is stated.
#:
#: Read it against that table:
#:   S1 list    — L1/L2/L3 render; L4 is derived and *purpose does not lift it*
#:                (I-35: the ambient path has nowhere to put a payload); L5 never.
#:   S1 detail  — L4 renders, and takes no purpose: opening the pane is the
#:                declaration. Decided 2026-08-04, by widget rather than dialog.
#:   S2 prompt  — L3 derived, L4 derived *with no exception*. Purpose lifts
#:                nothing here at all: "if a local model needs the diagnosis to
#:                do its job, that is a signal the job is wrong."
#:   S3 agent   — L3 derived, L4 derived unless a purpose is declared.
#:   S4 egress  — same ceilings as S3. What differs between them is the trust
#:                tier and the ledger entry, and this module enforces neither;
#:                identical ceilings are the honest transcription rather than a
#:                copy-paste.
_CEILING: dict[Surface, tuple[Rung, Rung]] = {
    Surface.S1_LIST:   (Rung.L3, Rung.L3),
    Surface.S1_DETAIL: (Rung.L4, Rung.L4),
    Surface.S2_PROMPT: (Rung.L2, Rung.L2),
    Surface.S3_AGENT:  (Rung.L2, Rung.L4),
    Surface.S4_EGRESS: (Rung.L2, Rung.L4),
}


def _check_crossing() -> frozenset[Rung]:
    """Validate the table at import, and derive what follows from it.

    Every one of these is a property the rest of the module then gets to assume
    rather than re-check, and every one of them is the kind of thing a
    twenty-five-cell table lets an author get wrong in exactly one cell.
    """
    missing = sorted(s.value for s in Surface if s not in _CEILING)
    if missing:
        raise RuntimeError(
            f"surfaces with no ceiling: {missing}. A surface added to the enum "
            "and forgotten here would fail open on the day something rendered "
            "to it — which is BUG-6's shape, one member missing from a "
            "hand-kept enumeration."
        )
    for surface, (plain, with_purpose) in _CEILING.items():
        if not isinstance(surface, Surface):
            raise RuntimeError(f"_CEILING has a key that is not a surface: {surface!r}")
        for ceiling in (plain, with_purpose):
            if not isinstance(ceiling, Rung):
                raise RuntimeError(
                    f"{surface.value}: a ceiling must be a Rung, not "
                    f"{type(ceiling).__name__} — I-14, and a bare integer here "
                    "would compare against the wrong scale silently"
                )
            if ceiling is Rung.L5:
                raise RuntimeError(
                    f"{surface.value}: no surface may have an L5 ceiling. "
                    "I-13 — L5 has no override anywhere: no purpose, no "
                    "surface, no flag. A rung with an escape hatch is a label, "
                    "not a control."
                )
        if _ORDER[with_purpose] < _ORDER[plain]:
            raise RuntimeError(
                f"{surface.value}: declaring a purpose must never *lower* a "
                f"ceiling ({plain.value} without, {with_purpose.value} with)."
            )
        if FACTS[surface].ambient and _ORDER[with_purpose] >= _ORDER[Rung.L4]:
            raise RuntimeError(
                f"{surface.value} is ambient and its ceiling is "
                f"{with_purpose.value}. I-35 — an ambient surface draws things "
                "the operator did not ask for one at a time, so an L4 payload "
                "on one is sensitive material rendered by default."
            )

    # The rungs that can ever be served as a stand-in rather than as themselves:
    # above the lowest ceiling any surface has, and below L5 (which is served as
    # nothing at all). Derived rather than written down, so it stays true if a
    # ceiling moves. `Classified` demands a derived form for exactly these.
    floor = min((plain for plain, _ in _CEILING.values()), key=lambda r: _ORDER[r])
    return frozenset(
        r for r in Rung if _ORDER[floor] < _ORDER[r] < _ORDER[Rung.L5]
    )


_NEEDS_DERIVED = _check_crossing()


# ── the decision function ────────────────────────────────────────────────────

def may_render(rung: Any, surface: Any, *, purpose: Any = None) -> bool:
    """May the **payload** of a datum at `rung` be rendered on `surface`?

    `True` means the datum itself. `False` means it may not be, and says
    nothing about whether a derived form may — use `decide()` for that, because
    the difference between "serve the instruction instead" and "serve nothing"
    is a difference `_fact_blocked` did not have and needed.

    `purpose` is a declared reason, and it can only ever *lift* a ceiling. A
    blank or non-text purpose is no purpose. On S1's detail pane it is neither
    required nor refused: the act of opening the pane is the declaration, and an
    extra string buys nothing.

    An unreadable rung — `None`, `"unknown"`, `3` — reads `L5` and returns
    `False`. An unreadable surface raises; see `UnknownSurface`.
    """
    target = _read_surface(surface)
    read = _read_rung(rung)
    if read is None:
        return False
    plain, with_purpose = _CEILING[target]
    ceiling = with_purpose if _declared(purpose) else plain
    return _ORDER[read] <= _ORDER[ceiling]


def decide(rung: Any, surface: Any, *, purpose: Any = None) -> Disposition:
    """`(rung, surface, purpose) → render | derive | deny`.

    The whole of what `workflow._fact_blocked` should have been. `DENY` is
    reached by `L5` and by an unreadable rung, and by nothing else — every
    other refusal is a `DERIVE`, because a household that cannot see the
    instruction cannot act on the deadline.
    """
    target = _read_surface(surface)
    read = _read_rung(rung)
    if read is None or read is Rung.L5:
        return Disposition.DENY
    return Disposition.RENDER if may_render(read, target, purpose=purpose) else Disposition.DERIVE


# ── what a surface is handed ─────────────────────────────────────────────────

@dataclass(frozen=True)
class Classified:
    """One datum, its rung, and the instruction that stands in for it.

    `derived` is **required for every rung that can ever be derived** — which
    the crossing table says is `L3` and `L4`, and which is computed from that
    table rather than written down here. That requirement is the other half of
    BUG-5: law-gazelle's screen said "Excluded from drafting" while the packet
    carried the atom, and the mismatch was possible because the exclusion had no
    representation of what to show instead. Here a datum that *can* be withheld
    arrives carrying the true sentence to put in its place.

    `L5` needs none: it is never served, in any form.

    **`derived` is not checked for safety and cannot be.** Nothing here can
    tell whether "a recurring parenting-time obligation on Tue/Thu" leaks less
    than the schedule it replaces — that is the re-identification judgement the
    spec puts on a human at classification time, and this class only insists
    that a human made one.
    """

    rung: Rung
    payload: Any
    derived: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.rung, Rung):
            raise UnclassifiedField(
                f"a classified datum needs a Rung, not {self.rung!r}. This is "
                "the build-time half of I-11 — construction is where an "
                "unclassified value should stop, so nothing downstream has to "
                "decide what to do with one."
            )
        if self.rung in _NEEDS_DERIVED and not (
            isinstance(self.derived, str) and self.derived.strip()
        ):
            raise UnclassifiedField(
                f"{self.rung.value} is served as a derived form on at least one "
                "surface, so it must carry one. A withheld payload with nothing "
                "in its place is the screen saying 'Excluded from drafting' over "
                "a packet that still contains the fact (BUG-5)."
            )


@dataclass(frozen=True)
class Served:
    """The answer for one datum on one surface: what may go, and what went.

    `value` is the payload under `RENDER`, the derived form under `DERIVE`, and
    `None` under `DENY` — where it is `None` because the payload is **not in
    this object at all**, not because it was blanked. That is the difference
    from law-gazelle, whose drafting packet contained the `do_not_use` atom and
    merely failed to mark it.
    """

    surface: Surface
    rung: Rung
    disposition: Disposition
    value: Any | None


def serve(item: Classified, surface: Any, *, purpose: Any = None) -> Served:
    """Score one datum against one surface and hand back only what may go.

    A `DENY` result tells the caller *that* something was withheld; it never
    tells them what. Rendering "1 item withheld" is itself a rendering, and at
    `L5` the existence of a refusal is exactly what must not be revealed — see
    `serve_all`, which drops denials without leaving a count behind.
    """
    if not isinstance(item, Classified):
        raise TypeError(
            f"serve() takes a Classified, not {type(item).__name__} — an "
            "unclassified value has no rung to score and must not acquire one "
            "here (I-11)"
        )
    target = _read_surface(surface)
    disposition = decide(item.rung, target, purpose=purpose)
    if disposition is Disposition.RENDER:
        value = item.payload
    elif disposition is Disposition.DERIVE:
        value = item.derived
    else:
        value = None
    return Served(surface=target, rung=item.rung, disposition=disposition, value=value)


def serve_all(
    items: Iterable[Classified], surface: Any, *, purpose: Any = None
) -> list[Served]:
    """`serve()` over many, with denials **dropped rather than marked**.

    The result is what the surface may have and nothing else: no placeholder,
    no count, no ordering gap that reconstructs one. A `do_not_use` fact is not
    in the drafting packet flagged; it is not in the drafting packet.

    The composed rung of the result is bounded by the surface's ceiling, which
    is I-12 pointed at S2: a prompt assembled this way cannot exceed what the
    prompt may hold, however many neighbours retrieval pulled in.
    """
    target = _read_surface(surface)
    out = [serve(item, target, purpose=purpose) for item in items]
    return [s for s in out if s.disposition is not Disposition.DENY]


@dataclass(frozen=True)
class AmbientRow:
    """One line in an ambient pane. A rung, and a line of text.

    **This type is I-35.** The list pane cannot render an `L4` payload not
    because a check refuses it but because the object a list pane draws has
    nowhere to keep one: `text` is the derived form whenever the rung is above
    the ambient ceiling, and there is no other attribute. A Phase 4 renderer
    typed to take these has no expression that reaches a payload.

    `rung` is here for I-33 — one indicator per surface, *"showing derived · L4
    present"* — which needs to know that an `L4` is on the pane without putting
    a badge on fifty rows. See PHASE2-SURFACES.md: whether that indicator may
    also say an `L5` is present is a product decision, and it is not this one.
    """

    rung: Rung
    text: str


def ambient_rows(items: Iterable[Classified]) -> list[AmbientRow]:
    """The list pane's whole render path (I-35).

    Denials are dropped. Anything above the ambient ceiling is the derived form.
    Nothing that comes out of here carries a payload it should not, because
    nothing that comes out of here carries a payload at all — `text` is a string
    that was either the payload or the stand-in, and by then the choice is made.
    """
    rows: list[AmbientRow] = []
    for served in serve_all(items, Surface.S1_LIST):
        rows.append(AmbientRow(rung=served.rung, text=str(served.value)))
    return rows


# ── classification, at schema-definition time ────────────────────────────────

def _rung_of_declaration(declaration: Any) -> tuple[Rung | None, str]:
    """Read one field's declaration. Returns `(rung, why-not)`.

    Accepted: a `Rung`; the string spelling of one (`"L3"`); a mapping with a
    `"rung"` key; any object with a `.rung` attribute. That last two are so a
    schema can carry the matter, the jurisdiction and the sentence explaining
    the choice alongside the rung — the spec's step 5 — without this function
    having to know the shape of the thing that carries them.
    """
    if declaration is None:
        return None, "declares no rung"
    if isinstance(declaration, Rung):
        return declaration, ""
    if isinstance(declaration, bool) or isinstance(declaration, int):
        return None, (
            f"declares {declaration!r}. Rungs are strings — `L3`, never `3` "
            "(I-14). Trust runs the other direction, so an integer here is "
            "read against the wrong scale and reads perfectly in review"
        )
    if isinstance(declaration, str):
        read = _read_rung(declaration)
        if read is None:
            return None, (
                f"declares {declaration!r}, which is not a rung. The ladder is "
                f"{[r.value for r in Rung]}"
            )
        return read, ""
    if isinstance(declaration, Mapping):
        if "rung" not in declaration:
            return None, (
                "is a mapping with no 'rung' key. A nested schema is not a "
                "declaration at Phase 2 — classify it separately and compose() "
                "the results, so the max is taken deliberately"
            )
        return _rung_of_declaration(declaration["rung"])
    if hasattr(declaration, "rung"):
        return _rung_of_declaration(declaration.rung)
    return None, (
        f"declares a {type(declaration).__name__}, which carries no rung this "
        "classifier can read"
    )


def classify_schema(schema: Mapping[str, Any]) -> dict[str, Rung]:
    """Every field's rung, or refuse — and refusing is a **build failure**.

    This is I-11's first half. A schema is defined at import time, so calling
    this from a schema definition means an unclassified field stops the process
    that is defining it: the build fails, rather than the field defaulting to
    something. The second half is at runtime, in `may_render` and `decide`,
    where an unreadable rung reads `L5` and is not served.

    Refuses, and names every offending field rather than the first:

    * a field with no rung (`None`), which is the case the contract pins;
    * an **integer** rung — `3`, `4`, `True` — with the I-14 reason attached,
      because that is not a typo, it is the cross-scale confusion arriving;
    * a string that is not a rung (`"L6"`, `"unknown"`, `""`);
    * a mapping with no `"rung"` key, including a nested schema — compose those
      deliberately rather than letting this function pick a `max` for you;
    * an **empty schema**, because a classifier that ran and found nothing is
      absence, and absence fails closed. A schema object with no fields is far
      more often a definition that failed to pick anything up than it is a
      record with nothing in it.

    **What it does not check.** That the rung is *right*. A case number is `L1`
    in a bankruptcy and `L3` in a family matter — the spec's step 5 says record
    the matter type and the jurisdiction alongside the rung, and neither is
    derivable from the field name. This function will accept `L1` for a sealed
    family case number without a murmur. Holding a schema to its matter needs
    the registry, which is Phase 3 (I-23).
    """
    if not isinstance(schema, Mapping):
        raise TypeError(
            f"a schema is a mapping of field name to declaration, not "
            f"{type(schema).__name__}"
        )
    if not schema:
        raise UnclassifiedField(
            "an empty schema classifies nothing, and classifying nothing is not "
            "the same as having nothing to classify. Absence fails closed "
            "(I-11): a definition that picked up no fields must stop the build, "
            "not return an empty answer that composes to L5 somewhere later."
        )

    classified: dict[str, Rung] = {}
    problems: list[str] = []
    for name, declaration in schema.items():
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{name!r}: a field name must be a non-empty string")
            continue
        rung, why_not = _rung_of_declaration(declaration)
        if rung is None:
            problems.append(f"{name!r}: {why_not}")
        else:
            classified[name] = rung

    if problems:
        raise UnclassifiedField(
            "every field carries a rung, set at schema-definition time — an "
            "unclassified field is a build failure (I-11), not a default. "
            + "; ".join(problems)
            + ". Classify with docs/homestead-rungs.md 'Classifying a new "
            "field': public in this matter's forum → L1; names or resolves to "
            "a person → L3; and a category the law follows → L4; would "
            "rendering reveal a refusal, expose privileged strategy, disclose "
            "key material or breach a sealing order → L5."
        )
    return classified
