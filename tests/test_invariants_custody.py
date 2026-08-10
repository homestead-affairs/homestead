"""Bite 2 of docs/PLAN-first-runnable.md — the custody pack, and
`classify_schema` called for the first time.

Phase 2 built the refusal and tested it hard, but against synthetic schemas: the
exit criterion *"an unclassified field fails the build"* was, in the words of
`DECISION-unclassified-field-instrument.md`, *"a lock on an empty room."* This is
the room getting something in it — the first real schema in the package, a US-CA
custody matter, classified at **import** so an unclassified field stops the build
rather than surprising someone at runtime.

Packs are fixed: the operator-extends-a-pack question (P-3, Option A) is answered
*no* for v1, so a pack is a closed schema authored by the project, and the only
way a field goes unclassified is an author's omission — which is exactly what
import-time classification catches.

The rungs here are the model's own worked examples, not this file's invention: a
case number is `L3` in a *custody* matter (family records are commonly sealed)
where it is `L1` in a bankruptcy, an SSN is `L5`, a minor's name and schedule are
`L4`. `docs/homestead-rungs.md` § "Classifying a new field" and the surfaces
corpus are the provenance.
"""
from __future__ import annotations

import copy

import pytest

from homestead.keep.rungs import Rung, classify_schema
from homestead.packs import custody


def test_the_pack_classifies_at_import():
    """Importing the module already ran the classifier — `FIELDS` exists because
    `classify_schema(SCHEMA)` ran at module top level. A pack that deferred
    classification to a caller would move the build failure to runtime, which is
    the whole thing this bite exists to prevent."""
    assert isinstance(custody.FIELDS, dict)
    assert custody.FIELDS
    assert all(isinstance(r, Rung) for r in custody.FIELDS.values())
    assert set(custody.FIELDS) == set(custody.SCHEMA)


def test_the_pack_spans_the_ladder_with_defensible_rungs():
    """The reference pack, field by field, against the model. Each is traceable
    to a rule in homestead-rungs.md or an example in the surfaces corpus."""
    expected = {
        "courthouse": Rung.L1,       # the court's public identity
        "hearing_date": Rung.L2,     # a bare date; names no one, no category
        "case_number": Rung.L3,      # family records commonly sealed (the worked example)
        "docket": Rung.L3,           # same posture as a case number in a family matter
        "opposing_party": Rung.L3,   # names a person; no protected category
        "child_name": Rung.L4,       # names a person who is a minor — a category the law follows
        "parenting_time": Rung.L4,   # the minor's whereabouts on a schedule
        "diagnosis": Rung.L4,        # a medical category attached to a person
        "notes": Rung.L4,            # free operator text; routinely carries a protected category (F-4)
        "ssn": Rung.L5,              # sealed / key material — L5 has no override
    }
    assert custody.FIELDS == expected


def test_the_dangerous_rungs_are_where_they_must_be():
    """Spot-checks that would be catastrophic to get wrong, stated on their own
    so a change to them fails by name."""
    assert custody.FIELDS["ssn"] is Rung.L5, "an SSN is L5 — L5 has no override"
    assert custody.FIELDS["child_name"] is Rung.L4, "a minor's name identifies a minor"
    assert custody.FIELDS["diagnosis"] is Rung.L4, "a diagnosis is a category the law follows"


def test_every_field_records_matter_and_jurisdiction():
    """Step 5 of the classification procedure: the rung is recorded *with* the
    matter type and the jurisdiction, because step 1 (is it public in this
    matter's forum?) depends on both and neither is derivable from the field
    name. A pack that dropped them would be un-reviewable — nobody could check a
    rung without knowing the forum it was set in."""
    for name, spec in custody.SCHEMA.items():
        assert spec.get("matter") == "custody", name
        assert spec.get("jurisdiction"), name
        assert spec.get("why"), f"{name} declares a rung with no recorded reason"


def test_deleting_a_fields_rung_fails_the_build_naming_it():
    """The bite's 'done when', exactly: strip one field's rung and the pack no
    longer classifies — and the failure names the field, so the fix is where the
    omission is and not a hunt. This is I-11 at import, on a real schema."""
    for victim in custody.SCHEMA:
        wounded = copy.deepcopy(custody.SCHEMA)
        del wounded[victim]["rung"]
        with pytest.raises(Exception) as caught:
            classify_schema(wounded)
        assert victim in str(caught.value), (
            f"stripping {victim}'s rung must fail the build and name {victim}"
        )


def test_a_name_based_default_is_not_what_saved_this_pack():
    """The rungs are declared, not inferred. Proof: the *same* field names, with
    their declarations removed, all fail — so nothing here is keyed on the name
    'ssn' looking dangerous. classify_schema never guesses from a name."""
    for name in custody.SCHEMA:
        with pytest.raises(Exception):
            classify_schema({name: None})
