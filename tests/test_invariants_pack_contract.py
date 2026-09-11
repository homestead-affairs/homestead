"""E1-pack-contract — `JURISDICTIONS` on packs, and the `"derived"` schema key.

Decision 1 (plan): packs declare `JURISDICTION` (default) + `JURISDICTIONS` (the
full supported set); an instance's jurisdiction is validated against the tuple
and arithmetic refuses when it is absent (Wave 3, not this bite). Decision 3:
derived forms live in the pack as a `"derived"` key per field declaration, and
`classify_schema` keeps ignoring it — the same shape `"matter"`/`"jurisdiction"`/
`"why"` already have, none of which `classify_schema` reads either.

This file holds the contract two ways: the schema-reading half
(`derived_of`, `classify_schema`'s continued indifference to the key) and the
registry-reading half (`MatterType.jurisdictions`, `_validate`'s new checks).
The corpus packs (`custody`, `bankruptcy`) are exercised as the real, already-
registered instances of the contract; a fake pack plants each violation
`_validate` exists to catch, per house style — a scan that has never fired has
not been shown to check anything.
"""
from __future__ import annotations

import re

import pytest

from homestead.keep import registry as registry_mod
from homestead.keep.registry import REGISTRY, all_matters, matter
from homestead.keep.rungs import Rung, classify_schema, derived_of
from homestead.packs import bankruptcy, custody

_DIGIT = re.compile(r"\d")


# ── classify_schema keeps ignoring "derived" ─────────────────────────────────

def test_classify_schema_ignores_a_derived_key():
    """A `"derived"` key alongside `"rung"` changes nothing about classification
    — the same way `classify_schema` already ignores `"matter"`/`"jurisdiction"`/
    `"why"`. Two schemas differing only in whether a field carries a `"derived"`
    sentence must classify identically, and a schema *whose only field is a
    `"derived"` string with no `"rung"`* must still refuse exactly as an
    undeclared field always has — `"derived"` is not a second way to declare a
    rung."""
    without = {"x": {"rung": Rung.L3, "why": "test"}}
    with_derived = {"x": {"rung": Rung.L3, "why": "test", "derived": "A value is on file"}}
    assert classify_schema(without) == classify_schema(with_derived) == {"x": Rung.L3}

    with pytest.raises(Exception):
        classify_schema({"x": {"derived": "A value is on file"}})


def test_classify_schema_still_ignores_derived_on_the_real_packs():
    """The corpus packs carry `"derived"` on every L3/L4 field now; classifying
    them must produce the exact same `FIELDS` a rung-only copy of the schema
    would, proving the key rode along without ever reaching the classifier."""
    for pack in (custody, bankruptcy):
        stripped = {
            name: {k: v for k, v in decl.items() if k != "derived"}
            for name, decl in pack.SCHEMA.items()
        }
        assert classify_schema(stripped) == pack.FIELDS == classify_schema(pack.SCHEMA)


# ── derived_of ────────────────────────────────────────────────────────────────

def test_derived_of_reads_the_declared_sentence():
    assert derived_of(custody.SCHEMA, "case_number") == "A case number is on file"
    assert derived_of(bankruptcy.SCHEMA, "creditors") == "A creditor list is on file"


def test_derived_of_returns_none_for_a_field_without_one():
    """`courthouse` (L1) and `ssn` (L5) never carry a `"derived"` key — neither
    rung is ever served as a stand-in, so a pack author has nothing to write
    for them (`_NEEDS_DERIVED` in `keep/rungs.py`). Also `None` for a field name
    that is not in the schema at all: absence, not an error, same as
    `classify_schema`'s data-side (I-11) rather than its build-side."""
    assert derived_of(custody.SCHEMA, "courthouse") is None
    assert derived_of(custody.SCHEMA, "ssn") is None
    assert derived_of(custody.SCHEMA, "not_a_field") is None
    assert derived_of({}, "anything") is None


def test_derived_of_is_the_derived_form_never_a_payload_path():
    """The docstring's central claim, held behaviourally: what comes back is the
    stand-in sentence itself — a human-readable string with no field name or
    lookup syntax in it — never something a caller could mistake for a path
    into the record (`(matter, field, id)` or a dotted attribute chain)."""
    sentence = derived_of(custody.SCHEMA, "notes")
    assert sentence == "An operator note is on file"
    assert "." not in sentence
    assert "notes" not in sentence.split()


# ── every L3/L4 field carries a non-empty derived form ───────────────────────

def test_every_l3_and_l4_field_carries_a_non_empty_derived_form():
    """Over every registered pack (`all_matters()`, not a hand-picked pair) —
    the contract is pack-shaped, not custody-shaped or bankruptcy-shaped."""
    assert set(all_matters()) == {"custody", "bankruptcy"}, (
        "this test's coverage claim depends on iterating every registered "
        "matter; if a third pack lands, it is covered by the same loop with no "
        "edit here needed"
    )
    checked = 0
    for name in all_matters():
        mt = matter(name)
        for field, rung in mt.fields.items():
            if rung in (Rung.L3, Rung.L4):
                sentence = derived_of(mt.schema, field)
                assert isinstance(sentence, str) and sentence.strip(), (
                    f"{name}.{field} is {rung.value} and must carry a non-empty "
                    "'derived' sentence"
                )
                checked += 1
    assert checked >= 7, "expected at least custody's four L3 + three L4 fields"


