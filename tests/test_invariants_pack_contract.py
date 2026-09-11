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

import ast
import json
import re
from pathlib import Path

import pytest

from homestead.keep import registry as registry_mod
from homestead.keep.registry import REGISTRY, all_matters, matter
from homestead.keep.rungs import Rung, classify_schema, derived_of
from homestead.packs import bankruptcy, custody

PKG = Path(__file__).resolve().parent.parent / "homestead"

_DIGIT = re.compile(r"\d")
#: A weekday or a month, in any of the spellings a schedule is written in. A
#: schema-level derived form is one sentence for *every* instance of the field,
#: so a day or a month in it is either a restatement of one household's value or
#: a falsehood about the next household's — see `test_a_derived_form_names_no_day`.
_CALENDAR_WORD = re.compile(
    r"\b("
    r"mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|jan|feb|apr|jun|jul|aug|sep|sept|oct|nov|dec"
    r"|january|february|march|april|june|july|august|september"
    r"|october|november|december"
    r")\b",
    re.IGNORECASE,
)
# "may" and "mar" are left out on purpose: a derived form reading "a payment
# may be due" is not a month, and a scan with a false positive that common
# gets an exemption written next to it, which is how a scan stops being read.


def _leaks(sentence: str) -> list[str]:
    """Every way one derived sentence restates the value it stands in for.
    Returned rather than asserted so the scan can be fired against a planted
    violation as well as run over the real packs."""
    found: list[str] = []
    if _DIGIT.search(sentence):
        found.append("digit")
    hit = _CALENDAR_WORD.search(sentence)
    if hit:
        found.append(f"calendar word {hit.group(0)!r}")
    return found


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
    """No digit characters (a date, an amount, a case number fragment), no day
    or month name, and the sentence is never simply the field name — each would
    restate the value the derived form exists to stand in for instead of naming
    it. Run over every registered pack, not a hand-picked pair, for the same
    reason the coverage test above is."""
    for name in all_matters():
        mt = matter(name)
        for field, decl in mt.schema.items():
            sentence = decl.get("derived")
            if sentence is None:
                continue
            assert not _leaks(sentence), (
                f"{name}.{field}'s derived form {sentence!r} carries "
                f"{_leaks(sentence)} — it restates the value rather than "
                "standing in for it"
            )
            assert sentence != field, (
                f"{name}.{field}'s derived form is exactly the field name"
            )


def test_a_derived_form_names_no_day():
    """The audit's finding, planted so the scan is shown to fire.

    `docs/PHASE2-SURFACES.md` uses *"a recurring parenting-time obligation on
    Tue/Thu"* as its worked derived form, and the pack shipped that sentence
    verbatim as `custody.parenting_time`'s declaration. A *record's* stand-in
    may name the days — it was composed for a schedule that really falls on
    them. A *schema's* may not: one sentence serves every instance of the
    field, so on the household whose schedule is Mon/Wed it is false, and on
    the household whose schedule is Tue/Thu it is the schedule itself, served
    to S2 and S3 in place of the payload those surfaces are not allowed. Both
    halves of BUG-5 at once — the screen saying something other than the truth,
    over a fact it claimed to withhold.

    The digit scan alone did not catch it: "Tue/Thu" has no digits."""
    assert _leaks("A recurring parenting-time obligation on Tue/Thu"), (
        "the scan must catch the day-naming sentence this test exists for"
    )
    for planted in (
        "A recurring parenting-time obligation on Tue/Thu",
        "A hearing is set for Thursday",
        "A payment is due in March",
        "A case number ending 4417 is on file",
    ):
        assert _leaks(planted), f"{planted!r} passed the derived-form scan"
    for clean in (
        "A recurring parenting-time obligation is on file",
        "A medical category is on file for a person",
        "The other parent is named",
    ):
        assert not _leaks(clean), f"{clean!r} was wrongly flagged"

    assert derived_of(custody.SCHEMA, "parenting_time") == (
        "A recurring parenting-time obligation is on file"
    ), "the pack must carry the instance-independent sentence, not the doc's example"


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
    # the membership message specifically — "JURISDICTION" alone also matches
    # the shape message above it, so the plant could pass on the wrong refusal
    assert "is not in" in str(exc.value)
    assert "'US-OR'" in str(exc.value) and "('US-NM',)" in str(exc.value)


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


