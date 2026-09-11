"""Grep guards for the sentences the build moved past — X7-drift-engine.

This project's own rule, applied to prose instead of code: a scan that has
never fired has not been shown to check anything, so every guard below plants
its own violation and proves the check catches it, the same way
`test_invariants_registry.py::test_the_stale_claim_check_fires_on_a_planted_phrase`
does for the "only custody is registered" guard. `_strikethrough.live()` is
reused rather than re-implemented, for the reason its own docstring gives:
two copies of "what counts as a live claim" is the exact way to drift.

**What this file is not.** It is not a re-audit of every doc in `docs/` —
most of the known suspects from the affairs build plan's drift-inventory list
(bankruptcy "unbuilt", the `homestead-law` console-script collision, the PAT
sentence in `releasing.md`, `UNBUILT` naming built modules, the "no
encryption"/"no public reader" `IntegrityLog` claims) were already corrected
by the bites that built the thing they described, each with its own guard in
its own file (`test_invariants_registry.py`, `test_invariants_release.py`,
`test_invariants_pending.py`, `test_invariants_sealed.py`,
`test_invariants_logs.py`). Re-guarding those here would be a second copy of
a check that already exists, which is the failure this module's docstring
warns against. What follows is the drift this sweep actually found still
live in the tree at `ff33787`: the Nestor pin description fell behind
`pyproject.toml`'s own bump in three places, and a `PHASE2-SURFACES.md`
paragraph never got the annotation `docs/DECISION-purpose-sync.md` explicitly
left for "the operator's or the ratifying hand" to add.
"""
from __future__ import annotations

from pathlib import Path

from _strikethrough import live

ROOT = Path(__file__).resolve().parent.parent

NESTOR_SEAM_PY = ROOT / "homestead" / "keep" / "nestor_seam.py"
TEST_NESTOR_SEAM_PY = ROOT / "tests" / "test_invariants_nestor_seam.py"
SEAM_CROSS_REF = ROOT / "docs" / "seam-pattern-cross-reference.md"
PHASE2_SURFACES = ROOT / "docs" / "PHASE2-SURFACES.md"


def _live_text_for(path: Path) -> str:
    """The same reading `test_invariants_registry.py` uses: struck spans
    gone, whitespace flattened — so a hard-wrapped sentence and a
    strikethrough-preserved one are both read the way a person reads them."""
    return live(path.read_text("utf-8"))


# ── guard 1..4: the Nestor pin, described three ways in three files ─────────
#
# `pyproject.toml`'s `entity` extra moved from a VCS tag (`v0.2.0`) to a PyPI
# release range (`nestor-meaning>=0.11.0,<1.0`) before this bite, and
# `homestead/keep/nestor_seam.py`'s own opening docstring already said so
# ("Landed at `nestor` pin `v0.2.0`, bumped to `nestor-meaning>=0.11.0`").
# Three *other* sentences in the tree still described the pin as a live tag,
# each written before the bump and never touched by it: the seam's own
# "NESTOR IS PINNED TO A TAG" section, that file's test's module docstring,
# and two sentences in `docs/seam-pattern-cross-reference.md` (prose and a
# table cell). All four are corrected by this bite; these are the regression
# guards that keep the correction from drifting back.

_STALE_NESTOR_PIN_PHRASES = {
    NESTOR_SEAM_PY: "NESTOR IS PINNED TO A TAG.",
    TEST_NESTOR_SEAM_PY: "pinned to the tag `v0.2.0`, never a required",
    SEAM_CROSS_REF: "Pinned at `v0.2.0`, a tag (fleet rule R14).",
}

#: The table-cell phrasing is checked separately because it is short enough
#: to collide with legitimate historical prose elsewhere in the same file
#: (`seam-pattern-cross-reference.md` still narrates "At the pinned `v0.2.0`"
#: as dated history, correctly) — keeping it as its own exact string means
#: this guard cannot be satisfied by accident from an unrelated correction.
_STALE_NESTOR_PIN_TABLE_CELL = "| Pin | `v0.2.0`, tag |"


