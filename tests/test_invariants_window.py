"""Bite 4 of docs/PLAN-first-runnable.md — the two S1 surfaces, list and detail.

The first thing in the package that *renders*. `Window` is the surface, and it is
deliberately display-agnostic: it holds the state (cover / list / detail) and the
rows or the served datum for the current state, and a view (tkinter, in
`view.py`) draws them. That split is I-29 — *the surface layer holds no domain
logic* — taken literally: `Window` composes through `serve` and calculates
nothing, so there is no rung arithmetic in it to drift from the gate.
law-gazelle's 1,296-line `app.py` is what the other choice looks like.

Two invariants meet here:

* **I-21 — no auto-render on start.** A fresh `Window` rests on the cover and
  shows no record. The queue is not drawn before a human asks; an app that
  renders on mount has shipped F-5 once.
* **the crossing — the list cannot carry what the detail can.** The list is
  `S1_LIST`, ceiling `L3`: it shows `L1`-`L3` payloads, the *derived* form for
  `L4`, and nothing at all for `L5`. The detail is `S1_DETAIL`, ceiling `L4`, and
  opening it is the purpose declaration — so it may show the `L4` payload.
  Neither ever shows an `L5`.

A `Row` carries a **reference** (the record's key), never a payload — so the list
is interactive (a click opens an item by ref) without a datum ever living on the
surface. `Window` reaches no `.payload`; the chokepoint
(`test_invariants_chokepoint.py`) makes that a build failure.
"""
from __future__ import annotations

from homestead.app.window import Row, Window
from homestead.keep.rungs import Classified, Disposition, Rung, Served


# A custody matter with a field on every relevant rung, each paired with its
# reference (matter, item_type, item_id). The derived forms are the human's
# re-identification judgement (the pack does not author them); L1 and L5 need
# none. The payloads are the strings that must not leak upward.
COURTHOUSE = Classified(Rung.L1, "Dept 4, Superior Court of California")
CASE_NUMBER = Classified(Rung.L3, "FL-2026-00123", derived="A case number is on file")
CHILD_NAME = Classified(Rung.L4, "A.R.", derived="A minor child is named in this matter")
SSN = Classified(Rung.L5, "xxx-xx-1234")

COURTHOUSE_REF = ("custody", "courthouse", "main")
CASE_REF = ("custody", "case_number", "fl-2026-00123")
CHILD_REF = ("custody", "child_name", "ar")
SSN_REF = ("custody", "ssn", "primary")

MATTER = [
    (COURTHOUSE_REF, COURTHOUSE),
    (CASE_REF, CASE_NUMBER),
    (CHILD_REF, CHILD_NAME),
    (SSN_REF, SSN),
]

L4_PAYLOAD = CHILD_NAME.payload   # "A.R." — must never appear in the list
L5_PAYLOAD = SSN.payload          # must never appear anywhere


# ── promoted from test_invariants_pending.py ─────────────────────────────────

def test_i21_the_app_does_not_render_on_start():
    """A fresh window rests on the cover. The record is not drawn before a human
    asks (F-5)."""
    assert Window().state == "cover"


def test_the_resting_state_holds_no_record():
    """I-21, one layer deeper: not merely 'state == cover' but that there is
    nothing to draw — no rows, no open detail. A cover that already held the
    rows and merely hid them would leak them to the first bug in the view."""
    w = Window()
    assert w.rows == []
    assert w.detail is None


# ── the list · S1_LIST, ceiling L3 ───────────────────────────────────────────

def test_the_list_renders_low_rungs_and_derives_the_l4():
    """The plan's 'done when', on the list side: L1 and L3 payloads render, the
    L4 shows its derived form, and the L5 is not there at all."""
    w = Window()
    rows = w.open_list(MATTER)

    assert w.state == "list"
    assert all(isinstance(r, Row) for r in rows)
    texts = [r.text for r in rows]

    assert "Dept 4, Superior Court of California" in texts   # L1 payload
    assert "FL-2026-00123" in texts                          # L3 payload
    assert "A minor child is named in this matter" in texts  # L4 derived form
    assert L4_PAYLOAD not in texts, "the L4 payload rendered on the ambient list"
    assert L5_PAYLOAD not in texts, "the L5 payload rendered on the ambient list"


def test_the_list_drops_the_l5_without_a_trace():
    """serve drops denials rather than marking them (product decision 2): four
    records in, three rows out, and no placeholder, count, or gap that
    reconstructs the sealed one. The existence of a refusal is itself L5."""
    rows = Window().open_list(MATTER)
    assert len(rows) == 3
    assert all(L5_PAYLOAD not in r.text for r in rows)
    assert all(r.rung is not Rung.L5 for r in rows)
    assert SSN_REF not in {r.ref for r in rows}


def test_a_row_carries_a_reference_not_a_payload():
    """A row is a reference, a rung, and served text — so the list is openable
    without a payload on it. The L4 row shows the derived form and carries the
    ref that opens the real thing; the payload is nowhere in the row."""
    rows = {r.ref: r for r in Window().open_list(MATTER)}
    child_row = rows[CHILD_REF]
    assert child_row.rung is Rung.L4
    assert child_row.text == "A minor child is named in this matter"
    assert child_row.text != L4_PAYLOAD


# ── the detail · S1_DETAIL, ceiling L4 ───────────────────────────────────────

def test_the_detail_shows_the_l4_payload():
    """The plan's 'done when', on the detail side: opening an item by its ref
    shows the L4 payload itself. Opening it is the purpose declaration."""
    w = Window()
    w.open_list(MATTER)
    served = w.open_detail(CHILD_REF)

    assert w.state == "detail"
    assert isinstance(served, Served)
    assert served.disposition is Disposition.RENDER
    assert served.value == "A.R."


def test_the_detail_still_refuses_the_l5():
    """L5 has no override anywhere — not even in the pane the operator opened
    (I-13). The detail denies it: nothing rendered, and value is None because the
    payload is not in the object, not because it was blanked."""
    w = Window()
    w.open_list(MATTER)
    served = w.open_detail(SSN_REF)
    assert served.disposition is Disposition.DENY
    assert served.value is None
    assert served.value != L5_PAYLOAD


def test_closing_returns_to_the_cover():
    """The reveal does not persist. Closing drops back to the cover and lets go
    of the working set — the precondition for I-32's timeout, which a later bite
    adds on top of this."""
    w = Window()
    w.open_list(MATTER)
    w.open_detail(CHILD_REF)
    w.close()
    assert w.state == "cover"
    assert w.rows == []
    assert w.detail is None


# ── I-29 · the surface calculates nothing ────────────────────────────────────

def test_the_window_holds_no_rung_arithmetic():
    """I-29: the surface composes and renders; anything calculating lives in
    homestead.keep. If window.py started comparing rungs or reaching into the
    ceiling table, a second copy of the crossing would exist to drift from the
    first. Scanned structurally rather than trusted."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent
           / "homestead" / "app" / "window.py").read_text("utf-8")
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"_CEILING", "_ORDER", "_NEEDS_DERIVED"}, (
                "window.py reaches into the gate's private crossing tables — "
                "the surface must ask serve()/decide(), not re-derive the ceiling"
            )
        if isinstance(node, ast.Name):
            assert node.id not in {"_CEILING", "_ORDER", "may_render", "decide"}, (
                "window.py names a decision primitive directly; a surface routes "
                "through serve(), which is the one door"
            )
