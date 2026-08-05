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

* **Loud on type, closed on data** (ratified 2026-08-05). The *surface* and the
  *purpose* are call-site properties: the code that renders knows which surface
  it is and why it is asking, and neither can arrive out of a record. So both
  raise on anything unreadable — `UnknownSurface`, `UndeclaredPurpose`. The
  *rung* is a data property, so an unreadable one reads `L5` and denies quietly
  (I-11). The asymmetry is the whole rule and not an oversight.

## A purpose is a closed enum, and per-call

`Purpose` is a closed set of members and `purpose=None` means none declared,
which is not an error. Anything else raises. A purpose used to be any non-blank
string, which meant `"x"` bought the same lift as `"medical"` — and I-13 calls a declared
purpose a *control*, so that made it a label. Closing the set changed no answer:
it was a tightening of what counts as **declared**, not a change to the
crossing.

**A purpose lifts on S4 and nowhere else.** S3's column was closed on
2026-08-05 — the only change to the crossing since Phase 2 — because closing
the set had made plain what the set was doing there: no member outranks
another, so "declare a purpose" was a boolean any of six constants set, buying
two rungs on the surface with no human in the loop, against a ledger entry that
is Phase 3+ and unbuilt. S3 keeps its `L1` and `L2` payloads and takes the
derived form above that. See the S3 row of `_CEILING`.

Nothing here remembers a purpose between calls, and that is now a stated
invariant rather than an accident of statelessness. One declaration lifts one
call. A session cache would turn the set into one hardcoded string per
call site inside a month, after which `L4` on S4 is unlocked unconditionally
and the whole thing is decorative — which is the same failure the S3 column was
closed for, arriving by a different road.

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
  reads a tier, and `may_render() is True` is not an authorization. That gap is
  why S3's purpose column is closed rather than gated: a lift conditioned on a
  tier this module cannot read is a lift conditioned on nothing.
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
    "Purpose",
    "Disposition",
    "compose",
    "context_rung",
    "classify_schema",
    "UnclassifiedField",
    "UnknownSurface",
    "UndeclaredPurpose",
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


