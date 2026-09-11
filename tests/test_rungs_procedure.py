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
import re
from pathlib import Path
from typing import Any, Mapping

import homestead.packs as packs_pkg

DOC = Path(__file__).resolve().parent.parent / "docs" / "homestead-rungs-procedure.md"

#: A step *citation*, not the word "step". The procedure has exactly five
#: numbered steps, so a `why` that names one names a number between 1 and 5.
#: Matching the bare substring `"step"` would accept "steps", "stepping stone",
#: "sidestep" and "step back" — prose that cites nothing — which is the whole
#: failure this guard exists to catch, arriving as a word that happens to
#: contain the right letters.
_STEP_CITATION = re.compile(r"\bstep\s+[1-5]\b", re.IGNORECASE)


def _fields_missing_step(schema: Mapping[str, Any]) -> list[str]:
    """Field names in `schema` whose `why` does not cite a numbered step.

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

    The match is `_STEP_CITATION`, `step <1-5>`, and deliberately not the
    substring `"step"`: the point of the citation is *which* of the five steps
    justified the rung, so a `why` that says "steps" or "a stepping stone
    towards L4" has cited nothing and must fail.
    """
    missing: list[str] = []
    for name, declaration in schema.items():
        why = declaration.get("why") if isinstance(declaration, Mapping) else None
        if not isinstance(why, str) or not _STEP_CITATION.search(why):
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
    field whose `why` never cites a numbered step.

    A scan that has never fired has not been shown to check anything. This
    builds a fake schema mapping — never registered with any pack, never
    classified, nothing this repo would import on its own — and asserts the
    same helper `test_every_pack_field_why_names_a_step` relies on names every
    planted field and no other.

    Four plants, because the guard has four ways to be too lax: a `why` that
    gives a reason and cites no step at all; a `why` with no `why` key; and
    the two near misses a bare `"step" in why` substring test would wave
    through — **"steps"** (plural, citing nothing) and **"a stepping stone"**
    (the letters, none of the meaning). Those last two are the reason this
    helper matches `step <1-5>` and not the word.
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
        "planted_plural_steps_field": {
            "rung": "L3",
            "matter": "_fake",
            "jurisdiction": "US-XX",
            "why": "it clears the classification steps and lands here",
        },
        "planted_stepping_stone_field": {
            "rung": "L3",
            "matter": "_fake",
            "jurisdiction": "US-XX",
            "why": "a stepping stone towards the protected rung",
        },
    }
    missing = _fields_missing_step(fake_schema)
    assert missing == [
        "planted_bad_field",
        "planted_no_why_field",
        "planted_plural_steps_field",
        "planted_stepping_stone_field",
    ], (
        f"expected the checker to flag exactly the four planted violations and "
        f"leave `good_field` alone, got {missing}"
    )


def test_the_step_check_is_not_satisfied_by_the_bare_word_step():
    """The tightening itself, pinned: `step` is not a citation, `step 3` is.

    Without this the guard could be loosened back to `"step" in why` and every
    test above would still pass — the packs all cite numbered steps, so the
    weaker rule agrees with the stronger one on the real data and the
    difference only shows on prose nobody has written yet. This is that
    difference, written down.
    """
    cites = "resolves to a person (step 2), no protected category"
    assert _STEP_CITATION.search(cites)
    for not_a_citation in (
        "one of the classification steps",
        "a stepping stone towards L4",
        "sidestep the question",
        "step back and look at the matter",
        "step six of the procedure",
        "step",
    ):
        assert not _STEP_CITATION.search(not_a_citation), not_a_citation
