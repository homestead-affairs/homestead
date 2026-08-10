"""The custody pack — the first real schema in the package (bite 2).

A US-CA custody matter, classified at **import**. `classify_schema(SCHEMA)` runs
at module top level, so an author who adds a field and forgets its rung stops the
build with that field named (I-11) — the refusal Phase 2 built and tested against
synthetic schemas, now aimed at a real one. Until this pack existed, that refusal
was, in `DECISION-unclassified-field-instrument.md`'s phrase, *"a lock on an
empty room."*

**The rungs are declared, never inferred from the field name.** A case number is
`L1` in a bankruptcy (dockets are public) and `L3` in a family matter (records
are commonly sealed), so nothing here is keyed on a name — the same field name
takes different rungs in different matters, and only a declaration knows which.
`docs/homestead-rungs.md` § "Classifying a new field" is the procedure; each
field below carries the answer to its five steps in `why`, alongside the matter
and jurisdiction step 5 requires.

**Each field is a mapping, not a bare rung, on purpose.** `classify_schema` reads
the `"rung"` key and ignores the rest, so a pack can carry the matter, the
jurisdiction and the sentence that justifies the rung — the reviewable record a
rung is useless without. A reviewer cannot check `L3` for a case number without
knowing it is a *family* case number, and the field says so.

**What this pack cannot catch, and does not pretend to.** `classify_schema`
checks that a rung was *declared*, not that it was declared *well*: it would
accept `L1` for `ssn` without a murmur. The advisory content check that would
flag a rung shaped wrong for its content — declared `L1`, content shaped like an
SSN — is the next bite, and it may only ever argue a rung *up*, never down.
"""
from __future__ import annotations

from typing import Any

from homestead.keep.rungs import Rung, classify_schema

__all__ = ["MATTER", "JURISDICTION", "SCHEMA", "FIELDS"]

MATTER = "custody"
JURISDICTION = "US-CA"


def _field(rung: Rung, why: str) -> dict[str, Any]:
    return {"rung": rung, "matter": MATTER, "jurisdiction": JURISDICTION, "why": why}


#: The closed custody schema. Field → declaration (rung + matter + jurisdiction +
#: reason). Ordered by rung so the ladder reads down the page. Nothing here is
#: keyed on the field name; the rung is a property of the field *in this matter
#: and jurisdiction* (step 5), which is why the same name can sit elsewhere.
SCHEMA: dict[str, dict[str, Any]] = {
    "courthouse": _field(
        Rung.L1,
        "the court's public identity — public in this matter's forum (step 1)",
    ),
    "hearing_date": _field(
        Rung.L1,
        "the hearing's date, time and department — posted on the court calendar, "
        "so public in this matter's forum (step 1). homestead-rungs.md "
        "§ Custody classifies it L1 for that reason; the doc's worked example "
        "is 'Hearing · Aug 15 · 8:30 am · Dept 3 · County Courthouse.'",
    ),
    "case_number": _field(
        Rung.L3,
        "resolves to the parties, no protected category. The model's worked "
        "example: L1 in a bankruptcy where the docket is public, L3 in a family "
        "matter where records are commonly sealed (step 2, then step 4 does not "
        "raise it).",
    ),
    "docket": _field(
        Rung.L3,
        "same posture as the case number in a family matter — resolves to the "
        "parties, commonly sealed but not itself key material or a refusal.",
    ),
    "opposing_party": _field(
        Rung.L3,
        "names the co-parent — a person — with no protected category attached to "
        "the name itself (step 2 yes, step 3 no).",
    ),
    "child_name": _field(
        Rung.L4,
        "names a person who is a minor. A minor is a category the law follows "
        "(step 3 yes), and the whole model turns on not rendering it by default.",
    ),
    "parenting_time": _field(
        Rung.L3,
        "the parenting schedule — resolves to the child (step 2), which "
        "homestead-rungs.md § Custody classifies L3. The operator sees it on "
        "their own list; a model prompt (S2, ceiling L2) gets only the derived "
        "'a recurring parenting-time obligation on Tue/Thu' — the doc's worked "
        "example for this field. Not L4: it resolves to the child but does not "
        "itself carry a protected category the way a diagnosis does.",
    ),
    "diagnosis": _field(
        Rung.L4,
        "a medical category attached to a person (step 3). 'Medical' belongs to "
        "the rung, which carries it at L4; it never reaches a model prompt.",
    ),
    "notes": _field(
        Rung.L4,
        "free operator text that resolves to a person and routinely carries a "
        "protected category — substance use, a diagnosis, an allegation (F-4 was "
        "exactly this content leaking). L4 blocks the F-3/F-4 shape: a note never "
        "reaches a model prompt (S2, ceiling L2 → derived) or an agent (I-15), "
        "and the operator reads their own note in the detail pane. **Kept at L4 "
        "by decision (2026-08-10), against the bite-1-3 audit that argued L5** — "
        "see docs/audits/bites-1-3-remediation.md. The residual the audit named "
        "is real: a note holding L5-worthy content would egress on a "
        "purpose-declared S4 export, past L5's no-egress rule. Closing it needs a "
        "per-field operator-visible / non-exportable split, which the one-rung "
        "model does not express; until that lands the advisory content matcher "
        "(declared L4, content shaped like an L5 datum → raise) is the intended "
        "guard, and v1 is synthetic-data-only. Not L5: a note the operator cannot "
        "read is not a note.",
    ),
    "ssn": _field(
        Rung.L5,
        "key material — sealed, and L5 has no override anywhere (step 4). The "
        "corpus's canonical L5 datum; served on no surface, in any form.",
    ),
}

#: Classified at import (I-11). This line is the build failure: remove any
#: field's rung above and the process defining the schema dies, naming the field.
FIELDS: dict[str, Rung] = classify_schema(SCHEMA)