# ── derived_of is not a payload path, held structurally ──────────────────────

def _derived_of_source() -> ast.FunctionDef:
    """The `derived_of` definition, parsed out of the shipped `keep/rungs.py`."""
    source = (Path(__file__).resolve().parent.parent
              / "homestead" / "keep" / "rungs.py").read_text("utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == "derived_of":
            return node
    raise AssertionError("derived_of is not defined in homestead/keep/rungs.py")


def test_derived_of_reaches_no_payload_and_reflects_on_nothing():
    """I-16 for the one new reader in the gate's own file.

    `tests/test_invariants_chokepoint.py` allows `keep/rungs.py` to reach a
    `.payload` — it is the gate, and `serve()` must. That allowance is
    module-wide, so a *new* function added to this file inherits it: a payload
    reach inside `derived_of` would be invisible to the package scan. The
    allowance is for the gate, not for everything that shares its file, so the
    claim is held here at function scope instead, using the chokepoint's own
    helpers rather than a second copy of them — if the scan changes, this
    changes with it.

    `derived_of` reads a *schema*: a mapping the pack authored, not a record.
    So inside its body there is no `.payload`, no reflection primitive, and no
    mention of `Classified` at all — there is no expression in it that could
    reach a stored value, whatever a caller passes.
    """
    from tests.test_invariants_chokepoint import _payload_reaches, _reflection_reaches

    fn = _derived_of_source()
    assert not _payload_reaches(fn), (
        "derived_of reaches a .payload. It reads the schema a pack declared; a "
        "payload is reached through serve() and nowhere else (I-16), and this "
        "function living in the gate's file is not a licence to do it here."
    )
    assert not _reflection_reaches(fn), (
        "derived_of uses a reflection primitive — the by-computed-name read the "
        "chokepoint audit used to walk past the literal .payload scan."
    )
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)} | {
        a.attr for a in ast.walk(fn) if isinstance(a, ast.Attribute)
    }
    assert "Classified" not in names, (
        "derived_of names Classified. A Classified holds a payload; a function "
        "that never touches one cannot return what one holds."
    )


def test_derived_of_refuses_a_record_that_is_shaped_like_a_declaration():
    """The near miss, fired.

    `keep/record.py` dumps a `Classified` as `{"rung", "payload", "derived"}` —
    structurally a declaration that carries a derived form. A mapping of field
    name to *stored record* would therefore read through `derived_of` silently
    and hand back record content from a function documented as reading schema
    content. Not a payload escape (nothing here reads `"payload"`), but the
    one shape that makes reading a record through this function look reasonable,
    so it is refused by the key a declaration never has.

    The record is built by the store's own serializer, not by a dict typed
    here, so the shape under test is the shape that actually gets written.
    """
    from homestead.keep.record import _dump
    from homestead.keep.rungs import Classified

    stored = json.loads(_dump(Classified(Rung.L3, "the schedule", "An obligation is on file")))
    assert set(stored) == {"rung", "payload", "derived"}

    with pytest.raises(TypeError) as exc:
        derived_of({"parenting_time": stored}, "parenting_time")
    message = str(exc.value)
    assert "parenting_time" in message, "an error names the field (I-15)"
    assert "the schedule" not in message, (
        "an error message never echoes an L3+ value (I-15)"
    )


# ── the entry's copied jurisdiction cannot drift from its pack ───────────────

