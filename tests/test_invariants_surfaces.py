"""I-11 … I-15 and I-35 — the rungs, the surfaces, and the decision between them.

Promoted out of `test_invariants_pending.py` when `homestead.keep.surfaces`
landed, which is what `test_pending_liveness` is for: the moment the module
existed the pending file failed by name, and would not go green again until the
four Phase 2 tests were promoted out, unmarked.

**One of those four was mis-attributed and the correction is deliberate.**
`test_i11_unclassified_field_is_a_build_failure` was marked
`@pending("homestead.keep.registry", "classify_schema is Phase 2")` while
importing `classify_schema` from `homestead.keep.rungs`. Its real dependency
was `rungs.classify_schema`, and `registry` is Phase 3. The cause is a limit in
R-6 rather than a slip — the liveness guard asserts that a *module* does not
exist, `rungs` has existed since Phase 0, and there was therefore no honest way
to name the dependency. That is written up where it will be read, in the
`UNBUILT` comment in `test_invariants_pending.py`.

The four promoted tests keep their original bodies and docstrings. Everything
after them is the rest of the phase.

**On what these tests are worth.** Written by the implementation hand, which is
the hand that has been wrong before: Phase 0 failed both its audits because the
same author wrote the code and the test, so the test learned the code's shape.
The independent corpus is `tests/test_surfaces_corpus.py`, written concurrently
by an agent that did not read this file or the implementation. Where the two
disagree, the disagreement is the finding.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import itertools
import pkgutil
import random
import string
import subprocess
import sys
import types
from pathlib import Path
from typing import Mapping

import pytest

from homestead.keep import rungs as rungs_mod
from homestead.keep import surfaces as surfaces_mod
from homestead.keep.rungs import (
    AmbientRow,
    Classified,
    Disposition,
    Rung,
    UnclassifiedField,
    UnknownSurface,
    ambient_rows,
    classify_schema,
    compose,
    context_rung,
    decide,
    may_render,
    serve,
    serve_all,
)
from homestead.keep.surfaces import FACTS, Surface

ROOT = Path(__file__).resolve().parent.parent

#: Every shape a caller might put in the `purpose` slot, including the ones that
#: are the *absence* of a purpose wearing its clothes.
PURPOSES = (
    None, "", "   ", "medical", "anything", "drafting", "because I said so",
    True, False, 0, 1, ["medical"], {"purpose": "medical"}, object(),
)

#: Values that are not a rung. Every one of them must read `L5`.
NOT_RUNGS = (None, "", "   ", "L", "L0", "L6", "l3", "3", 3, 4, 5, True, False,
             0.0, [Rung.L3], {"rung": "L3"}, object())


# ── promoted from test_invariants_pending.py ─────────────────────────────────

def test_i11_unclassified_field_is_a_build_failure():
    from homestead.keep.rungs import classify_schema

    with pytest.raises(Exception):
        classify_schema({"body": None})  # no rung declared


def test_i13_l5_has_no_override_on_any_surface():
    """BUG-5: `_fact_blocked` tested only `needs_source`, so `do_not_use` —
    the *stronger* rejection — still flowed into the drafting packet and the
    model prompt, while the screen said 'Excluded from drafting'."""
    from homestead.keep.rungs import Rung, may_render
    from homestead.keep.surfaces import Surface

    for surface in Surface:
        assert may_render(Rung.L5, surface, purpose="anything") is False


def test_i35_the_list_pane_cannot_render_an_l4_payload():
    from homestead.keep.rungs import Rung, may_render
    from homestead.keep.surfaces import Surface

    assert may_render(Rung.L4, Surface.S1_LIST, purpose=None) is False
    assert may_render(Rung.L4, Surface.S1_LIST, purpose="medical") is False
    assert may_render(Rung.L4, Surface.S1_DETAIL, purpose=None) is True


def test_i13_l4_never_reaches_a_model_prompt():
    from homestead.keep.rungs import Rung, may_render
    from homestead.keep.surfaces import Surface

    assert may_render(Rung.L4, Surface.S2_PROMPT, purpose="medical") is False


# ── the surfaces exist, all of them, once ────────────────────────────────────

def test_the_four_surfaces_are_five_members_because_s1_has_two_panes():
    """Four surfaces; S1 is two panes with different powers, so five members.

    The split is not cosmetic — it is the whole of I-35. A single `S1` member
    would have to carry one ceiling, and whichever one it carried would be
    wrong for the other pane.
    """
    assert {s.name for s in Surface} == {
        "S1_LIST", "S1_DETAIL", "S2_PROMPT", "S3_AGENT", "S4_EGRESS"
    }
    assert all(isinstance(s.value, str) for s in Surface)
    assert sum(1 for s in Surface if FACTS[s].ambient) == 1, (
        "the list pane is the only ambient surface at Phase 2; the cover (I-31) "
        "is the second and it is Phase 4"
    )


def test_every_surface_has_facts_and_a_ceiling():
    """BUG-6's shape: three matter types enumerated by hand in three places.

    A surface added to the enum and left out of either table would fail open on
    the day something rendered to it, so both tables are complete or the module
    does not import.
    """
    assert set(FACTS) == set(Surface)
    assert set(rungs_mod._CEILING) == set(Surface)


def test_an_unknown_surface_raises_rather_than_denying():
    """The asymmetry with an unknown *rung*, which denies, is deliberate.

    A rung is data and can legitimately be missing, so absence fails closed. A
    surface is code — the call site is a render path and knows which one it is.
    A mistyped surface that quietly returned `False` would draw an empty pane
    with no cause, and an empty pane with no cause gets fixed by deleting the
    check.
    """
    for bad in ("S1_LIST", "S1", "s1_list", "", None, 1, Rung.L3, object()):
        with pytest.raises(UnknownSurface):
            may_render(Rung.L1, bad)
        with pytest.raises(UnknownSurface):
            decide(Rung.L1, bad)
        with pytest.raises(UnknownSurface):
            serve(Classified(Rung.L1, "x"), bad)
    assert issubclass(UnknownSurface, TypeError)
    assert may_render(Rung.L1, Surface.S1_LIST) is True


# ── I-11 · absence fails closed, twice over ──────────────────────────────────

def test_i11_classify_schema_refuses_every_shape_of_missing_rung():
    for declaration in (None, "", "   ", "L0", "L6", "l3", "unknown", [], (),
                        set(), object(), {}, {"why": "it identifies"}):
        with pytest.raises(UnclassifiedField):
            classify_schema({"body": declaration})


def test_i11_an_integer_rung_is_refused_and_told_why():
    """I-14 arriving as data rather than as code.

    `3` is not a typo for `L3`; it is the cross-scale confusion itself, and the
    refusal says so rather than saying 'invalid'.
    """
    for declaration in (1, 3, 4, 5, True, False):
        with pytest.raises(UnclassifiedField) as exc:
            classify_schema({"body": declaration})
        assert "I-14" in str(exc.value) or "string" in str(exc.value)


def test_i11_every_unclassified_field_is_named_not_just_the_first():
    """A build failure that names one of four unclassified fields costs four
    build cycles to fix, and the fourth one gets classified in a hurry."""
    with pytest.raises(UnclassifiedField) as exc:
        classify_schema({
            "case_number": Rung.L3,
            "body": None,
            "diagnosis": 4,
            "school": "L6",
        })
    message = str(exc.value)
    for name in ("body", "diagnosis", "school"):
        assert repr(name) in message, message
    assert "case_number" not in message


def test_i11_an_empty_schema_is_refused():
    """A classifier that ran and found nothing is absence, and absence fails
    closed. A schema object with no fields is far more often a definition that
    failed to pick anything up than a record with nothing in it."""
    with pytest.raises(UnclassifiedField):
        classify_schema({})


def test_i11_a_schema_is_a_mapping_of_names_to_declarations():
    for not_a_schema in ([Rung.L3], "L3", Rung.L3, None, 4):
        with pytest.raises((TypeError, UnclassifiedField)):
            classify_schema(not_a_schema)
    with pytest.raises(UnclassifiedField):
        classify_schema({"": Rung.L3})
    with pytest.raises(UnclassifiedField):
        classify_schema({7: Rung.L3})


def test_i11_a_declaration_may_carry_more_than_the_rung():
    """The spec's step 5 wants the matter and the jurisdiction recorded
    alongside the rung, because a case number is `L1` in a bankruptcy and `L3`
    in a family matter. This function does not *enforce* that — the registry
    is Phase 3 — but it must not stand in the way of a schema that does it."""
    class Field:
        def __init__(self, rung, matter, jurisdiction, why):
            self.rung, self.matter = rung, matter
            self.jurisdiction, self.why = jurisdiction, why

    got = classify_schema({
        "hearing_date": Rung.L1,
        "case_number": "L3",
        "child_dob": {"rung": Rung.L4, "matter": "custody", "why": "a minor"},
        "treatment": Field(Rung.L5, "workers_comp", "US-federal", "42 CFR Part 2"),
    })
    assert got == {
        "hearing_date": Rung.L1,
        "case_number": Rung.L3,
        "child_dob": Rung.L4,
        "treatment": Rung.L5,
    }
    assert all(isinstance(r, Rung) for r in got.values())


def test_i11_the_runtime_half_reads_l5_and_is_not_served():
    """The second closure. If an unclassified value reaches a render path
    anyway, it reads `L5` — never `L1`, which is the direction every
    convenience default goes."""
    for value in NOT_RUNGS:
        for surface in Surface:
            for purpose in PURPOSES:
                assert may_render(value, surface, purpose=purpose) is False
                assert decide(value, surface, purpose=purpose) is Disposition.DENY


def test_i11_a_classified_datum_cannot_be_built_without_a_rung():
    """Construction is where an unclassified value should stop, so that
    nothing downstream has to decide what to do with one."""
    for value in NOT_RUNGS:
        with pytest.raises(UnclassifiedField):
            Classified(rung=value, payload="x", derived="y")


def test_i11_a_derivable_rung_must_carry_the_form_it_derives_to():
    """BUG-5's other half. law-gazelle's screen said 'Excluded from drafting'
    while the packet still carried the atom, and that mismatch was possible
    because the exclusion had no representation of what to show instead."""
    for rung in (Rung.L3, Rung.L4):
        with pytest.raises(UnclassifiedField):
            Classified(rung=rung, payload="12% whole-person impairment")
        with pytest.raises(UnclassifiedField):
            Classified(rung=rung, payload="x", derived="  ")
        assert Classified(rung=rung, payload="x", derived="an obligation exists")
    # L1/L2 render everywhere and L5 is served in no form, so none of the three
    # needs a stand-in. That set is derived from the ceiling table, not typed in.
    assert rungs_mod._NEEDS_DERIVED == frozenset({Rung.L3, Rung.L4})
    for rung in (Rung.L1, Rung.L2, Rung.L5):
        assert Classified(rung=rung, payload="x")


# ── I-11 · an unclassified field fails the build ─────────────────────────────

def _schema_like(name: str, obj: object) -> bool:
    """Is this module-level object something `classify_schema` must accept?

    Two independent triggers, because either one alone has a hole:

    * **by name** — `SCHEMA` or `*_SCHEMA`. Catches a schema with no rungs in it
      at all, which is the fully-unclassified case a value scan cannot see.
    * **by content** — any mapping with a `Rung` among its values. Catches the
      *partially* classified case regardless of what it is called, which is
      BUG-5's shape exactly: some of the thing guarded, some of it not.
    """
    if not isinstance(obj, Mapping):
        return False
    return name == "SCHEMA" or name.endswith("_SCHEMA") or any(
        isinstance(v, Rung) for v in obj.values()
    )


def _unclassified_in(module: types.ModuleType) -> list[str]:
    found = []
    for name, obj in vars(module).items():
        if _schema_like(name, obj):
            try:
                classify_schema(obj)
            except Exception as exc:
                found.append(f"{module.__name__}.{name}: {exc}")
    return found


def test_i11_the_scan_fires_on_an_unclassified_schema():
    """The positive control, run on every invocation rather than once by hand.

    Phase 0's lesson was that a scan which has never fired is theatre, and two
    of its scans were. This one fires here, now, against a module built for the
    purpose — including the half-classified case, which is the one that gets
    past a reviewer.
    """
    fake = types.ModuleType("homestead.keep._injected")
    fake.CUSTODY_SCHEMA = {"body": None}                       # nothing declared
    fake.PARTLY = {"case_number": Rung.L3, "diagnosis": None}  # half of it
    fake.INTEGER_SCHEMA = {"case_number": 3}                   # I-14 as data
    fake.FINE = {"case_number": Rung.L3, "diagnosis": Rung.L4}
    fake.PLAIN_MAPPING = {"a": 1, "b": 2}      # neither trigger; not a schema

    found = _unclassified_in(fake)
    names = {entry.split(":")[0] for entry in found}
    assert names == {
        "homestead.keep._injected.CUSTODY_SCHEMA",
        "homestead.keep._injected.PARTLY",
        "homestead.keep._injected.INTEGER_SCHEMA",
    }, found


def test_i11_the_scan_has_a_hole_and_this_is_where_it_is():
    """Stated as a test rather than as a sentence, so it cannot rot quietly.

    A mapping that is a schema *in intent*, is not named `*_SCHEMA`, and
    contains no `Rung` at all — every field declared with a bare integer, say —
    trips neither trigger and is invisible to this scan. That is not
    hypothetical: `{"case_number": 3}` is precisely what I-14 exists to stop,
    and a value scan looking for `Rung` cannot see a dict that contains none.

    The control that does not depend on a naming convention is the one below
    it: defining a schema *calls* `classify_schema`, and an unclassified field
    then stops the import. This scan is a second net with a known hole in it,
    not the primary control.
    """
    fake = types.ModuleType("homestead.keep._injected2")
    fake.custody_fields = {"case_number": 3, "body": None}
    assert _unclassified_in(fake) == []


def test_i11_no_schema_in_this_package_is_unclassified():
    """The scan itself, over every module that ships.

    It is vacuous today — Phase 2 defines no schemas — and it is here so that it
    is not vacuous on the day Phase 3 defines the first one. Its limit is the
    convention it depends on: a schema built at runtime, or held somewhere other
    than a module-level mapping, is not seen by it. The control that does not
    depend on a convention is that defining a schema *calls* `classify_schema`,
    and an unclassified field then stops the import.
    """
    import homestead

    offenders: list[str] = []
    for info in pkgutil.walk_packages(homestead.__path__, prefix="homestead."):
        offenders += _unclassified_in(importlib.import_module(info.name))
    offenders += _unclassified_in(homestead)
    assert not offenders, offenders


def test_i11_an_unclassified_field_stops_the_import_that_defines_it(tmp_path):
    """The build failure, end to end, in the shape a schema module has.

    A schema is defined at import time, so `classify_schema` refusing at import
    time *is* the build failing. Run in a subprocess so the failure is a real
    non-zero exit rather than an exception this process caught.
    """
    module = tmp_path / "matter_schema.py"
    module.write_text(
        "from homestead.keep.rungs import Rung, classify_schema\n"
        "CUSTODY_SCHEMA = classify_schema({\n"
        "    'hearing_date': Rung.L1,\n"
        "    'guardian_ad_litem_report': None,\n"   # the unclassified one
        "})\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-c", "import matter_schema"],
        cwd=ROOT, capture_output=True, text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(tmp_path)},
    )
    assert result.returncode != 0, result.stdout
    assert "UnclassifiedField" in result.stderr
    assert "guardian_ad_litem_report" in result.stderr
    assert "hearing_date" not in result.stderr


# ── I-12 · composition is max, everywhere ────────────────────────────────────

def test_i12_composition_is_max_over_every_combination():
    order = {r: i for i, r in enumerate(Rung)}
    for n in (1, 2, 3):
        for combination in itertools.product(Rung, repeat=n):
            assert compose(*combination) == max(combination, key=order.get)


def test_i12_a_projection_never_lowers_a_rung():
    """The one direction aggregation is allowed to move.

    A record is the max of its fields, a chronology of its events, a draft of
    every fact it cites. Nothing composes downward, on any input, ever.
    """
    order = {r: i for i, r in enumerate(Rung)}
    for combination in itertools.product(Rung, repeat=3):
        assert order[compose(*combination)] >= max(order[r] for r in combination)


def test_i12_a_prompt_is_the_max_of_its_whole_context_window():
    """Including the neighbours a semantic search pulled in.

    That clause is the one that gets skipped, and skipping it is what turns a
    retrieval seam into an `L4` leak: every fragment scored `L2` on its own, the
    window scored on the fragment that was checked, and the neighbour nobody
    chose riding in beside it.
    """
    chosen = [Rung.L1, Rung.L2]
    neighbours = [Rung.L2, Rung.L4]
    assert context_rung(chosen) is Rung.L2
    assert context_rung(chosen + neighbours) is Rung.L4
    assert context_rung([]) is Rung.L5, "an empty window is not a harmless one"
    assert context_rung([Rung.L1, None]) is Rung.L5, "an unclassified neighbour"
    assert context_rung([Classified(Rung.L4, "x", "an obligation"),
                         Rung.L1]) is Rung.L4


def test_i12_what_actually_reaches_a_surface_is_within_its_ceiling():
    """I-12 pointed at S2. Assemble a window through the chokepoint and the
    composed rung of what went in cannot exceed what the surface may hold,
    however many neighbours retrieval added."""
    window = [
        Classified(Rung.L1, "Hearing Aug 15, Dept 3"),
        Classified(Rung.L2, "4 items due this week"),
        Classified(Rung.L3, "minor child A.R., Tue/Thu",
                   derived="a recurring parenting-time obligation"),
        Classified(Rung.L4, "12% whole-person impairment",
                   derived="a medical records response is due"),
        Classified(Rung.L5, "do_not_use: the allegation under seal",
                   derived="never served"),
    ]
    for surface in Surface:
        served = serve_all(window, surface, purpose="drafting")
        rendered = [s.rung for s in served
                    if s.disposition is Disposition.RENDER]
        assert compose(*rendered, Rung.L1) in (Rung.L1, Rung.L2, Rung.L3, Rung.L4)
        for rung in rendered:
            assert may_render(rung, surface, purpose="drafting")
        assert all(s.rung is not Rung.L5 for s in served)


# ── I-13 · L5 has no override, L4 never reaches a prompt ─────────────────────

def test_i13_l5_is_refused_on_every_surface_for_every_purpose():
    """No purpose, no surface, no flag. A rung with an escape hatch is a label,
    not a control — so the exhaustive version, not the three-case version."""
    for surface in Surface:
        for purpose in PURPOSES:
            assert may_render(Rung.L5, surface, purpose=purpose) is False
            assert decide(Rung.L5, surface, purpose=purpose) is Disposition.DENY


def test_i13_l5_is_refused_structurally_not_by_a_special_case():
    """`L5` is refused because no ceiling is `L5`, which the module checks when
    it imports. Five rows saying `never` would be five things to get right."""
    for surface, (plain, with_purpose) in rungs_mod._CEILING.items():
        assert plain is not Rung.L5 and with_purpose is not Rung.L5


def test_i13_l4_reaches_a_model_prompt_under_no_condition():
    for purpose in PURPOSES:
        assert may_render(Rung.L4, Surface.S2_PROMPT, purpose=purpose) is False
        assert decide(Rung.L4, Surface.S2_PROMPT, purpose=purpose) is Disposition.DERIVE
    assert may_render(Rung.L3, Surface.S2_PROMPT, purpose="drafting") is False, (
        "L3 on a prompt is the derived form too — the crossing table gives S2 "
        "no purpose lift at all"
    )


def test_i13_bug5_the_stronger_rejection_is_never_the_weaker_one():
    """The defect this whole model replaces, stated as a property.

    `_fact_blocked` returned `status == "needs_source"`. `do_not_use` — the
    stronger rejection — was not in the condition, so it flowed into the
    drafting packet and the model prompt while the Review Facts screen said
    "Excluded from drafting". Here: whatever is refused at a rung is refused at
    every rung above it, on every surface, for every purpose, by arithmetic.
    """
    ladder = list(Rung)
    for surface in Surface:
        for purpose in PURPOSES:
            for i, lower in enumerate(ladder):
                if may_render(lower, surface, purpose=purpose):
                    continue
                for higher in ladder[i + 1:]:
                    assert may_render(higher, surface, purpose=purpose) is False, (
                        f"{lower.value} is refused on {surface.value} but "
                        f"{higher.value} is not — the stronger case walking "
                        "past the guard is BUG-5"
                    )


def test_i13_no_purpose_string_is_magic():
    """The hole the hand-written `PURPOSES` list leaves, closed by sampling.

    Found by injection, not by reading: a `may_render` that returned `True` for
    the single string `"court order"` passed every other test in this file,
    because every other test iterates a list somebody typed. An exhaustive-
    looking test that is exhaustive only over a hand-written list is the exact
    failure mode both Phase 0 audits found.

    This samples; the test below it is the one that does not.
    """
    plausible = ["court order", "override", "admin", "root", "yes", "true",
                 "1", "*", "all", "force", "debug", "test", "sudo", "urgent",
                 "the operator asked", "L5", "unseal", "", "None"]
    rng = random.Random(20260805)
    sampled = ["".join(rng.choice(string.printable) for _ in range(rng.randint(1, 24)))
               for _ in range(500)]
    for purpose in plausible + sampled:
        for surface in Surface:
            assert may_render(Rung.L5, surface, purpose=purpose) is False
        assert may_render(Rung.L4, Surface.S2_PROMPT, purpose=purpose) is False
        assert may_render(Rung.L4, Surface.S1_LIST, purpose=purpose) is False


def test_i13_the_decision_never_reads_the_content_of_a_purpose():
    """The same hole, closed structurally rather than by sampling.

    A purpose is an explicit act; the decision turns on **whether one was
    declared**, never on what it says. So in the whole of `rungs.py` the name
    `purpose` may only be *passed on* — to `_declared`, or to another function
    in the same family. Comparing it, matching it, indexing it, or handing it to
    anything else fails here, which makes a magic value unrepresentable rather
    than merely absent from a list.

    `_declared` is the single exemption, because it is the one function whose
    job is to look at a purpose — and all it looks at is whether the string has
    anything in it. See the test below.
    """
    allowed = {"_declared", "may_render", "decide", "serve", "serve_all"}
    tree = ast.parse((ROOT / "homestead" / "keep" / "rungs.py").read_text("utf-8"))

    passed_on: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in allowed:
                for value in [*node.args, *(kw.value for kw in node.keywords)]:
                    if isinstance(value, ast.Name):
                        passed_on.add(id(value))

    declared = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "_declared")
    exempt = {id(n) for n in ast.walk(declared)}

    offenders = [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "purpose"
        and id(node) not in passed_on and id(node) not in exempt
    ]
    assert not offenders, (
        f"rungs.py reads the content of a purpose at line(s) {offenders}. The "
        "decision turns on whether a purpose was declared, not on what it says "
        "— a purpose the code recognises by value is an escape hatch, and I-13 "
        "says there is no escape hatch."
    )


def test_i13_a_declared_purpose_is_a_declared_purpose_whatever_it_says():
    """`_declared` is exempted above, so it is pinned here instead.

    It must be blind to content: any non-blank string is a declaration and no
    non-blank string is more of one than another.
    """
    rng = random.Random(20260805)
    for _ in range(500):
        text = "".join(rng.choice(string.printable) for _ in range(rng.randint(1, 24)))
        assert rungs_mod._declared(text) is bool(text.strip())
    assert rungs_mod._declared("court order") is rungs_mod._declared("x") is True


def _non_monotone(permits) -> list[str]:
    """Every place a permission function is not downward-closed in the rung.

    Takes the function rather than reading the module, so it can be run against
    a deliberately broken table — which is the only way to know it would notice.
    """
    ladder = list(Rung)
    broken = []
    for surface in Surface:
        for purpose in (None, "medical"):
            allowed = [r for r in ladder if permits(r, surface, purpose=purpose)]
            expected = ladder[: len(allowed)]
            if allowed != expected:
                broken.append(f"{surface.value}/{purpose}: {allowed}")
    return broken


def test_i13_monotonicity_holds_and_the_check_that_says_so_can_fail():
    """A check that has never failed has not been shown to check anything.

    The hand-written table below is `_fact_blocked`'s exact defect — a guard
    that blocks the middle case and lets the stronger one through — and the
    checker catches it. Then the same checker is run against the real function.
    """
    def bug5_shaped(rung, surface, *, purpose=None):
        return rung is not Rung.L3          # blocks L3, lets L4 and L5 past

    assert _non_monotone(bug5_shaped), "the monotonicity check does not fire"
    assert not _non_monotone(may_render)


def test_i13_the_import_time_guards_reject_a_table_that_breaks_the_rules(
    monkeypatch,
):
    """`_check_crossing()` is the reason the properties above are structural.

    Fired here against four broken tables rather than asserted about. Each one
    is a thing a table author could plausibly write.
    """
    original = dict(rungs_mod._CEILING)

    def with_table(table):
        monkeypatch.setattr(rungs_mod, "_CEILING", table)
        with pytest.raises(RuntimeError):
            rungs_mod._check_crossing()

    # L5 given an override somewhere
    with_table({**original, Surface.S4_EGRESS: (Rung.L2, Rung.L5)})
    # an ambient surface given an L4 ceiling — I-35
    with_table({**original, Surface.S1_LIST: (Rung.L3, Rung.L4)})
    # a purpose that lowers rather than lifts
    with_table({**original, Surface.S3_AGENT: (Rung.L4, Rung.L2)})
    # a surface dropped from the table — BUG-6's shape
    with_table({s: v for s, v in original.items() if s is not Surface.S3_AGENT})
    # a bare integer ceiling — I-14
    with_table({**original, Surface.S2_PROMPT: (2, 2)})

    monkeypatch.setattr(rungs_mod, "_CEILING", original)
    assert rungs_mod._check_crossing() == rungs_mod._NEEDS_DERIVED


# ── I-14 · rungs are strings ─────────────────────────────────────────────────

def test_i14_the_crossing_table_holds_rungs_not_integers():
    """`if level >= 3` is correct against this scale and catastrophic against
    WillowGate trust, which runs the other way — and reads perfectly either
    way. The table cannot contain the thing that makes that possible."""
    for plain, with_purpose in rungs_mod._CEILING.values():
        assert isinstance(plain, Rung) and isinstance(with_purpose, Rung)
        assert not isinstance(plain, int) and not isinstance(with_purpose, int)


def test_i14_an_integer_never_becomes_a_rung_by_being_compared():
    for n in (1, 2, 3, 4, 5):
        for surface in Surface:
            assert may_render(n, surface, purpose="medical") is False
            assert decide(n, surface, purpose="medical") is Disposition.DENY
    with pytest.raises(TypeError):
        Rung.L3 >= 3


def test_i14_the_string_spelling_is_the_one_that_works():
    for rung in Rung:
        assert may_render(rung.value, Surface.S1_DETAIL) is may_render(
            rung, Surface.S1_DETAIL
        )


# ── I-15 · note bodies reach neither a log nor a prompt ──────────────────────

def test_i15_a_note_body_is_derived_on_a_prompt_and_never_rendered():
    """F-3/F-4: `add_note` copied the first 80 characters of every private note
    into the activity log, and the last eight log rows went into every model
    prompt. Note → log → prompt, and `a` opened the log from the main screen.

    The log half is closed in `logs.py` — `VisibleLog.record` has no parameter
    that takes text. This is the prompt half.
    """
    body = "he was drunk again at pickup and the child was in the car"
    note = Classified(Rung.L4, body, derived="a note is attached to this item")

    for purpose in PURPOSES:
        result = serve(note, Surface.S2_PROMPT, purpose=purpose)
        assert result.disposition is Disposition.DERIVE
        assert result.value == note.derived
        assert body not in str(result.value)

    # And ambiently on the operator's own screen, which is where `a` opened the
    # confession timeline in one keypress.
    assert serve(note, Surface.S1_LIST).disposition is Disposition.DERIVE

    # The detail pane serves it — the act of opening is the declaration — and
    # S3/S4 serve it only on a declared purpose. Both are the model working, not
    # a leak, and stating them here keeps this test from claiming more than
    # I-15 does: it is about a *prompt* and a *log*, not about every surface.
    assert serve(note, Surface.S1_DETAIL).disposition is Disposition.RENDER
    for surface in (Surface.S3_AGENT, Surface.S4_EGRESS):
        assert serve(note, surface).disposition is Disposition.DERIVE
        assert serve(note, surface, purpose="medical").disposition is Disposition.RENDER


def test_i15_the_visible_log_and_the_prompt_agree_about_what_a_note_is():
    """The two halves of I-15 in one place, so neither can be closed alone."""
    from homestead.keep import logs

    assert not any(
        p in inspect.signature(logs.VisibleLog.record).parameters
        for p in ("body", "text", "summary", "content", "note")
    )
    assert may_render(Rung.L4, Surface.S2_PROMPT, purpose="any reason at all") is False


# ── I-35 · the list pane's render path does not accept a payload ─────────────

def test_i35_an_ambient_row_has_nowhere_to_put_a_payload():
    """Not a policy — the type. A Phase 4 list renderer typed to take these has
    no expression that reaches a payload, because the object does not hold one.
    """
    assert set(AmbientRow.__dataclass_fields__) == {"rung", "text"}
    row = AmbientRow(rung=Rung.L4, text="Medical records response due Aug 15")
    assert not hasattr(row, "payload")


def test_i35_the_list_pane_shows_the_instruction_and_not_the_diagnosis():
    """The spec's own worked example, run.

    The workers' comp file holds *"IME 2026-06-14: L4–L5 disc herniation, 12%
    whole-person impairment, permanent lifting restriction 20 lb."* What Today
    renders is *"Medical records response due Aug 15 — 11 days."*
    """
    ime = "IME 2026-06-14: 12% whole-person impairment, 20 lb lifting restriction"
    items = [
        Classified(Rung.L1, "Hearing · Aug 15 · 8:30 am · Dept 3"),
        Classified(Rung.L4, ime, derived="Medical records response due Aug 15"),
        Classified(Rung.L5, "do_not_use: the sealed allegation",
                   derived="this should never appear"),
    ]
    rows = ambient_rows(items)
    texts = [r.text for r in rows]
    assert texts == ["Hearing · Aug 15 · 8:30 am · Dept 3",
                     "Medical records response due Aug 15"]
    assert not any("impairment" in t for t in texts)
    assert not any("sealed" in t or "never appear" in t for t in texts)


def test_i35_an_ambient_surface_may_not_be_given_an_l4_ceiling():
    for surface in Surface:
        if FACTS[surface].ambient:
            plain, with_purpose = rungs_mod._CEILING[surface]
            assert compose(plain, with_purpose) in (Rung.L1, Rung.L2, Rung.L3)


# ── the chokepoint drops what it refuses, rather than marking it ─────────────

def test_a_denied_datum_is_absent_from_the_result_not_flagged_in_it():
    """BUG-5's mechanism, made unrepresentable.

    law-gazelle's `draft_context` selected atoms by status and never read
    `fact_verification`, so both `needs_source` and `do_not_use` atoms flowed
    into the packet, into the markdown, and into the prompt — unmarked. Here
    the refused item is not in the packet marked; it is not in the packet.
    """
    do_not_use = Classified(Rung.L5, "the allegation under a protective order",
                            derived="never served")
    fine = Classified(Rung.L2, "4 items due this week")

    served = serve_all([do_not_use, fine], Surface.S2_PROMPT)
    assert [s.value for s in served] == ["4 items due this week"]
    assert all(Rung.L5 is not s.rung for s in served)
    assert not any("protective order" in str(s.value) for s in served)


def test_a_denial_carries_no_trace_of_what_was_denied():
    """At `L5` the existence of a refusal is itself what must not be rendered —
    'rendering it would reveal a refusal' is the rung's own definition. So a
    `DENY` result says a denial happened and nothing about its subject, and the
    plural form leaves no count behind either."""
    secret = "the substance-use treatment record"
    item = Classified(Rung.L5, secret, derived=secret)
    result = serve(item, Surface.S4_EGRESS, purpose="filing")
    assert result.disposition is Disposition.DENY
    assert result.value is None
    assert secret not in repr(result)
    assert len(serve_all([item, item, item], Surface.S4_EGRESS)) == 0


def test_serve_refuses_an_unclassified_value_rather_than_scoring_it():
    for value in ("a bare string", {"rung": "L1"}, None, 1):
        with pytest.raises(TypeError):
            serve(value, Surface.S1_DETAIL)


# ── purpose · it lifts, and only sometimes, and never lowers ─────────────────

def test_a_purpose_can_only_ever_lift_a_ceiling():
    for rung in Rung:
        for surface in Surface:
            without = may_render(rung, surface, purpose=None)
            with_one = may_render(rung, surface, purpose="medical")
            assert with_one or not without, (
                f"{rung.value} on {surface.value} renders without a purpose and "
                "not with one — declaring a reason must never take a power away"
            )


def test_the_absence_of_a_purpose_wearing_its_clothes_does_not_lift():
    """A blank string is the absence of a purpose arriving in the shape of one,
    and an empty form field is the commonest way it arrives."""
    for blank in (None, "", "   ", "\n", "\t ", True, False, 0, 1, [], {}, object()):
        assert may_render(Rung.L4, Surface.S3_AGENT, purpose=blank) is False
        assert may_render(Rung.L4, Surface.S4_EGRESS, purpose=blank) is False
    assert may_render(Rung.L4, Surface.S3_AGENT, purpose="medical") is True
    assert may_render(Rung.L4, Surface.S4_EGRESS, purpose="filing") is True


def test_the_detail_pane_needs_no_purpose_and_is_not_confused_by_one():
    """Decided 2026-08-04, by widget rather than by dialog: the deliberate act
    of opening the pane *is* the purpose declaration, so a person in crisis
    pays no ceremony tax. An extra string buys nothing and costs nothing."""
    assert may_render(Rung.L4, Surface.S1_DETAIL, purpose=None) is True
    assert may_render(Rung.L4, Surface.S1_DETAIL, purpose="medical") is True
    assert may_render(Rung.L4, Surface.S1_DETAIL, purpose="") is True
    assert may_render(Rung.L5, Surface.S1_DETAIL, purpose="medical") is False


# ── time does not declassify ─────────────────────────────────────────────────

def test_nothing_here_lowers_a_rung_and_nothing_here_takes_a_date():
    """Declassification is an act with a name and a date, recorded in the
    ledger. No rung falls by inertia, on a schedule, or as a side effect of
    aggregation — so there is no function here to do it, and no function here
    accepts a time at all.

    A closed matter's medical records stay `L4`; a child turning eighteen
    changes who may hold the file, not what the data is. When a real
    declassification lands it will be a ledgered act somewhere else, and this
    test should be updated deliberately rather than deleted quietly.
    """
    forbidden = ("declassify", "downgrade", "lower", "relax", "expire",
                 "age", "decay", "unseal", "reclassify")
    for module in (rungs_mod, surfaces_mod):
        for name in dir(module):
            if name.startswith("__"):
                continue          # `__package__` contains "age"; so would a scan
            assert not any(f in name.lower() for f in forbidden), (
                f"{module.__name__}.{name} — a rung falls by an act, not by a "
                "function named after the passage of time"
            )

    time_words = ("date", "day", "today", "now", "age", "since", "until",
                  "expires", "ttl", "timeout")
    for fn in (may_render, decide, serve, serve_all, compose, context_rung,
               classify_schema, ambient_rows):
        for param in inspect.signature(fn).parameters:
            assert not any(w in param.lower() for w in time_words), (
                f"{fn.__name__}({param}) — a decision that takes a time is a "
                "decision time can change"
            )


def test_aggregation_can_only_raise_a_rung():
    """`L2` is the rung an aggregate reaches *after* a re-identification check,
    and until it passes the aggregate inherits the max of its inputs. Nothing
    here can be the thing that lowers it."""
    order = {r: i for i, r in enumerate(Rung)}
    for combination in itertools.product(Rung, repeat=2):
        for extra in Rung:
            before = compose(*combination)
            after = compose(*combination, extra)
            assert order[after] >= order[before]