def test_deleting_a_derived_sentence_is_not_caught_by_classify_schema_but_is_caught_here():
    """`classify_schema` does not enforce this contract — decision 3 keeps it
    ignorant of the key — so the L3/L4-coverage test above is what actually
    holds the requirement. Demonstrated: a schema with an L3 field's `"derived"`
    stripped still classifies cleanly, and only the coverage test over it fails."""
    import copy

    wounded = copy.deepcopy(custody.SCHEMA)
    del wounded["case_number"]["derived"]
    classified = classify_schema(wounded)  # does not raise
    assert classified["case_number"] is Rung.L3
    assert derived_of(wounded, "case_number") is None


# ── a derived form restates no value ─────────────────────────────────────────

def test_a_derived_form_restates_no_value():
    """No digit characters (a date, an amount, a case number fragment), and the
    sentence is never simply the field name — both would restate the value
    the derived form exists to stand in for instead of naming."""
    for pack in (custody, bankruptcy):
        for field, decl in pack.SCHEMA.items():
            sentence = decl.get("derived")
            if sentence is None:
                continue
            assert not _DIGIT.search(sentence), (
                f"{pack.MATTER}.{field}'s derived form {sentence!r} contains a "
                "digit — it restates the value rather than standing in for it"
            )
            assert sentence != field, (
                f"{pack.MATTER}.{field}'s derived form is exactly the field name"
            )


# ── JURISDICTIONS ─────────────────────────────────────────────────────────────

def test_custody_and_bankruptcy_jurisdictions():
    assert custody.JURISDICTIONS == ("US-CA",)
    assert custody.JURISDICTION in custody.JURISDICTIONS
    assert bankruptcy.JURISDICTIONS == ("US-federal",)
    assert bankruptcy.JURISDICTION in bankruptcy.JURISDICTIONS


def test_jurisdictions_is_read_live_from_the_pack():
    """`MatterType.jurisdictions` is a property over `pack.JURISDICTIONS`, the
    same shape as `fields`/`schema` — identity with the pack's own tuple, not a
    copy, so the registry cannot carry a stale second copy of it (BUG-6's
    mechanism, applied to the third pack attribute this bite adds)."""
    entry = matter("custody")
    assert entry.jurisdictions is custody.JURISDICTIONS
    entry2 = matter("bankruptcy")
    assert entry2.jurisdictions is bankruptcy.JURISDICTIONS


def test_a_default_jurisdiction_outside_the_supported_tuple_fails_the_build():
    """Decision 1's planted violation: a pack whose default `JURISDICTION` is
    not itself a member of its own `JURISDICTIONS`. Fired against `_validate`
    directly, on a fake pack, so the guard is shown to catch it rather than
    merely asserted to."""
    from tests.test_invariants_registry import _fake_pack

    broken_pack = _fake_pack(
        "workers_comp", jurisdiction="US-OR", jurisdictions=("US-NM",)
    )
    entry = registry_mod._entry(broken_pack)
    broken_registry = {**REGISTRY, "workers_comp": entry}
    on_disk = {"custody": custody, "bankruptcy": bankruptcy, "workers_comp": broken_pack}
    with pytest.raises(RuntimeError) as exc:
        registry_mod._validate(broken_registry, on_disk)
    assert "workers_comp" in str(exc.value)
    assert "JURISDICTION" in str(exc.value)


def test_an_empty_jurisdictions_tuple_fails_the_build():
    """The other half of decision 1's validation: `JURISDICTIONS` itself must be
    a non-empty tuple of non-empty strings — an empty tuple, a blank member, or
    a non-tuple all read as absence and fail closed the way an unclassified
    field does (I-11's shape, applied here)."""
    from tests.test_invariants_registry import _fake_pack

    for bad in ((), ("",), ("US-CA", "  "), ["US-CA"]):
        broken_pack = _fake_pack("workers_comp", jurisdiction="US-CA", jurisdictions=bad)
        entry = registry_mod._entry(broken_pack)
        broken_registry = {**REGISTRY, "workers_comp": entry}
        on_disk = {
            "custody": custody,
            "bankruptcy": bankruptcy,
            "workers_comp": broken_pack,
        }
        with pytest.raises(RuntimeError) as exc:
            registry_mod._validate(broken_registry, on_disk)
        assert "JURISDICTIONS" in str(exc.value), f"failed for {bad!r}"


def test_a_pack_with_no_jurisdictions_attribute_at_all_fails_the_build():
    """A pack that never declares `JURISDICTIONS` — not even an empty one — is
    the same absence as any other, read by `getattr(..., None)` rather than a
    bare attribute access that would raise the wrong exception type."""
    import types

    broken_pack = types.ModuleType("homestead.packs._fake_workers_comp")
    broken_pack.MATTER = "workers_comp"
    broken_pack.JURISDICTION = "US-NM"
    broken_pack.FIELDS = {"case_number": Rung.L3}
    broken_pack.SCHEMA = {"case_number": {"rung": Rung.L3, "matter": "workers_comp"}}
    entry = registry_mod._entry(broken_pack)
    broken_registry = {**REGISTRY, "workers_comp": entry}
    on_disk = {"custody": custody, "bankruptcy": bankruptcy, "workers_comp": broken_pack}
    with pytest.raises(RuntimeError) as exc:
        registry_mod._validate(broken_registry, on_disk)
    assert "JURISDICTIONS" in str(exc.value)


def test_the_real_registry_passes_the_jurisdiction_checks():
    """The positive side, run against what actually ships — `_validate` already
    runs at import (registry.py's module body), so this re-runs it explicitly to
    keep the guard exercised by the suite on every invocation, not only once at
    collection."""
    registry_mod._validate(REGISTRY, registry_mod._discover_packs())