class Purpose(str, Enum):
    """The closed set of reasons a call site may declare. Ratified 2026-08-05.

    A purpose used to be any non-blank string, and that made it a label rather
    than a control: `"x"` bought the same lift as `"medical"`. I-13 calls a
    declared purpose a control, and *a control nothing can check is a label* —
    which is the sentence that renamed `SealedLog`. R-7 is the same shape and
    the same answer: `VisibleLog.record`'s first argument was a free string,
    that is where the note content leaked, and it became a closed enum.

    **Closing the set changed no answer.** That was a tightening of what counts
    as *declared*, not a change to the crossing. **Closing S3's column, on
    2026-08-05, did change answers** — deliberately, and it is the only change
    to the crossing since Phase 2. A purpose now lifts on **S4 alone**, still
    only ever lifts, and still lifts nothing at `L5`.

    The two are worth keeping distinct, because the first is what made the
    second legible. Once every member was interchangeable and none could be
    ranked, "declare a purpose" on S3 was a boolean any of six constants set,
    against a ledger that does not exist — and the surface it unlocked is the
    one with no human in the loop. See the S3 row of `_CEILING`.

    **The ceremony objection does not apply.** "No ceremony tax" was decided
    about S1's detail pane, where opening the pane *is* the declaration and
    `purpose` lifts nothing at all. The one surface where a purpose changes an
    answer is S4, an export, and that caller is not a person typing into a box
    under stress. It is also what makes S4's spec row implementable: *"explicit
    act + purpose + ledgered"* cannot be honoured with free text, because you
    can write a free string to a ledger but you cannot audit it.

    **These six are acts, not categories and not widgets**, and that distinction
    is itself the argument for closing the set. `"medical"` is a data
    *category* — it belongs to the rung, which already carries it at `L4`.
    `"operator opened the record"` is a *surface act* — it belongs to
    `S1_DETAIL`, which already carries it. Free text invited all three kinds of
    thing into one slot and could not tell them apart. **Membership is
    provisional**; see PHASE2-SURFACES.md § 3.

    **`ANSWERING` was `AGENT_RETRIEVAL` until 2026-08-05**, and the rename is
    that same distinction turned on the set's own member. "Agent retrieval" is
    what `S3_AGENT` *is*, so declaring it there declared the surface you were
    already standing on — the `"operator opened the record"` mistake, admitted
    by the one name nobody re-read. `ANSWERING` names the act instead.

    **The rename was an honesty fix and not a remedy, and establishing that is
    what closed the column.** Nothing here ranks members, so every member lifted
    S3 exactly as far; renaming one changed a ledger line and moved no answer.
    A rename that cannot move an answer cannot be the fix for an answer that was
    wrong — so what the old name was a symptom of got closed on its own terms
    the same day. S3's ceiling is now `(L2, L2)`.
    See docs/DECISION-agent-retrieval.md.

    A `str` enum for the same reason `Rung` and `Surface` are (I-14): the value
    that ends up in a ledger line, a manifest or an error message should read as
    itself. That is *all* it is for. `Purpose.DRAFTING == "drafting"` is `True`,
    and the gate refuses the bare string anyway — being readable in a log is not
    a licence to be accepted in a permission call. `Surface` had exactly this
    bug at Phase 2 and the corpus found it.

    **Two glosses are narrower than they were, and one gap is left open on
    purpose** (2026-08-05; docs/DECISION-redisclosure.md,
    docs/DECISION-compelled-disclosure.md).

    `REDISCLOSURE` read *"42 CFR Part 2-style permitted re-disclosure"*, and that
    was taken for the member's **scope** when it was meant as an exemplar. It is
    not scoped to Part 2: the corpus already declares it over a relocated home
    address. Part 2 is the clearest instance of the act, not the boundary of it.
    (The objection that raised this — a Part 2 record is `L5`, `L5` has no
    override, so the member is dead — does not hold. The member is live at `L3`
    and `L4` on S4; four of the six have a canonical `L5` datum they cannot
    reach, which is I-13 working rather than a defect in a member.)

    `FILING` read *"submitting it to a court or agency"*, which is true of a
    voluntary filing **and of a compelled production**, and named only the
    destination. A subpoena response and a mandated report are inside those words
    as written. The gloss now says *voluntarily* — but **the set still has no
    member for a compelled disclosure**, so a production under process is
    declared as `FILING` today and a ledger cannot tell the two apart afterwards.
    That is a known, open gap and not an oversight; whether to close it is a
    product question about whether these households field discovery. Note that
    the set already individuates by posture elsewhere — `SUBJECT_ACCESS` is an
    `EXPORT` with a statute behind it, and gets its own member for that alone.
    """

    DRAFTING = "drafting"                # preparing a document the operator will file
    FILING = "filing"                    # submitting it, voluntarily, to a court or agency
    COMPELLED_DISCLOSURE = "compelled_disclosure"   # producing it because process required it
    EXPORT = "export"                    # the operator taking their own record out
    SUBJECT_ACCESS = "subject_access"    # a statutory subject-access request
    REDISCLOSURE = "redisclosure"        # passing on a record received under a permission
    ANSWERING = "answering"              # an agent answering a question the operator asked


