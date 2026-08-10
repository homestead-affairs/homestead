"""I-23 — the registry is the only enumeration.

Promoted out of `test_invariants_pending.py` when `homestead.keep.registry`
landed, which is what `test_pending_liveness` is for: the moment the module
existed the pending file failed by name, and would not go green again until the
Phase 3 test was promoted out, unmarked. This is the fourth occasion of that
same promotion — dates, surfaces, record, now the registry — and it went
through the same door: the `"homestead.keep.registry"` key comes out of
`UNBUILT`, and the pending `test_i23…` moves here with its body and docstring
kept.

BUG-6 is the failure this whole file exists against. The predecessor advertised
three matter types and enumerated them by hand in three places — navigation, the
urgent queue, the briefing. The lists drifted, workers' comp fell out of the
queue's copy, and a deadline in a workers'-comp matter could not become urgent
because the loop that raised urgency never iterated that type. Every test that
asked "are all matters handled?" asked its own hand-kept list, so none caught
it. The answer is one enumeration — `all_matters()` over `REGISTRY` — and a
structural guard that a matter which exists but is not registered stops the
build rather than going silently unhandled.
"""
from __future__ import annotations

import ast
import types
from pathlib import Path

import pytest

from homestead.keep import registry as registry_mod
from homestead.keep.registry import (
    REGISTRY,
    MatterType,
    all_matters,
    matter,
)
from homestead.keep.rungs import Rung
from homestead.packs import custody

PKG = Path(__file__).resolve().parent.parent / "homestead"


# ── promoted from test_invariants_pending.py ─────────────────────────────────

def test_i23_the_registry_is_the_only_enumeration():
    """BUG-6: workers' comp — one of three advertised matter types — was
    structurally absent from the urgent queue, because three types were
    enumerated by hand in three places."""
    from homestead.keep.registry import REGISTRY, all_matters

    assert set(all_matters()) == set(REGISTRY)


# ── what the registry holds ──────────────────────────────────────────────────

def test_custody_is_registered_and_is_the_only_built_pack():
    """One pack in v1 — *"one pack proves the seam; three prove nothing that one
    does not."* Bankruptcy and workers' comp are Phase 5 and are deliberately
    **not** here: a matter name with no pack behind it is the hand-kept phantom
    I-23 forbids, the missing half of BUG-6."""
    assert set(all_matters()) == {"custody"}
    assert "bankruptcy" not in REGISTRY, "Phase 5, not built — no phantom entry"
    assert "workers_comp" not in REGISTRY, "Phase 5, not built — no phantom entry"


def test_all_matters_iterates_the_registry_and_nothing_else():
    """The one function everything that needs 'all matter types' calls. It reads
    `REGISTRY` at call time, so it cannot hold a stale copy — and it hands back a
    tuple, so a caller cannot mutate the enumeration by keeping what it returns.
    """
    assert set(all_matters()) == set(REGISTRY)
    assert isinstance(all_matters(), tuple)
    assert all(isinstance(name, str) for name in all_matters())


def test_an_entry_ties_a_matter_to_its_pack():
    """The value shape: a `MatterType` carrying the name, the jurisdiction and
    the pack — the host holding the thing it consumes (Article IV's injected
    seam), never the reverse."""
    entry = matter("custody")
    assert isinstance(entry, MatterType)
    assert entry.name == custody.MATTER == "custody"
    assert entry.jurisdiction == custody.JURISDICTION == "US-CA"
    assert entry.pack is custody


def test_the_registry_does_not_hardcode_the_field_list_it_reads_it():
    """The pack is reachable through the registry without the registry copying
    the pack's field list. `fields` is a property over `pack.FIELDS`, so it *is*
    the pack's one list — identity, not equality — and there is nowhere for a
    second copy to drift from the first, which is BUG-6's mechanism removed."""
    entry = matter("custody")
    assert entry.fields is custody.FIELDS
    assert entry.schema is custody.SCHEMA
    assert entry.fields["ssn"] is Rung.L5
    assert set(entry.fields) == set(custody.SCHEMA)


def test_matter_is_strict_about_an_unknown_name():
    """Like `surfaces.facts`: a caller holding a name that is not registered has
    skipped a step, and a `KeyError` here is cheaper than the missing schema read
    it would otherwise have caused downstream."""
    with pytest.raises(KeyError):
        matter("bankruptcy")
    with pytest.raises(KeyError):
        matter("not_a_matter")


# ── the import-time guard fires — BUG-6's shape, from each side ───────────────

