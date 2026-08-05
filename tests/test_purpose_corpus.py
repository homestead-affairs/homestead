"""`Purpose` — the closed enum. Written by a hand that has not seen the code.

The blind half of the 2026-08-05 change. `tests/test_surfaces_corpus.py` is the
Phase 2 corpus *converted* onto the enum — it keeps proving what it proved
before, in the stronger form the enum permits. This file is the other half: the
guarantees the enum is supposed to **buy**, which nothing before it could state.

**Why this is a separate hand.** Phase 0 was audited twice and failed both
times, because the same hand wrote the code and the test and the test learned
the code's shape. Phases 1 and 2 split the hands and it worked. The enum was
ratified in `docs/PHASE2-SURFACES.md` and deliberately **not** implemented at
the time, in as many words: *"that translation would be performed by the same
hand that wrote the implementation, on 1,700 lines of corpus written blind
precisely so that would not happen."* So it goes through the same method.

This file starts red. `Purpose` and `UndeclaredPurpose` do not exist when it
lands and the import fails loudly. There is no `importorskip`, no
`try/except ImportError` and no `xfail` anywhere below — a skipped corpus is a
corpus that cannot fail.

---

## The contract this is written against, and nothing else

```
S1_LIST    (L3, L3)   inert
S1_DETAIL  (L4, L4)   inert — opening the pane is the declaration
S2_PROMPT  (L2, L2)   inert — the hard stop
S3_AGENT   (L2, L4)   lifts
S4_EGRESS  (L2, L4)   lifts
```

* `may_render(rung, surface, *, purpose=None)` — signature unchanged.
* `purpose=None` means no purpose was declared. **Not an error.**
* Anything that is neither `None` nor a `Purpose` member raises
  `UndeclaredPurpose`. **Loud on type, closed on data** — a purpose is a
  *call-site* property like a surface and can never arrive from a record, so an
  unreadable one is a programmer error. An unreadable *rung* still denies
  quietly, because I-11 says an unclassified value reaching runtime "reads `L5`
  and is not served".
* `purpose` stays accepted on all five surfaces and is inert on three. The
  proposal to drop it from `S1_DETAIL` was considered and **withdrawn**, because
  it would break the sweep that passes every purpose to every surface to prove
  nothing unlocks `L5` anywhere.
* A purpose is **per-call, never per-session**.
* The ceiling table **does not change** for a validly declared purpose.

## The four things this file is hunting

1. **The `str`-Enum hole.** `Purpose` is a `str` subclass, so
   `Purpose.DRAFTING == "drafting"` is `True` and — checked below rather than
   assumed — `hash(Purpose.DRAFTING) == hash("drafting")`, which means a `dict`
   or `set` keyed on members *finds the bare string*. Every natural spelling of
   a membership test (`purpose in _VALID`, `purpose == Purpose.EXPORT`,
   `_TABLE[purpose]`) is therefore passed by a caller who never imported the
   enum. `Surface` had exactly this bug in Phase 2 and it is the reason
   `rungs._read_surface` is an `isinstance` check rather than a lookup.
2. **The enum being decorative in the other direction.** A `_declared` that
   refuses *everything* — members included — satisfies every rejection test ever
   written and quietly turns S3 and S4 into surfaces on which `L4` can never be
   served. §4 asserts the lift, exhaustively, so that failure cannot pass.
3. **Transposition.** There are now three `str` enums in one three-argument
   call. Six ways to swap two of them, every one type-checks, and the one that
   matters most is a `Purpose` arriving where a `Rung` belongs.
4. **`UndeclaredPurpose` being a `TypeError`.** Which means a caller's bare
   `except TypeError` swallows it, and so does `except Exception`. §7 states
   that as a fact rather than wishing it away.
"""
from __future__ import annotations

import inspect
import itertools
import random
import re
import string

import pytest

from homestead.keep.rungs import (Classified, Disposition, Purpose, Rung,
                                  UnclassifiedField, UndeclaredPurpose,
                                  UnknownSurface, classify_schema, compose,
                                  decide, may_render, serve, serve_all)
from homestead.keep.surfaces import Surface

LADDER = (Rung.L1, Rung.L2, Rung.L3, Rung.L4, Rung.L5)
MEMBERS = tuple(Purpose)
VALID_PURPOSES = (None,) + MEMBERS

S1_LIST = Surface.S1_LIST
S1_DETAIL = Surface.S1_DETAIL
S2_PROMPT = Surface.S2_PROMPT

#: The S3 and S4 members are found by prefix, exactly as the Phase 2 corpus
#: finds them, because a member name is the implementation's call.
S3 = frozenset(s for s in Surface if s.name.startswith("S3_"))
S4 = frozenset(s for s in Surface if s.name.startswith("S4_"))

#: The two surfaces on which a purpose changes an answer, and the three on
#: which it cannot. Derived from the published ceiling table, transcribed once.
LIFTING_SURFACES = S3 | S4
INERT_SURFACES = frozenset({S1_LIST, S1_DETAIL, S2_PROMPT})

