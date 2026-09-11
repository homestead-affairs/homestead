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
warns against. **Corrected on audit, 2026-09-11:** two of the names in that
list did not belong in it. The README's IntegrityLog row was corrected by
*this* bite's own docs commit and so had no guard anywhere, and
`test_invariants_pending.py`'s "I-39 waits on `E4-postgres-fleet`" was still
live three releases after it landed. Both are guarded below, by the exact
sentence, planted. What follows is the drift this sweep actually found still
live in the tree at `ff33787`: the Nestor pin description fell behind
`pyproject.toml`'s own bump in three places, and a `PHASE2-SURFACES.md`
paragraph never got the annotation `docs/DECISION-purpose-sync.md` explicitly
left for "the operator's or the ratifying hand" to add.
"""
from __future__ import annotations

import ast
import re
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
        path.relative_to(ROOT).as_posix(): phrase
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


# ── guard 6..7: sentences this bite corrected, and the archive rule ─────────
#
# Two exact sentences that were live in the tree and are not any more. Both
# are kept *struck through*, never deleted, so the guard has two halves: the
# sentence must be gone from the live reading, and still present in the raw
# text. A correction that deleted the original would pass the first half and
# lose the record, which is the other way this house style fails.

README_MD = ROOT / "README.md"
PENDING_PY = ROOT / "tests" / "test_invariants_pending.py"

_CORRECTED_SENTENCES = {
    README_MD: "It is **not** encrypted and does **not** withstand someone who "
               "edits both the log and its anchor",
    PENDING_PY: "I-39 waits on",
}


def test_the_corrected_sentences_are_struck_and_not_deleted():
    """The README row that described `IntegrityLog` as unencrypted and
    forgeable went stale the day E5 (0.10.0) and E6 (0.11.0) each closed half
    of it for a log that opts in; the pending file's note that I-39 was still
    waiting on `E4-postgres-fleet` went stale when that bite shipped as
    0.9.0 and its test was promoted to `test_invariants_fleet.py`. Neither is
    a live claim now, and neither has been deleted."""
    still_claimed = {
        path.relative_to(ROOT).as_posix(): phrase
        for path, phrase in _CORRECTED_SENTENCES.items()
        if phrase in _live_text_for(path)
    }
    assert not still_claimed, (
        f"these corrected sentences are live again: {still_claimed}"
    )
    deleted = {
        path.relative_to(ROOT).as_posix(): phrase
        for path, phrase in _CORRECTED_SENTENCES.items()
        if phrase not in live(path.read_text("utf-8").replace("~~", ""))
    }
    assert not deleted, (
        f"these corrections deleted the sentence they corrected instead of "
        f"striking it: {deleted}. History is struck through, never removed."
    )


def test_the_corrected_sentence_guard_fires_on_a_planted_revival(tmp_path):
    """A scan that has never fired has not been shown to check anything: each
    corrected sentence, written back live into a temp copy, must be caught,
    and the same sentence struck through must not."""
    for phrase in _CORRECTED_SENTENCES.values():
        revived = tmp_path / "revived.md"
        revived.write_text(f"Context.\n{phrase} — as it used to say.\n", "utf-8")
        assert phrase in _live_text_for(revived)

        struck = tmp_path / "struck.md"
        struck.write_text(f"Context.\n~~{phrase}~~ (struck 2026-09-11)\n", "utf-8")
        assert phrase not in _live_text_for(struck)


# ── guard 8: a doc that pins a test by name and location names a real one ───
#
# `docs/DECISION-compelled-disclosure.md` cited three tests by name *and*
# file, and the change it argued for renamed all three. A reader following
# the pointer finds a different test, or none. Narration of a dead name is
# fine and deliberate here — this repo's docs quote the names things used to
# have on purpose — so the guard fires only on a citation that also claims a
# **location**, which is a pointer rather than a memory. `docs/audits/` is
# out of scope for the same reason: an audit report is a dated artefact and
# is never edited.

_DOC_TEST_NAME = re.compile(r"`(test_[a-z0-9_]+)`")
_DOC_TEST_LOCATION = re.compile(r"`(?:tests/)?(test_[a-z0-9_]+\.py):\d+`")

#: How far past a cited name the location may sit for the two to count as one
#: pointer. Short on purpose: one wrapped line, not a paragraph — the doc
#: sentence "the defect the last brief renamed `X` for" sits a hundred or so
#: characters *after* an unrelated location and must not be read as pinning it.
_POINTER_WINDOW = 80


def _test_names_defined_in_tests() -> dict[str, set[str]]:
    """`{test function name: {the files that define it}}` for the whole
    suite."""
    defined: dict[str, set[str]] = {}
    for path in sorted((ROOT / "tests").glob("*.py")):
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                defined.setdefault(node.name, set()).add(path.name)
    return defined


def _dangling_test_pointers(text: str, defined: dict[str, set[str]]) -> list[str]:
    """Every `` `test_x` `` in `text` that is followed, within
    `_POINTER_WINDOW` characters, by a `file.py:line` — and that names no
    test, or no test in the file it points at. The *line* is not checked: a
    line number drifts on every edit above it, and a guard that churned on
    every unrelated edit is a guard somebody deletes."""
    dangling = []
    for match in _DOC_TEST_NAME.finditer(text):
        name = match.group(1)
        window = text[match.end() : match.end() + _POINTER_WINDOW]
        location = _DOC_TEST_LOCATION.search(window)
        if not location:
            continue
        files = defined.get(name)
        if not files:
            dangling.append(f"{name} -> {location.group(1)} (no such test)")
        elif location.group(1) not in files:
            dangling.append(
                f"{name} -> {location.group(1)} (defined in {sorted(files)})"
            )
    return dangling


def test_no_doc_pins_a_test_name_that_no_longer_exists():
    """A citation that names a test *and* a file is a pointer a reader is
    meant to follow. Three of them in `DECISION-compelled-disclosure.md`
    pointed at names the change that document argued for had renamed away;
    they are struck in place with the current name beside them, which is what
    makes this pass."""
    defined = _test_names_defined_in_tests()
    dangling = {}
    for path in sorted(ROOT.glob("docs/*.md")):
        hits = _dangling_test_pointers(_live_text_for(path), defined)
        if hits:
            dangling[path.relative_to(ROOT).as_posix()] = hits
    assert not dangling, (
        f"these docs point at tests that are not where they say: {dangling}. "
        "Strike the dead name and put the live one beside it — the pointer is "
        "the part that has to be true, the history is the part that stays."
    )


def test_the_dangling_pointer_guard_fires_on_a_planted_citation():
    """Planted three ways, because two of them are the ways it must NOT fire:
    a renamed test cited with a location is caught; the same dead name
    narrated with no location is not (this repo's docs quote old names on
    purpose); and a live name cited at the wrong file is caught, because a
    pointer into the wrong file is as dangling as a pointer to nothing."""
    defined = {"test_the_real_one": {"test_invariants_surfaces.py"}}

    caught = _dangling_test_pointers(
        "`test_the_renamed_one` (`tests/test_invariants_surfaces.py:647`) pins it.",
        defined,
    )
    assert caught == ["test_the_renamed_one -> test_invariants_surfaces.py "
                      "(no such test)"]

    assert _dangling_test_pointers(
        "the defect this suite renamed `test_the_renamed_one` for", defined
    ) == [], "a name narrated without a location is history, not a pointer"

    wrong_file = _dangling_test_pointers(
        "`test_the_real_one` (`tests/test_purpose_corpus.py:12`) pins it.", defined
    )
    assert wrong_file == ["test_the_real_one -> test_purpose_corpus.py "
                          "(defined in ['test_invariants_surfaces.py'])"]

    # And the collector the real run depends on, fired against a name it must
    # find and one it must not: a dangling-pointer guard whose idea of "the
    # tests that exist" came back empty would pass every doc in the repo.
    real = _test_names_defined_in_tests()
    assert real.get("test_no_doc_pins_a_test_name_that_no_longer_exists") == {
        "test_docs_drift.py"
    }
    assert "test_a_planted_name_defined_nowhere_at_all" not in real


# ── guard 9: PHASE1-DATES' rule table is the one in keep/dates.py ───────────
#
# `docs/PHASE1-DATES.md` § *US-NM and US-OR* carries a four-column status
# table — forward, short period, backward, mail — and a `short_period_max`
# per row. Those are the numbers a reader decides whether to trust a computed
# deadline on, and nothing checked them against `RULES`. The day someone
# reads Rule 1-006 NMRA and flips `short_period_status` to VERIFIED, this
# fails until the table says so too.

PHASE1_DATES = ROOT / "docs" / "PHASE1-DATES.md"

_RULE_ROW = re.compile(r"^\| `(US-[A-Z]{2})` \|(.*)\|\s*$", re.MULTILINE)
_SHORT_MAX = re.compile(r"short_period_max=(\d+)")


def _documented_rule_rows(text: str) -> dict[str, dict]:
    """`{jurisdiction: {"short_period_max": int|None, "<branch>": "VERIFIED"|
    "UNCERTAIN"}}` read off the table. A cell that says UNCERTAIN anywhere is
    UNCERTAIN — "VERIFIED-secondary, ... UNCERTAIN" is a refusal, and reading
    it the other way round is the only mistake this parser could make that
    would matter."""
    rows: dict[str, dict] = {}
    for match in _RULE_ROW.finditer(text):
        cells = [c.strip() for c in match.group(2).split("|")]
        if len(cells) != 4:
            continue
        forward, short, backward, mail = cells
        short_max = _SHORT_MAX.search(short)
        rows[match.group(1)] = {
            "short_period_max": int(short_max.group(1)) if short_max else None,
            "forward": "UNCERTAIN" if "UNCERTAIN" in forward else "VERIFIED",
            "short": "UNCERTAIN" if "UNCERTAIN" in short else "VERIFIED",
            "backward": "UNCERTAIN" if "UNCERTAIN" in backward else "VERIFIED",
            "mail": "UNCERTAIN" if "UNCERTAIN" in mail else "VERIFIED",
        }
    return rows


def _rule_table_disagreements(documented: dict[str, dict]) -> list[str]:
    """Every way the documented table and `keep/dates.py`'s `RULES` differ."""
    from homestead.keep.dates import RULES

    said = set(documented)
    real = {j for j in RULES if j != "US-federal"}
    problems = [f"documented but not in RULES: {sorted(said - real)}"] if said - real else []
    if real - said:
        problems.append(f"in RULES but undocumented: {sorted(real - said)}")
    for name in sorted(said & real):
        rule, row = RULES[name], documented[name]
        if rule.short_period_max != row["short_period_max"]:
            problems.append(
                f"{name}: doc says short_period_max="
                f"{row['short_period_max']}, RULES says {rule.short_period_max}"
            )
        for branch, status in (
            ("forward", rule.status),
            ("short", rule.short_period_status),
            ("backward", rule.backward_status),
            ("mail", rule.mail_status),
        ):
            if status.name != row[branch]:
                problems.append(
                    f"{name}: doc says {branch} is {row[branch]}, "
                    f"RULES says {status.name}"
                )
    return problems


