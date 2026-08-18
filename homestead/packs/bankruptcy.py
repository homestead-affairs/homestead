"""The bankruptcy pack — the second schema, proving the registry seam.

A US-federal bankruptcy matter (Chapter 7/13), classified at **import**. Where
custody classified a case number at L3 (family records are commonly sealed),
bankruptcy classifies it at L1 — dockets are public through PACER, which is the
model's canonical example of the same field name taking different rungs in
different matters. That contrast is the reason this pack exists alongside
custody: one pack proves the seam, two prove the seam carries a real rung
difference for the same field name.

**The rungs are declared, never inferred from the field name.** The five-step
procedure in ``docs/homestead-rungs.md`` § "Classifying a new field" applies
identically: each field below carries its steps in ``why``.
"""
from __future__ import annotations

from typing import Any

from homestead.keep.rungs import Rung, classify_schema

__all__ = ["MATTER", "JURISDICTION", "SCHEMA", "FIELDS"]

MATTER = "bankruptcy"
JURISDICTION = "US-federal"


def _field(rung: Rung, why: str) -> dict[str, Any]:
    return {"rung": rung, "matter": MATTER, "jurisdiction": JURISDICTION, "why": why}


SCHEMA: dict[str, dict[str, Any]] = {
    "courthouse": _field(
        Rung.L1,
        "the court's public identity — public in any federal forum (step 1)",
    ),
    "filing_date": _field(
        Rung.L1,
        "the petition date, posted on the public docket (step 1). A deadline "
        "computed from it is also L1.",
    ),
    "case_number": _field(
        Rung.L1,
        "the docket number — public through PACER in a bankruptcy (step 1). "
        "This is the model's worked example: L1 here, L3 in a family matter "
        "where records are commonly sealed.",
    ),
    "chapter": _field(
        Rung.L1,
        "Chapter 7 or 13 — a procedural classification on the public docket "
        "(step 1).",
    ),
    "trustee": _field(
        Rung.L1,
        "the assigned trustee is named on the public docket (step 1).",
    ),
    "creditor_meeting_date": _field(
        Rung.L1,
        "the 341 meeting date — posted on the court calendar and docket, "
        "public in this forum (step 1).",
    ),
    "discharge_date": _field(
        Rung.L1,
        "the discharge order date — on the public docket once entered (step 1).",
    ),
    "attorney": _field(
        Rung.L2,
        "the debtor's attorney — a person, but the name appears on the public "
        "docket as counsel of record. L2 rather than L1: derived form masks "
        "the direct-dial and email that filings carry (step 2).",
    ),
    "creditors": _field(
        Rung.L3,
        "the list of creditors and amounts owed — resolves to the debtor's "
        "financial obligations (step 2 yes). Not L1 despite the public schedule: "
        "aggregated creditor data reveals the debtor's financial posture in "
        "full, which is L3 material (step 2, then step 4 does not raise it).",
    ),
    "income": _field(
        Rung.L3,
        "the debtor's household income — resolves to a person's financial "
        "situation (step 2 yes, step 3 no). Filed under seal in some districts "
        "but required for the means test.",
    ),
    "assets": _field(
        Rung.L3,
        "the debtor's asset schedule — resolves to financial position (step 2). "
        "Public on the docket but aggregated here as structured data.",
    ),
    "notes": _field(
        Rung.L4,
        "free operator text that may carry protected content — same posture as "
        "custody's notes field: resolves to a person and routinely carries "
        "categories a model prompt must not see (step 3). L4 blocks it from "
        "S2 (ceiling L2) and S3.",
    ),
    "ssn": _field(
        Rung.L5,
        "key material — sealed, and L5 has no override anywhere (step 4). "
        "Bankruptcy filings use the last four digits on the docket; the full "
        "SSN is in the petition filed under seal.",
    ),
}

FIELDS: dict[str, Rung] = classify_schema(SCHEMA)
