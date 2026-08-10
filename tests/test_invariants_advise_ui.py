"""The advisory content matcher, surfaced — `app/advisories`, the display model.

`keep/advise` decides; `Sidecar.advise` runs it read-only over a stored record;
`app/advisories.advisory_lines` is the last, thin step: it turns the `Advisory`
objects the store hands back into lines a pane can draw, and returns *nothing* to
draw when there is nothing to say. The view (`view.show_detail`) draws those lines
as a muted note under the record — never a dialog, never a block. This file holds
the display model to the same three conditions the matcher is built to, because a
surface is exactly where the leak and the false clean-bill would ship.

The tkinter drawing itself is not unit-tested here (it opens no display on a
headless box); `python -m homestead.app --smoke` imports it. What is tested is the
display *model* — the function that decides what text, if any, a pane shows.
"""
from __future__ import annotations

import pytest

from homestead.app import advisories
from homestead.keep.record import Sidecar
from homestead.keep.rungs import Classified, Rung

#: An SSN written the way people write it. Declared L4 (a note), but shaped L5 —
#: the exact `notes = L4` gap the matcher exists to catch. The digits are what the
#: display must never echo (I-15).
_SSN = "123-45-6789"
_MISDECLARED = f"Parent disclosed SSN {_SSN} at the 08-01 hearing; follow up."


def _seed_misdeclared(store: Sidecar) -> tuple[str, str, str]:
    ref = ("custody", "notes", "primary")
    store.put(*ref, Classified(Rung.L4, _MISDECLARED, "An operator note is on file"),
              overwrite=True)
    return ref


def _seed_clean(store: Sidecar) -> tuple[str, str, str]:
    ref = ("custody", "courthouse", "primary")
    store.put(*ref, Classified(Rung.L1, "Dept 4, Superior Court, County of Marin"),
              overwrite=True)
    return ref


def test_misdeclared_record_yields_a_line_naming_the_category_and_the_rungs(
    tmp_path, monkeypatch
):
    """An SSN in an L4 note surfaces one advisory line, and the line names the
    category and both rungs — the same reference the operator would need to act on
    it (raise the rung), and no more."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    ref = _seed_misdeclared(store)

    lines = advisories.advisory_lines(store, ref)

    assert lines, "a misdeclared record must surface an advisory line"
    line = "\n".join(lines)
    assert "ssn" in line                 # the category
    assert "L5" in line and "L4" in line  # the implied rung and the declared one


def test_the_line_never_echoes_the_matched_content(tmp_path, monkeypatch):
    """I-15 at the surface: the advisory carries the category and the rungs, never
    the datum it matched. A line that quoted the SSN would be the leak the whole
    matcher exists to prevent — so no digit of it may appear in what is drawn."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    ref = _seed_misdeclared(store)

    line = "\n".join(advisories.advisory_lines(store, ref))

    assert _SSN not in line
    # and no fragment of it either — not the raw digits, not a run of them.
    assert "123456789" not in line
    for chunk in ("123", "456", "6789"):
        assert chunk not in line


def test_a_clean_record_is_silent(tmp_path, monkeypatch):
    """A record whose content matches no pattern produces nothing to draw — an
    empty result, which the pane renders as *nothing*."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    ref = _seed_clean(store)

    assert advisories.advisory_lines(store, ref) == ()


def test_silence_is_not_a_clean_bill(tmp_path, monkeypatch):
    """Condition 3: absence of advisories is *no pattern matched*, never a safety
    claim. A clean record emits no reassuring string — no "clean", no "ok", no "no
    issues", no check mark — because a false negative is the dangerous direction
    and the surface must not dress it up as a verdict (I-11's posture)."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    ref = _seed_clean(store)

    line = "".join(advisories.advisory_lines(store, ref)).lower()
    for reassurance in ("clean", "no issues", "no advisories", "ok", "safe", "✓", "all good"):
        assert reassurance not in line


def test_advisory_lines_never_blocks_or_raises(tmp_path, monkeypatch):
    """Advisory, never a gate: the display model reports and returns; it raises
    nothing on a misdeclared record. A surface step that could refuse would have
    relocated a human judgement into a pattern list (condition 2)."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    ref = _seed_misdeclared(store)

    # No exception on the flagged record; it is advisory all the way out.
    result = advisories.advisory_lines(store, ref)
    assert isinstance(result, tuple)


def test_multiple_shapes_each_surface_a_line(tmp_path, monkeypatch):
    """A note holding two shapes above its rung surfaces a line for each — the
    display does not collapse or hide concerns, and still never echoes a datum."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    ref = ("custody", "notes", "primary")
    store.put(*ref, Classified(Rung.L1, "SSN 123-45-6789, reach at a@b.co"),
              overwrite=True)

    lines = advisories.advisory_lines(store, ref)
    joined = "\n".join(lines)

    assert len(lines) >= 2
    assert "ssn" in joined and "email" in joined
    assert "123-45-6789" not in joined and "a@b.co" not in joined