def test_phase1_dates_rule_table_is_the_table_in_keep_dates():
    problems = _rule_table_disagreements(
        _documented_rule_rows(PHASE1_DATES.read_text("utf-8"))
    )
    assert not problems, (
        f"{PHASE1_DATES.name} describes a rule table this engine does not "
        f"have: {problems}. A status in a doc is what an operator decides "
        "whether to trust a deadline on."
    )


def test_the_rule_table_guard_fires_on_a_planted_status_flip():
    """Two plants and a control: a row whose short-period branch the doc
    calls VERIFIED while `RULES` refuses it, a row whose threshold drifted,
    and a jurisdiction in `RULES` with no row at all — each named, and the
    real table read through the same parser coming back clean."""
    from homestead.keep.dates import RULES

    real = _documented_rule_rows(PHASE1_DATES.read_text("utf-8"))
    assert set(real) == {j for j in RULES if j != "US-federal"} and not \
        _rule_table_disagreements(real)

    flipped = {name: dict(row) for name, row in real.items()}
    flipped["US-NM"]["short"] = "VERIFIED"
    assert any("short is VERIFIED" in p for p in _rule_table_disagreements(flipped))

    drifted = {name: dict(row) for name, row in real.items()}
    drifted["US-OR"]["short_period_max"] = 5
    assert any("short_period_max=5" in p for p in _rule_table_disagreements(drifted))

    missing = {name: dict(row) for name, row in real.items() if name != "US-NM"}
    assert any("undocumented: ['US-NM']" in p for p in _rule_table_disagreements(missing))