#: The published ceiling table, transcribed independently of the module. Every
#: cell is `(highest rung renderable with nothing declared, highest with a
#: purpose)`. This is the *only* place this file states the answers; every
#: expectation below is computed from it, so a disagreement is one edit to find.
_ORDER = {r: i for i, r in enumerate(LADDER, start=1)}
CEILINGS = {
    "S1_LIST": (Rung.L3, Rung.L3),
    "S1_DETAIL": (Rung.L4, Rung.L4),
    "S2_PROMPT": (Rung.L2, Rung.L2),
    "S3_": (Rung.L2, Rung.L4),
    "S4_": (Rung.L2, Rung.L4),
}


def expected(rung: Rung, surface: Surface, purpose) -> bool:
    """What the published table says, computed rather than typed in per cell.

    A twenty-five-cell table written out by hand is where a single wrong cell
    hides — that is BUG-5's shape and the reason `_CEILING` is ten numbers
    rather than twenty-five. This helper is the same discipline applied to the
    corpus's own expectations.
    """
    for key, (plain, with_purpose) in CEILINGS.items():
        if surface.name == key or surface.name.startswith(key):
            ceiling = with_purpose if purpose is not None else plain
            return _ORDER[rung] <= _ORDER[ceiling]
    raise AssertionError(f"{surface.name} has no row in the published table")


def _pid(value) -> str:
    if isinstance(value, Purpose):
        return value.name
    text = repr(value)
    return text if len(text) <= 28 else text[:25] + "…"


def verdict(rung, surface, purpose):
    """The answer, or the exception. Never a crash a test swallows into a pass."""
    try:
        return may_render(rung, surface, purpose=purpose)
    except Exception as exc:                    # noqa: BLE001 — that is the point
        return exc


# ═════════════════════════════════════════════════════════════════════════════
# 1 · The enum is what the contract says it is
# ═════════════════════════════════════════════════════════════════════════════

def test_the_six_members_are_exactly_the_six_that_were_ratified():
    """Membership is a **product decision**, ratified 2026-08-05, and it is
    pinned here so that a seventh member is an edit somebody has to make on
    purpose rather than a convenience somebody reaches for at midnight.

    Two entries from the free-text corpus's own "plausible purposes" list are
    deliberately absent, and the reason is itself the argument for closing the
    set: `"medical"` is a data **category** and `"operator opened the record"`
    is a **surface act**. Free text let all three kinds of thing into one slot,
    which is precisely why `"x"` bought the same lift as `"medical"`.
    """
    assert [p.name for p in Purpose] == [
        "DRAFTING", "FILING", "EXPORT",
        "SUBJECT_ACCESS", "REDISCLOSURE", "AGENT_RETRIEVAL",
    ]
    assert [p.value for p in Purpose] == [
        "drafting", "filing", "export",
        "subject_access", "redisclosure", "agent_retrieval",
    ]
    assert len({p.value for p in Purpose}) == 6, (
        "two members sharing a value are one member with two names, and any "
        "table keyed on it silently loses a row"
    )


def test_a_purpose_is_a_string_and_is_not_an_integer():
    """I-14's reason, applied to the third enum in the call. An `IntEnum` here
    would restore every arithmetic comparison the ladder forbids, and would do
    it in the one argument a caller controls."""
    for member in Purpose:
        assert isinstance(member, str)
        assert not isinstance(member, int), f"{member!r} is comparable to an int"
        with pytest.raises((ValueError, TypeError)):
            int(member)


def test_there_is_no_catch_all_purpose():
    """`ANY`, `ALL`, `OTHER`, `GENERAL`, `INTERNAL` or — worst — `OVERRIDE` is
    the escape hatch surviving the closure of the set. The whole point of the
    ruling is that a call site names an act somebody can be held to; a member
    that names no act is free text with a type annotation.

    `"internal processing"` is in the adversarial list of the Phase 2 corpus
    for the same reason: it is the phrase the model rejects for `S2`.
    """
    banned = re.compile(
        r"ANY|ALL|OTHER|MISC|DEFAULT|UNKNOWN|GENERAL|INTERNAL|OVERRIDE|FORCE|"
        r"ADMIN|ROOT|BYPASS|DEBUG|TEST|TEMP|LEGACY",
        re.IGNORECASE,
    )
    strays = [p.name for p in Purpose if banned.search(p.name)]
    assert not strays, f"catch-all purposes: {strays}"


def test_the_enum_refuses_every_spelling_that_is_not_a_member_value():
    """`Purpose("Drafting")` returning a member would mean one act has two
    spellings, and two spellings eventually mean two ledgers."""
    for bad in ("Drafting", "DRAFTING", "drafting ", " drafting", "draft",
                "medical", "operator opened the record", "", "   ", "*", "any",
                "L5", 0, 1, None, True, 3.0):
        with pytest.raises((ValueError, KeyError, TypeError)):
            Purpose(bad)