def _check_the_str_enums_cannot_be_confused() -> None:
    """`Rung`, `Surface` and `Purpose` are all `str` enums. Keep them disjoint.

    Every gate here is an `isinstance` against the right class, so a collision
    cannot *currently* change an answer. This runs anyway, at import, because
    the property those `isinstance` checks rely on is worth holding structurally
    rather than by the good luck of nobody yet having named a purpose `"L3"`.

    The concrete hazard it forecloses: `_read_rung` reaches `Rung(value)` for
    any `str`, and a `Purpose` **is** a `str`. Today `Rung("drafting")` raises
    and the purpose reads as unclassified, which denies. A purpose whose value
    collided with a rung's would be silently *read as that rung* — a call-site
    argument becoming a data classification, which is I-14's catastrophe with
    the scales swapped.
    """
    values: dict[str, str] = {}
    for enum in (Rung, Surface, Purpose):
        for member in enum:
            owner = f"{enum.__name__}.{member.name}"
            clash = values.get(member.value)
            if clash is not None:
                raise RuntimeError(
                    f"{owner} and {clash} share the value {member.value!r}. "
                    "Rung, Surface and Purpose are all str enums and all three "
                    "are read out of the same kind of argument slot; a shared "
                    "value means one of them can be silently read as another."
                )
            values[member.value] = owner