def _fake_pack(name: str, *, jurisdiction: str = "US-CA") -> types.ModuleType:
    """A stand-in pack with the attributes `_entry`/`_validate` read. Built for
    the guard tests the way `test_invariants_surfaces` builds fake modules for
    the schema scan — a real module object, not a mock."""
    mod = types.ModuleType(f"homestead.packs._fake_{name}")
    mod.MATTER = name
    mod.JURISDICTION = jurisdiction
    mod.FIELDS = {"case_number": Rung.L3}
    mod.SCHEMA = {"case_number": {"rung": Rung.L3, "matter": name}}
    return mod


def test_a_pack_on_disk_with_no_entry_fails_the_build():
    """BUG-6 exactly: a matter type that exists and is not enumerated. The guard
    is run here against a registry that omits a discovered pack, so it is shown
    to fire and not merely asserted to exist."""
    bankruptcy = _fake_pack("bankruptcy")
    on_disk = {"custody": custody, "bankruptcy": bankruptcy}
    with pytest.raises(RuntimeError) as exc:
        registry_mod._validate(dict(REGISTRY), on_disk)
    assert "bankruptcy" in str(exc.value)
    # and it names the failure it is, not a bare "invalid"
    assert "no registry entry" in str(exc.value)


def test_a_registry_entry_with_no_pack_is_a_phantom_and_fails_the_build():
    """The other half of BUG-6: a name in the enumeration with nothing behind it.
    Inventing a `bankruptcy` entry before its pack exists is the exact thing that
    would let `all_matters()` advertise a type no pack can serve."""
    phantom = registry_mod._entry(_fake_pack("bankruptcy"))
    broken = {**REGISTRY, "bankruptcy": phantom}
    with pytest.raises(RuntimeError) as exc:
        registry_mod._validate(broken, {"custody": custody})
    assert "bankruptcy" in str(exc.value)
    assert "no pack" in str(exc.value)


def test_a_key_that_disagrees_with_its_packs_matter_fails_the_build():
    """A key kept by hand next to a name set in the pack is a transcription that
    can drift — so it is not allowed to. The registry is keyed by the pack's own
    `MATTER`, read once, and a mismatch stops the build."""
    misfiled = registry_mod.MatterType(
        name="custardy", jurisdiction="US-CA", pack=custody  # typo'd key
    )
    broken = {"custardy": misfiled}
    with pytest.raises(RuntimeError) as exc:
        registry_mod._validate(broken, {"custody": custody})
    assert "disagrees" in str(exc.value)


def test_an_entry_that_is_not_a_matter_type_fails_the_build():
    """The table holds `MatterType`s, the way `FACTS` holds `SurfaceFacts` — a
    bare string or a raw pack in the value slot is caught at import."""
    with pytest.raises(RuntimeError):
        registry_mod._validate({"custody": "custody"}, {"custody": custody})


def test_the_real_registry_passes_its_own_guard():
    """The positive side: what actually ships is consistent with the packs that
    actually exist. Run here so the guard is exercised on the real inputs on
    every invocation, not only at import."""
    registry_mod._validate(REGISTRY, registry_mod._discover_packs())
    assert set(registry_mod._discover_packs()) == set(REGISTRY)


# ── the Phase-3 exit criterion, held behaviourally ───────────────────────────

def test_adding_a_pack_to_the_registry_needs_no_other_code_change(monkeypatch):
    """*"Adding a pack touches no navigation, queue, or briefing code."*

    The whole point of one enumeration: a second matter type appears everywhere
    that iterates `all_matters()` the instant it is in `REGISTRY`, with nothing
    else edited. Demonstrated by injecting a second entry into the registry and
    reading it back out of `all_matters()` — the function reads `REGISTRY` at
    call time, so the addition is reflected with no change to the function and no
    second list to keep in step."""
    bankruptcy = registry_mod._entry(_fake_pack("bankruptcy"))
    monkeypatch.setitem(registry_mod.REGISTRY, "bankruptcy", bankruptcy)

    assert set(all_matters()) == {"custody", "bankruptcy"}
    assert set(all_matters()) == set(registry_mod.REGISTRY)
    assert matter("bankruptcy").fields == {"case_number": Rung.L3}


# ── the structural guard: the registry is the ONLY enumeration ───────────────

MATTER_ENUM_ALLOWED = {
    PKG / "keep" / "registry.py",
    # packs/*.py: a pack declares its own MATTER ("custody"); it is the source of
    # the name, so it is where the string is allowed to live.
}