def test_the_contract_names_are_importable_and_exported():
    """A type a caller cannot name is a type a caller cannot catch, and
    `UndeclaredPurpose` is the one they have to catch to write a call site that
    fails well."""
    import homestead.keep.rungs as rungs_mod

    for name in ("Purpose", "UndeclaredPurpose", "may_render"):
        assert hasattr(rungs_mod, name), f"homestead.keep.rungs has no {name}"
    exported = getattr(rungs_mod, "__all__", None)
    assert exported is not None
    assert "Purpose" in exported and "UndeclaredPurpose" in exported, (
        f"__all__ is {sorted(exported)} — a published contract that is not "
        "exported is a contract callers import by accident"
    )


def test_may_render_still_has_the_published_signature():
    """The contract says the signature is unchanged. A `purposes=` plural, a
    positional third argument, or a required `purpose` would each break every
    existing call site, and a required one would break the detail pane where
    the whole ruling says there is no ceremony tax."""
    params = inspect.signature(may_render).parameters
    assert list(params) == ["rung", "surface", "purpose"]
    assert params["purpose"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["purpose"].default is None
    assert may_render(Rung.L1, S1_LIST) is True, (
        "purpose is optional — omitting it means nobody declared one"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 2 · No string is a purpose — including the member values
# ═════════════════════════════════════════════════════════════════════════════
# This is the section the whole change stands on. If a bare string is accepted
# anywhere, the enum is a type annotation over free text and `"x"` still buys
# what `"medical"` bought.

def test_the_str_enum_hole_is_real_and_this_is_what_it_looks_like():
    """The hazard, demonstrated on the enum itself before it is hunted in the
    decision function — so that a later reader knows this is not paranoia.

    Every one of these is `True`, which is what makes each natural spelling of
    a membership test wrong. **This test asserts the language's behaviour, not
    the module's**; it exists so the tests below cannot be dismissed as
    theoretical.
    """
    assert Purpose.DRAFTING == "drafting"
    assert hash(Purpose.DRAFTING) == hash("drafting")
    assert {Purpose.DRAFTING: 1}["drafting"] == 1
    assert "drafting" in {Purpose.DRAFTING}
    assert "drafting" in [p for p in Purpose]
    assert Purpose.DRAFTING in ("drafting", "filing")


@pytest.mark.parametrize("member", MEMBERS, ids=[p.name for p in MEMBERS])
def test_the_bare_value_of_a_member_is_not_a_purpose(member):
    """**The likeliest defect in the whole change.**

    `"drafting"` compares equal to `Purpose.DRAFTING`, hashes the same, and is
    found by `in` against any container of members. So a caller who never
    imported the enum can pass the string and — on every implementation that
    checks membership rather than type — get the lift. That is the enum being
    free text wearing a type, which is the thing it was ratified to stop.

    Asserted on every rung and every surface, because a check that is right on
    the inert surfaces and wrong on the lifting ones is the same defect with a
    smaller blast radius.
    """
    for surface in Surface:
        for rung in LADDER:
            with pytest.raises(UndeclaredPurpose):
                may_render(rung, surface, purpose=member.value)


@pytest.mark.parametrize("member", MEMBERS, ids=[p.name for p in MEMBERS])
def test_the_name_of_a_member_is_not_a_purpose_either(member):
    """`Purpose["DRAFTING"]` is the other way into the enum, so `"DRAFTING"` is
    the other spelling a caller might reach for."""
    for surface in Surface:
        with pytest.raises(UndeclaredPurpose):
            may_render(Rung.L4, surface, purpose=member.name)


def test_no_string_at_all_is_a_purpose_and_this_does_not_read_from_a_list():
    """The hole a hand-written table of bad strings always leaves, closed by
    sampling rather than by enumeration.

    The sighted half of Phase 2 found by injection that a `may_render` which
    returned `True` for the single string `"court order"` passed every other
    test in its file, because every other test iterated a list somebody typed.
    An exhaustive-*looking* test that is exhaustive only over a hand-written
    list is the exact failure mode both Phase 0 audits found. The seed is fixed
    so a failure is reproducible.
    """
    rng = random.Random(20260805)
    sampled = [
        "".join(rng.choice(string.printable) for _ in range(rng.randint(1, 32)))
        for _ in range(400)
    ]
    plausible = ["court order", "the operator asked", "because I said so",
                 "urgent", "case prep", "discovery", "appeal", "x", "purpose",
                 "Drafting", "DRAFTING", " drafting", "drafting ", "drafting\n",
                 "drafting;filing", "drafting|export", "drafting\x00filing"]
    for purpose in sampled + plausible:
        with pytest.raises(UndeclaredPurpose):
            may_render(Rung.L4, S1_DETAIL, purpose=purpose)
        with pytest.raises(UndeclaredPurpose):
            may_render(Rung.L1, S1_LIST, purpose=purpose)


def test_a_container_of_members_is_not_a_purpose():
    """The other reading of "declare a purpose" — declare several, and let the
    most permissive one win. There is no such call: the argument is one act, and
    a list of acts is a call site that has not decided which one it is doing."""
    for shape in ([Purpose.DRAFTING], (Purpose.DRAFTING,), {Purpose.DRAFTING},
                  frozenset({Purpose.EXPORT}), {"purpose": Purpose.EXPORT},
                  [Purpose.DRAFTING, Purpose.FILING], iter([Purpose.EXPORT])):
        for surface in LIFTING_SURFACES:
            with pytest.raises(UndeclaredPurpose):
                may_render(Rung.L4, surface, purpose=shape)


def test_a_subclass_of_str_that_claims_to_be_a_member_is_not_one():
    """The shape that walks through an equality-based guard. `_AlwaysEqual` did
    this to the free-text corpus; here it is the same idea narrowed to the one
    comparison the enum invites."""

    class Claimant(str):
        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

        def __hash__(self):
            return hash("drafting")

    for surface in LIFTING_SURFACES:
        assert verdict(Rung.L4, surface, Claimant("drafting")) is not True
        with pytest.raises(UndeclaredPurpose):
            may_render(Rung.L4, surface, purpose=Claimant("drafting"))


def test_an_enum_of_the_same_shape_from_somewhere_else_is_not_a_purpose():
    """A second `Purpose` — a copy pasted into a caller, a stale import from a
    module that got split, a test double — is a different type with the same
    members and the same values, and `isinstance` is the only check that can
    tell them apart. This is the test that distinguishes a real type check from
    a value check dressed as one."""
    from enum import Enum

    class Purpose(str, Enum):                   # noqa: F811 — deliberate shadow
        DRAFTING = "drafting"
        FILING = "filing"
        EXPORT = "export"
        SUBJECT_ACCESS = "subject_access"
        REDISCLOSURE = "redisclosure"
        AGENT_RETRIEVAL = "agent_retrieval"

    for member in Purpose:
        for surface in Surface:
            with pytest.raises(UndeclaredPurpose):
                may_render(Rung.L4, surface, purpose=member)


# ═════════════════════════════════════════════════════════════════════════════
# 3 · No `Purpose` member unlocks `L5`, anywhere — exhaustively
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("purpose", VALID_PURPOSES, ids=[_pid(p) for p in VALID_PURPOSES])
@pytest.mark.parametrize("surface", list(Surface), ids=[s.name for s in Surface])
def test_no_member_serves_l5_on_any_surface(surface, purpose):
    """I-13, restated for a world where the purposes are countable — so this is
    no longer a sample of the strings someone thought of, it is **all of them**.

    `L5` includes any fact the operator marked `do_not_use` and why, the content
    of a sealed record, export-ledger key material, substance-use treatment
    records under 42 CFR Part 2, and anything under a protective order. The one
    that stings is `REDISCLOSURE`: 42 CFR Part 2 *permits* a re-disclosure, and
    permitting an act is not lowering a rung. A member named after a statute is
    exactly the member somebody will expect to be an exception.
    """
    assert may_render(Rung.L5, surface, purpose=purpose) is False
    assert decide(Rung.L5, surface, purpose=purpose) is Disposition.DENY


def test_l5_is_refused_structurally_rather_than_member_by_member():
    """The property behind the sweep: **the set of surfaces `L5` reaches is
    empty for every purpose, and it is the same empty set every time.**

    Stated this way because "no member unlocks `L5`" could be satisfied by six
    special cases, and six special cases is five chances to add a seventh member
    that misses one.
    """
    reach = {
        purpose: frozenset(s for s in Surface
                           if may_render(Rung.L5, s, purpose=purpose) is True)
        for purpose in VALID_PURPOSES
    }
    assert set(reach.values()) == {frozenset()}, reach


@pytest.mark.parametrize("purpose", VALID_PURPOSES, ids=[_pid(p) for p in VALID_PURPOSES])
def test_the_whole_chokepoint_family_refuses_l5_not_just_may_render(purpose):
    """`may_render` is not the only door that takes a purpose. `decide`,
    `serve` and `serve_all` all pass one through, and a gate with one guarded
    door and three unguarded ones is I-16's complaint about this module already
    — *"a gate wired to one entry point is not a gate."*

    A `DENY` carries no trace either: at `L5` the existence of a refusal is
    itself the thing that must not be rendered.
    """
    sealed = Classified(Rung.L5, "the allegation under a protective order")
    for surface in Surface:
        result = serve(sealed, surface, purpose=purpose)
        assert result.disposition is Disposition.DENY
        assert result.value is None
        assert "protective order" not in repr(result)
        assert serve_all([sealed, sealed], surface, purpose=purpose) == []


def test_the_chokepoint_family_refuses_a_bad_purpose_at_every_door():
    """The same reasoning pointed at the type check rather than at `L5`.

    If `decide` or `serve` accepts `"drafting"` where `may_render` refuses it,
    then the enum is enforced on the door nobody uses. Asserted in the split
    form this project uses everywhere: the safety half unconditionally, the
    loudness half separately.
    """
    item = Classified(Rung.L4, "12% whole-person impairment",
                      derived="a medical records response is due")
    for surface in LIFTING_SURFACES:
        for bad in ("drafting", "override", "", "medical", Rung.L4, 1):
            assert verdict(Rung.L4, surface, bad) is not True
            with pytest.raises(UndeclaredPurpose):
                decide(Rung.L4, surface, purpose=bad)
            with pytest.raises(UndeclaredPurpose):
                serve(item, surface, purpose=bad)
            with pytest.raises(UndeclaredPurpose):
                serve_all([item], surface, purpose=bad)


# ═════════════════════════════════════════════════════════════════════════════
# 4 · Inert on three surfaces, lifting on two — and both halves matter
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("purpose", MEMBERS, ids=[p.name for p in MEMBERS])
@pytest.mark.parametrize("surface", sorted(INERT_SURFACES, key=lambda s: s.name),
                         ids=lambda s: s.name)
def test_a_purpose_changes_no_answer_on_an_inert_surface(surface, purpose):
    """The three surfaces whose ceilings are equal with and without a purpose.

    `S1_LIST` is inert because the threat is ambient exposure — someone walking
    past thirty seconds later — and a declaration does not change who is
    standing behind the operator (I-35). `S1_DETAIL` is inert because *opening
    the pane is the declaration*, decided 2026-08-04 by widget rather than by
    dialog, so a person in crisis pays no ceremony tax. `S2_PROMPT` is inert
    because of I-13's first hard stop: if a local model needs the diagnosis to
    do its job, that is a signal the job is wrong.

    Inert means **identical**, rung by rung — not "mostly the same", and not
    "the same except at `L4`".
    """
    for rung in LADDER:
        assert (
            may_render(rung, surface, purpose=purpose)
            is may_render(rung, surface, purpose=None)
        ), (
            f"{purpose.name} changed the answer for {rung.name} on "
            f"{surface.name}, where the ceiling is the same with and without "
            "a purpose"
        )


@pytest.mark.parametrize("purpose", MEMBERS, ids=[p.name for p in MEMBERS])
@pytest.mark.parametrize("surface", sorted(LIFTING_SURFACES, key=lambda s: s.name),
                         ids=lambda s: s.name)
def test_every_member_lifts_the_ceiling_on_s3_and_s4(surface, purpose):
    """**The test that stops the enum being decorative in the other
    direction.**

    A `_declared` that refuses everything — members included — passes every
    rejection test in this file and in the converted corpus, and quietly makes
    `L4` unservable on S3 and S4 for the rest of the project's life. Nobody
    would notice for months, because the symptom is a pane that renders less
    than it should, and §2's evidence would all still be green.

    So: no member is more of a declaration than another, and every one of them
    is one. `"x"` bought the same lift as `"medical"` before; the fix is that
    `"x"` buys nothing, **not** that `EXPORT` buys less than `FILING`.
    """
    assert may_render(Rung.L4, surface, purpose=purpose) is True
    assert may_render(Rung.L3, surface, purpose=purpose) is True
    assert may_render(Rung.L4, surface, purpose=None) is False
    assert may_render(Rung.L3, surface, purpose=None) is False
    assert may_render(Rung.L5, surface, purpose=purpose) is False


def test_all_six_members_are_interchangeable_at_the_decision_function():
    """The corollary, stated as a property over the whole table.

    Every member produces the *same* answer as every other member, on every
    rung and every surface. The decision turns on **whether a purpose was
    declared**, never on which one — that is the free-text rule surviving the
    closure of the set, and it is what keeps a magic value unrepresentable. The
    enum exists so that the declaration is auditable and ledgerable, not so that
    the code can start reading it.
    """
    answers = {
        purpose: tuple(may_render(r, s, purpose=purpose)
                       for r in LADDER for s in Surface)
        for purpose in MEMBERS
    }
    assert len(set(answers.values())) == 1, (
        "two members get different answers, so the code is reading the purpose "
        f"rather than counting it: { {p.name: a for p, a in answers.items()} }"
    )


@pytest.mark.parametrize("purpose", VALID_PURPOSES, ids=[_pid(p) for p in VALID_PURPOSES])
@pytest.mark.parametrize("surface", list(Surface), ids=[s.name for s in Surface])
@pytest.mark.parametrize("rung", LADDER, ids=[r.name for r in LADDER])
def test_the_ceiling_table_did_not_move(rung, surface, purpose):
    """Every cell of the published table, against an independent transcription.

    The ruling says the table does not change for a validly declared purpose,
    and this is that sentence made checkable rather than believed. `CEILINGS` at
    the top of this file is the corpus's own reading of the contract; if it and
    the module disagree, one of the two transcriptions is wrong and the
    disagreement is the finding — which is what this method is for.
    """
    got = may_render(rung, surface, purpose=purpose)
    assert got is expected(rung, surface, purpose), (
        f"may_render({rung.name}, {surface.name}, purpose={_pid(purpose)}) is "
        f"{got}; the published ceiling table says {expected(rung, surface, purpose)}"
    )


def test_the_parameter_is_still_accepted_on_all_five_surfaces():
    """The proposal to remove `purpose` from `S1_DETAIL` was **considered and
    withdrawn**, and this is the reason, held as a test so it is not re-proposed
    by someone who only sees the inertness.

    The corpus's most valuable sweep passes every purpose to every surface to
    prove that nothing unlocks `L5` anywhere. A signature that refuses the
    argument on three of five surfaces destroys that sweep to prevent a lesser
    error — an inert argument passed hopefully — which is a bad trade. So the
    argument is accepted everywhere and inert on three, and the enum plus the
    inertness test carry the weight instead.
    """
    for surface in Surface:
        for purpose in VALID_PURPOSES:
            assert may_render(Rung.L1, surface, purpose=purpose) is True
            assert isinstance(decide(Rung.L1, surface, purpose=purpose),
                              Disposition)


# ═════════════════════════════════════════════════════════════════════════════
# 5 · Per-call, never per-session
# ═════════════════════════════════════════════════════════════════════════════
# Ratified the same day: "a purpose is per-call, never per-session." It was
# already true by accident of statelessness rather than by decision, which is
# exactly the gap the ruling exists to close — so it gets a test, and a later
# phase adding a session cache has to argue with it rather than route around it.

def test_a_purpose_declared_in_one_call_does_not_leak_into_the_next():
    """The failure predicted when the enum was ratified: *"every call site
    hardcodes one purpose within a month, after which `L4` on S3/S4 is unlocked
    unconditionally and the ceremony is decorative."* The memoised version of
    that is a purpose that sticks.

    Interleaved deliberately — declared, then not, then declared — because a
    cache keyed on `(rung, surface)` and forgetting the purpose answers the
    *previous* question, which is BUG-7's shape: the AI cache fingerprint
    ignored every substantive input and re-served a stale answer for seven days.
    """
    for surface in LIFTING_SURFACES:
        for member in MEMBERS:
            assert may_render(Rung.L4, surface, purpose=member) is True
            assert may_render(Rung.L4, surface, purpose=None) is False, (
                f"a {member.name} declared on the previous call is still in "
                f"force on {surface.name}"
            )
            assert may_render(Rung.L4, surface) is False, (
                "and it survives omitting the argument entirely"
            )


def test_the_same_call_twice_gives_the_same_answer_in_any_order():
    """Every cell, three times, interleaved differently each pass. A memoised
    table keyed on the wrong tuple answers the previous question, and `None`
    versus a member is precisely the component such a key drops."""
    cells = [(r, s, p) for r in LADDER for s in Surface for p in VALID_PURPOSES]
    first = {c: may_render(c[0], c[1], purpose=c[2]) for c in cells}
    for order in (list(reversed(cells)),
                  sorted(cells, key=lambda c: c[1].name),
                  sorted(cells, key=lambda c: _pid(c[2]))):
        for cell in order:
            assert may_render(cell[0], cell[1], purpose=cell[2]) is first[cell], cell


def test_a_refused_purpose_does_not_poison_the_next_call():
    """The other direction, and the one a `try/except` around a call site
    produces in practice: the exception is caught, the loop continues, and the
    next call has to be answered as if nothing happened. A gate that latches
    into a refusing state after a bad argument is an outage with a plausible
    cause, and it is the shape a person in crisis experiences as "the app
    stopped showing my hearing date"."""
    for bad in ("drafting", "override", "", 1, object(), Rung.L1):
        with pytest.raises(UndeclaredPurpose):
            may_render(Rung.L4, next(iter(S3)), purpose=bad)
        assert may_render(Rung.L1, S1_LIST, purpose=None) is True
        assert may_render(Rung.L4, S1_DETAIL, purpose=None) is True
        for surface in LIFTING_SURFACES:
            assert may_render(Rung.L4, surface, purpose=Purpose.EXPORT) is True


def test_nothing_in_the_module_remembers_a_purpose():
    """Statelessness where a signature cannot state it. A module-level mutable
    holding the last purpose is how "per-call" becomes "per-session" without
    anybody deciding to change it, and it is invisible in every behavioural test
    that does not interleave."""
    import homestead.keep.rungs as rungs_mod

    for member in MEMBERS:
        may_render(Rung.L4, next(iter(S4)), purpose=member)

    suspicious = re.compile(r"last|current|active|session|cache|state|memo|"
                            r"recent|pending|declared_", re.IGNORECASE)
    offenders = [
        name for name, obj in vars(rungs_mod).items()
        if suspicious.search(name) and isinstance(obj, (list, dict, set))
    ]
    assert not offenders, (
        f"module-level mutable state named {offenders} — a purpose that "
        "outlives its call is a session, and the ruling says per-call"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 6 · Transposition — three `str` enums in one three-argument call
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("purpose", MEMBERS, ids=[p.name for p in MEMBERS])
def test_a_purpose_is_not_usable_as_a_rung(purpose):
    """`Rung` is a `str` subclass and so is `Purpose`, so
    `may_render(Purpose.EXPORT, Surface.S4_EGRESS, purpose=None)` type-checks
    and `isinstance(rung, str)` cannot tell them apart. One transposed argument.

    It reads `L5` and is not served — the *rung* half of "loud on type, closed
    on data", because an unreadable rung is exactly the condition I-11
    legislates for. What must never happen is that it reads as `L1`: a value
    that fails to parse as a rung and defaults to the least-restricted one is
    I-11's catastrophe, and `"export"` sorting to something permissive is how it
    would arrive.
    """
    for surface in Surface:
        assert may_render(purpose, surface, purpose=None) is False
        assert decide(purpose, surface, purpose=None) is Disposition.DENY
        assert may_render(purpose, surface, purpose=Purpose.EXPORT) is False


@pytest.mark.parametrize("purpose", MEMBERS, ids=[p.name for p in MEMBERS])
def test_a_purpose_cannot_be_classified_as_a_rung_upstream_either(purpose):
    """The other half of the rung asymmetry, and the reason the quiet denial
    above is safe: these values cannot reach `may_render` through any classified
    path, because construction and classification both raise on them.

    That pairing is the standing argument in this repo for `may_render` denying
    quietly rather than refusing loudly — *loud on the way in, closed at the
    point of render* — and it is a load-bearing claim with a test rather than a
    load-bearing claim in a docstring.
    """
    with pytest.raises(UnclassifiedField):
        Classified(purpose, "text")
    with pytest.raises(UnclassifiedField):
        classify_schema({"a_field": purpose})


@pytest.mark.parametrize("purpose", MEMBERS, ids=[p.name for p in MEMBERS])
def test_a_purpose_is_not_usable_as_a_surface(purpose):
    """The third transposition. A surface is code, not data — the call site is a
    render path and it knows which one it is — so this is loud, and it is loud
    the same way a bare string is."""
    for rung in LADDER:
        with pytest.raises(UnknownSurface):
            may_render(rung, purpose, purpose=None)


def test_a_purpose_does_not_compose_as_a_rung():
    """`compose` is `max` over rungs, and it is the function every projection
    routes through. A `Purpose` reaching it is an unclassified input, and an
    unclassified input reads `L5` — never `L1`, which is the direction every
    convenience default goes."""
    for member in MEMBERS:
        try:
            got = compose(member)
        except Exception:                       # noqa: BLE001 — refusal is fine
            continue
        assert got is Rung.L5, f"compose({member!r}) answered {got!r}"
    for member in MEMBERS:
        try:
            got = compose(Rung.L1, member, Rung.L2)
        except Exception:                       # noqa: BLE001
            continue
        assert got is Rung.L5, (
            f"compose(L1, {member!r}, L2) answered {got!r} — the unreadable "
            "input was dropped rather than failing closed"
        )


def test_every_pairwise_transposition_of_the_three_enums_fails_closed():
    """All of them at once, so none is left to a reader's imagination.

    Three enums, three slots, and every wrong arrangement type-checks. The one
    unacceptable answer is `True`; whether a given arrangement raises or denies
    depends on which slot went wrong, and both are asserted where they are
    known rather than folded together here.
    """
    values = {"rung": Rung.L1, "surface": S1_DETAIL, "purpose": Purpose.EXPORT}
    slots = ("rung", "surface", "purpose")
    for a, b in itertools.permutations(slots, 2):
        arrangement = dict(values)
        arrangement[a], arrangement[b] = values[b], values[a]
        assert verdict(arrangement["rung"], arrangement["surface"],
                       arrangement["purpose"]) is not True, arrangement


# ═════════════════════════════════════════════════════════════════════════════
# 7 · `UndeclaredPurpose` is a `TypeError`, and that has consequences
# ═════════════════════════════════════════════════════════════════════════════

def test_undeclared_purpose_is_the_type_the_contract_names():
    """A `TypeError`, because that is what it is: a purpose is a call-site
    property and an unreadable one is a programmer error, not data. `ValueError`
    would put it in the family a caller catches when *parsing input*, which is
    the wrong mental model for an argument that can never come from a record."""
    assert issubclass(UndeclaredPurpose, TypeError)
    assert UndeclaredPurpose is not TypeError, (
        "a caller must be able to catch this one specifically; if it *is* "
        "TypeError there is no narrower except clause to write"
    )
    assert not issubclass(UndeclaredPurpose, (UnknownSurface, UnclassifiedField))
    assert not issubclass(UnknownSurface, UndeclaredPurpose), (
        "a caller catching one must not silently catch the other — a bad "
        "surface and a bad purpose are different bugs with different fixes"
    )


def test_a_bare_except_typeerror_swallows_it_and_this_is_the_hazard():
    """**Stated as a fact rather than wished away, because it is a fact.**

    `UndeclaredPurpose` is a `TypeError`, so `except TypeError` catches it, and
    so does `except Exception`. A Phase 4 render path written defensively —
    `try: ... except TypeError: return None` — turns "this call site declared a
    purpose that does not exist" into a blank pane with no cause, and an empty
    pane with no cause gets fixed by deleting the check. That is the exact
    reasoning `UnknownSurface` is documented with, and it applies here word for
    word.

    Two things follow, and both are asserted:

    * the exception is **distinguishable** — its own class, so a caller who
      knows about it can re-raise;
    * and the swallowing is **real**, so the mitigation is a chokepoint rule in
      Phase 4 (I-16) rather than anything this module can do. Writing that down
      here is what stops it being discovered at the first blank pane.
    """
    def defensive_render():
        try:
            return may_render(Rung.L4, next(iter(S3)), purpose="drafting")
        except TypeError:
            return None

    assert defensive_render() is None, (
        "if this stops being true the exception left the TypeError family, "
        "which is a contract change and should be a deliberate one"
    )

    def careful_render():
        try:
            return may_render(Rung.L4, next(iter(S3)), purpose="drafting")
        except UndeclaredPurpose:
            raise
        except TypeError:
            return None

    with pytest.raises(UndeclaredPurpose):
        careful_render()


def test_a_bad_purpose_is_loud_even_when_the_rung_is_also_bad():
    """**The corpus's reading of the contract, and a place the two hands may
    honestly disagree — flagged in the report rather than assumed.**

    The rule as published is unconditional: *a `purpose` that is neither `None`
    nor a `Purpose` member raises `UndeclaredPurpose`.* It does not say "unless
    the rung was unreadable, in which case deny quietly first."

    The order matters, and it matters in the direction that costs something. An
    unreadable rung denies — correctly, I-11 — so a decision function that reads
    the rung first and returns `False` never reaches the purpose, and a call
    site that passed `"drafitng"` gets a blank pane instead of an exception. Two
    bugs, one symptom, and the loud one is hidden by the quiet one. Loud on
    type, closed on data reads more naturally the other way round: check the
    arguments that are code, then decide about the argument that is data.

    Asserted with an unreadable rung *and* with an integer one, because `3` is
    I-14's cross-scale confusion and is exactly what a caller passes on the day
    they also mistype a purpose.
    """
    for surface in Surface:
        for bad_rung in (None, "unknown", 3, object()):
            with pytest.raises(UndeclaredPurpose):
                may_render(bad_rung, surface, purpose="drafting")
    # And the quiet denial is intact for the case where only the rung is bad.
    for bad_rung in (None, "unknown", 3, object()):
        assert may_render(bad_rung, S1_DETAIL, purpose=None) is False
        assert may_render(bad_rung, S1_DETAIL, purpose=Purpose.EXPORT) is False


def test_the_refusal_says_what_would_have_been_acceptable():
    """A refusal that does not name the closed set is a refusal the developer
    works around — most likely by passing `None`, which is the one wrong answer
    that is not an error. `chronology_builder`'s `gaps` pattern (I-8) is the
    house standard: the thing that could not be handled is named, not swallowed.

    Deliberately weak about *how* it says so: the member names, the values, or
    the type name all count. This is a legibility claim, not a safety claim, and
    it is written not to be able to masquerade as one.
    """
    with pytest.raises(UndeclaredPurpose) as caught:
        may_render(Rung.L4, next(iter(S4)), purpose="medical")
    message = str(caught.value)
    named = sum(
        1 for p in Purpose if p.name in message or p.value in message
    )
    assert named >= 2 or "Purpose" in message, (
        f"the refusal reads {message!r} and points at nothing a caller could "
        "pass instead"
    )
    assert "medical" in message, "the refusal does not say what was rejected"


# ═════════════════════════════════════════════════════════════════════════════
# 8 · This file's own guards
# ═════════════════════════════════════════════════════════════════════════════

def test_this_corpus_asserts_permission_as_well_as_refusal():
    """The self-check that matters most, inherited from the Phase 2 corpus.

    A file made only of refusals is passed by an implementation that refuses
    everything, and `_declared` refusing every member is a live way to pass §§2
    and 3 completely. So: on the two lifting surfaces something must be served
    *because* a purpose was declared, and served *only* because of it.
    """
    lifted = 0
    for surface in LIFTING_SURFACES:
        for member in MEMBERS:
            if (may_render(Rung.L4, surface, purpose=member) is True
                    and may_render(Rung.L4, surface, purpose=None) is False):
                lifted += 1
    assert lifted == len(LIFTING_SURFACES) * len(MEMBERS), (
        f"only {lifted} of {len(LIFTING_SURFACES) * len(MEMBERS)} "
        "(surface, member) pairs lift anything — a purpose that never lifts is "
        "an enum nobody needed"
    )
    for surface in Surface:
        assert may_render(Rung.L1, surface, purpose=None) is True
        assert may_render(Rung.L5, surface, purpose=Purpose.EXPORT) is False


def test_this_corpus_has_not_been_hollowed_out():
    """Table sizes, asserted, because a table trimmed to two rows is the
    cheapest way for a scan to stop scanning — which is what Phase 0's audit
    found twice."""
    assert len(Purpose) == 6
    assert len(VALID_PURPOSES) == 7
    assert len(LADDER) == 5
    assert len(Surface) == 5
    assert len(INERT_SURFACES) == 3
    assert len(LIFTING_SURFACES) == 2
    assert INERT_SURFACES | LIFTING_SURFACES == frozenset(Surface), (
        "every surface is either inert or lifting; a sixth surface with no "
        "row in CEILINGS is a render path this file never scored"
    )
    assert not INERT_SURFACES & LIFTING_SURFACES
    assert set(CEILINGS) >= {"S1_LIST", "S1_DETAIL", "S2_PROMPT", "S3_", "S4_"}
    for _, with_purpose in CEILINGS.values():
        assert with_purpose is not Rung.L5, (
            "the corpus's own transcription must not contain an L5 ceiling — "
            "I-13, and a wrong expectation here would license a wrong answer"
        )