_check_the_str_enums_cannot_be_confused()


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

    `.reason` names *which* failure this is, so the three can be told apart
    without matching on the message text (decision 4, ratified 2026-08-05):

    * `"no_fields"` — the schema has no fields at all. Almost always a loader
      that returned nothing, or a definition that picked nothing up.
    * `"none_classified"` — it has fields and **not one** of them declared a
      rung it could read. Almost always the declaration *format* is wrong: the
      wrong key, the wrong wrapper, integers throughout.
    * `"some_unclassified"` — most fields classified, some did not. Almost
      always a field added to a schema and not classified with it.

    Those are three different bugs with three different fixes and they used to
    read alike. It is an attribute rather than a subclass so that every
    `except UnclassifiedField` already written keeps working unchanged.
    """

    def __init__(self, *args: Any, reason: str = "") -> None:
        super().__init__(*args)
        self.reason = reason


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


class UndeclaredPurpose(TypeError):
    """A purpose that is not a `Purpose` member.

    `None` is not one of these: **no purpose declared is not an error**, it is
    the ordinary case and the one the plain ceiling exists for. What raises is a
    purpose slot holding something that is neither `None` nor a member.

    **Loud on type, closed on data** — ratified 2026-08-05, the same day as the
    enum, and this class is that rule applied. A purpose is a *call-site*
    property, exactly like a surface: the code that declares it is the code that
    knows why it is asking, and a purpose can never arrive out of a record. So
    an unreadable one is a programmer error and says so.

    **Keep the contrast.** An unreadable *rung* still denies quietly, because a
    rung **is** data — it comes out of a record, a schema declares it as the
    string `"L3"` (I-14), and it can legitimately be missing, so absence there
    reads `L5` and is not served (I-11). A list pane drawing fifty rows should
    not die on the one unclassified row; a call site that invented its own
    purpose should.

    A bare string raises **even when it spells a member**. `Purpose` is a `str`
    enum, so `Purpose.DRAFTING == "drafting"` is `True`, and a check that let
    that equality answer for it would accept the enum's own spellings while
    refusing every other string — which is precisely the bug the corpus found in
    `Surface` at Phase 2, and the most substantive thing it found.
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
    """Whether a purpose was declared — and the only place a purpose is checked.

    Three outcomes and no fourth:

    * `None` → `False`. **No purpose declared, and that is not an error.** It is
      the ordinary call and the plain ceiling is what it gets.
    * a `Purpose` member → `True`.
    * anything else → `UndeclaredPurpose`. Loud on type.

    `""`, `"   "`, `"medical"`, `1`, `True`, a `Rung`, and `"drafting"` are all
    the same case now: not a member, therefore not a purpose. The blank string
    used to be the interesting one — the absence of a purpose arriving in the
    shape of one — and it is no longer a special case, because the closed set
    makes every non-member the same error.

    **`isinstance` against the enum, never a value comparison.** `Purpose` is a
    `str` enum, so `Purpose.DRAFTING == "drafting"` is `True` and a membership
    test written as `purpose in {p.value for p in Purpose}` — or as
    `Purpose(purpose)`, which coerces — would accept the bare spellings of the
    six members while refusing every other string. That is not a smaller hole
    than free text, it is a *stranger* one: six magic strings instead of none.
    `Surface` had exactly this shape at Phase 2.

    Nothing here reads *which* member it is, and nothing downstream does either.
    The decision turns on whether a purpose was declared; the ceiling table has
    two columns, not seven. No member is more of a declaration than another —
    validating the set is not the same as ranking it, and ranking is what a
    trust tier and a ledger are for, neither of which this module has.
    """
    if purpose is None:
        return False
    if isinstance(purpose, Purpose):
        return True
    raise UndeclaredPurpose(
        f"{purpose!r} is not a Purpose. Declare one of "
        f"{[p.value for p in Purpose]} — as the member, not its spelling — or "
        "declare none at all by passing None, which is not an error and is what "
        "the plain ceiling is for. A purpose is a call-site property like a "
        "surface: it cannot arrive from a record, so an unreadable one is a "
        "programmer error and is loud. (A rung is data, and an unreadable one "
        "still denies quietly — I-11.) A bare string is refused even when it "
        "spells a member: Purpose is a str enum so that its value reads as "
        "itself in a ledger line, not so a permission check will accept the "
        "spelling in the argument that lifts a ceiling."
    )


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
#:   S3 agent   — L3 derived, L4 derived, **and a purpose lifts neither**.
#:                Closed 2026-08-05; it was `(L2, L4)` from Phase 2 until then.
#:                The column bought two rungs on the one surface with no human
#:                in the loop, in exchange for a boolean that any of six
#:                constants sets — and the thing that was meant to make that
#:                boolean mean something, the ledger entry, is Phase 3+ and does
#:                not exist. An unlock is not deferred by naming its key well;
#:                `AGENT_RETRIEVAL` was renamed to `ANSWERING` earlier the same
#:                day and moved no answer, which is what established that the
#:                name was never the load-bearing part. S3 keeps `L1` and `L2`
#:                payloads and is handed the derived form for `L3` and `L4` —
#:                `decide()` returns DERIVE, not DENY, so nothing here blinds an
#:                agent. Reopening it is this one cell, once S3 carries a trust
#:                tier (P-1) and S4's ledger exists to copy.
#:   S4 egress  — L3 derived, L4 derived unless a purpose is declared. **No
#:                longer the same ceilings as S3**, and the difference is now
#:                stated rather than transcribed: S4's caller is an operator
#:                performing an explicit act on their own record, which is what
#:                the spec row means by "explicit act + purpose + ledgered". S3's
#:                caller is a tool invocation. This module still enforces neither
#:                the tier nor the ledger, so this asymmetry is the spec's, not
#:                an authority claimed here.
_CEILING: dict[Surface, tuple[Rung, Rung]] = {
    Surface.S1_LIST:   (Rung.L3, Rung.L3),
    Surface.S1_DETAIL: (Rung.L4, Rung.L4),
    Surface.S2_PROMPT: (Rung.L2, Rung.L2),
    Surface.S3_AGENT:  (Rung.L2, Rung.L2),
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

    `purpose` is a declared reason from the closed set `Purpose`, and it can
    only ever *lift* a ceiling. `None` is no purpose declared and is not an
    error; anything that is not a member raises `UndeclaredPurpose`. On S1's
    detail pane a purpose is inert — the act of opening the pane is the
    declaration — but it is still *checked*: the type check is unconditional,
    because a check that only ran where the argument mattered would let a
    call site build the habit of passing rubbish on three surfaces and then
    carry it to the two where it lifts.

    **Per-call, never per-session.** This function holds nothing between calls.
    A purpose declared here is spent here; the next call starts undeclared.

    An unreadable rung — `None`, `"unknown"`, `3` — reads `L5` and returns
    `False`. An unreadable surface or purpose raises; see `UnknownSurface` and
    `UndeclaredPurpose`. The two call-site arguments are checked **before** the
    rung is read, so a programmer error is reported even when the data would
    have been refused anyway — a `False` that happens to be right is not the
    same answer as a `False` that is right for the reason given.
    """
    target = _read_surface(surface)
    declared = _declared(purpose)
    read = _read_rung(rung)
    if read is None:
        return False
    plain, with_purpose = _CEILING[target]
    ceiling = with_purpose if declared else plain
    return _ORDER[read] <= _ORDER[ceiling]


def decide(rung: Any, surface: Any, *, purpose: Any = None) -> Disposition:
    """`(rung, surface, purpose) → render | derive | deny`.

    The whole of what `workflow._fact_blocked` should have been. `DENY` is
    reached by `L5` and by an unreadable rung, and by nothing else — every
    other refusal is a `DERIVE`, because a household that cannot see the
    instruction cannot act on the deadline.

    The purpose is checked here as well as in `may_render`, and it has to be:
    an `L5` or an unreadable rung returns `DENY` without ever reaching
    `may_render`, so a check that lived only there would let a malformed
    purpose through on exactly the rungs that matter most.
    """
    target = _read_surface(surface)
    _declared(purpose)
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

    The purpose is checked before the item is, so a malformed purpose is
    reported even when the item would have been refused for its own reasons.
    """
    _declared(purpose)
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

    The surface and the purpose are checked once, up front, rather than once
    per item — so an empty iterable still refuses a malformed purpose. A gate
    that validates only when it has something to validate against is a gate
    that goes quiet on the empty case, and the empty case is the one nobody
    tests.
    """
    target = _read_surface(surface)
    _declared(purpose)
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

    **The refusal says which of three failures it is** — decision 4, ratified
    2026-08-05 — both in the first clause of the message and on the exception's
    `.reason`: `"no_fields"`, `"none_classified"`, `"some_unclassified"`. An
    empty schema is a loader that returned nothing; a schema where *nothing*
    classified is a declaration format this function cannot read, which is one
    fault wearing N field names; a schema where most classified and some did
    not is a field that was added and not classified with it. Three different
    bugs, three different places to look, and they used to read identically.
    The empty-schema case in particular used to be indistinguishable from a
    format failure at exactly the moment the difference matters — one is
    upstream of this call and one is in the declarations in front of you.

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
            "no fields at all: this schema is empty. An empty schema classifies "
            "nothing, and classifying nothing is not the same as having nothing "
            "to classify. Absence fails closed (I-11): a definition that picked "
            "up no fields must stop the build, not return an empty answer that "
            "composes to L5 somewhere later. Look upstream of this call — at "
            "whatever was supposed to produce the fields — rather than at the "
            "declarations, because there are none to be wrong.",
            reason="no_fields",
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
        # Decision 4, ratified 2026-08-05. "No fields at all" and "fields, none
        # classified" are different bugs — an empty loader versus a declaration
        # format nothing here can read — and they used to read identically. The
        # third case, most of them classified and some not, is a third bug
        # again: a field added to a schema and not classified with it.
        if not classified:
            head = (
                f"fields, none classified: all {len(problems)} of them failed. "
                "Not one declaration in this schema was readable, which points "
                "at the declaration *format* rather than at any one field — the "
                "wrong key, the wrong wrapper, or integers throughout — so read "
                "the reasons below as one fault and not as a list. "
            )
            reason = "none_classified"
        else:
            head = (
                f"{len(problems)} of {len(problems) + len(classified)} fields "
                f"are unclassified; {len(classified)} classified cleanly, so "
                "the declaration format is fine and these fields are the "
                "fault. "
            )
            reason = "some_unclassified"
        raise UnclassifiedField(
            head
            + "Every field carries a rung, set at schema-definition time — an "
            "unclassified field is a build failure (I-11), not a default. "
            + "; ".join(problems)
            + ". Classify with docs/homestead-rungs.md 'Classifying a new "
            "field': public in this matter's forum → L1; names or resolves to "
            "a person → L3; and a category the law follows → L4; would "
            "rendering reveal a refusal, expose privileged strategy, disclose "
            "key material or breach a sealing order → L5.",
            reason=reason,
        )
    return classified
