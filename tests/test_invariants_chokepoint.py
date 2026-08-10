"""I-16 — one authorization chokepoint. Bite 3, hardened after the bite-1-3 audit.

`serve()`, `serve_all()` and `ambient_rows()` are the *shape* of one door;
`rungs.py` says so about itself and adds the sentence this bite answers:

    A gate wired to one entry point is not a gate, and at Phase 2 it is wired to
    none.

The first version of this bite wired it by banning the literal `.payload`
attribute — and the audit broke it in the way the prior audits break things: the
scan enforced the *spelling* of the bypass, not the property. `getattr(record,
"payload")` in a surface file reached a sealed L5 payload and passed the suite,
exactly the desktop-leak-evasion shape ("the scan misses the leak it was written
to prevent"). A one-word change walked the SSN onto the screen, green.

So the rule is now stated as a property of the **surface layer** rather than of
one token. `Classified.payload` — the sensitive datum — may be reached in exactly
two engine modules:

  * `keep/rungs.py`, the gate, where `serve()` reads the payload to decide
    whether it may cross a surface; and
  * `keep/record.py`, the store, where persistence serializes it. Disk is not a
    surface (S1-S4).

Everywhere else that is the ban. And in the surface layer — `homestead/app/` —
the ban is wider, because a surface has no honest use for reflection at all: a
surface *renders what it is handed*, `Served.value` and `AmbientRow.text`, and
never reaches around the gate by any spelling. So `getattr`, `vars`, `__dict__`,
`dataclasses.astuple`/`asdict`/`fields` and `operator.attrgetter` are all a build
failure in a surface, whatever they name — the field-by-name reads the literal
scan could not see. `keep/dates.py` reflects over its own `Deadline`, which is
why the reflection ban is scoped to the surface layer and not the whole package;
an engine type reflecting over itself is not a gate bypass.

The regression fixtures are the important half, and they now plant the leak in a
real surface path and run the **package scan** over it — not the helper over a
string — so a passing suite means the actual enforcement caught the actual leak.
"""
from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "homestead"

#: The two engine modules that legitimately touch a raw payload. Everything else
#: — surfaces included — goes through the gate and receives `Served.value`.
GATE = PKG / "keep" / "rungs.py"
STORE = PKG / "keep" / "record.py"
ALLOWED = {GATE, STORE}

#: Reflection primitives that read a field without naming it — the forms the
#: audit used to walk past the literal `.payload` scan. A surface has no honest
#: use for any of them. Matched on the leaf name, so `operator.attrgetter`,
#: `dataclasses.astuple` and a bare `getattr` are all caught.
REFLECTION_CALLS = {
    "getattr", "setattr", "vars", "astuple", "asdict", "attrgetter", "fields",
    "__getattribute__", "__getattr__",
}
REFLECTION_ATTRS = {"__dict__", "__getattribute__", "__getattr__"}


def _modules() -> list[Path]:
    return sorted(p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts)


def _is_surface(mod: Path) -> bool:
    return "app" in mod.relative_to(PKG).parts


def _payload_reaches(tree: ast.AST) -> list[int]:
    """Every `.payload` attribute access in a tree, by line. A dict key
    (`{"payload": ...}`) is an `ast.Constant`, not an `ast.Attribute`, so the
    store's serialization is not a reach — only `something.payload` is."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "payload"
    ]


def _reflection_reaches(tree: ast.AST) -> list[tuple[int, str]]:
    """Every reflection primitive in a tree — a call to `getattr`/`vars`/
    `astuple`/… or an access of `.__dict__`/`.__getattribute__`. These read a
    field by computed name, which is how the literal `.payload` scan was walked
    past."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            leaf = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if leaf in REFLECTION_CALLS:
                hits.append((node.lineno, leaf))
        elif isinstance(node, ast.Attribute) and node.attr in REFLECTION_ATTRS:
            hits.append((node.lineno, node.attr))
    return hits


def test_i16_only_the_gate_and_the_store_reach_a_payload():
    """The chokepoint, across the whole package. A module that is neither the
    gate nor the store reaching a payload has walked past the one door."""
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
        "direct .payload read is the gate wired to nothing."
    )


