"""I-1 … I-5 — the date type, the strict parser, and the counting rules.

Promoted out of `test_invariants_pending.py` when `homestead.keep.dates` landed,
which is what `test_pending_liveness` is for: the moment the module existed, the
pending file failed by name and these three could not stay xfailing.

The three promoted tests keep their original bodies and their original
docstrings. Everything after them is the rest of the phase — the counting rules
(I-4), the refusal set the parser is *for*, and one structural scan asserting
that no other module in this package has learned to parse a date.
"""
from __future__ import annotations

import ast
import importlib.metadata as md
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from homestead.keep.dates import (
    Deadline,
    UnparseableDate,
    court_days,
    parse_deadline,
)

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "homestead"


# ── promoted from test_invariants_pending.py ─────────────────────────────────

def test_i1_i2_strict_parse_or_refuse():
    """BUG-1: `_days_until` sliced to 10 chars before trying the long-form
    formats it declared, so every `"July 1, 2026"` returned None — and the
    failure was data-dependent, because `"May 5 2026"` is exactly 10."""
    from homestead.keep.dates import parse_deadline

    assert parse_deadline("2026-08-10").iso == "2026-08-10"
    assert parse_deadline("July 1, 2026").iso == "2026-07-01"
    assert parse_deadline("May 5, 2026").iso == "2026-05-05"
    for junk in ("2026", "June", "30", "next week", "", "not a date"):
        with pytest.raises(ValueError):
            parse_deadline(junk)


def test_i3_overdue_never_disagrees_with_days_until():
    """BUG-3: `overdue` string-compared the raw value while `days_until`
    parsed it, so one item carried days_until=-91 and overdue=False at once."""
    from homestead.keep.dates import Deadline

    d = Deadline.from_text("May 5, 2026", today="2026-08-04")
    assert d.days_until == -91
    assert d.overdue is True


def test_i5_no_free_text_dates_reach_storage():
    """BUG-4: snooze took free text and `is_snoozed` compared it to today as a
    string, so `"next week"` hid an item until 2099 and `"08/11/2026"` did
    nothing at all — and there was no un-snooze anywhere in the codebase."""
    from homestead.keep.dates import parse_deadline

    with pytest.raises(ValueError):
        parse_deadline("next week")


# ── I-1 · one type, and only this module makes one ───────────────────────────

def test_i1_a_deadline_is_immutable():
    d = parse_deadline("2026-08-10")
    with pytest.raises(Exception):
        d.date = date(2020, 1, 1)          # frozen dataclass
    with pytest.raises(Exception):
        d.reference = date(2020, 1, 1)


def test_i1_everything_derives_from_the_one_stored_date():
    """`iso`, `days_until` and `overdue` are computed, never stored.

    A second stored copy is what BUG-3 was: two fields describing one fact,
    written by two different mechanisms, free to disagree.
    """
    d = Deadline(date(2026, 8, 10), date(2026, 8, 4))
    assert d.iso == d.date.isoformat()
    assert d.days_until == (d.date - d.reference).days
    assert d.overdue is (d.days_until < 0)
    assert "iso" not in vars(d) and "days_until" not in vars(d)


def test_i1_a_datetime_is_not_a_deadline():
    """`datetime` is a `date` subclass, so an unguarded field accepts one and
    `.iso` silently grows a `T09:00:00`. A deadline is a court day."""
    with pytest.raises(UnparseableDate):
        Deadline(datetime(2026, 8, 10, 9, 0))
    with pytest.raises(UnparseableDate):
        Deadline(date(2026, 8, 10), datetime(2026, 8, 4, 9, 0))
    with pytest.raises(UnparseableDate):
        Deadline("2026-08-10")             # the string never becomes the value


def test_i1_two_deadlines_on_the_same_day_are_the_same_deadline():
    """The reckoning day is not part of the identity of a court date."""
    a = Deadline.from_text("2026-08-10", "2026-08-04")
    b = Deadline.from_text("Aug 10 2026", "2020-01-01")
    assert a == b and hash(a) == hash(b)
    assert sorted([parse_deadline("2026-09-01"), parse_deadline("2026-01-01")])[0].iso \
        == "2026-01-01"


