"""The reconstructed rungs-procedure doc, and the "every `why` names a step"
guard over the packs it documents.

`docs/homestead-rungs.md` — the authoritative model and its five-step
classification procedure — lives in the safe-app-store, which this build does
not have. `docs/homestead-rungs-procedure.md` reconstructs it from what this
repo actually contains: the `Rung`/`Purpose`/`_CEILING` machinery in
`homestead/keep/rungs.py`, and the two packs' own worked application of the
procedure, field by field, each citing "step 1" … "step 5" in its `why`.

That citation discipline is itself worth a test, and — per this project's own
rule that a scan which has never fired has not been shown to check anything —
the test that checks it needs a planted violation proving it actually fires.
The checker is factored out as a plain helper so both tests share it: the real
one asserts it finds nothing wrong with the packs as shipped, and the planted
one builds a fake schema with a step-less `why` and asserts the same function
catches it.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Mapping

import homestead.packs as packs_pkg

DOC = Path(__file__).resolve().parent.parent / "docs" / "homestead-rungs-procedure.md"


def _fields_missing_step(schema: Mapping[str, Any]) -> list[str]:
    """Field names in `schema` whose `why` does not mention a "step".

    This is the whole checker `test_every_pack_field_why_names_a_step` and
    `test_the_step_check_fires_on_a_step_less_why` share — one function, two
    call sites, exactly so the second test proves the first one actually
    fires on a violation rather than passing vacuously because nothing in the
    real packs happens to trip it today.

    Reads `schema[field]["why"]` the same way `classify_schema` reads a
    field's `"rung"` key (`homestead/keep/rungs.py`'s `_rung_of_declaration`):
    a plain mapping lookup, no rung logic duplicated here. A field whose
    declaration carries no `"why"` at all, or whose `why` is not a string,
    counts as missing a step too — silence is not a step citation.
    """
    missing: list[str] = []
    for name, declaration in schema.items():
        why = declaration.get("why") if isinstance(declaration, Mapping) else None
        if not isinstance(why, str) or "step" not in why:
            missing.append(name)
    return missing


def _every_pack_schema() -> dict[str, Mapping[str, Any]]:
    """`{module_name: SCHEMA}` for every module under `homestead/packs/`.

    Walks the package rather than importing `custody` and `bankruptcy` by
    name, so a third pack added later is picked up automatically — the same
    "don't hand-keep an enumeration" discipline I-23 states for matter types,
    applied here to which packs this test covers.
    """
    schemas: dict[str, Mapping[str, Any]] = {}
    for info in pkgutil.iter_modules(packs_pkg.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"homestead.packs.{info.name}")
        schema = getattr(module, "SCHEMA", None)
        if schema is not None:
            schemas[info.name] = schema
    return schemas


def test_the_procedure_doc_exists_and_says_it_is_reconstructed():
    """The doc exists, and its banner tells a reader not to trust it as the
    authoritative text."""
    assert DOC.is_file(), f"expected {DOC} to exist"
    text = DOC.read_text(encoding="utf-8")
    assert "RECONSTRUCTED" in text, (
        "the doc must say plainly, near the top, that it is a reconstruction "
        "and not the authoritative docs/homestead-rungs.md"
    )
    assert "2026-09-11" in text, "the banner must carry the reconstruction date"
    assert "safe-app-store" in text and "docs/homestead-rungs.md" in text, (
        "the banner must name where the authoritative text actually lives, so "
        "a reader knows this is not it"
    )
    assert "(reconstructed)" in text, (
        "at least one inferred sentence must be marked (reconstructed), per "
        "the banner's own promise"
    )


def test_every_pack_field_why_names_a_step():
    """Every `SCHEMA[f]["why"]` in `homestead/packs/*.py` names a step.

    Both shipped packs cite the classification procedure's step number inline
    in every field's `why` (custody.py, bankruptcy.py) — that is how this repo
    documents *which* of the five steps justified each field's rung, in the
    absence of the authoritative doc. This is the discipline check: it fails
    loudly, naming the pack and the field, the day a field is added without
    doing the same.
    """
    schemas = _every_pack_schema()
    assert schemas, "expected at least one pack under homestead/packs/"
    offenders = {
        pack_name: bad
        for pack_name, schema in schemas.items()
        if (bad := _fields_missing_step(schema))
    }
    assert not offenders, (
        f"fields with a step-less `why`: {offenders}. Every field's `why` "
        "must cite the classification-procedure step that justifies its "
        "rung ('step 1' .. 'step 5'), the way every field in custody.py and "
        "bankruptcy.py already does."
    )


def test_the_step_check_fires_on_a_step_less_why():
    """Planted counterpart: `_fields_missing_step` must actually catch a
    field whose `why` never mentions a step.

    A scan that has never fired has not been shown to check anything. This
    builds a fake schema mapping — never registered with any pack, never
    classified, nothing this repo would import on its own — with one field
    carrying a `why` that gives a reason but cites no step, and asserts the
    same helper `test_every_pack_field_why_names_a_step` relies on names it.
    """
    fake_schema = {
        "good_field": {
            "rung": "L1",
            "matter": "_fake",
            "jurisdiction": "US-XX",
            "why": "public in this matter's forum (step 1)",
        },
        "planted_bad_field": {
            "rung": "L3",
            "matter": "_fake",
            "jurisdiction": "US-XX",
            "why": "resolves to a person, so it is attributed",
        },
        "planted_no_why_field": {
            "rung": "L4",
            "matter": "_fake",
            "jurisdiction": "US-XX",
        },
    }
    missing = _fields_missing_step(fake_schema)
    assert missing == ["planted_bad_field", "planted_no_why_field"], (
        f"expected the checker to flag exactly the two planted violations, "
        f"got {missing}"
    )