def test_an_entry_whose_jurisdiction_drifted_from_its_pack_fails_the_build():
    """`fields`, `schema` and `jurisdictions` are properties over the pack and
    cannot disagree with it. `jurisdiction` is a *copy*, taken by `_entry` at
    construction — the one field on an entry with BUG-6's mechanism still in it.
    Planted: an entry built by hand with a jurisdiction its pack does not
    declare, which before this check passed `_validate` and left the registry
    saying `US-OR` while the pack said `US-CA` and `jurisdictions` said
    `("US-CA",)` — the copy and the live read openly disagreeing."""
    drifted = registry_mod.MatterType(
        name="custody", jurisdiction="US-OR", pack=custody
    )
    broken_registry = {**REGISTRY, "custody": drifted}
    on_disk = {"custody": custody, "bankruptcy": bankruptcy}
    with pytest.raises(RuntimeError) as exc:
        registry_mod._validate(broken_registry, on_disk)
    assert "disagrees with its pack" in str(exc.value)
    assert drifted.jurisdiction not in drifted.jurisdictions


# ── the jurisdiction set is not hand-kept either (I-23's shape) ──────────────

def _all_declared_jurisdictions() -> set[str]:
    """Every jurisdiction any registered pack declares — read from the packs,
    which is the point: the scan's own list of names is not hand-kept."""
    names: set[str] = set()
    for name in all_matters():
        names.update(matter(name).jurisdictions)
    return names


#: Where a jurisdiction name may be written as a literal. The packs declare
#: theirs, the registry validates them — and `keep/dates.py` authors a *second,
#: different* set: the jurisdictions whose counting rules are implemented
#: (`RULES`/`JURISDICTIONS` there). Those two sets are not the same question —
#: a matter can be filed somewhere the rule table has not been written for, and
#: `_calendar_for` refuses exactly that — so the rule table is its own source
#: and is exempt, the way a pack is exempt for its own `MATTER`.
JURISDICTION_LITERAL_ALLOWED = {
    (PKG / "keep" / "registry.py").resolve(),
    (PKG / "keep" / "dates.py").resolve(),
}


def test_no_module_outside_the_packs_hardcodes_a_jurisdiction():
    """I-23's shape, one attribute over — decision 1 makes jurisdiction a
    per-matter fact, so a jurisdiction name enumerated by hand in a surface, a
    queue or a CLI is the same drift BUG-6 was: a second list that can disagree
    with the packs', quietly excluding the matter that moved. Uses the registry
    test's own enumeration scan, not a copy of it."""
    from tests.test_invariants_registry import _is_pack, _matter_name_enumerations

    names = _all_declared_jurisdictions()
    assert names, "the scan needs the packs' jurisdictions to look for"
    offenders: list[str] = []
    for mod in sorted(PKG.rglob("*.py")):
        if "__pycache__" in mod.parts or _is_pack(mod):
            continue
        if mod.resolve() in JURISDICTION_LITERAL_ALLOWED:
            continue
        for lineno in _matter_name_enumerations(ast.parse(mod.read_text("utf-8")), names):
            offenders.append(f"{mod.relative_to(PKG.parent)}:{lineno}")
    assert not offenders, (
        f"a jurisdiction is enumerated by hand at {offenders}. Decision 1 puts "
        "the jurisdiction set on the pack (`JURISDICTIONS`) and the registry "
        "reads it live — ask `matter(name).jurisdictions` rather than keeping a "
        "second list, because the second list is the one that will still say "
        "US-CA after the household has moved."
    )


def test_the_jurisdiction_guard_fires_on_a_planted_literal(tmp_path):
    """A scan that has never fired has not been shown to check anything. Planted
    in both shapes an enumeration takes, and a display string is left alone."""
    from tests.test_invariants_registry import _matter_name_enumerations

    names = _all_declared_jurisdictions() | {"US-NM", "US-OR"}
    literal = tmp_path / "queue.py"
    literal.write_text("STATES = ['US-CA', 'US-NM', 'US-OR']\n", "utf-8")
    membership = tmp_path / "cli.py"
    membership.write_text(
        "def counts(j):\n    return j in ('US-federal', 'US-CA')\n", "utf-8"
    )
    clean = tmp_path / "view.py"
    clean.write_text("def draw(w):\n    return f'filed in {w}'\n", "utf-8")

    assert _matter_name_enumerations(ast.parse(literal.read_text()), names)
    assert _matter_name_enumerations(ast.parse(membership.read_text()), names)
    assert not _matter_name_enumerations(ast.parse(clean.read_text()), names)