def _modules() -> list[Path]:
    return sorted(p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts)


def test_i1_i2_nothing_else_in_this_package_parses_a_date():
    """One parser, at one edge — and it is not spelled `strptime`.

    `dateutil.parser.parse` is banned outright: it invents from today
    (`'2026'` → 2026-08-04, `'June'` → 2026-06-04), which is BUG-1 inverted —
    a confident wrong deadline instead of a lost one.

    `strptime` and `fromisoformat` are banned everywhere *including*
    `dates.py`, and that is not an accident of this phase. `%B` resolves month
    names through the process `LC_TIME` locale (CPython `_strptime` builds
    `f_month` from `calendar.month_name` and caches on
    `locale.getlocale(LC_TIME)`), so a `%B` format set is a per-machine format
    set. `date.fromisoformat` is the other half of BUG-2: it is strict, it
    raises, and law-gazelle called it on a string it had already truncated.
    Both are replaced by anchored patterns and an explicit English month table.
    """
    banned_calls = {"strptime", "fromisoformat"}
    offenders: list[str] = []
    for mod in _modules():
        tree = ast.parse(mod.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in banned_calls:
                    offenders.append(f"{mod.relative_to(ROOT)}:{node.lineno} {name}")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                if any(m.split(".")[0] == "dateutil" for m in mods):
                    offenders.append(f"{mod.relative_to(ROOT)}:{node.lineno} dateutil")
    assert not offenders, (
        "dates are parsed in homestead/keep/dates.py and nowhere else, and not "
        f"by strptime, fromisoformat or dateutil. Found: {offenders}"
    )


# ── I-2 · parse strictly or refuse ───────────────────────────────────────────

def test_i2_the_bug1_pair_cannot_disagree():
    """`"May 5 2026"` is exactly ten characters and `"May 5, 2026"` is eleven.

    That one character decided whether law-gazelle parsed the date or lost it.
    Here the two are the same deadline, because nothing is sliced.
    """
    assert (
        parse_deadline("May 5 2026").iso
        == parse_deadline("May 5, 2026").iso
        == parse_deadline("2026-05-05").iso
        == "2026-05-05"
    )


def test_i2_nothing_is_truncated_before_parsing():
    """A string with anything extra in it is refused, not trimmed to fit."""
    for s in (
        "2026-08-10 (per order)",
        "August 10, 2026 or sooner",
        "before 2026-08-10",
        "2026-08-10\n2026-08-11",
    ):
        with pytest.raises(UnparseableDate):
            parse_deadline(s)


def test_i2_accepts_the_verified_fixture_set():
    """The real values law-gazelle's data actually carried."""
    cases = {
        "2026-08-10": "2026-08-10",
        "2026-8-4": "2026-08-04",                       # unpadded, from real data
        "August 10, 2026": "2026-08-10",
        "July 1, 2026": "2026-07-01",
        "January 1, 2027": "2027-01-01",
        "May 5, 2026": "2026-05-05",
        "May 5 2026": "2026-05-05",
        "Aug 10, 2026": "2026-08-10",
        "Sept. 1st, 2026": "2026-09-01",
        "1 Jul 2026": "2026-07-01",
        "10 August 2026": "2026-08-10",
        "2026-07-01T00:00:00": "2026-07-01",
        "2026-08-10T09:00:00+00:00": "2026-08-10",
        "2026-08-10 09:00": "2026-08-10",
        "  2026-08-10  ": "2026-08-10",
    }
    for text, iso in cases.items():
        assert parse_deadline(text).iso == iso, text


def test_i2_refuses_the_verified_garbage_set():
    """Partial dates, natural language, and the shapes `dateutil` invents from."""
    for junk in (
        "TBD", "see order", "Monday", "2026", "June", "30", "on or before Aug 1",
        "12/31/2026 or sooner", "", "   ", "next week", "tomorrow", "not a date",
        "August 2026", "2026-08", "26-08-10", "May 5, 26", "Augsut 10, 2026",
        "20260810", "2026-W32-1", "0000-00-00",
    ):
        with pytest.raises(UnparseableDate):
            parse_deadline(junk)


def test_i2_refuses_slashed_numeric_dates_uniformly():
    """`%m/%d/%Y` and `%d/%m/%Y` cannot be told apart, so the family goes.

    Refusing `03/04/2026` while accepting `12/31/2026` would put one format
    with two behaviours back in the parser, decided by the value — which is the
    shape that let BUG-1 survive testing. `08/11/2026` is also BUG-4's silent
    no-op, entered by a real user into a real snooze box.
    """
    for s in ("03/04/2026", "08/11/2026", "12/31/2026", "2026/08/11", "8/11/2026"):
        with pytest.raises(UnparseableDate):
            parse_deadline(s)


def test_i2_refuses_impossible_days():
    for s in ("2026-02-30", "February 30, 2026", "2026-13-01", "2025-02-29",
              "2026-08-00", "0 August 2026"):
        with pytest.raises(UnparseableDate):
            parse_deadline(s)
    assert parse_deadline("2028-02-29").iso == "2028-02-29"     # a real leap day


def test_i2_refuses_what_is_not_text_rather_than_raising_something_else():
    """A missing deadline is BUG-1's exact shape and must arrive as a refusal.

    One exception type for every refusal, so a caller that handles refusal
    handles all of it.
    """
    for value in (None, 42, 3.5, True, ["2026-08-10"], date(2026, 8, 10),
                  datetime(2026, 8, 10)):
        with pytest.raises(UnparseableDate):
            parse_deadline(value)


def test_i2_a_refusal_says_what_would_have_worked():
    with pytest.raises(UnparseableDate) as exc:
        parse_deadline("next week")
    assert "2026-08-10" in str(exc.value) or "YYYY-MM-DD" in str(exc.value)


# ── I-3 · overdue derives from the parsed value ──────────────────────────────

def test_i3_overdue_and_days_until_cannot_disagree():
    today = date(2026, 8, 4)
    for offset in range(-400, 401):
        d = Deadline(today + timedelta(days=offset), today)
        assert d.days_until == offset
        assert d.overdue is (offset < 0)
        assert d.overdue is (d.date < today)      # tied to the parsed value


def test_i3_the_day_of_the_deadline_is_not_yet_overdue():
    d = Deadline.from_text("2026-08-04", "2026-08-04")
    assert d.days_until == 0 and d.overdue is False


def test_i3_a_string_comparison_would_still_get_this_wrong():
    """The BUG-3 case, kept as a live demonstration rather than a memory.

    `"May 5, 2026" < "2026-08-04"` is False in ASCII (`'M'` is 0x4D, `'2'` is
    0x32), which is how a 91-day-overdue deadline rendered as "Due Soon".
    """
    raw, today = "May 5, 2026", "2026-08-04"
    assert (raw < today) is False                          # the old wrong answer
    assert Deadline.from_text(raw, today).overdue is True   # the derived one


# ── I-4 · FRCP 6(a) counting, stated and tested ──────────────────────────────

def test_i4_frcp_6a1a_the_day_of_the_event_is_not_counted():
    assert court_days("2026-08-10", 1).iso == "2026-08-11"
    assert court_days("2026-08-04", 21).iso == "2026-08-25"


def test_i4_frcp_6a1b_intermediate_weekends_and_holidays_are_counted():
    """Every day counts on the way; only the last day can move."""
    assert court_days("2026-08-07", 3).iso == "2026-08-10"     # Fri +3 = Mon
    assert court_days("2026-11-12", 14).iso == "2026-11-27"    # over Thanksgiving
    assert court_days("2026-05-20", 5).iso == "2026-05-26"     # over Memorial Day


def test_i4_frcp_6a1c_and_6a6_the_last_day_rolls_forward():
    assert court_days("2026-12-19", 14).iso == "2027-01-04"    # Sat -> Mon
    assert court_days("2027-01-14", 4).iso == "2027-01-19"     # MLK Mon -> Tue
    assert court_days("2026-07-01", 3).iso == "2026-07-06"     # Sat -> Mon


def test_i4_an_observed_holiday_is_a_legal_holiday():
    """2026-07-04 is a Saturday, so Friday 2026-07-03 is the legal holiday and
    the courthouse is shut. A calendar without observed days lands on it."""
    assert court_days("2026-07-01", 2).iso == "2026-07-06"


def test_i4_the_answer_is_never_a_saturday_sunday_or_federal_holiday():
    import holidays

    cal = holidays.US()
    start = date(2026, 1, 1)
    for n in range(0, 400):
        got = court_days(start, n).date
        assert got.weekday() < 5 and got not in cal, (n, got)
        assert got >= start + timedelta(days=n)


def test_i4_zero_days_is_the_day_itself_rolled():
    assert court_days("2026-08-04", 0).iso == "2026-08-04"     # a Tuesday
    assert court_days("2026-08-08", 0).iso == "2026-08-10"     # a Saturday


def test_i4_backward_counting_is_refused_not_guessed():
    """FRCP 6(a)(5) rolls *backward* off a weekend. A sign flip on this
    function would move a deadline the wrong way past a weekend."""
    with pytest.raises(UnparseableDate):
        court_days("2026-08-10", -14)


def test_i4_a_period_is_a_whole_number_of_days():
    for n in (1.0, "14", None, True):
        with pytest.raises(UnparseableDate):
            court_days("2026-08-10", n)


def test_i4_an_unimplemented_jurisdiction_is_refused():
    """Silently applying federal rules to a California court-day period is a
    wrong answer with no visible cause."""
    for j in ("US-CA", "california", "", None):
        with pytest.raises(UnparseableDate):
            court_days("2026-08-10", 14, jurisdiction=j)


def test_i4_the_calendar_is_injectable():
    """A national holiday list is not a court calendar. Local closures must be
    addable without editing this module."""
    closed = frozenset({date(2026, 8, 11), date(2026, 8, 12)})
    got = court_days("2026-08-10", 1, jurisdiction="US-County", holiday_calendar=closed)
    assert got.iso == "2026-08-13"


def test_i4_start_may_be_a_deadline_and_keeps_its_reckoning_day():
    start = parse_deadline("2026-12-19", "2026-08-04")
    end = court_days(start, 14)
    assert end.iso == "2027-01-04"
    assert end.reference == date(2026, 8, 4) and end.days_until == 153


def test_i4_a_period_beyond_the_calendar_is_refused():
    with pytest.raises(UnparseableDate):
        court_days("2026-08-10", 10 ** 9)


# ── I-5 · no free-text dates ─────────────────────────────────────────────────

def test_i5_every_bug4_snooze_value_is_refused_at_the_edge():
    """The exact values that were entered into law-gazelle's snooze box.

    `"next week"` hid an urgent deadline until 2099; `"08/11/2026"` did nothing
    at all; and nothing in the codebase could undo either.
    """
    for value in ("next week", "tomorrow", "Aug 11", "2026/08/11", "08/11/2026",
                  "in 3 days", "later", "when the letter arrives"):
        with pytest.raises(UnparseableDate):
            parse_deadline(value)


def test_i5_a_reckoning_day_is_validated_the_same_way():
    """`today` goes through the same parser. There is no second one."""
    with pytest.raises(UnparseableDate):
        Deadline.from_text("2026-08-10", "next week")
    assert Deadline.from_text("2026-08-10", date(2026, 8, 4)).days_until == 6


# ── I-27 · the declaration is true, and the license is what we said ──────────

def test_i27_holidays_is_declared_and_installed_and_mit():
    """`holidays` is this repo's first real dependency.

    Declared in `pyproject.toml`, present at runtime, and MIT — verified from
    the installed distribution's own metadata rather than from a report about
    it. If a future upgrade changes the license, this fails here rather than in
    someone's diligence review.
    """
    declared = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    deps = re.search(r"^dependencies\s*=\s*\[(.*?)\]", declared,
                     re.MULTILINE | re.DOTALL)
    assert deps and re.search(r'"holidays[><=~!]', deps.group(1)), (
        "holidays must be a declared runtime dependency, not an ambient one"
    )
    meta = md.metadata("holidays")
    license_text = " ".join(
        filter(None, [meta.get("License-Expression"), meta.get("License"),
                      *(meta.get_all("Classifier") or [])])
    )
    assert "MIT" in license_text, license_text
    assert md.version("holidays")
