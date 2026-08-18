"""Invariants for the bankruptcy pack — the second schema, proving the registry
seam carries a real rung difference for the same field name.

The canonical example: ``case_number`` is L1 in a bankruptcy (dockets are
public through PACER) and L3 in a family matter (records are commonly sealed).
That is not a policy preference this test enforces — it is a *fact about the
world* this test confirms the schema declares correctly.
"""
from __future__ import annotations

import pytest

from homestead.keep.registry import REGISTRY, matter
from homestead.keep.rungs import Rung, classify_schema
from homestead.packs import bankruptcy


def test_bankruptcy_is_registered():
    entry = matter("bankruptcy")
    assert entry.name == "bankruptcy"
    assert entry.jurisdiction == "US-federal"
    assert entry.pack is bankruptcy


def test_bankruptcy_fields_classified_at_import():
    assert isinstance(bankruptcy.FIELDS, dict)
    assert len(bankruptcy.FIELDS) > 0
    assert all(isinstance(r, Rung) for r in bankruptcy.FIELDS.values())


def test_case_number_is_l1_in_bankruptcy():
    """The model's worked example: a case number is L1 in a bankruptcy (public
    docket) and L3 in a family matter. This test pins the bankruptcy side."""
    assert bankruptcy.FIELDS["case_number"] is Rung.L1


def test_case_number_rung_differs_from_custody():
    """The whole point of two packs: the same field name takes different rungs
    in different matters."""
    from homestead.packs import custody
    assert bankruptcy.FIELDS["case_number"] is Rung.L1
    assert custody.FIELDS["case_number"] is Rung.L3


def test_ssn_is_l5():
    assert bankruptcy.FIELDS["ssn"] is Rung.L5


def test_notes_is_l4():
    assert bankruptcy.FIELDS["notes"] is Rung.L4


def test_public_docket_fields_are_l1():
    for field in ("courthouse", "filing_date", "case_number", "chapter",
                  "trustee", "creditor_meeting_date", "discharge_date"):
        assert bankruptcy.FIELDS[field] is Rung.L1, f"{field} should be L1"


def test_financial_fields_are_l3():
    for field in ("creditors", "income", "assets"):
        assert bankruptcy.FIELDS[field] is Rung.L3, f"{field} should be L3"


def test_attorney_is_l2():
    assert bankruptcy.FIELDS["attorney"] is Rung.L2


def test_classify_schema_round_trips():
    """The FIELDS dict is what classify_schema produces from SCHEMA — run it
    again to confirm the result is stable."""
    fresh = classify_schema(bankruptcy.SCHEMA)
    assert fresh == bankruptcy.FIELDS


def test_every_field_carries_matter_and_jurisdiction():
    for field_name, decl in bankruptcy.SCHEMA.items():
        assert decl["matter"] == "bankruptcy", f"{field_name} missing matter"
        assert decl["jurisdiction"] == "US-federal", f"{field_name} missing jurisdiction"
        assert "why" in decl, f"{field_name} missing why"


def test_registry_reads_fields_through_the_pack():
    entry = matter("bankruptcy")
    assert entry.fields is bankruptcy.FIELDS
    assert entry.schema is bankruptcy.SCHEMA
