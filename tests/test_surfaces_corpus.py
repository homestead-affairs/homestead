"""I-11 … I-15 — the surface corpus. Written by a hand that has not seen the code.

Phase 0 was audited twice and failed its exit criteria both times: every claimed
guarantee was weaker than its documentation, and one path scan missed the exact
leak it was written to prevent. The cause was structural — the same hand wrote
the code and the test, so the test learned the code's shape. Phase 1 split the
hands, the corpus landed red against a module that did not exist, and the
implementation had to meet it rather than describe itself. This file is the
blind half of Phase 2.

It starts red. `homestead.keep.surfaces` does not exist when this file lands, so
collection fails loudly rather than skipping quietly. There is no
`importorskip` and no `try/except ImportError` anywhere below — a skipped
corpus is a corpus that cannot fail, and that is the failure mode this method
exists to eliminate.

**Phase 2 is not the UI.** The windows are Phase 4. This is the decision
function every later render must route through: `(rung, surface, purpose) →
may this payload be rendered`. It is `workflow._fact_blocked`'s successor.

---

**The defect this corpus exists to prevent is BUG-5**, from
`apps/law-gazelle/docs/bug_list.md`:

> `_fact_blocked()` is `return status == "needs_source"`. An atom the operator
> explicitly marked `do_not_use` — the **stronger** rejection — got
> `infer_card_status → ready_to_draft`, flowed into `draft_context()`, into
> `schedule_response_packet()`, into `format_draft_context_markdown`, and from
> there into the `gazelle_ai_draft` prompt, unmarked. The Review Facts screen
> said "Excluded from drafting". It was excluded from nothing.

A guard checked a weaker condition and the stronger case walked straight past
it, while the screen claimed otherwise. **The general form of that shape is a
monotonicity violation**: if a rung is refused on a surface, every higher rung
must also be refused on that surface. A table written by hand is exactly where
one hides — one cell, one row, one surface that got a `True` it should not
have — so §4 sweeps every `(rung × surface × purpose)` cell rather than
sampling the table's diagonal.

**The rest of what is asserted here, and where it comes from**
(`docs/homestead-rungs.md`, and the invariant rows in
`docs/homestead-law-build-plan.md`):

* **I-11 — absence fails closed, twice over.** An unclassified field is a
  *build failure*, not a default. If one reaches runtime anyway it reads `L5`.
  A classifier that **errors denies** — it never returns `L1`. So §8 tests the
  erroring classifier and the unenumerable schema, not only the missing key.
* **I-12 — composition is `max`, everywhere.** Records, joins, chronologies,
  drafts — and **a prompt is the `max` of its whole context window, including
  the retrieved neighbours a semantic search pulled in**. A projection never
  lowers a rung.
* **I-13 — `L4` reaches no surface as a payload without a declared purpose, and
  reaches a model prompt never. `L5` has no override anywhere.**
* **I-14 — rungs are strings.** `L3`, never `3`. Trust in the sibling system
  runs the *other* direction (`Rookie → Steady → Veteran`, ascending
  privilege), so `if level >= 3` is correct against one scale and catastrophic
  against the other, and it reads perfectly in review either way.
* **I-35 — the list pane cannot render an `L4` payload.** Not a policy; the
  ambient render path does not accept one. Payloads exist only in a detail pane
  the operator opened, and the **deliberate act of opening *is* the purpose
  declaration** — "by widget, not by dialog", decided 2026-08-04, so there is
  no ceremony tax on a person in crisis.
* **F-5** is why any of this is load-bearing: the application this one replaces
  builds a structured dossier on a non-consenting third party and a minor, with
  no rung enforcement on any of the four surfaces, and a manifest declaring
  sidecar retention "permanent local".

**S2 is a rendering.** It is the point most easily missed and the one with the
most consequence, so it has its own section (§6). A model prompt is not
"internal processing"; it is a surface with a reader that summarizes, retains
in a cache, and produces text a human acts on.

**On surface member names.** `S1_LIST`, `S1_DETAIL` and `S2_PROMPT` are fixed
by the published contract in `tests/test_invariants_pending.py`. The names of
the S3 (agent/MCP over stdio) and S4 (egress) members are the implementation's
call, and this file has not seen them — so every sweep iterates `Surface` and
every claim about S3/S4 is made by prefix, never by a guessed name.

**Where this file is deliberately permissive**, and why, so nothing here reads
as stronger than it is: the exact shape of a `classify_schema` field spec is
not pinned by the contract, so §8 probes a set of plausible spellings and
reports which were accepted rather than asserting one. A failure there is an
**API disagreement**, cheaper to have now than at the first schema. Everything
in §§1-7 and §9-11 is a safety claim and none of it is shape-tolerant.

---

## The 2026-08-05 conversion — a purpose is a closed enum

This file shipped parameterised on **free-text purposes** throughout, because
that is what `purpose` was: any non-blank string. The operator ratified the fix
on 2026-08-05 — *a purpose is a closed enum* — and this is the faithful
translation of the corpus onto it, performed by the blind hand rather than the
implementing one, because the translation is what decides what the tests prove.

Three rules governed every edit below, and any departure from them is written
down in the report rather than made quietly:

1. **Nothing adversarial was deleted.** `"medical\\x00override"`, `"M" * 4096`,
   `"медицинский"`, `"🔓"`, the blanks, the SQL and path-traversal shapes are all
   still here, in `ADVERSARIAL_PURPOSES`, still swept. What changed is the claim
   made about them: they move from *"must not unlock anything"* to **"must not
   be accepted as a purpose at all"**, which is strictly stronger — a string
   that cannot enter cannot unlock. §5 is where that is asserted, exhaustively,
   against every rung and every surface.
2. **The cell sweeps run on the valid set** — the six `Purpose` members plus
   `None` — because a sweep whose every cell raises has stopped sweeping the
   table. `SWEEP_PURPOSES` is now `VALID_PURPOSES` and the ceiling claims are
   unchanged in meaning: no rung/surface answer moves for a validly declared
   purpose.
3. **A valid purpose is used wherever a purpose was standing in for "declared"
   while some *other* argument was the thing under test.** `verdict(bad_rung,
   surface, "medical")` would now raise on the purpose and never reach the rung,
   so every such probe passes vacuously. That substitution is the single largest
   class of edit in this file and the one most able to hollow it out silently.

**The new guarantees the enum is supposed to buy live in
`tests/test_purpose_corpus.py`** — that no string is a purpose including the
member *values*, that no member unlocks `L5` anywhere, that a member is inert on
the three surfaces whose ceilings are equal, that the decision is stateless, and
what happens when a `Purpose` and a `Rung` are transposed.
"""
from __future__ import annotations

import ast
import inspect
import itertools
import re
from pathlib import Path

import pytest

from homestead.keep.rungs import (Classified, Purpose, Rung, UnclassifiedField,
                                  UndeclaredPurpose, classify_schema, compose,
                                  may_render)
from homestead.keep.surfaces import Surface

ROOT = Path(__file__).resolve().parent.parent
KEEP = ROOT / "homestead" / "keep"

# The ladder, low to high. Higher is MORE restricted — the opposite of
# WillowGate trust, and that opposition is deliberate and is not reconciled.
LADDER = (Rung.L1, Rung.L2, Rung.L3, Rung.L4, Rung.L5)

# The three members the published contract names. Everything else is found by
# prefix, because this file has not seen the implementation.
S1_LIST = Surface.S1_LIST
S1_DETAIL = Surface.S1_DETAIL
S2_PROMPT = Surface.S2_PROMPT


def _by_prefix(prefix: str) -> frozenset:
    return frozenset(s for s in Surface if s.name.startswith(prefix))


S1 = _by_prefix("S1_")          # the operator's own screen, two panes
S2 = _by_prefix("S2_")          # a model prompt
S3 = _by_prefix("S3_")          # agent retrieval, MCP over stdio
S4 = _by_prefix("S4_")          # egress — drafts, exports, filings, manifests
OFF_SCREEN = frozenset(Surface) - S1        # every surface that is not S1

# ── purposes ─────────────────────────────────────────────────────────────────
# Until 2026-08-05 a purpose was a free string, and therefore the only argument
# a caller controlled — the attack surface. It is now a closed enum, so the
# families below split in two: the ones `may_render` **accepts**, and the ones it
# must **refuse to accept at all**. Every string that was here before is still
# here; the claim made about it got stronger.

#: The six, and the fact that there are six. Membership is the product decision
#: — see the report — but *that the set is closed* is what is under test.
MEMBERS = tuple(Purpose)

#: Everything `may_render` accepts in the purpose slot, and the whole of it.
#: `None` is not an error: it means no purpose was declared.
VALID_PURPOSES = (None,) + MEMBERS

#: Not a declaration, and now not even a well-typed one. A caller that passes
#: one of these declared nothing; blank must never unlock what `None` does not,
#: and under the enum it does not get as far as being asked.
BLANK_PURPOSES = ("", " ", "   ", "\t", "\n", "\t \n ")

#: What a real caller would say — in the free-text world. Two of these are
#: deliberately *not* members and the reason is the argument for closing the
#: set: `"medical"` is a data **category** and `"operator opened the record"` is
#: a **surface act**. Free text invited all three kinds of thing into one slot.
PLAUSIBLE_PURPOSES = (
    "medical",
    "drafting",
    "export",
    "filing",
    "briefing",
    "subject access request",
    "42 CFR Part 2 re-disclosure",
    "operator opened the record",
)

#: What someone reaching for an escape hatch would say — including the words
#: this very model uses about itself. Before the enum these had to not *serve*
#: `L5`; now they have to not be *accepted*, which is the stronger claim and the
#: reason none of them was deleted in the conversion.
ADVERSARIAL_PURPOSES = (
    "override",
    "admin",
    "root",
    "sudo",
    "bypass",
    "force",
    "all",
    "any",
    "*",
    "true",
    "yes",
    "1",
    "-1",
    "0",
    "none",
    "None",
    "null",
    "L1",
    "L5",
    "sealed",
    "do_not_use",
    "needs_source",
    "purpose",
    "internal processing",
    "not a rendering",
    "medical\noverride=true",
    "medical\x00override",
    "../medical",
    "medical'; --",
    "M" * 4096,
    "медицинский",
    "🔓",
)

PURPOSE_STRINGS = BLANK_PURPOSES + PLAUSIBLE_PURPOSES + ADVERSARIAL_PURPOSES

#: **The likely hole, and it is new with the enum.** `Purpose` is a `str`
#: subclass, so `Purpose.DRAFTING == "drafting"` is `True`, and — checked, not
#: assumed — `hash(Purpose.DRAFTING) == hash("drafting")`, so a `dict` or a
#: `set` keyed on members finds the bare string. Any membership test written as
#: `purpose in _VALID` accepts `"drafting"` from a caller who never imported the
#: enum. `Surface` had exactly this bug in Phase 2. The spellings are both the
#: value and the member name, because `Purpose["DRAFTING"]` is the other way in.
MEMBER_VALUE_STRINGS = tuple(p.value for p in Purpose)
MEMBER_NAME_STRINGS = tuple(p.name for p in Purpose)

#: Everything that must be refused outright. The old free-text corpus in full,
#: plus the member spellings. Nothing was dropped to build this.
REJECTED_PURPOSES = PURPOSE_STRINGS + MEMBER_VALUE_STRINGS + MEMBER_NAME_STRINGS