def test_the_nestor_pin_is_not_described_as_a_tag_outside_history():
    """Each of the three files, read live (struck spans removed), must not
    assert the tag pin as a current fact. The dated narrations that mention
    `v0.2.0` as history (`nestor_seam.py`'s own "Landed at..." and "At the
    pinned `v0.2.0`..." sentences) are deliberately not in this dict — they
    are true statements about the past, not stale claims about the present,
    and a guard that flagged them would be asking prose to stop describing
    its own history."""
    offenders = {
        str(path.relative_to(ROOT)): phrase
        for path, phrase in _STALE_NESTOR_PIN_PHRASES.items()
        if phrase in _live_text_for(path)
    }
    assert not offenders, (
        f"stale Nestor-pin claims outside a struck-through span: {offenders}. "
        "The extra moved to nestor-meaning>=0.11.0,<1.0 on PyPI; see "
        "pyproject.toml's `entity` extra and nestor_seam.py's own docstring."
    )
    assert _STALE_NESTOR_PIN_TABLE_CELL not in _live_text_for(SEAM_CROSS_REF), (
        f"the pin table in {SEAM_CROSS_REF.relative_to(ROOT)} still asserts "
        "the retired v0.2.0 tag live"
    )


def test_the_nestor_pin_guard_fires_on_a_planted_stale_sentence(tmp_path):
    """A scan that has never fired has not been shown to check anything.
    Each of the four stale sentences is planted into a temp copy — once
    live, once struck-through — and the checker must catch the live one and
    ignore the struck one, exactly as `_stale_hits`'s own tests do for the
    registry guard."""
    for phrase in (*_STALE_NESTOR_PIN_PHRASES.values(), _STALE_NESTOR_PIN_TABLE_CELL):
        live_copy = tmp_path / "live.md"
        live_copy.write_text(f"Some context.\n{phrase}\nMore context.\n", "utf-8")
        assert phrase in _live_text_for(live_copy), (
            f"planted phrase {phrase!r} was not detected live — the checker "
            "is not actually reading what it claims to"
        )

        struck_copy = tmp_path / "struck.md"
        struck_copy.write_text(f"Some context.\n~~{phrase}~~\nMore context.\n", "utf-8")
        assert phrase not in _live_text_for(struck_copy), (
            f"a struck-through {phrase!r} was still read as live — history "
            "must not trip this guard"
        )


# ── guard 5: PHASE2-SURFACES.md names the eighth Purpose member ─────────────
#
# `docs/DECISION-purpose-sync.md` § *Doc sites* found this exact gap and
# explicitly declined to close it itself: "Same treatment
# `docs/DECISION-compelled-disclosure.md` gave the eleven `PHASE2-SURFACES.md`
# lines that said 'six' — they are the operator's or the ratifying hand's to
# annotate, not this bite's to rewrite." X7-drift is that hand. The fix is an
# appended, dated annotation (archive-don't-delete: the six/seven narrative
# stays exactly as written), so the guard checks for the annotation's
# presence rather than the old count's absence — the old count is supposed
# to still be there.

_EIGHTH_MEMBER_ANNOTATION = "member, `SYNC`, was ratified 2026-09-11"
_RENAMED_TEST_ANNOTATION = "test_the_purpose_enum_is_the_set_that_was_ratified"


def test_phase2_surfaces_names_the_eighth_purpose_member():
    """The two present-tense gaps this bite found: the doc's `Purpose`
    summary row stopped counting at seven, and its narrative section still
    cites the pre-rename test name with no pointer to the current one. Both
    are annotated in place, per `DECISION-purpose-sync.md`'s instruction, and
    the original dated text stays — this only checks that the annotation was
    actually added, not that the old text was removed."""
    text = _live_text_for(PHASE2_SURFACES)
    assert _EIGHTH_MEMBER_ANNOTATION.lower() in text.lower(), (
        f"{PHASE2_SURFACES.relative_to(ROOT)} still stops at seven Purpose "
        "members with no annotation naming SYNC as the eighth"
    )
    assert _RENAMED_TEST_ANNOTATION in text, (
        f"{PHASE2_SURFACES.relative_to(ROOT)} cites the pre-rename test name "
        "with no annotation pointing at its current name"
    )


def test_the_eighth_member_guard_fires_on_a_planted_omission(tmp_path):
    """Planted the way the positive checks above are planted, just inverted:
    a temp copy carrying the OLD, unannotated paragraph (the six/seven count
    and the dead test-name citation, with no correction appended) must fail
    both assertions the real check makes — proving the guard would have
    caught this drift had it existed before the doc went stale."""
    stale = tmp_path / "phase2_stale.md"
    stale.write_text(
        "| `Purpose` | *(2026-08-05)* The closed set — six as ratified, seven "
        "once `COMPELLED_DISCLOSURE` was authorised the same day. |\n\n"
        "`test_the_purpose_enum_is_the_six_that_were_published` pins the set, "
        "so a seventh member is a decision someone has to make on purpose.\n",
        "utf-8",
    )
    text = _live_text_for(stale)
    assert _EIGHTH_MEMBER_ANNOTATION.lower() not in text.lower()
    assert _RENAMED_TEST_ANNOTATION not in text