def test_i16_the_surface_layer_does_not_reflect():
    """The audit's finding, closed as a property rather than a spelling. A
    surface renders what it is handed and never reaches around the gate — so in
    `homestead/app/` there is no getattr, no vars, no __dict__, no astuple/
    asdict/fields, no attrgetter. Those are the by-computed-name reads that made
    `getattr(record, "payload")` invisible to the literal scan; here they are a
    build failure whatever they name, because a surface that needs one is a
    surface reaching for a payload it was not handed."""
    offenders = []
    for mod in _modules():
        if not _is_surface(mod):
            continue
        for lineno, how in _reflection_reaches(ast.parse(mod.read_text("utf-8"))):
            offenders.append(f"{mod.relative_to(PKG.parent)}:{lineno} {how}")
    assert not offenders, (
        f"the surface layer reflects at {offenders}. A surface renders "
        "Served.value and AmbientRow.text; reflection is how a payload is read "
        "without naming it, and the audit proved getattr(record, 'payload') "
        "reached a sealed datum while passing the literal scan. No reflection "
        "on a surface — ask serve()."
    )


def test_i16_the_surface_layer_reaches_no_payload():
    """The plan's original words, kept as their own named check for the surface
    layer, where the failure would actually ship."""
    offenders = []
    for mod in _modules():
        if not _is_surface(mod):
            continue
        for lineno in _payload_reaches(ast.parse(mod.read_text("utf-8"))):
            offenders.append(f"{mod.relative_to(PKG.parent)}:{lineno}")
    assert not offenders, (
        f"the surface layer reaches a payload directly at {offenders}."
    )


def _scan_surface_dir(app_dir: Path) -> list[str]:
    """The real package scan, pointed at a directory: both the payload reach and
    the reflection ban, as the two surface-layer tests apply them together."""
    offenders = []
    for mod in sorted(app_dir.rglob("*.py")):
        tree = ast.parse(mod.read_text("utf-8"))
        for lineno in _payload_reaches(tree):
            offenders.append(f"{mod.name}:{lineno} .payload")
        for lineno, how in _reflection_reaches(tree):
            offenders.append(f"{mod.name}:{lineno} {how}")
    return offenders


def test_i16_regression_every_bypass_the_audit_found_is_caught(tmp_path):
    """The audit's eight bypasses, planted in a surface file and run through the
    real scan — not the helper over a string. Each must be caught, or the guard
    is passing only because `app/` happens to be clean today. This is the test
    whose weakness let finding #1 through: it now exercises the enforcement, on
    every form, in a surface path."""
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    bypasses = [
        "record.payload",
        'getattr(record, "payload")',
        'getattr(record, "pay" + "load")',
        'record.__dict__["payload"]',
        'vars(record)["payload"]',
        "dataclasses.astuple(record)[1]",
        'dataclasses.asdict(record)["payload"]',
        'operator.attrgetter("payload")(record)',
        "[getattr(record, f.name) for f in dataclasses.fields(record)]",
    ]
    for i, expr in enumerate(bypasses):
        (app_dir / f"leak_{i}.py").write_text(
            "import dataclasses, operator\n"
            f"def draw(record):\n    return {expr}\n"
        )
    offenders = _scan_surface_dir(app_dir)
    # every planted file must raise at least one offence
    caught_files = {o.split(":")[0].split(" ")[0] for o in offenders}
    missed = [
        f"leak_{i}.py" for i in range(len(bypasses))
        if f"leak_{i}.py" not in caught_files
    ]
    assert not missed, (
        f"these audit bypasses passed the surface scan: {missed}. Each is a way "
        "to read a payload a surface was not handed; none may be invisible."
    )


def test_i16_serve_is_the_obvious_path():
    """The doors are exported and callable, and what they hand back is *not* a
    payload. A surface that only ever sees `Served.value` and `AmbientRow.text`
    has no expression that reaches a withheld datum — I-35's structural argument,
    generalized to the chokepoint."""
    from homestead.keep import rungs
    from homestead.keep.rungs import AmbientRow, Served

    for door in ("serve", "serve_all", "ambient_rows"):
        assert door in rungs.__all__, f"{door} is a door and must be exported"
        assert callable(getattr(rungs, door))

    assert "value" in Served.__dataclass_fields__
    assert "payload" not in Served.__dataclass_fields__
    assert set(AmbientRow.__dataclass_fields__) == {"rung", "text"}