def _matter_name_enumerations(tree: ast.AST, names: set[str]) -> list[int]:
    """Every place a matter name appears *as an enumeration* — an element of a
    list/set/tuple literal, or an operand of an `in`/`==` test. That is BUG-6's
    literal shape: `["custody", "bankruptcy", "workers_comp"]`, or
    `if m in ("custody", ...)`. Bare display strings (`Label(text="custody")`)
    and prose in a docstring are *not* enumerations and are not caught — the ban
    is on hand-keeping the set, not on the word appearing."""
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
            for elt in node.elts:
                if isinstance(elt, ast.Constant) and elt.value in names:
                    hits.append(node.lineno)
        elif isinstance(node, ast.Compare):
            for operand in (node.left, *node.comparators):
                if isinstance(operand, ast.Constant) and operand.value in names:
                    hits.append(node.lineno)
    return hits


def _is_pack(mod: Path) -> bool:
    return "packs" in mod.relative_to(PKG).parts


def test_no_module_outside_the_registry_hardcodes_the_set_of_matters():
    """I-23 held structurally. No navigation, queue or briefing keeps its own
    matter list — the failure was three of them, and with one matter built we
    cannot watch three drift, so we hold the seam instead: a matter name used as
    an *enumeration* (in a collection literal, or an `in`/`==` test) may appear
    only where the enumeration legitimately lives — this registry, and the packs
    that declare their own names. Everywhere else it is a build failure.

    Vacuous the day it is written, on purpose: there is no consumer iterating
    matters yet (navigation, the queue and the briefing are Phase 3+). It is here
    so it is *not* vacuous the moment someone writes `matters = ["custody",
    "bankruptcy"]` in the queue instead of calling `all_matters()` — which is the
    exact line BUG-6 was."""
    names = set(all_matters())
    offenders: list[str] = []
    for mod in sorted(PKG.rglob("*.py")):
        if "__pycache__" in mod.parts:
            continue
        if mod in MATTER_ENUM_ALLOWED or _is_pack(mod):
            continue
        for lineno in _matter_name_enumerations(ast.parse(mod.read_text("utf-8")), names):
            offenders.append(f"{mod.relative_to(PKG.parent)}:{lineno}")
    assert not offenders, (
        f"a matter name is enumerated by hand outside the registry at {offenders}. "
        "I-23 — the registry is the only enumeration; iterate all_matters() "
        "rather than keeping a list, because a second list is one that can drift "
        "from this one, and workers' comp fell out of exactly such a list (BUG-6)."
    )


def test_the_structural_guard_fires_on_a_planted_enumeration(tmp_path):
    """A scan that has never fired has not been shown to check anything — Phase
    0's lesson, applied. BUG-6's own line is planted in a fake non-registry
    module and the guard must catch it, in each of the two shapes an enumeration
    takes: a collection literal, and a membership test."""
    names = {"custody", "bankruptcy", "workers_comp"}

    literal = tmp_path / "queue.py"
    literal.write_text(
        "URGENT_MATTERS = ['custody', 'bankruptcy', 'workers_comp']\n", "utf-8"
    )
    membership = tmp_path / "nav.py"
    membership.write_text(
        "def is_matter(m):\n    return m in ('custody', 'bankruptcy')\n", "utf-8"
    )
    clean = tmp_path / "view.py"
    clean.write_text(
        "import tkinter as tk\n"
        "def draw(w):\n    tk.Label(w, text='custody').pack()\n",  # a display string, not an enum
        "utf-8",
    )

    assert _matter_name_enumerations(ast.parse(literal.read_text()), names)
    assert _matter_name_enumerations(ast.parse(membership.read_text()), names)
    assert not _matter_name_enumerations(ast.parse(clean.read_text()), names), (
        "a bare display string is not an enumeration and must not be caught — "
        "the ban is on hand-keeping the set, not on the word appearing"
    )


def test_the_guard_would_catch_the_registry_itself_if_it_were_not_exempt():
    """The exemption is load-bearing, so it is pinned: the registry and the packs
    are *allowed* to name matters, and everything else is not. If the allow-list
    were dropped the registry could still enumerate (it builds from
    `custody.MATTER`, an attribute, not a literal today) — but a future authored
    `REGISTRY = {"custody": ...}` with a literal key is exactly the enumeration
    this file is *for*, so it must be exempt, and this test states that it is."""
    assert PKG / "keep" / "registry.py" in MATTER_ENUM_ALLOWED
    assert _is_pack(PKG / "packs" / "custody.py")
    assert not _is_pack(PKG / "app" / "view.py")
