"""I-16 — one authorization chokepoint. Bite 3 of docs/PLAN-first-runnable.md.

`serve()`, `serve_all()` and `ambient_rows()` are the *shape* of one door;
`rungs.py` says so about itself and adds the sentence this bite answers:

    A gate wired to one entry point is not a gate, and at Phase 2 it is wired to
    none.

This wires it — not by a runtime guard the module can't hold, but by making a
reach past the gate a **build failure**, the same way the corpus holds `purpose`
and `_declared` honest: an AST scan, structural rather than sampled.

The rule is one sentence. `Classified.payload` — the sensitive datum itself —
may be reached in exactly two engine modules:

  * `keep/rungs.py`, the gate, where `serve()` reads the payload to decide
    whether it may cross a surface as itself or must be withheld; and
  * `keep/record.py`, the store, where persistence serializes it to the sidecar
    and hydrates it back. Disk is not a surface — S1-S4 are the surfaces, and a
    payload written to the household's own record has not been *rendered* to
    anyone.

Everywhere else, and on every surface, a payload arrives only as `Served.value`
or `AmbientRow.text` — having already been through the gate, which is the whole
point. A renderer that reads `.payload` directly is BUG-5 with the gate removed:
the screen says one thing and the packet carries another.

The regression fixture is the important half. A scan that passes because the
surface layer happens to be empty today has proven nothing; the fixture injects
the exact reach this forbids and asserts the scanner catches it.
"""
from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "homestead"

#: The two engine modules that legitimately touch a raw payload. Everything else
#: — surfaces included — must go through the gate and receive `Served.value`.
GATE = PKG / "keep" / "rungs.py"
STORE = PKG / "keep" / "record.py"
ALLOWED = {GATE, STORE}


def _modules() -> list[Path]:
    return sorted(p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts)


def _payload_reaches(tree: ast.AST) -> list[int]:
    """Every `.payload` attribute access in a tree, by line.

    An attribute access, not a dict key: `record.py` writes `{"payload": ...}` to
    the sidecar, and a string key is an `ast.Constant`, not an `ast.Attribute`,
    so serialization is not a reach. Only `something.payload` — the gate bypass —
    is one.
    """
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "payload"
    ]


def test_i16_only_the_gate_and_the_store_reach_a_payload():
    """The chokepoint, across the whole package. If a module that is neither the
    gate nor the store reaches a payload, it has walked past the one door."""
    offenders = []
    for mod in _modules():
        if mod in ALLOWED:
            continue
        for lineno in _payload_reaches(ast.parse(mod.read_text("utf-8"))):
            offenders.append(f"{mod.relative_to(PKG.parent)}:{lineno}")
    assert not offenders, (
        "a payload is reached outside the gate and the store, at "
        f"{offenders}. I-16 — the payload crosses a surface only through "
        "serve()/serve_all()/ambient_rows(), which hand back Served.value; a "
        "direct .payload read is the gate wired to nothing. If a new engine "
        "module has a real reason to touch a raw payload, it joins ALLOWED "
        "deliberately and says why — it does not slip in as a surface."
    )


def test_i16_the_surface_layer_reaches_no_payload():
    """The plan's words, as their own named check: every read of a record in
    `homestead/app/` goes through `serve` or `ambient_rows`. The general test
    above already covers this, but the surface layer is where the failure would
    actually ship, so it fails by name here."""
    offenders = []
    for mod in _modules():
        if "app" not in mod.relative_to(PKG).parts:
            continue
        for lineno in _payload_reaches(ast.parse(mod.read_text("utf-8"))):
            offenders.append(f"{mod.relative_to(PKG.parent)}:{lineno}")
    assert not offenders, (
        f"the surface layer reaches a payload directly at {offenders}. A "
        "surface renders Served.value and AmbientRow.text; it never holds a "
        "Classified's payload, because the object it is handed does not carry "
        "one past the gate."
    )


def test_i16_regression_a_direct_reach_is_caught(tmp_path):
    """The scan's teeth, demonstrated. Injected into the surface layer, a
    renderer that reads `.payload` is exactly the bypass this forbids — and both
    the general scan and the surface-layer scan must catch it, or they are
    passing today only because `app/` is nearly empty."""
    leak = tmp_path / "renderer.py"
    leak.write_text(
        "def draw(record):\n"
        "    # reaches straight past serve() — the BUG-5 shape\n"
        "    return record.payload\n"
    )
    hits = _payload_reaches(ast.parse(leak.read_text()))
    assert hits, "the scan must catch a bare .payload read on the surface"


def test_i16_serve_is_the_obvious_path():
    """The other half of 'make .payload awkward and serve() obvious': the doors
    are exported and callable, and what they hand back is *not* a payload. A
    surface that only ever sees `Served.value` and `AmbientRow.text` has no
    expression that reaches a withheld datum — I-35's structural argument,
    generalized to the chokepoint."""
    from homestead.keep import rungs
    from homestead.keep.rungs import AmbientRow, Served

    for door in ("serve", "serve_all", "ambient_rows"):
        assert door in rungs.__all__, f"{door} is a door and must be exported"
        assert callable(getattr(rungs, door))

    assert "value" in Served.__dataclass_fields__
    assert "payload" not in Served.__dataclass_fields__, (
        "Served must not carry a field named payload — the surface receives the "
        "scored value, never the raw datum under its own name"
    )
    assert set(AmbientRow.__dataclass_fields__) == {"rung", "text"}, (
        "an ambient row is a rung and a line of text and nothing else (I-35); a "
        "payload field on it would be a place for a withheld datum to ride"
    )