#: The set the exhaustive cell sweep runs over. Before the enum this was a
#: trimmed selection of free text; it is now the whole accepted set, which is
#: both smaller and complete — every purpose an implementation may be handed is
#: swept against every rung on every surface, with none left over.
SWEEP_PURPOSES = VALID_PURPOSES


def _pid(value) -> str:
    """A readable parametrize id for a purpose that may be 4 KiB of `M`."""
    if isinstance(value, Purpose):
        return value.name
    text = repr(value)
    return text if len(text) <= 28 else text[:25] + "…"


def verdict(rung, surface, purpose):
    """The answer, or the exception — never a crash a test swallows into a pass.

    Used only where the *type* of an argument is in question. Returning the
    exception object rather than re-raising lets a single assertion cover both
    acceptable answers (refuse loudly / deny quietly) while still failing on
    the one unacceptable answer, which is `True`.

    **Re-checked at the 2026-08-05 conversion**, because the whole type
    discipline section rests on it: `except Exception` catches
    `UndeclaredPurpose` (a `TypeError`) exactly as it caught everything before,
    so every `verdict(...) is not True` assertion survives the change with its
    meaning intact. What does *not* survive is comparing two `verdict` results
    with `is` — two raised exceptions are two distinct objects — and the one
    test that did that is converted explicitly rather than left to rot.
    """
    try:
        return may_render(rung, surface, purpose=purpose)
    except Exception as exc:                    # noqa: BLE001 — that is the point
        return exc


def rendered_on(rung, purpose) -> frozenset:
    """The set of surfaces on which this rung may be rendered as a payload.

    Takes an **accepted** purpose — `None` or a `Purpose`. A rejected one raises
    out of here, which is deliberate: a helper that swallowed it would turn
    "refused to accept" into "rendered nowhere", and those are different
    findings.
    """
    return frozenset(
        s for s in Surface if may_render(rung, s, purpose=purpose) is True
    )


def surfaces_refusing_to_accept(purpose) -> frozenset:
    """Every surface on which this purpose is refused **as a purpose**, at every
    rung. The counterpart to `rendered_on` for the rejected family."""
    return frozenset(
        s for s in Surface
        if all(isinstance(verdict(r, s, purpose), UndeclaredPurpose) for r in LADDER)
    )


def _keep_modules() -> list[Path]:
    """The two modules Phase 2 owns. Scanned, not imported, for source claims."""
    return [KEEP / "rungs.py", KEEP / "surfaces.py"]


# ═════════════════════════════════════════════════════════════════════════════
# 1 · The ladder — I-14, rungs are strings
# ═════════════════════════════════════════════════════════════════════════════

def test_i14_the_ladder_has_exactly_five_rungs_named_l1_to_l5():
    """A sixth rung is a row that falls outside every crossing table written
    against five. The table is exhaustive by construction or it is not
    exhaustive at all."""
    assert [r.name for r in Rung] == ["L1", "L2", "L3", "L4", "L5"]
    assert [r.value for r in Rung] == ["L1", "L2", "L3", "L4", "L5"]


@pytest.mark.parametrize("rung", LADDER, ids=[r.name for r in LADDER])
def test_i14_a_rung_is_a_string_and_is_not_an_integer(rung):
    """I-14. `L3`, never `3`. WillowGate trust runs the other direction —
    `Rookie → Steady → Veteran`, ascending *privilege* — so `if level >= 3` is
    correct against one scale and catastrophic against the other, and it reads
    perfectly in review either way. The only defence is that a rung is never a
    number in the first place."""
    assert isinstance(rung, str)
    assert not isinstance(rung, int), "an int rung is comparable to a trust tier"
    assert rung.value == rung.name
    with pytest.raises((ValueError, TypeError)):
        int(rung)


@pytest.mark.parametrize("bad", [1, 2, 3, 4, 5, 0, -1, "3", "l3", "L6", "L0",
                                "", None, True, 3.0])
def test_i14_the_rung_enum_refuses_every_non_rung_spelling(bad):
    """`Rung(3)` returning `Rung.L3` would be the whole defect in one call: a
    trust tier of 3 (Veteran, the *most* privileged) silently reading as `L3`
    (attributed). Lowercase and off-by-one spellings are refused for the same
    reason — a rung that can be spelled two ways has two tables."""
    with pytest.raises((ValueError, KeyError, TypeError)):
        Rung(bad)


def test_i14_no_integer_comparison_against_a_rung_in_the_phase_2_source():
    """I-14's literal signature, scanned the way the store scans for raw SOIL
    reads and the way `test_dates_corpus` scans for `[:10]`.

    `if rung >= 3` is the sentence this invariant exists to make unwritable. It
    cannot be caught behaviourally once written — it *works*, against the wrong
    scale — so it is caught in the source. A belt to the behavioural braces in
    §9, not a substitute for them.
    """
    suspicious = re.compile(r"rung|level|sensitivity|tier|grade", re.IGNORECASE)
    offenders = []
    for mod in _keep_modules():
        tree = ast.parse(mod.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            operands = [node.left, *node.comparators]
            named = any(
                suspicious.search(ast.unparse(o))
                for o in operands
                if isinstance(o, (ast.Name, ast.Attribute, ast.Subscript, ast.Call))
            )
            inty = any(
                isinstance(o, ast.Constant)
                and isinstance(o.value, int)
                and not isinstance(o.value, bool)
                for o in operands
            )
            if named and inty:
                offenders.append(f"{mod.relative_to(ROOT)}:{node.lineno}: "
                                 f"{ast.unparse(node)}")
    assert not offenders, (
        "a rung compared against a bare integer is I-14 verbatim — the same "
        f"expression is correct against this ladder and inverted against "
        f"WillowGate trust. Found: {offenders}"
    )


def test_i14_neither_phase_2_enum_is_an_int_enum():
    """An `IntEnum` restores every integer comparison the invariant forbids,
    and does it invisibly: `Rung.L3 >= 3` would be `True` with nothing in the
    source to scan for."""
    for member in list(Rung) + list(Surface):
        assert not isinstance(member, int), f"{member!r} is comparable to an int"


# ═════════════════════════════════════════════════════════════════════════════
# 2 · The four surfaces — the closed set
# ═════════════════════════════════════════════════════════════════════════════

def test_the_surface_set_is_the_four_from_the_model():
    """"Every render happens on exactly one of these." Four surfaces, and S1
    carries two panes with different powers: the **list** (ambient, cannot
    render an `L4` payload — I-35) and the **detail** (opened deliberately,
    expires back to derived — I-32)."""
    assert len(S1) == 2, f"S1 is two panes with different powers, found {sorted(S1)}"
    assert S1 == {S1_LIST, S1_DETAIL}
    assert S2_PROMPT in S2
    assert S3, "no S3 member — agent retrieval over MCP stdio is a surface"
    assert S4, "no S4 member — egress is a surface"
    assert len(Surface) >= 5


def test_every_surface_belongs_to_one_of_the_four():
    """A member outside `S1`-`S4` is a render path the crossing table never
    scored. The naming carries the number so that cannot happen silently."""
    pattern = re.compile(r"\AS[1-4]_[A-Z0-9_]+\Z")
    strays = [s.name for s in Surface if not pattern.match(s.name)]
    assert not strays, (
        f"{strays} are not on one of the four surfaces. A fifth surface is not "
        "a naming question — it is a render path with no row in the table."
    )
    assert S1 | S2 | S3 | S4 == frozenset(Surface)


def test_there_is_no_catch_all_surface():
    """`INTERNAL`, `ANY`, `NONE` or `OTHER` is the escape hatch by another name
    — and "internal processing" is precisely the phrase the model rejects for
    `S2`. A datum rendered on a surface with no row in the table is a datum
    rendered with no decision made about it."""
    banned = re.compile(r"INTERNAL|ANY|ALL|NONE|OTHER|MISC|DEFAULT|UNKNOWN|TEST",
                        re.IGNORECASE)
    strays = [s.name for s in Surface if banned.search(s.name)]
    assert not strays, f"catch-all surfaces: {strays}"


def test_surface_members_are_distinct_and_the_enum_is_closed():
    """Two members sharing a value are one member with two names, and a table
    keyed on it silently loses a row."""
    assert len({s.value for s in Surface}) == len(list(Surface))
    for bogus in ("S5", "s5", "internal", "", None, 5, "S1"):
        with pytest.raises((ValueError, KeyError, TypeError)):
            Surface(bogus)


# ═════════════════════════════════════════════════════════════════════════════
# 3 · The published contract, re-asserted
# ═════════════════════════════════════════════════════════════════════════════
# These four groups are the agreed API in `tests/test_invariants_pending.py`.
# They are restated here because a corpus that assumes the contract holds is a
# corpus that cannot tell you which half broke.

def test_contract_an_undeclared_rung_is_a_build_failure():
    """I-11. `{"body": None}` is a field with no rung declared. Unclassified is
    a build failure, not a default — because the alternative is a field that
    reaches runtime with nobody having decided what it is."""
    with pytest.raises(Exception):
        classify_schema({"body": None})


@pytest.mark.parametrize("surface", list(Surface), ids=[s.name for s in Surface])
def test_contract_l5_is_never_served_on_any_surface(surface):
    """`L5` — sealed. Never served on any surface, **including to the
    operator's own agents**. A fact marked `do_not_use` is `L5`, and this is
    the line BUG-5 walked past.

    Was `purpose="anything"`, one string. Under the enum `"anything"` is not a
    purpose and never reaches the rung, so the claim is made twice instead: once
    over every purpose that *is* accepted, and once over the string, which must
    be refused. Losing the second half would be losing the test.
    """
    for purpose in VALID_PURPOSES:
        assert may_render(Rung.L5, surface, purpose=purpose) is False
    with pytest.raises(UndeclaredPurpose):
        may_render(Rung.L5, surface, purpose="anything")


def test_contract_the_list_pane_never_renders_l4_and_the_detail_pane_does():
    """I-35, and the resolved open question. The list pane cannot render an
    `L4` payload **with or without a purpose** — its render path does not
    accept one, so nothing sensitive can be ambient even by mistake. The detail
    pane serves it with **no purpose string at all**, because the deliberate
    act of opening it *is* the declaration: by widget, not by dialog, so there
    is no ceremony tax on a person in crisis.

    `"medical"` was the purpose here and it is deliberately **not** a member —
    it is a data category, not a purpose — so the with-a-purpose half runs over
    every member instead, which is more than it checked before.
    """
    assert may_render(Rung.L4, S1_LIST, purpose=None) is False
    for purpose in MEMBERS:
        assert may_render(Rung.L4, S1_LIST, purpose=purpose) is False
    assert may_render(Rung.L4, S1_DETAIL, purpose=None) is True


def test_contract_l4_never_reaches_a_model_prompt():
    """I-13's first hard stop. If a local model needs the diagnosis to do its
    job, that is a signal the job is wrong, not that the rung should bend."""
    for purpose in VALID_PURPOSES:
        assert may_render(Rung.L4, S2_PROMPT, purpose=purpose) is False


# ═════════════════════════════════════════════════════════════════════════════
# 4 · The crossing table — every cell, and the shape of BUG-5
# ═════════════════════════════════════════════════════════════════════════════
#
#   | Rung | S1 · screen        | S2 · prompt      | S3 · agent        | S4 · egress |
#   | L1   | render             | render           | render            | render      |
#   | L2   | render             | render           | render            | render      |
#   | L3   | render             | derived          | derived           | explicit act|
#   | L4   | derived unless … | derived, no exc. | derived, +purpose | +purpose    |
#   | L5   | never              | never            | never             | never       |
#
# "derived" means the payload does not appear; `may_render` is the payload
# question, so every "derived" cell is `False`.

@pytest.mark.parametrize("purpose", SWEEP_PURPOSES, ids=[_pid(p) for p in SWEEP_PURPOSES])
@pytest.mark.parametrize("surface", list(Surface), ids=[s.name for s in Surface])
@pytest.mark.parametrize("rung", LADDER, ids=[r.name for r in LADDER])
def test_every_cell_answers_with_a_real_bool(rung, surface, purpose):
    """The whole table, cell by cell. Two things at once.

    First, the answer is `True` or `False` and nothing else. BUG-3's repair
    path never ran because a guard read `is None` and the broken value was
    `False`; a decision function that can return `None` to mean "derived" hands
    every caller the same trap, and `None` is falsy so the mistake is invisible
    until the one call site that checks `is False`.

    Second, the sweep exists so that no cell is unvisited. A table written by
    hand is where a single wrong cell hides, and the audit's finding was that
    sampling the diagonal proves nothing about the corners.
    """
    result = may_render(rung, surface, purpose=purpose)
    assert result is True or result is False, (
        f"may_render({rung.name}, {surface.name}, purpose={purpose!r}) returned "
        f"{result!r} ({type(result).__name__}) — not a bool"
    )


@pytest.mark.parametrize("purpose", SWEEP_PURPOSES, ids=[_pid(p) for p in SWEEP_PURPOSES])
@pytest.mark.parametrize("surface", list(Surface), ids=[s.name for s in Surface])
def test_bug5_a_refused_rung_refuses_every_rung_above_it(surface, purpose):
    """**BUG-5 in its general form, and the single most important test here.**

    `_fact_blocked` was `return status == "needs_source"`, so `do_not_use` —
    the *stronger* rejection — was not blocked at all, while the Review Facts
    screen said "Excluded from drafting". A guard checked a weaker condition
    and the stronger case walked past it.

    Stated as a property: refusal is monotone up the ladder. If a rung is
    refused on a surface, every higher rung is refused on that same surface
    with the same purpose. Any hand-written table has five chances per column
    to get this wrong, and a violation is BUG-5 wearing different clothes.
    """
    for low, high in itertools.combinations(LADDER, 2):
        if may_render(low, surface, purpose=purpose) is False:
            assert may_render(high, surface, purpose=purpose) is False, (
                f"{surface.name} refuses {low.name} but serves {high.name} "
                f"(purpose={purpose!r}). That is BUG-5: the weaker rejection "
                f"blocks and the stronger one does not."
            )


@pytest.mark.parametrize("purpose", SWEEP_PURPOSES, ids=[_pid(p) for p in SWEEP_PURPOSES])
def test_bug5_the_permitted_surfaces_only_shrink_as_the_rung_rises(purpose):
    """The same property read as set inclusion, which is how it should be read
    in review: `served(L5) ⊆ served(L4) ⊆ served(L3) ⊆ served(L2) ⊆ served(L1)`.
    A rung that is "more restricted" and reaches a surface its junior cannot is
    a contradiction in terms, and it is the exact contradiction the Review
    Facts screen was displaying."""
    sets = [rendered_on(r, purpose) for r in LADDER]
    for (low_r, low), (high_r, high) in zip(zip(LADDER, sets), zip(LADDER[1:], sets[1:])):
        assert high <= low, (
            f"{high_r.name} is served on {sorted(s.name for s in high - low)} "
            f"where {low_r.name} is not (purpose={purpose!r})"
        )


@pytest.mark.parametrize("purpose", VALID_PURPOSES, ids=[_pid(p) for p in VALID_PURPOSES])
def test_l1_is_rendered_on_every_surface(purpose):
    """`L1` — already public, or publishable, in this matter's own forum;
    survives being read aloud in a hallway. The crossing table says `render` in
    all four columns.

    This test is why the corpus cannot be passed by `return False`. A gate that
    denies everything is not a gate, it is an outage, and a person in crisis
    who cannot see their own hearing date has been failed by the tool.

    **And it is why the enum cannot be passed by refusing everything either.**
    A `_declared` that rejected every purpose, members included, would satisfy
    every rejection test in §5 and this one would still fail.
    """
    assert rendered_on(Rung.L1, purpose) == frozenset(Surface)


@pytest.mark.parametrize("purpose", VALID_PURPOSES, ids=[_pid(p) for p in VALID_PURPOSES])
def test_l2_is_rendered_on_every_surface_without_a_purpose(purpose):
    """`L2` — household. Counts, schedules, operational state; no person's
    identity and no protected category. "Renderable on any household surface
    without a purpose" is the definition of the rung.

    The re-identification check that decides whether an aggregate *is* `L2`
    happens before this call, not inside it — see §7, where an aggregate that
    has not passed it inherits the `max` of its inputs.
    """
    assert rendered_on(Rung.L2, purpose) == frozenset(Surface)


def test_l3_is_rendered_on_the_operators_screen_and_nowhere_else():
    """`L3` — attributed. Names or resolves to a person: the operator, a child,
    the other party, a creditor, an employer, a witness.

    "Rendered in full on **S1**. On **S2/S3/S4** it is `NULL` and a derived
    form is served in its place." The worked example is exact: the operator
    sees `Parenting time · Tue/Thu · minor child A.R.`; the model prompt gets
    *"a recurring parenting-time obligation on Tue/Thu."*
    """
    assert rendered_on(Rung.L3, None) == S1


def test_l4_is_rendered_only_in_the_detail_pane_without_a_purpose():
    """`L4` — protected: identifies a person **and** carries a category the law
    follows. "The derived instruction is the normal serving mode, and the
    payload is the exception."

    With no purpose declared, exactly one surface serves the payload — the
    detail pane, because opening it *is* the declaration. Not the list (I-35),
    not the prompt (I-13), not the agent, not egress.
    """
    assert rendered_on(Rung.L4, None) == frozenset({S1_DETAIL})


@pytest.mark.parametrize("purpose", MEMBERS, ids=[p.name for p in MEMBERS])
def test_l4_with_a_purpose_still_never_reaches_the_list_or_the_prompt(purpose):
    """The two cells a declared purpose does **not** open, whatever it says.

    The list pane is `never` because the threat is ambient exposure — someone
    walking past thirty seconds later (F-5) — and a purpose string does not
    change who is standing behind the operator. The prompt is `never` because
    of I-13's first hard stop.

    Everything else is left open here on purpose: whether a purpose alone
    suffices for S3 (which the table also gates on `≥ Veteran` trust) or S4
    (which the table also requires be ledgered) depends on parameters this
    signature does not carry, and this corpus will not invent an answer.
    """
    got = rendered_on(Rung.L4, purpose)
    assert S1_DETAIL in got, "the detail pane serves L4 with or without a purpose"
    assert S1_LIST not in got, "I-35: the list pane's render path does not accept an L4 payload"
    assert S2_PROMPT not in got, "I-13: L4 reaches a model prompt never"
    assert got <= frozenset({S1_DETAIL}) | S3 | S4


@pytest.mark.parametrize("purpose", MEMBERS, ids=[p.name for p in MEMBERS])
def test_l3_with_a_purpose_still_never_reaches_a_model_prompt(purpose):
    """The `L3 · S2` cell reads `derived`, flat, where `L3 · S4` reads
    `explicit act, ledgered` and `L4 · S1` reads `derived unless purpose`. The
    table spells out an unlock wherever there is one; this cell has none.

    **Flagged as a place the spec is not perfectly consistent**: the `L3`
    section's prose says *"unless an explicit act says otherwise"* about
    S2/S3/S4 collectively. The crossing table is the more specific statement
    and the table is what `may_render` implements, so the corpus takes the
    table's reading. If the implementation disagrees, this is the disagreement
    worth having now — see the report.
    """
    assert S2_PROMPT not in rendered_on(Rung.L3, purpose)


def test_nothing_off_the_operators_screen_serves_l3_without_an_explicit_act():
    """S2, S3 and S4 are the surfaces where a datum *leaves*, and the whole
    `L3` row off S1 is `derived` or `explicit act`. Asserted for every surface
    that is not S1, by prefix, because this file does not know what the S3 and
    S4 members are called.

    **Converted 2026-08-05.** This was parameterised over the sweep and guarded
    by `if purpose is None or not str(purpose).strip()`, so what it actually
    tested was the *undeclared* cases — `None` and the blanks. Under the enum
    `None` is the whole of "undeclared", because a blank is no longer a value
    the function will take. So the `None` half is asserted directly here and the
    blank half moves to the test below it, where it is asserted as a refusal —
    which is the stronger of the two readings and not a loss.
    """
    for surface in OFF_SCREEN:
        assert may_render(Rung.L3, surface, purpose=None) is False, (
            f"{surface.name} served an L3 payload with no purpose declared — "
            "the L3 row off S1 is derived or an explicit act"
        )


@pytest.mark.parametrize("purpose", BLANK_PURPOSES, ids=[_pid(p) for p in BLANK_PURPOSES])
def test_a_blank_purpose_unlocks_nothing_that_no_purpose_unlocks(purpose):
    """"Purpose declared" must mean a purpose was declared. If `""` opens a
    cell that `None` does not, then every call site that forgot to fill the
    field is authorized, and the declaration is a formality rather than a
    decision. This is the cheapest possible way for the whole `L4` regime to
    become decorative.

    **The enum closes this differently and more completely.** A blank is not
    weighed and found wanting; it is not a `Purpose`, so it is refused before
    anything is decided, on every rung and every surface. The old assertion
    (`rendered_on(rung, blank) <= rendered_on(rung, None)`) is kept underneath
    it in the only form that still means anything — the blank renders nothing
    anywhere, because it never gets an answer at all.
    """
    for rung in LADDER:
        for surface in Surface:
            with pytest.raises(UndeclaredPurpose):
                may_render(rung, surface, purpose=purpose)
    assert surfaces_refusing_to_accept(purpose) == frozenset(Surface)


@pytest.mark.parametrize("purpose", MEMBERS, ids=[p.name for p in MEMBERS])
def test_declaring_a_purpose_never_takes_a_permission_away(purpose):
    """The other direction: a purpose is a widening, not a filter. If the
    detail pane serves `L4` to a caller who said nothing, it must serve it to a
    caller who also said *why* — otherwise the safest call site is the one that
    declares least, and the incentive points the wrong way."""
    for rung in LADDER:
        assert rendered_on(rung, None) <= rendered_on(rung, purpose), (
            f"{rung.name} lost "
            f"{sorted(s.name for s in rendered_on(rung, None) - rendered_on(rung, purpose))} "
            f"when the caller declared purpose={purpose!r}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 5 · `L5` has no override anywhere — the hunt
# ═════════════════════════════════════════════════════════════════════════════
# "A rung with an escape hatch is a label, not a control." This section tries
# hard to find one.

@pytest.mark.parametrize("purpose", VALID_PURPOSES, ids=[_pid(p) for p in VALID_PURPOSES])
def test_l5_is_served_by_no_argument_on_no_surface(purpose):
    """Every purpose that can legally be declared, against every surface. `L5`
    includes any fact the operator marked **`do_not_use`** and why, the content
    of a sealed record, export-ledger key material, substance-use treatment
    records under 42 CFR Part 2, and anything under a protective order.

    `do_not_use` is BUG-5's own datum. There is no purpose a caller can declare
    that puts it back in the drafting packet — and now there is no string a
    caller can pass either, which is the test below.
    """
    assert rendered_on(Rung.L5, purpose) == frozenset(), (
        f"purpose={purpose!r} served L5 on "
        f"{sorted(s.name for s in rendered_on(Rung.L5, purpose))}"
    )


@pytest.mark.parametrize("purpose", REJECTED_PURPOSES,
                         ids=[_pid(p) for p in REJECTED_PURPOSES])
def test_no_string_is_a_purpose_and_none_of_them_gets_near_l5(purpose):
    """**The conversion of the old sweep, and the reason nothing was deleted.**

    Every adversarial string this corpus ever carried is still swept here —
    `"override"`, `"L5"`, `"do_not_use"`, `"medical\\x00override"`, 4 KiB of
    `M`, `"медицинский"`, `"🔓"`, the SQL and path-traversal shapes, the blanks
    — plus the six member *values* and the six member *names*, which are the new
    hole a `str` enum opens.

    Before 2026-08-05 the claim was *this string does not unlock `L5`*. It is
    now *this string is not a purpose*, which subsumes it: a value that cannot
    enter the argument cannot unlock anything at any rung, so this runs the
    whole ladder rather than just `L5`. Asserted as `UndeclaredPurpose`
    specifically, because the contract names it — "loud on type, closed on
    data" — and because a bare `TypeError` here could as easily be an arity
    error that means the call did not happen at all.
    """
    for surface in Surface:
        for rung in LADDER:
            with pytest.raises(UndeclaredPurpose):
                may_render(rung, surface, purpose=purpose)
    assert rendered_on(Rung.L1, None) == frozenset(Surface), (
        "sanity: the same call with a declared-nothing purpose still answers, "
        "so the refusal above is about the purpose and not about the module"
    )


class _AlwaysEqual:
    """An object that claims to be whatever it is compared against.

    A guard written as `if purpose == "medical"` — or as `if rung ==
    Rung.L1` — is passed by this. It is not a hypothetical shape: BUG-5 *was*
    a single `==` against one value, and `_related_intersections()` in the same
    codebase decides relatedness by substring match over free text.
    """

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __hash__(self):
        return hash("medical")

    def __contains__(self, item):
        return True

    def __bool__(self):
        return True

    def __str__(self):
        return "medical"

    def __repr__(self):
        return "<AlwaysEqual>"


NON_STRING_PURPOSES = [
    True, False, 1, 0, -1, 3.14, object(), _AlwaysEqual(),
    ["medical"], ("medical",), {"medical"}, {"purpose": "medical"},
    b"medical", bytearray(b"medical"),
]


@pytest.mark.parametrize("purpose", NON_STRING_PURPOSES, ids=[_pid(p) for p in NON_STRING_PURPOSES])
@pytest.mark.parametrize("surface", list(Surface), ids=[s.name for s in Surface])
def test_l5_is_not_served_by_a_purpose_that_is_not_a_string(purpose, surface):
    """The type question, asserted only in its safety half so the answer to the
    *loudness* half cannot weaken it. Refusing loudly and denying quietly are
    both defensible for a malformed purpose; returning `True` is not.

    `_AlwaysEqual` is the sharp one — it is the object shape that walks through
    any equality-based guard, and `may_render` is the guard the whole
    application routes through. Under the enum it is sharper still: a
    membership test written `purpose == Purpose.DRAFTING` or `purpose in
    _VALID` is passed by it, and `Purpose` being a `str` subclass makes both
    spellings the natural ones to write.

    **The safety half is unchanged and is asserted first**, exactly as it was
    before the enum, so the answer to the loudness question below cannot weaken
    it.
    """
    assert verdict(Rung.L5, surface, purpose) is not True


@pytest.mark.parametrize("purpose", NON_STRING_PURPOSES, ids=[_pid(p) for p in NON_STRING_PURPOSES])
@pytest.mark.parametrize("surface", list(Surface), ids=[s.name for s in Surface])
def test_a_purpose_that_is_not_a_purpose_is_refused_loudly(purpose, surface):
    """The loudness half, separately — and after 2026-08-05 it has an answer.

    Before the enum this was open: refusing loudly and denying quietly were both
    defensible for a malformed purpose. The ratified rule closes it —
    **loud on type, closed on data** — and a purpose is a *call-site* property
    like a surface, never something that arrives from a record, so an unreadable
    one is a programmer error. Contrast the rung immediately below in §9, which
    denies quietly because I-11 says an unclassified value reaching runtime
    "reads `L5` and is not served".
    """
    for rung in LADDER:
        with pytest.raises(UndeclaredPurpose):
            may_render(rung, surface, purpose=purpose)


@pytest.mark.parametrize("purpose", NON_STRING_PURPOSES, ids=[_pid(p) for p in NON_STRING_PURPOSES])
def test_a_malformed_purpose_does_not_unlock_l4_off_the_detail_pane(purpose):
    """The same probe one rung down, where there *is* something to unlock. A
    purpose that is not a string has declared nothing, whatever it claims when
    compared."""
    for surface in frozenset(Surface) - {S1_DETAIL}:
        assert verdict(Rung.L4, surface, purpose) is not True


@pytest.mark.parametrize("rung", LADDER, ids=[r.name for r in LADDER])
def test_a_rung_passed_as_a_purpose_is_only_its_own_string(rung):
    """A hazard that comes free with I-14: `Rung` is a `str` subclass, so
    `may_render(r, s, purpose=Rung.L1)` type-checks as a purpose, and
    `isinstance(purpose, str)` cannot tell the two arguments apart. That is one
    transposed argument away from being written by accident.

    **The claim changed on 2026-08-05, and it got stronger — this is a
    meaning change and it is reported as one.** It used to be *a rung as a
    purpose gets no special power*: `Rung.L1` **is** the string `"L1"`, `"L1"`
    was a purpose string like any other, and the two spellings only had to
    agree. Under a closed enum a `Rung` is not a `Purpose`, so the transposed
    argument is now **refused**, which is the outcome the old test could not
    ask for.

    The old assertion cannot be kept verbatim for a mechanical reason worth
    writing down: it compared two `verdict()` results with `is`, and two raised
    exceptions are two distinct objects, so it would fail on identity while the
    behaviour was in fact identical. Agreement between the two spellings is
    therefore asserted by *type* rather than by identity.
    """
    for surface in Surface:
        for scored in LADDER:
            as_member = verdict(scored, surface, rung)
            as_string = verdict(scored, surface, rung.value)
            assert isinstance(as_member, UndeclaredPurpose), (
                f"purpose={rung!r} was accepted as a purpose on {surface.name}"
            )
            assert type(as_member) is type(as_string), (
                f"purpose={rung!r} and purpose={rung.value!r} disagree: "
                f"{as_member!r} vs {as_string!r}"
            )
        assert verdict(Rung.L5, surface, rung) is not True


def test_there_is_no_override_parameter_on_the_decision_function():
    """"`L5` has no override anywhere" is a claim about the signature before it
    is a claim about the body. A keyword named `force`, `override`, `allow` or
    `bypass` is an escape hatch that no amount of table correctness closes, and
    it will be reached for the first time someone is debugging at midnight.

    Any parameter beyond the contract's three must also carry a default, or the
    published call `may_render(Rung.L4, Surface.S1_DETAIL, purpose=None)` stops
    working and every call site grows an argument it does not understand.
    """
    banned = re.compile(
        r"force|override|bypass|allow|admin|root|unsafe|ignore|skip|escape|god",
        re.IGNORECASE,
    )
    for fn in (may_render, compose, classify_schema):
        params = inspect.signature(fn).parameters
        offenders = [n for n in params if banned.search(n)]
        assert not offenders, f"{fn.__name__} takes {offenders}"

    contract = {"rung", "surface", "purpose"}
    for name, param in inspect.signature(may_render).parameters.items():
        if name in contract:
            continue
        assert param.default is not inspect.Parameter.empty or param.kind in (
            inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD
        ), f"may_render grew a required parameter {name!r} outside the contract"


def test_purpose_is_keyword_only_and_defaults_to_nothing_permissive():
    """The contract passes `purpose=` by keyword every time. A positional third
    argument lets two call sites mean different things by
    `may_render(r, s, x)`, and the whole point of one chokepoint (I-16) is that
    every call through it reads the same way.

    If `purpose` carries a default it must be `None`. A default of `""`, `"*"`
    or `"any"` would authorize every caller that forgot the argument — and
    after 2026-08-05, a default of any `Purpose` member would do the same thing
    with a type check in front of it.

    **The positional probe had to change and the reason is the sharpest thing
    in this conversion.** It read `may_render(Rung.L1, S1_LIST, "medical")` and
    expected `TypeError`. `UndeclaredPurpose` **is** a `TypeError`, so under the
    enum that line passes whether or not `purpose` is keyword-only: a
    positional-friendly signature would take `"medical"`, reject it as not a
    member, and raise the very exception the test is watching for. The probe
    now passes a **valid** purpose positionally, so the only thing that can
    raise is the arity — and to make sure of it, the refusal is asserted *not*
    to be an `UndeclaredPurpose`.
    """
    param = inspect.signature(may_render).parameters["purpose"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY, (
        "purpose is keyword-only in the published contract"
    )
    if param.default is not inspect.Parameter.empty:
        assert param.default is None, (
            f"purpose defaults to {param.default!r} — a default that declares "
            "something is a declaration nobody made"
        )
    with pytest.raises(TypeError) as caught:
        may_render(Rung.L1, S1_LIST, Purpose.DRAFTING)
    assert not isinstance(caught.value, UndeclaredPurpose), (
        "the third positional argument was read as a purpose and rejected on "
        "its value — which means it was accepted positionally"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 6 · S2 is a rendering, not "internal processing"
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("purpose", VALID_PURPOSES, ids=[_pid(p) for p in VALID_PURPOSES])
def test_s2_serves_l1_and_l2_and_refuses_everything_above(purpose):
    """The `S2` column of the crossing table, whole, for every purpose.

    "A prompt is not *internal processing*; it is a surface with a reader, and
    the reader summarizes, retains in a cache, and produces text a human will
    act on." Under this model `intelligence.py` is a rendering path and is
    governed like one — which is exactly what it was not, in the codebase where
    the last eight rows of the activity log went into every prompt (F-4) and
    `do_not_use` atoms went into the drafting packet unmarked (BUG-5).
    """
    for surface in S2:
        assert may_render(Rung.L1, surface, purpose=purpose) is True
        assert may_render(Rung.L2, surface, purpose=purpose) is True
        assert may_render(Rung.L3, surface, purpose=purpose) is False
        assert may_render(Rung.L4, surface, purpose=purpose) is False
        assert may_render(Rung.L5, surface, purpose=purpose) is False


def test_s2_is_not_more_permissive_than_the_operators_own_screen():
    """A model prompt is further from the operator than the operator's own
    screen, on every axis that matters: it is cached, it is summarized, and its
    output is text somebody acts on. If any rung reached `S2` that could not
    reach `S1`, the ladder would be scoring the wrong thing entirely."""
    for purpose in VALID_PURPOSES:
        for rung in LADDER:
            for prompt in S2:
                if may_render(rung, prompt, purpose=purpose) is True:
                    assert may_render(rung, S1_DETAIL, purpose=purpose) is True, (
                        f"{rung.name} reaches the model prompt but not the "
                        f"operator's own detail pane (purpose={purpose!r})"
                    )


# ═════════════════════════════════════════════════════════════════════════════
# 7 · Composition is `max` — I-12
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("rung", LADDER, ids=[r.name for r in LADDER])
def test_i12_composing_one_rung_is_that_rung(rung):
    """The identity case, pinned so the sweeps below are anchored to something."""
    assert compose(rung) is Rung(rung)


@pytest.mark.parametrize("a,b", list(itertools.product(LADDER, LADDER)),
                         ids=[f"{a.name}+{b.name}" for a, b in itertools.product(LADDER, LADDER)])
def test_i12_composition_is_max_over_every_pair(a, b):
    """All twenty-five pairs. `max`, commutative, and idempotent — a record is
    the `max` of its fields, a chronology of its events, a draft of every fact
    it cites."""
    expected = LADDER[max(LADDER.index(a), LADDER.index(b))]
    assert compose(a, b) is expected
    assert compose(b, a) is expected
    assert compose(a, b, a, b) is expected


def test_i12_composition_is_max_over_every_triple():
    """One hundred and twenty-five, plus associativity. A join of three
    sources is the realistic case — a chronology built from a record, a note
    and a retrieved neighbour — and it is where a pairwise-only implementation
    that folds left with a stale accumulator shows up."""
    for a, b, c in itertools.product(LADDER, repeat=3):
        expected = LADDER[max(LADDER.index(a), LADDER.index(b), LADDER.index(c))]
        assert compose(a, b, c) is expected, (a, b, c)
        assert compose(compose(a, b), c) is expected, (a, b, c)
        assert compose(a, compose(b, c)) is expected, (a, b, c)


def test_i12_a_projection_never_lowers_a_rung():
    """"A projection never lowers a rung. Only an explicit, dated, sealed
    declassification does." Stated as the property rather than as cases: the
    composed answer is never below any of its inputs, for every combination up
    to three, which is the whole of the claim `max` is making."""
    for size in (1, 2, 3):
        for combo in itertools.product(LADDER, repeat=size):
            got = compose(*combo)
            for member in combo:
                assert LADDER.index(Rung(got)) >= LADDER.index(member), (combo, got)


def test_i11_composing_nothing_is_l5():
    """"Composing nothing is not composing something harmless." An empty
    context window, a record with no classified fields, a draft citing no
    facts — every one of those is a thing whose sensitivity nobody established,
    and the fail-closed reading of "nobody established it" is `L5`."""
    assert compose() is Rung.L5
    assert rendered_on(compose(), None) == frozenset()


@pytest.mark.parametrize("surface", list(Surface), ids=[s.name for s in Surface])
def test_i12_a_composed_rung_meets_may_render_as_its_max(surface):
    """What happens when a composed rung meets `may_render` — the join between
    §4 and this section, and the place a leak would live if the two halves were
    written to different tables.

    Every combination up to three rungs, on every surface. The composed answer
    must be treated exactly as its `max` would be — not as its first element,
    not as its last, and not as an average.
    """
    for size in (1, 2, 3):
        for combo in itertools.product(LADDER, repeat=size):
            top = LADDER[max(LADDER.index(r) for r in combo)]
            # was `(None, "medical")`; "medical" is a data category, not a
            # purpose, and never was one — AGENT_RETRIEVAL is the member that
            # actually lifts a ceiling, which is what this pair is testing.
            for purpose in (None, Purpose.AGENT_RETRIEVAL):
                assert (
                    may_render(compose(*combo), surface, purpose=purpose)
                    is may_render(top, surface, purpose=purpose)
                ), (combo, surface.name, purpose)


@pytest.mark.parametrize("surface", list(Surface), ids=[s.name for s in Surface])
def test_bug5_one_sealed_fact_in_a_record_seals_the_record(surface):
    """BUG-5 at the composition seam, which is where it actually lived: the
    `do_not_use` atom was not rejected on its own card *and* the two functions
    that assembled drafting material never consulted `fact_verification` at
    all, so it flowed into the packet alongside four clean facts.

    A packet of `L1 + L1 + L1 + L5` is `L5`. There is no surface on which four
    public facts launder the fifth.
    """
    packet = compose(Rung.L1, Rung.L1, Rung.L1, Rung.L5)
    assert packet is Rung.L5
    for purpose in VALID_PURPOSES:
        assert may_render(packet, surface, purpose=purpose) is False
    for purpose in REJECTED_PURPOSES:
        assert verdict(packet, surface, purpose) is not True


def test_i12_compose_returns_a_rung_and_not_a_bare_string():
    """The result crosses the next boundary and is composed again. If it comes
    back as a plain `str` the second composition is comparing something the
    ladder does not own, and I-14's whole point was that a rung carries its
    prefix wherever it goes."""
    for size in (1, 2, 3):
        for combo in itertools.product(LADDER, repeat=size):
            got = compose(*combo)
            assert isinstance(got, Rung), f"compose{combo} returned {type(got).__name__}"


@pytest.mark.parametrize("junk", [3, 1, 0, -1, "3", "L6", "l3", "", None, True,
                                  3.0, ["L3"], ("L3",), {"rung": "L3"}, object(),
                                  _AlwaysEqual()])
def test_i11_compose_refuses_junk_and_never_answers_l1(junk):
    """Absence fails closed, and so does nonsense. The unacceptable answer is
    not "raised" — it is a low rung, because a low rung is a permission.

    `compose(1)` returning `L1` would be I-14's catastrophe with the scales
    crossed: WillowGate's `Rookie` is trust tier one and `L1` is *public*, so
    the least-trusted principal and the least-restricted datum are the same
    integer.
    """
    try:
        got = compose(junk)
    except Exception:                           # noqa: BLE001 — refusal is fine
        return
    assert got is Rung.L5, (
        f"compose({junk!r}) answered {got!r}. Junk in the composition is an "
        "unclassified input, and an unclassified input reads L5."
    )


@pytest.mark.parametrize("junk", [3, "L6", None, ["L3"], object()])
def test_i11_junk_mixed_with_real_rungs_does_not_dilute_the_answer(junk):
    """The realistic shape: one field in a record of twelve arrives malformed.
    The composition must not quietly drop it and return the `max` of the
    survivors — that is I-8's "never silently drop input" applied to the rung
    path, and dropping the one field nobody classified is exactly how an
    unclassified field reaches a surface."""
    try:
        got = compose(Rung.L1, junk, Rung.L2)
    except Exception:                           # noqa: BLE001
        return
    assert got is Rung.L5, (
        f"compose(L1, {junk!r}, L2) answered {got!r} — the malformed field was "
        "dropped rather than failing closed"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 8 · Absence fails closed, twice over — I-11 and the schema seam
# ═════════════════════════════════════════════════════════════════════════════
# The exact shape of a field spec is not pinned by the published contract, so
# the *positive* tests here probe a set of plausible spellings and say which
# were accepted. A failure in this section is an API disagreement rather than a
# safety defect — the negative tests around it are not shape-tolerant and are
# the ones that matter.

#: Every way this corpus can imagine a field being left unclassified. All of
#: them are build failures; none of them is a default.
UNCLASSIFIED_SPECS = [
    None,
    {},
    {"rung": None},
    {"rung": ""},
    {"rung": "   "},
    {"matter": "custody", "jurisdiction": "US-CA"},      # everything but the rung
    {"type": "text", "nullable": True},
    {"Rung": "L4"},                                      # wrong case on the key
    {"sensitivity": "L4"},                               # a near-miss key name
    [],
    "",
]

#: Declared, but not with anything on the ladder. A build failure too: an
#: unknown rung is not "clamp to L5 and carry on", it is a typo nobody caught.
MISDECLARED_SPECS = [
    {"rung": "L0"},
    {"rung": "L6"},
    {"rung": "l4"},
    {"rung": "L4 "},
    {"rung": 4},
    {"rung": 0},
    {"rung": True},
    {"rung": ["L4"]},
    {"rung": "L4,L5"},
    {"rung": "public"},
    {"rung": "sealed"},
    {"rung": "unknown"},
]


@pytest.mark.parametrize("spec", UNCLASSIFIED_SPECS, ids=[_pid(s) for s in UNCLASSIFIED_SPECS])
def test_i11_an_unclassified_field_fails_the_build(spec):
    """I-11, and the phase's exit criterion in one line: **an unclassified
    field fails the build.**

    Not a warning, not a default, not `L5`-and-carry-on at schema-definition
    time. The runtime `L5` fallback exists for a field that reaches production
    unclassified *anyway*; it is the second line of defence and it is not
    permission to skip the first.
    """
    with pytest.raises(Exception):
        classify_schema({"body": spec})


@pytest.mark.parametrize("spec", MISDECLARED_SPECS, ids=[_pid(s) for s in MISDECLARED_SPECS])
def test_i11_a_rung_that_is_not_on_the_ladder_fails_the_build(spec):
    """`"l4"`, `"L4 "` and `4` are three ways of typing `L4` that are not `L4`.
    A classifier that normalizes them has two spellings for one rung and
    therefore, eventually, two tables. `4` is refused for I-14's reason on top
    of that."""
    with pytest.raises(Exception):
        classify_schema({"body": spec})


def test_i11_the_build_failure_names_the_field():
    """A build failure that does not say *which* field is a build failure the
    developer works around. `chronology_builder`'s `gaps` pattern (I-8) is the
    house standard: the thing that could not be handled is named, not
    swallowed."""
    with pytest.raises(Exception) as caught:
        classify_schema({"body": None})
    assert "body" in str(caught.value), (
        f"the refusal reads {str(caught.value)!r} and does not name the "
        "unclassified field"
    )


def test_i11_one_unclassified_field_among_many_still_fails():
    """BUG-6's shape applied to classification. Workers' comp — one of three
    advertised matter types — was structurally absent from `urgent_queue()`,
    Today, and the MCP briefing, under a docstring that said "all cases". An
    omission inside a mostly-correct table is invisible; a classifier that
    checks the first field, or any field, rather than every field, is the same
    defect."""
    schema = {f"field_{i}": {"rung": "L2"} for i in range(30)}
    schema["the_one_nobody_classified"] = None
    with pytest.raises(Exception) as caught:
        classify_schema(schema)
    assert "the_one_nobody_classified" in str(caught.value)


def test_i11_classification_is_never_inferred_from_the_field_name():
    """"**The rung is a property of the field in its jurisdiction, not of the
    data type.** A bankruptcy docket is a public record; a family-court file is
    commonly sealed. The *same* field — a case number — is `L1` in one matter
    and `L3` in another. Anything that classifies by column name alone is
    wrong."

    So every one of these must fail the build, however obvious the name looks.
    A name-based default is the most tempting thing in this whole module and it
    is explicitly the wrong answer.
    """
    for name in ("case_number", "hearing_date", "courthouse", "ssn",
                 "diagnosis", "child_name", "public_notice", "docket",
                 "creditor_amount", "notes"):
        with pytest.raises(Exception):
            classify_schema({name: None})


class _HostileSpec(dict):
    """A field spec that raises when the classifier reads it.

    Stands in for the real thing: a schema loader that hits a decoding error,
    a plugin that throws, a field whose rung is computed by something that is
    currently broken. "A classifier that errors **denies** — never `L1`."
    """

    def __getitem__(self, key):
        raise RuntimeError("the classifier blew up reading this field")

    def get(self, *args, **kwargs):
        raise RuntimeError("the classifier blew up reading this field")

    def keys(self):
        raise RuntimeError("the classifier blew up reading this field")


class _UnenumerableSchema(dict):
    """A schema whose fields cannot be listed."""

    def items(self):
        raise RuntimeError("the schema blew up while being enumerated")

    def keys(self):
        raise RuntimeError("the schema blew up while being enumerated")

    def __iter__(self):
        raise RuntimeError("the schema blew up while being enumerated")


def test_i11_a_classifier_that_errors_denies():
    """I-11's third clause, and the one a corpus written from the code would
    skip because there is no code path to read.

    The failure mode this forbids is a `try/except` around the classification
    that logs and moves on. Whatever the exception, the answer is not a
    classification — and specifically it is never `L1`, which is the value a
    default-shaped `except` reaches for.
    """
    with pytest.raises(Exception):
        classify_schema({"body": _HostileSpec()})


def test_i11_a_schema_that_cannot_be_enumerated_does_not_classify_clean():
    """The nastiest version, because the fail-open answer here *looks* like
    success: enumerate nothing, find no unclassified fields, return an empty
    classification, pass the build. A schema you cannot read is a schema you
    have not classified."""
    schema = _UnenumerableSchema({"body": {"rung": "L4"}})
    with pytest.raises(Exception):
        classify_schema(schema)


@pytest.mark.parametrize("schema", [None, "", 0, [], ["body"], object(), 42])
def test_i11_a_schema_that_is_not_a_schema_is_refused(schema):
    """Passing the wrong thing entirely must not be the quietest way through
    the gate. `classify_schema([])` returning cleanly is a build that passes
    because nothing was checked."""
    with pytest.raises(Exception):
        classify_schema(schema)


# ── the positive half: which spellings does the seam accept? ─────────────────
# The contract fixes the refusal (`{"body": None}` raises) and says nothing
# about the accepted shape. These candidates are the plausible readings of
# "record the matter type and jurisdiction alongside the rung" (step 5 of the
# classification procedure).

def _spellings(rung: Rung) -> dict:
    return {
        "bare enum": rung,
        "bare string": rung.value,
        "dict rung enum": {"rung": rung},
        "dict rung string": {"rung": rung.value},
        "dict with provenance": {
            "rung": rung.value, "matter": "workers-comp", "jurisdiction": "US-CA",
        },
    }


def _accepted_spellings() -> dict:
    accepted = {}
    for name, spec in _spellings(Rung.L4).items():
        try:
            classify_schema({"ime_findings": spec})
        except Exception:                       # noqa: BLE001
            continue
        accepted[name] = spec
    return accepted


def test_the_schema_seam_accepts_at_least_one_declared_spelling():
    """If nothing here is accepted, the corpus cannot verify the positive half
    of I-11 at all — only that everything fails. That is a corpus reporting
    honestly that it could not reach the feature, and it is a red worth having.

    **API question, flagged rather than assumed.** Add the real spelling to
    `_spellings` if it is none of these; that edit is the disagreement being
    resolved, not the corpus being softened.
    """
    accepted = _accepted_spellings()
    assert accepted, (
        "classify_schema accepted none of the candidate field-spec spellings: "
        f"{sorted(_spellings(Rung.L4))}. Either the seam takes a shape this "
        "corpus did not guess, or it refuses everything."
    )


def test_i11_every_rung_is_declarable_in_every_accepted_spelling():
    """A spelling that accepts `L4` and refuses `L1` would put half the ladder
    out of reach of the schema, and the fields nobody could declare would end
    up declared as something they are not."""
    for name in _accepted_spellings():
        for rung in LADDER:
            spec = _spellings(rung)[name]
            classify_schema({"ime_findings": spec})     # must not raise


def test_i11_the_same_field_name_takes_different_rungs_in_different_matters():
    """The model's own worked example, as a test: a case number is `L1` in a
    bankruptcy matter (dockets are public) and `L3` in a custody matter (family
    records are commonly sealed). Both declarations must be accepted, by the
    same classifier, for the same field name — which is only possible if
    nothing is keyed on the name."""
    for name in _accepted_spellings():
        classify_schema({"case_number": _spellings(Rung.L1)[name]})
        classify_schema({"case_number": _spellings(Rung.L3)[name]})


def test_i11_a_declared_classification_is_readable_and_says_what_was_declared():
    """A classifier whose output cannot be read is a build step, not a model —
    and the surface layer has to get a rung from somewhere to call
    `may_render`.

    **API question.** The return shape is not in the contract. This reader
    handles a mapping of field to rung, a mapping of field to spec, and an
    object exposing either; if it understands none of them it fails loudly
    rather than passing vacuously, because a shape-tolerant test that tolerates
    everything is the Phase 0 failure exactly.
    """
    accepted = _accepted_spellings()
    if not accepted:
        pytest.fail("no accepted spelling — see the previous test")
    name, _ = next(iter(accepted.items()))

    for rung in LADDER:
        result = classify_schema({"ime_findings": _spellings(rung)[name]})
        assert _rung_from(result, "ime_findings") is rung, (
            f"declared {rung.name}, classification reads {result!r}"
        )


def _rung_from(result, field: str) -> Rung:
    """Pull one field's rung out of whatever `classify_schema` returned."""
    for candidate in (result,
                      getattr(result, "fields", None),
                      getattr(result, "rungs", None),
                      getattr(result, "classification", None)):
        if candidate is None:
            continue
        try:
            entry = candidate[field]
        except Exception:                       # noqa: BLE001
            continue
        if isinstance(entry, Rung):
            return entry
        for attr in ("rung", "value"):
            inner = entry.get(attr) if isinstance(entry, dict) else getattr(entry, attr, None)
            if isinstance(inner, Rung):
                return inner
            if isinstance(inner, str):
                return Rung(inner)
        if isinstance(entry, str):
            return Rung(entry)
    pytest.fail(
        f"the corpus cannot read a rung for {field!r} out of {result!r}. This "
        "is a shape disagreement, not a safety failure — but a classification "
        "the surface layer cannot read is a classification nothing enforces."
    )


# ═════════════════════════════════════════════════════════════════════════════
# 9 · Type discipline at the chokepoint
# ═════════════════════════════════════════════════════════════════════════════
# Every test in this section asserts the safety half unconditionally and the
# loudness half separately, so a disagreement about *how* to refuse cannot cost
# the guarantee that it refuses.

NOT_A_RUNG = [1, 2, 3, 4, 5, 0, -1, "1", "3", "5", "l1", "l5", "L0", "L6",
              "public", "sealed", "", "   ", None, True, False, 1.0,
              ["L1"], ("L1",), {"rung": "L1"}, object(), _AlwaysEqual(),
              Surface.S1_LIST,
              # Added 2026-08-05: `Purpose` is a third `str` enum in the same
              # three-argument call, so there are now six ways to transpose two
              # of them and every one of them type-checks.
              Purpose.DRAFTING, Purpose.AGENT_RETRIEVAL]


@pytest.mark.parametrize("bad", NOT_A_RUNG, ids=[_pid(b) for b in NOT_A_RUNG])
@pytest.mark.parametrize("surface", list(Surface), ids=[s.name for s in Surface])
def test_i14_nothing_that_is_not_a_rung_is_ever_rendered(bad, surface):
    """The safety half. The integers are the ones that matter: WillowGate trust
    runs `Rookie(1) → Steady(2) → Veteran(3)`, ascending privilege, so a `1`
    arriving where a rung is expected is the *least* trusted principal, and if
    it coerced to `L1` it would be the *least* restricted datum — rendered on
    every surface including egress. The two scales meet at the integer and the
    integer is where they must not meet.

    **The declared-purpose probe had to become a real purpose.** It was
    `"medical"`. Under the enum that raises on the *purpose* before the rung is
    ever looked at, so `is not True` would hold for a reason that has nothing
    to do with rungs and this whole sweep — 30 bad values × every surface —
    would pass vacuously. That is the single easiest way for this conversion to
    hollow the corpus out, and it is why every stand-in purpose in this file was
    replaced with a member rather than deleted.
    """
    assert verdict(bad, surface, Purpose.AGENT_RETRIEVAL) is not True
    assert verdict(bad, surface, None) is not True


@pytest.mark.parametrize("bad", [3, 1, 0, -1, None, object(), ["L1"], 1.0])
def test_i14_a_non_rung_denies_rather_than_raising(bad):
    """The loudness half. **Decided 2026-08-05: it denies. The spec says so.**

    This test asserted `raise` when it was written, and it was written blind —
    the corpus author had not seen the implementation and did not know it
    disagreed. The disagreement was real, both readings were argued, and the
    operator resolved it. The history is kept because the reasoning is the
    valuable part and a resolved question that leaves no trace gets re-opened
    by the next person.

    **What decides it.** I-11, in as many words: *"if one reaches runtime
    unclassified anyway it **reads `L5` and is not served**."* That is a
    rendering decision, not an exception. `may_render` answers "may this be
    shown"; an unreadable rung reads `L5`, and `L5` is not shown. Raising here
    would contradict the sentence the invariant is written in.

    **The asymmetry is deliberate, not an oversight.** `classify_schema`,
    `Classified`, and the *surface* argument all raise. A surface is a
    call-site property that can never arrive from data, so an unreadable one
    is a programmer error and should be loud. A rung **is** a data property,
    so an unreadable one is precisely the condition I-11 legislates for. Loud
    on type, closed on data.

    **What the corpus argued, preserved because it is not wrong about the
    risk:** `3` is not an unclassified field, it is a type confusion, and I-14
    exists because `3` means something on the *other* scale — `Rookie(1) →
    Steady(2) → Veteran(3)`, ascending privilege. A silent `False` shows the
    operator a blank pane and the developer a working gate, and the fix
    reached for is a cast at the call site, which is how a `1` becomes an
    `L1`. That risk is real and it is now **carried upstream**: the values
    cannot enter through `classify_schema` or `Classified`, both of which
    raise on every one of them. If a later phase opens a path into
    `may_render` that bypasses both, this reasoning is what says the path is
    the defect.

    **The safety guarantee never depended on the outcome.**
    `test_i14_nothing_that_is_not_a_rung_is_ever_rendered` above sweeps 28 bad
    values × every surface × two purposes and passes either way: nothing that
    is not a `Rung` is ever served. What was at stake was only whether a
    developer finds out — and the answer is that they find out upstream.
    """
    assert may_render(bad, S1_LIST, purpose=None) is False


@pytest.mark.parametrize("bad", [3, 1, 0, -1, None, object(), ["L1"], 1.0])
def test_i14_the_same_non_rungs_are_refused_loudly_upstream(bad):
    """The other half of the decision above, and the reason it is safe.

    `may_render` denying quietly is only defensible because these values
    **cannot reach it through any classified path**: `classify_schema` and
    `Classified` both raise on every one of them. Deliberately the same eight
    values as the test above, so the pair reads as one decision — loud on the
    way in, closed at the point of render.

    Written 2026-08-05 when the denial was ratified. The argument for quiet
    denial leans on this being true, and a load-bearing claim with no test is
    the defect this project keeps finding. Now it has one: if a later change
    lets any of these through classification, this fails, and the reasoning in
    the test above stops being valid at the same moment.
    """
    with pytest.raises(UnclassifiedField):
        classify_schema({"a_field": bad})
    with pytest.raises(UnclassifiedField):
        Classified(bad, "text")


NOT_A_SURFACE = ["S1_LIST", "s1_list", "S1", "screen", "prompt", "", None, 0, 1,
                 True, ["S1_LIST"], object(), _AlwaysEqual(), Rung.L1,
                 Purpose.DRAFTING]


@pytest.mark.parametrize("bad", NOT_A_SURFACE, ids=[_pid(b) for b in NOT_A_SURFACE])
def test_nothing_that_is_not_a_surface_is_ever_rendered_on(bad):
    """The safety half for the other argument. A surface that is not one of the
    four has no row in the crossing table, so nothing about it has been
    decided, and the answer to "may I render on a surface nobody scored" is
    no.

    `"medical"` became `Purpose.AGENT_RETRIEVAL` for the reason given above the
    rung sweep: a rejected purpose raises first and the surface claim would
    never be reached.
    """
    for rung in LADDER:
        assert verdict(rung, bad, Purpose.AGENT_RETRIEVAL) is not True
        assert verdict(rung, bad, None) is not True


@pytest.mark.parametrize("bad", ["S1_LIST", "screen", None, 0, object(), Rung.L1])
def test_an_unknown_surface_is_refused_loudly(bad):
    """Same reasoning as the rung case, and sharper: `"S1_LIST"` is the *right
    surface spelled wrong*, and a quiet `False` for it produces a pane that
    renders nothing with no error anywhere — which is indistinguishable from a
    correctly-empty pane until someone notices the app has stopped working."""
    with pytest.raises((TypeError, ValueError, KeyError)):
        may_render(Rung.L1, bad, purpose=None)


def test_a_rung_spelled_as_its_own_string_agrees_with_the_enum_or_is_refused():
    """I-14 says a rung *is* a string, so `"L3"` is not obviously wrong — and
    because `Rung` is a `str` enum, a dict-keyed table will accept it whether
    or not anyone decided it should. What must never happen is that the two
    spellings of one rung get **different answers**, which is one rung with two
    tables."""
    for rung in LADDER:
        for surface in Surface:
            for purpose in (None, Purpose.AGENT_RETRIEVAL):
                loose = verdict(rung.value, surface, purpose)
                if isinstance(loose, Exception):
                    continue
                assert loose is may_render(rung, surface, purpose=purpose), (
                    f"{rung.value!r} and {rung!r} disagree on {surface.name}"
                )


def test_the_decision_function_is_deterministic_and_holds_no_state():
    """A memoised table keyed on the wrong tuple answers the previous
    question. Every cell, three times, interleaved in a different order each
    pass — and the answers must be identical.

    BUG-7 is the house precedent: the AI cache fingerprint ignored every
    substantive input, so rewriting a body, adding evidence, or moving a
    deadline four days closer all produced the same key and a stale answer was
    re-served for up to seven days.
    """
    cells = [(r, s, p) for r in LADDER for s in Surface for p in SWEEP_PURPOSES]
    first = {c: may_render(c[0], c[1], purpose=c[2]) for c in cells}
    for order in (list(reversed(cells)), sorted(cells, key=lambda c: c[1].name)):
        for cell in order:
            assert may_render(cell[0], cell[1], purpose=cell[2]) is first[cell], cell


# ═════════════════════════════════════════════════════════════════════════════
# 10 · Time does not declassify
# ═════════════════════════════════════════════════════════════════════════════

def test_the_decision_function_takes_no_clock():
    """"**Time does not declassify.** A closed matter's medical records stay
    `L4`. A child turning eighteen changes who may hold the file, not what the
    data is."

    A rung that can fall on its own is a retention schedule wearing a
    classification's clothes, and the parameter is where that starts. A
    `may_render(..., as_of=...)` is an invitation to write "records older than
    N years are `L2`", which is declassification by inertia — the thing the
    model forbids by name.
    """
    banned = re.compile(r"today|now|date|time|clock|age|when|as_of|since|until|"
                        r"expire|stale|ttl", re.IGNORECASE)
    for fn in (may_render, compose):
        offenders = [n for n in inspect.signature(fn).parameters if banned.search(n)]
        assert not offenders, f"{fn.__name__} takes a clock: {offenders}"


def test_no_clock_is_read_inside_the_phase_2_source():
    """The same claim where a signature cannot make it: a module that reads the
    machine clock while deciding what may be rendered has a decision that
    changes overnight with nothing recorded anywhere.

    **Scoped to `rungs.py` and `surfaces.py` deliberately.** I-32's reveal
    timeout is a Phase 4 surface concern and it moves in the *safe* direction
    (back to derived); a constant naming its duration is fine here, a call into
    the clock from the decision path is not.
    """
    calls = re.compile(r"\A(datetime\.(now|today|utcnow)|date\.today|"
                       r"time\.(time|monotonic)|monotonic|perf_counter)\Z")
    offenders = []
    for mod in _keep_modules():
        tree = ast.parse(mod.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                spelled = ast.unparse(node.func)
                if calls.match(spelled) or spelled.endswith((".now", ".today", ".utcnow")):
                    offenders.append(f"{mod.relative_to(ROOT)}:{node.lineno}: {spelled}()")
    assert not offenders, (
        f"the rung decision reads the clock: {offenders}. Time does not "
        "declassify, so nothing here may depend on when it is asked."
    )


def test_a_closed_matter_keeps_its_rung():
    """The property, stated over the only handle the module gives us: the rung
    is a value, and the same value answers the same way however many times it
    is asked. Nothing about "the matter is closed" is an input, because it is
    not one."""
    medical = Rung.L4
    for _ in range(50):
        assert rendered_on(medical, None) == frozenset({S1_DETAIL})
    assert compose(medical, Rung.L1, Rung.L2) is Rung.L4


def test_any_declassification_seam_demands_a_name_and_a_date():
    """"**Declassification is an act with a name and a date**, recorded in the
    ledger `homestead.keep` already binds. No rung falls by inertia, on a
    schedule, or as a side effect of aggregation."

    Phase 2 is not the phase that lands it. But if a callable shaped like one
    appears in these modules, it must not be invocable with a rung alone —
    a one-argument `declassify(rung)` *is* declassification by inertia, with a
    function call standing in for the act.
    """
    import homestead.keep.rungs as rungs_mod
    import homestead.keep.surfaces as surfaces_mod

    shaped = re.compile(r"declassif|downgrade|unseal|relax|lower|reduce|demote",
                        re.IGNORECASE)
    checked = 0
    for module in (rungs_mod, surfaces_mod):
        for name, obj in vars(module).items():
            if name.startswith("_") or not callable(obj) or not shaped.search(name):
                continue
            checked += 1
            with pytest.raises(TypeError):
                obj(Rung.L4)
    # Non-vacuous companion: whether or not such a seam exists, composition
    # itself must never be the thing that lowers a rung.
    assert compose(Rung.L5, Rung.L1) is Rung.L5
    assert compose(Rung.L4, Rung.L1, Rung.L2, Rung.L3) is Rung.L4
    assert checked >= 0


def test_aggregation_is_not_a_declassifier():
    """"No rung falls … as a side effect of aggregation." The re-identification
    check is the whole of `L2`, and it bites harder at household scale: *"one
    matter has an overdue medical response"*, over a household with three
    matters, names the workers' comp matter immediately.

    Until that check passes, the aggregate inherits the `max` of its inputs —
    so the composed value is `L4` and the cover screen (I-31: "the resting
    state reveals nothing") cannot render it.
    """
    aggregate = compose(Rung.L1, Rung.L4)       # a count over one L1 and one L4 fact
    assert aggregate is Rung.L4
    assert may_render(aggregate, S1_LIST, purpose=None) is False
    assert may_render(aggregate, S2_PROMPT, purpose=Purpose.AGENT_RETRIEVAL) is False
    for surface in OFF_SCREEN:
        assert may_render(aggregate, surface, purpose=None) is False


# ═════════════════════════════════════════════════════════════════════════════
# 11 · Worked examples, end to end
# ═════════════════════════════════════════════════════════════════════════════
# Every fixture below is a row from the model's own class→rung table or its
# worked examples, so each of these can be read against `homestead-rungs.md`
# directly.

WORKERS_COMP = {
    "claim_number": Rung.L3,          # identifies
    "carrier": Rung.L3,
    "employer": Rung.L3,
    "response_due": Rung.L1,          # a calendar date, publicly posted
    "ime_findings": Rung.L4,          # "L4–L5 disc herniation, 12% impairment"
    "prescription_record": Rung.L5,   # 42 CFR Part 2
}

CUSTODY = {
    "hearing_date": Rung.L1,
    "courthouse": Rung.L1,
    "department": Rung.L1,
    "case_number": Rung.L3,           # family records commonly sealed — NOT L1
    "parenting_schedule": Rung.L3,
    "child_name": Rung.L4,
    "child_dob": Rung.L4,
    "child_school": Rung.L4,
    "guardian_ad_litem_report": Rung.L4,
    "substance_use_treatment": Rung.L5,
    "protective_order_allegations": Rung.L5,
}

BANKRUPTCY = {
    "chapter": Rung.L1,
    "filing_date": Rung.L1,
    "meeting_341_date": Rung.L1,
    "case_number": Rung.L1,           # bankruptcy dockets ARE public
    "creditor_names": Rung.L4,
    "means_test_income": Rung.L4,
    "ssn": Rung.L5,
    "account_numbers": Rung.L5,
}


def test_worked_example_the_workers_comp_today_card():
    """The model's central worked example, asserted rather than described.

    The file holds *"IME 2026-06-14: L4–L5 disc herniation, 12% whole-person
    impairment, permanent lifting restriction 20 lb."* What Today renders is
    *"Medical records response due Aug 15 — 11 days."* The operator can act.
    The diagnosis is not on the Today list, not in the local model's prompt,
    and not in the MCP briefing. Opening the record shows it.
    """
    assert may_render(WORKERS_COMP["response_due"], S1_LIST, purpose=None) is True
    assert may_render(WORKERS_COMP["ime_findings"], S1_LIST, purpose=None) is False
    assert may_render(WORKERS_COMP["ime_findings"], S1_DETAIL, purpose=None) is True
    assert may_render(WORKERS_COMP["ime_findings"], S2_PROMPT,
                      purpose=Purpose.AGENT_RETRIEVAL) is False
    for surface in S3:
        assert may_render(WORKERS_COMP["ime_findings"], surface, purpose=None) is False


def test_worked_example_the_prescription_record_reaches_nothing():
    """42 CFR Part 2 re-disclosure. `L5`, so it does not reach the detail pane
    the IME reaches, and it does not reach the operator's own agents. This is
    the one row where "the operator holds everything" stops being true, and it
    stops being true deliberately."""
    for surface in Surface:
        for purpose in VALID_PURPOSES:
            assert may_render(WORKERS_COMP["prescription_record"], surface,
                              purpose=purpose) is False
        # And the free text that used to be swept here is now refused rather
        # than merely refused-to-serve. `REDISCLOSURE` is the member that
        # names this act, and even it does not reach an L5 record: 42 CFR
        # Part 2 permits a re-disclosure, it does not lower the rung.
        for purpose in REJECTED_PURPOSES:
            assert verdict(WORKERS_COMP["prescription_record"], surface,
                           purpose) is not True
        assert may_render(WORKERS_COMP["prescription_record"], surface,
                          purpose=Purpose.REDISCLOSURE) is False


@pytest.mark.parametrize("matter,fields", [("workers-comp", WORKERS_COMP),
                                           ("custody", CUSTODY),
                                           ("bankruptcy", BANKRUPTCY)])
def test_worked_example_a_whole_matter_composes_to_its_worst_field(matter, fields):
    """"A record is the `max` of its fields." Each of these three matters holds
    an `L5` field, so each record as a whole is `L5` — which is the correct and
    initially surprising answer, and is why a record is never the unit of
    rendering. Fields are."""
    assert compose(*fields.values()) is Rung.L5
    for surface in Surface:
        for purpose in VALID_PURPOSES:
            assert may_render(compose(*fields.values()), surface,
                              purpose=purpose) is False


def test_worked_example_the_same_case_number_is_l1_or_l3_by_matter():
    """The model's sharpest sentence about classification: *"The same field — a
    case number — is `L1` in one matter and `L3` in another. Anything that
    classifies by column name alone is wrong."* A bankruptcy docket is public;
    a family-court file is commonly sealed."""
    assert BANKRUPTCY["case_number"] is Rung.L1
    assert CUSTODY["case_number"] is Rung.L3
    assert may_render(BANKRUPTCY["case_number"], S2_PROMPT, purpose=None) is True
    assert may_render(CUSTODY["case_number"], S2_PROMPT, purpose=None) is False


def test_worked_example_a_model_prompt_is_the_max_of_its_context_window():
    """I-12's hardest clause: *"a prompt is the `max` of its whole context
    window — and that includes the retrieved neighbours a semantic search
    pulled in."*

    So a prompt assembled from three innocuous facts is `L1`, and the same
    prompt after a semantic search pulls in one `L4` neighbour is `L4`, and
    `L4` reaches a model prompt never. The retrieval is where this is lost in
    practice — nothing in the prompt-assembly code chose the neighbour, so
    nothing in it thinks to score it.
    """
    prompt = [CUSTODY["hearing_date"], CUSTODY["courthouse"], BANKRUPTCY["chapter"]]
    assert compose(*prompt) is Rung.L1
    assert may_render(compose(*prompt), S2_PROMPT, purpose=None) is True

    retrieved_neighbour = CUSTODY["guardian_ad_litem_report"]        # L4
    assert compose(*prompt, retrieved_neighbour) is Rung.L4
    assert may_render(compose(*prompt, retrieved_neighbour), S2_PROMPT,
                      purpose=Purpose.DRAFTING) is False

    sealed_neighbour = CUSTODY["substance_use_treatment"]            # L5
    assert compose(*prompt, sealed_neighbour) is Rung.L5
    for surface in Surface:
        assert may_render(compose(*prompt, sealed_neighbour), surface,
                          purpose=Purpose.DRAFTING) is False


def test_worked_example_bug5_the_drafting_packet():
    """BUG-5 end to end, in the shape the bug report confirmed it.

    `ATM-001` was marked `do_not_use` and `ATM-002` `needs_source`. Both flowed
    into `draft_context('schedule_response').atom_ids`, into
    `schedule_response_packet().proposals`, into the packet markdown, and into
    the `gazelle_ai_draft` prompt — while the Review Facts row for ATM-001 read
    *"do_not_use | Excluded from drafting"*.

    Under this model `do_not_use` is `L5`, a draft is the `max` of every fact
    it cites, and egress and the prompt are both surfaces. The packet cannot be
    assembled, let alone rendered, and no purpose string changes that.
    """
    atm_001 = Rung.L5           # marked do_not_use by the operator
    atm_002 = Rung.L3           # needs_source, but attributed
    clean = [Rung.L1, Rung.L1, Rung.L2]

    packet = compose(*clean, atm_002, atm_001)
    assert packet is Rung.L5
    for surface in S2 | S4:
        for purpose in (None, Purpose.DRAFTING, Purpose.FILING):
            assert may_render(packet, surface, purpose=purpose) is False
        # `"override"` was the fourth entry and is now not a purpose at all,
        # which is the stronger form of what it was here to prove.
        with pytest.raises(UndeclaredPurpose):
            may_render(packet, surface, purpose="override")

    # And the weaker rejection alone is still not renderable off the screen —
    # the defect was that the *stronger* one behaved like the absence of one.
    weaker_only = compose(*clean, atm_002)
    assert weaker_only is Rung.L3
    assert may_render(weaker_only, S1_DETAIL, purpose=None) is True
    for surface in OFF_SCREEN:
        assert may_render(weaker_only, surface, purpose=None) is False


def test_worked_example_the_cover_screen_reveals_nothing():
    """I-31. The resting state shows counts that survive the `L2`
    re-identification check and no more. A count over `L1` and `L2` fields is
    `L2` and renders; a count that inherits an `L4` input does not, and
    *"1 matter has an overdue medical response"* over three matters names the
    matter."""
    safe_count = compose(Rung.L2, Rung.L1, Rung.L2)
    assert safe_count is Rung.L2
    assert may_render(safe_count, S1_LIST, purpose=None) is True

    resolving_count = compose(Rung.L2, WORKERS_COMP["ime_findings"])
    assert resolving_count is Rung.L4
    assert may_render(resolving_count, S1_LIST, purpose=None) is False


def test_worked_example_the_parenting_schedule_is_seen_and_not_said():
    """`L3`'s worked example. `Parenting time · Tue/Thu · minor child A.R.` is
    rendered in full on the operator's screen and is `NULL` in the model
    prompt, where *"a recurring parenting-time obligation on Tue/Thu"* is
    served instead. The derived form is not this module's business; refusing
    the payload is."""
    schedule = CUSTODY["parenting_schedule"]
    assert may_render(schedule, S1_LIST, purpose=None) is True
    assert may_render(schedule, S1_DETAIL, purpose=None) is True
    assert may_render(schedule, S2_PROMPT, purpose=None) is False
    for surface in S3 | S4:
        assert may_render(schedule, surface, purpose=None) is False


def test_worked_example_f4_the_address_that_left_the_house():
    """F-4, scored on this ladder. `tool_context.py`'s citation regex matched
    `1420 Maple 87501` as a case citation and POSTed the whole drafting packet
    — atom bodies, verbatim quotes, the chronology — to courtlistener.com. The
    finding scores it `L4` on `S4`, and the datum it leaked is the one whose
    disclosure gets people killed: a relocated address.

    `L4` on egress without a declared purpose is `False`. There is no reading
    of "verify these citations" that is a declared purpose for exporting a
    party's home address.

    **The enum makes that last sentence enforceable rather than rhetorical.**
    Before 2026-08-05 `purpose="citation check"` was a declaration like any
    other and the only thing standing between F-4 and an `L4` egress was that
    nobody had declared one. Now there is no member for it: the call site
    cannot say "verify these citations", because the closed set does not
    contain that act. It has to claim `EXPORT` or `FILING` or `REDISCLOSURE`
    to get an `L4` out, and each of those is a sentence somebody can be held
    to in a ledger. That is the whole argument for closing the set.
    """
    relocated_address = Rung.L4
    for surface in S4:
        assert may_render(relocated_address, surface, purpose=None) is False
    with pytest.raises(UndeclaredPurpose):
        may_render(relocated_address, S2_PROMPT, purpose="citation check")
    for purpose in VALID_PURPOSES:
        assert may_render(relocated_address, S2_PROMPT, purpose=purpose) is False


# ═════════════════════════════════════════════════════════════════════════════
# 12 · The corpus's own guards
# ═════════════════════════════════════════════════════════════════════════════

def test_the_corpus_has_not_been_hollowed_out():
    """Phase 0's audit found tests that had quietly stopped enforcing what they
    claimed. A table trimmed to two rows is the cheapest way for that to happen
    again, so the tables assert their own size — and the sweep asserts that it
    actually sweeps a full cross-product rather than a diagonal."""
    assert len(LADDER) == 5
    assert len(BLANK_PURPOSES) >= 6
    assert len(PLAUSIBLE_PURPOSES) >= 8
    assert len(ADVERSARIAL_PURPOSES) >= 30
    assert len(PURPOSE_STRINGS) >= 44
    assert len(UNCLASSIFIED_SPECS) >= 11
    assert len(MISDECLARED_SPECS) >= 12
    assert len(NOT_A_RUNG) >= 25
    assert len(NOT_A_SURFACE) >= 14
    assert len(NON_STRING_PURPOSES) >= 14
    assert len(Surface) >= 5

    # ── added at the 2026-08-05 conversion ───────────────────────────────────
    # The failure this file most had to fear was the enum being used as an
    # excuse to trim the free-text tables. Their sizes are asserted above; that
    # they are still *swept* is asserted here.
    assert len(Purpose) == 6, (
        "membership is a product decision and the set is closed; a seventh "
        "member is a new act somebody has to authorise, not a convenience"
    )
    assert len(VALID_PURPOSES) == 7, "the six, and None for 'nobody declared one'"
    assert SWEEP_PURPOSES == VALID_PURPOSES
    assert len(REJECTED_PURPOSES) >= 58
    for family in (BLANK_PURPOSES, PLAUSIBLE_PURPOSES, ADVERSARIAL_PURPOSES,
                   MEMBER_VALUE_STRINGS, MEMBER_NAME_STRINGS):
        assert set(family) <= set(REJECTED_PURPOSES), (
            "a purpose family stopped being swept — the free-text strings are "
            "this corpus's inheritance from before the enum, and losing them "
            "would be the single worst outcome of the conversion"
        )
    for sharp in ("medical\x00override", "M" * 4096, "медицинский", "🔓",
                  "../medical", "medical'; --", "override", "L5",
                  "do_not_use", "", "   "):
        assert sharp in REJECTED_PURPOSES, f"{sharp[:20]!r} was deleted"
    # The cell sweep is smaller than it was (7 purposes, not 12) and it is now
    # *complete*: there is no accepted purpose it fails to visit.
    assert len(LADDER) * len(Surface) * len(SWEEP_PURPOSES) >= 175
    assert set(SWEEP_PURPOSES) == {None} | set(Purpose)


def test_the_corpus_asserts_permission_as_well_as_refusal():
    """The self-check that matters most here. A corpus made only of denials is
    passed by `def may_render(*a, **k): return False`, and an application that
    renders nothing has failed the person using it just as completely as one
    that renders everything — F-5's litigant needs to see their own hearing
    date.

    So: something must be `True` on every surface, and something must be
    `False` on every surface.
    """
    for surface in Surface:
        served = {r for r in LADDER if may_render(r, surface, purpose=None) is True}
        refused = {r for r in LADDER if may_render(r, surface, purpose=None) is False}
        assert served, f"{surface.name} serves nothing at all"
        assert refused, f"{surface.name} refuses nothing at all"
        assert Rung.L1 in served
        assert Rung.L5 in refused


def test_the_two_phase_2_modules_exist_where_the_contract_says():
    """`Rung`, `compose`, `classify_schema` and `may_render` in
    `homestead.keep.rungs`; `Surface` in `homestead.keep.surfaces`. The imports
    at the top of this file are the real assertion — this one only makes the
    reason legible when they fail, and pins that the split is by module rather
    than by re-export."""
    import homestead.keep.rungs as rungs_mod
    import homestead.keep.surfaces as surfaces_mod

    for name in ("Rung", "compose", "classify_schema", "may_render"):
        assert hasattr(rungs_mod, name), f"homestead.keep.rungs has no {name}"
    assert hasattr(surfaces_mod, "Surface")
    assert surfaces_mod.Surface is Surface
    assert rungs_mod.Rung is Rung
