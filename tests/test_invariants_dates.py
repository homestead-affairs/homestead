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
import inspect
import re
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import holidays
import pytest

from homestead.keep.dates import (
    JURISDICTIONS,
    RULES,
    Deadline,
    RuleStatus,
    UnparseableDate,
    add_mail_days,
    business_days,
    court_days,
    court_days_before,
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


# ── I-41 (provisional) · backward counting, mail days, business days ────────
#
# Provisional per the plan (E1-dates-a): backward counting under FRCP 6(a)(5)
# / FRBP 9006(a)(5), mail days under 6(d)/9006(f), a business-day counter, and
# 9006(a)(6)(C)'s forward-only state-holiday addition. `RuleStatus.UNCERTAIN`
# is the fail-closed half of the same invariant I-11 already names: a rule
# this module has not verified against a primary source is refused, never
# guessed at — the assertion below plants one to prove the refusal actually
# fires rather than assuming it would.

def test_jurisdictions_is_derived_from_rules_not_hand_kept():
    """`JURISDICTIONS` must be computed from `RULES`'s keys, not a second,
    separately maintained tuple — the shape that lets the two drift apart the
    moment one is edited and the other is not."""
    from homestead.keep import dates as dates_module

    assert dates_module.JURISDICTIONS == tuple(dates_module.RULES)
    assert dates_module.JURISDICTIONS == tuple(RULES)
    assert "US-federal" in RULES and RULES["US-federal"].status is RuleStatus.VERIFIED


def test_i41_an_unverified_rule_is_refused_never_guessed(monkeypatch):
    """Plant an `UNCERTAIN` rule in a scratch copy of `RULES` and prove every
    function that would need it refuses by name, rather than computing an
    answer from a rule this module has not checked."""
    fake = replace(
        RULES["US-federal"],
        jurisdiction="US-fake",
        source="a citation nobody has read",
        short_period_source="a short-period citation nobody has read",
        backward_source="a backward citation nobody has read",
        mail_days_source="a mail-days citation nobody has read",
        status=RuleStatus.UNCERTAIN,
        short_period_status=RuleStatus.UNCERTAIN,
        backward_status=RuleStatus.UNCERTAIN,
        mail_status=RuleStatus.UNCERTAIN,
    )
    monkeypatch.setitem(RULES, "US-fake", fake)

    for call in (
        lambda: court_days("2026-08-10", 14, jurisdiction="US-fake"),
        lambda: court_days_before("2026-08-10", 14, jurisdiction="US-fake"),
        lambda: add_mail_days(parse_deadline("2026-08-10"), jurisdiction="US-fake"),
        lambda: business_days("2026-08-10", 14, jurisdiction="US-fake"),
    ):
        with pytest.raises(UnparseableDate) as exc:
            call()
        message = str(exc.value)
        assert message.startswith("UNCERTAIN:"), message
        assert "US-fake" in message, message

    # Supplying holiday_calendar= bypasses the RULES lookup entirely, so the
    # same uncertain jurisdiction computes fine once the caller owns the
    # calendar — this is the documented seam, not a bug in the plant.
    got = court_days(
        "2026-08-10", 14, jurisdiction="US-fake",
        holiday_calendar=frozenset(),
    )
    assert isinstance(got, Deadline)


# ── backward counting · FRCP 6(a)(5) / FRBP 9006(a)(5) ───────────────────────

def test_backward_count_excludes_the_event_day():
    """6(a)(5)/(1)(A): the event day itself is not counted. One day before a
    Wednesday hearing is Tuesday, not Wednesday."""
    assert court_days_before("2026-08-12", 1).iso == "2026-08-11"    # Wed -> Tue


def test_backward_count_rolls_backward_off_a_weekend():
    """6(a)(5): a period measured before an event rolls BACKWARD off a
    Saturday, Sunday or legal holiday — never forward, which would land the
    computed date after the event it was counted back from."""
    # Hearing Monday 2026-09-21; 7 days before is Monday 2026-09-14 (both open
    # weekdays, nothing rolls — the baseline case).
    assert court_days_before("2026-09-21", 7).iso == "2026-09-14"

    # Hearing Tuesday 2026-09-08; 7 days before, raw, is Tuesday 2026-09-01 —
    # also open. Labor Day (Monday 2026-09-07) falls one day INSIDE this span
    # (day 1 of the backward count, counted like any other day under
    # 6(a)(1)(B)) but is not the LAST day, so nothing rolls because of it.
    assert court_days_before("2026-09-08", 7).iso == "2026-09-01"

    # Day 7 lands on a Sunday: 2026-08-30 is a Sunday, so 7 days before it,
    # raw, is 2026-08-23 — also a Sunday (7 days preserves the weekday).
    # Rolling BACKWARD from a Sunday passes Saturday 2026-08-22 too, landing
    # on Friday 2026-08-21.
    assert date(2026, 8, 30).weekday() == 6 and date(2026, 8, 23).weekday() == 6
    assert court_days_before("2026-08-30", 7).iso == "2026-08-21"


def test_backward_count_has_no_district_state_parameter():
    """9006(a)(6)(C) adds a state's holidays only for periods measured AFTER
    an event; accepting `district_state` here would invite applying that
    addition backward, which is not the rule."""
    assert "district_state" not in inspect.signature(court_days_before).parameters
    with pytest.raises(TypeError):
        court_days_before("2026-08-10", 7, district_state="NM")  # type: ignore[call-arg]


def test_negative_n_still_refused_on_court_days_and_names_court_days_before():
    """`court_days` keeps refusing a negative period — it is not this
    function's rule to guess at — and the refusal names the function that
    does implement it, not just the fact that the input was rejected."""
    with pytest.raises(UnparseableDate) as exc:
        court_days("2026-08-10", -7)
    assert "court_days_before" in str(exc.value)

    # court_days_before refuses a negative n from the other end: it already
    # counts backward, so a negative n has no meaning to guess at either.
    with pytest.raises(UnparseableDate):
        court_days_before("2026-08-10", -7)


def test_backward_count_refuses_the_same_garbage_the_parser_does():
    for bad in ("next week", "2026", "", "08/11/2026", None):
        with pytest.raises((ValueError, TypeError)):
            court_days_before(bad, 14)
    for bad in (1.0, "14", None, True):
        with pytest.raises(UnparseableDate):
            court_days_before("2026-08-10", bad)


def test_backward_count_result_is_never_a_saturday_sunday_or_holiday():
    cal = holidays.US()
    start = date(2026, 1, 1)
    for n in range(0, 400):
        got = court_days_before(start + timedelta(days=n), n).date
        assert got.weekday() < 5 and got not in cal, (n, got)
        assert got <= start + timedelta(days=n)


# ── mail days · FRCP 6(d) / FRBP 9006(f) ─────────────────────────────────────

def test_mail_days_are_added_after_the_rolled_end_and_roll_again():
    """9006(f)/6(d): the 3 days are added to the END that 6(a)/9006(a) already
    rolled, and the sum is itself rolled forward again if it lands closed."""
    # A 14-day period from Friday 2026-09-11 ends Friday 2026-09-25 (both
    # open, nothing to roll under (a)). +3 raw days is Monday 2026-09-28
    # (Fri -> Sat -> Sun -> Mon) — already open, so the "roll again" step is a
    # no-op here, which is itself worth pinning down.
    end = court_days("2026-09-11", 14)
    assert end.iso == "2026-09-25"
    assert add_mail_days(end).iso == "2026-09-28"


def test_mail_days_refuses_when_the_mail_branch_is_uncertain(monkeypatch):
    fake = replace(
        RULES["US-federal"], jurisdiction="US-fake",
        mail_days_source="unread", mail_status=RuleStatus.UNCERTAIN,
    )
    monkeypatch.setitem(RULES, "US-fake", fake)
    with pytest.raises(UnparseableDate) as exc:
        add_mail_days(parse_deadline("2026-08-10"), jurisdiction="US-fake")
    assert str(exc.value).startswith("UNCERTAIN:")


def test_mail_days_refuses_when_the_rule_records_no_figure(monkeypatch):
    fake = replace(RULES["US-federal"], jurisdiction="US-fake", mail_days=None)
    monkeypatch.setitem(RULES, "US-fake", fake)
    with pytest.raises(UnparseableDate):
        add_mail_days(parse_deadline("2026-08-10"), jurisdiction="US-fake")


# ── business days ─────────────────────────────────────────────────────────────

def test_business_days_skip_intermediate_closures():
    """Unlike `court_days`, `business_days` skips a closure WHILE counting —
    the property `court_days`'s own docstring says it deliberately lacks."""
    # Friday 2026-09-04. court_days would land on Sept 4 + 3 = Sept 7 (Labor
    # Day, Monday) -> rolled forward once to Tuesday 2026-09-08.
    assert court_days("2026-09-04", 3).iso == "2026-09-08"
    # business_days skips Sat 9/5, Sun 9/6 AND Labor Day 9/7 while counting,
    # landing three OPEN days later: Tue 9/8, Wed 9/9, Thu 9/10.
    assert business_days("2026-09-04", 3).iso == "2026-09-10"


def test_business_days_zero_is_the_day_itself_rolled():
    assert business_days("2026-08-04", 0).iso == "2026-08-04"      # a Tuesday
    assert business_days("2026-08-08", 0).iso == "2026-08-10"      # a Saturday


def test_business_days_refuses_a_negative_period():
    with pytest.raises(UnparseableDate):
        business_days("2026-08-10", -3)


def test_business_days_never_lands_on_a_weekend_or_holiday():
    cal = holidays.US()
    start = date(2026, 1, 1)
    for n in (0, 1, 5, 10, 30, 90):
        got = business_days(start, n).date
        assert got.weekday() < 5 and got not in cal, (n, got)


# ── district-state holidays · FRBP 9006(a)(6)(C), forward only ──────────────

def test_district_state_holidays_apply_forward_only():
    """A state holiday extends a FORWARD count (9006(a)(6)(C)) but must never
    reach a backward one — `court_days_before` cannot even be asked, and
    `court_days` with `district_state` differs from the federal-only answer
    exactly when a state-only holiday falls on the raw last day."""
    # Cesar Chavez Day, 2026-03-31, is a California state holiday and not a
    # federal one — confirmed against the installed `holidays` package rather
    # than hardcoded as a fact about a future year.
    day = date(2026, 3, 31)
    assert day in holidays.US(subdiv="CA", years=2026)
    assert day not in holidays.US(years=2026)
    assert day.weekday() < 5                        # a Tuesday: only the state closes it

    # 14 days from 2026-03-17 lands raw on 2026-03-31.
    federal_only = court_days("2026-03-17", 14)
    assert federal_only.iso == "2026-03-31"          # federal calendar: open, no roll

    with_ca = court_days("2026-03-17", 14, district_state="CA")
    assert with_ca.iso == "2026-04-01"               # CA calendar: closed, rolls one day

    # The asymmetry: nothing about court_days_before can be asked to add a
    # state's holidays at all.
    assert "district_state" not in inspect.signature(court_days_before).parameters


def test_district_state_is_rejected_with_an_explicit_holiday_calendar():
    """`holiday_calendar` already replaces the jurisdiction's calendar
    entirely; combining it with `district_state` would leave it ambiguous
    which calendar actually governs, so the combination refuses."""
    with pytest.raises(UnparseableDate):
        court_days(
            "2026-03-17", 14, district_state="CA",
            holiday_calendar=frozenset({date(2026, 3, 31)}),
        )


def test_district_state_refuses_an_unrecognized_code():
    with pytest.raises(UnparseableDate):
        court_days("2026-03-17", 14, district_state="ZZ")


def test_a_holiday_calendar_override_replaces_the_calendar_not_the_counting_rule(monkeypatch):
    """The seam replaces only the calendar. A jurisdiction whose counting
    rule is UNCERTAIN still uses this module's own roll logic once a calendar
    is supplied — only which days are closed comes from the caller."""
    fake = replace(RULES["US-federal"], jurisdiction="US-fake", status=RuleStatus.UNCERTAIN)
    monkeypatch.setitem(RULES, "US-fake", fake)
    closed = frozenset(d for d in holidays.US(years=2026))
    got = court_days("2026-08-04", 21, jurisdiction="US-fake", holiday_calendar=closed)
    expected = court_days("2026-08-04", 21, jurisdiction="US-federal")
    assert got.iso == expected.iso


# ── I-41 (provisional) · audit pass ─────────────────────────────────────────
#
# Six properties the build pass left unpinned. Each is a thing that is true of
# the module today and would still have a green suite if it stopped being true.


def _undisclosed(rule) -> list[str]:
    """Which of a rule's citation strings are VERIFIED on that branch but fail
    to say where the text was read. Factored out so the plant below can run
    the same check the real table is held to.

    A `CountingRule` carries four independent branches (forward, short-period,
    backward, mail — see `CountingRule`'s docstring) and each is checked
    against its OWN status: a row can be VERIFIED on its forward branch and
    UNCERTAIN on its backward one, and the backward branch's undisclosed text
    is not this function's business until backward is VERIFIED too.
    """
    missing = []
    for source_name, status in (
        ("source", rule.status),
        ("short_period_source", rule.short_period_status),
        ("backward_source", rule.backward_status),
        ("mail_days_source", rule.mail_status),
    ):
        if status is not RuleStatus.VERIFIED:
            continue
        if source_name == "mail_days_source" and rule.mail_days is None:
            continue                    # a rule with no mail figure cites none
        text = getattr(rule, source_name)
        if "PROVENANCE" not in text or not re.search(r"\d{4}-\d{2}-\d{2}", text):
            missing.append(source_name)
    return missing


def test_i41_verified_rows_disclose_where_their_text_came_from():
    """`VERIFIED` is a claim about *checking*, and a claim about checking that
    does not say what was checked against is not auditable — it is just a
    brighter shade of UNCERTAIN.

    The primary text of FRCP 6 / FRBP 9006 cannot be read from this build
    environment: law.cornell.edu, uscourts.gov, govinfo.gov, uscode.house.gov
    and supremecourt.gov are all refused by the egress proxy, on the build pass
    and again on the 2026-09-11 audit pass. Keeping `US-federal` VERIFIED on
    converging secondary restatements is defensible for settled, uncontested
    text. Keeping it VERIFIED while its `source` reads as though someone had
    the rule open in front of them is not — and `source` is the string a
    refusal message and (from Wave 3) a stored deadline's instruction will
    quote. So every VERIFIED row must carry a dated PROVENANCE sentence, and
    this is the check that makes "must" mean something.
    """
    offenders = {
        name: _undisclosed(rule) for name, rule in RULES.items() if _undisclosed(rule)
    }
    assert not offenders, (
        f"VERIFIED rows whose citation does not say where its text was read: "
        f"{offenders}. Add a dated PROVENANCE sentence naming the basis — a "
        "primary quotation if you could reach one, the secondary restatements "
        "and the blocked hosts if you could not."
    )

    # `district_state_source` carries no status of its own (it is not one of
    # the four branches) but it IS a citation the same refusal messages will
    # quote, so a row that records one must say where it came from too.
    for name, rule in RULES.items():
        if rule.district_state_source is None:
            continue
        assert "PROVENANCE" in rule.district_state_source, name
        assert re.search(r"\d{4}-\d{2}-\d{2}", rule.district_state_source), name

    # Every branch this table actually verifies is exercised here, not just
    # the two `US-federal` shipped with in E1-dates-a: `US-OR` is the row
    # that made the four-way split necessary, and its short-period branch is
    # the one VERIFIED state branch outside the forward ones.
    assert RULES["US-OR"].short_period_status is RuleStatus.VERIFIED
    assert _undisclosed(RULES["US-OR"]) == []


def test_i41_the_provenance_check_fires_on_a_row_that_hides_its_basis():
    """The plant. A scan that has never fired has not been shown to check
    anything, and this one is a string test over prose, which is exactly the
    kind that rots into a tautology."""
    hidden = replace(
        RULES["US-federal"],
        jurisdiction="US-fake",
        source="FRCP 6(a): exclude the day of the event that triggers the period.",
        mail_days_source="FRCP 6(d): 3 days are added.",
        status=RuleStatus.VERIFIED,
    )
    assert _undisclosed(hidden) == ["source", "mail_days_source"]

    # Undated is not disclosed either — "checked against some restatements" with
    # no date is a claim that cannot go stale and therefore cannot be reviewed.
    undated = replace(hidden, source="PROVENANCE: secondary restatements.")
    assert "source" in _undisclosed(undated)

    # And an UNCERTAIN row is exempt: it is not claiming to have been checked.
    # All four branches must drop to UNCERTAIN for the row to be fully exempt
    # — dropping only the forward one would still leave the still-hidden
    # `mail_days_source` flagged, which is the point: each branch answers for
    # itself.
    fully_uncertain = replace(
        hidden,
        status=RuleStatus.UNCERTAIN,
        short_period_status=RuleStatus.UNCERTAIN,
        backward_status=RuleStatus.UNCERTAIN,
        mail_status=RuleStatus.UNCERTAIN,
    )
    assert _undisclosed(fully_uncertain) == []
    assert _undisclosed(replace(hidden, status=RuleStatus.UNCERTAIN)) == ["mail_days_source"]

    # **One plant per branch.** E1-dates-a's plant only ever hid `source` and
    # `mail_days_source`, so `short_period_source` and `backward_source` — the
    # two citation strings E1-dates-b added — had nothing proving the check
    # reaches them. Each is planted alone here, VERIFIED with its basis
    # removed, and must come back flagged on its own.
    for source_name, status_name in (
        ("source", "status"),
        ("short_period_source", "short_period_status"),
        ("backward_source", "backward_status"),
        ("mail_days_source", "mail_status"),
    ):
        changes = {
            "jurisdiction": "US-fake",
            "status": RuleStatus.UNCERTAIN,
            "short_period_status": RuleStatus.UNCERTAIN,
            "backward_status": RuleStatus.UNCERTAIN,
            "mail_status": RuleStatus.UNCERTAIN,
        }
        changes[source_name] = "a rule, stated confidently, with no basis given."
        changes[status_name] = RuleStatus.VERIFIED
        planted = replace(RULES["US-federal"], **changes)
        assert _undisclosed(planted) == [source_name], (
            f"planting an undisclosed VERIFIED {source_name} did not fire the "
            "PROVENANCE check — that branch's citation is unguarded"
        )


def test_i41_rule_status_cannot_be_confused_with_the_gate_enums():
    """`RuleStatus` is a `str` enum, and `rungs._check_the_str_enums_cannot_be_
    confused` deliberately does not know about it. Confirm that is safe rather
    than lucky.

    The hazard that guard exists for is a value collision between enums that
    are read out of *the same kind of argument slot* — `_read_rung` reaching
    `Rung(value)` for any `str`, with a `Purpose` being a `str`. `RuleStatus`
    is not in that family: it is never passed to a gate, never read out of a
    record, and never compared to a string. Two things make that structural
    rather than incidental, and both are asserted here.
    """
    from homestead.keep import rungs as rungs_mod
    from homestead.keep import surfaces as surfaces_mod
    from homestead.keep import logs as logs_mod

    # 1 · Its values collide with nothing, so even a slot that did read it as a
    #     string could not read it as something else.
    others = {}
    for enum in (rungs_mod.Rung, rungs_mod.Purpose, rungs_mod.Disposition,
                 surfaces_mod.Surface, logs_mod.Event):
        for member in enum:
            others[member.value] = f"{enum.__name__}.{member.name}"
    clashes = {m.value: others[m.value] for m in RuleStatus if m.value in others}
    assert not clashes, (
        f"RuleStatus shares a value with {clashes}; the two would be readable "
        "as each other in any slot that takes a bare str."
    )

    # 2 · The status check is an IDENTITY test, so a bare string that merely
    #     compares equal to RuleStatus.VERIFIED still fails closed. This is the
    #     direction that matters: the failure mode of an `==` here is a rule
    #     nobody verified being computed from.
    plain = "".join(["veri", "fied"])                 # the value, not the member
    assert plain == RuleStatus.VERIFIED               # it is a str enum
    assert plain is not RuleStatus.VERIFIED           # and that is the whole point
    monkey = replace(RULES["US-federal"], jurisdiction="US-fake", status=plain)
    RULES["US-fake"] = monkey
    try:
        with pytest.raises(UnparseableDate) as exc:
            court_days("2026-08-04", 14, jurisdiction="US-fake")
        assert str(exc.value).startswith("UNCERTAIN:"), str(exc.value)
    finally:
        del RULES["US-fake"]


def test_i41_a_district_state_calendar_may_only_add_closures_never_remove_one():
    """The trap in `holidays.US(subdiv=...)`, which is not a superset of
    `holidays.US()`.

    New Mexico does not observe Washington's Birthday on the third Monday in
    February — it keeps Presidents' Day on the Friday after Thanksgiving — so
    `holidays.US(subdiv="NM")` **drops** 2026-02-16, a federal legal holiday on
    which every federal courthouse in the District of New Mexico is shut.
    9006(a)(6)(C) *adds* the state's days to the federal ones; it does not
    substitute one calendar for the other. An implementation that returned the
    state calendar alone would compute 2026-02-16 as the deadline — a day the
    court is closed, arrived at by the tool whose only job is not to do that —
    and every other test in this file would still pass.
    """
    trap = date(2026, 2, 16)
    assert trap in holidays.US(years=2026), "Washington's Birthday is federal"
    assert trap not in holidays.US(subdiv="NM", years=2026), (
        "the premise of this test has changed: NM now lists 2026-02-16"
    )
    assert trap.weekday() == 0                      # a Monday, so only the holiday closes it

    # 2026-02-02 + 14 raw days = 2026-02-16.
    assert court_days("2026-02-02", 14).iso == "2026-02-17"
    assert court_days("2026-02-02", 14, district_state="NM").iso == "2026-02-17", (
        "adding New Mexico's calendar removed a federal holiday instead of "
        "adding a state one"
    )

    # The general form: over four years of landings, the district-state answer
    # is never EARLIER than the federal-only answer. Adding closures can only
    # push a deadline later.
    start = date(2026, 1, 1)
    for n in range(0, 1460, 7):
        federal = court_days(start, n).date
        for state in ("NM", "CA"):
            assert court_days(start, n, district_state=state).date >= federal, (n, state)


def test_i41_a_day_closed_by_both_calendars_rolls_exactly_once():
    """The other half: a state holiday that is *also* a federal one must not be
    counted twice. Memorial Day 2026-05-25 is in both calendars; the roll is
    one day either way, to Tuesday 2026-05-26."""
    both = date(2026, 5, 25)
    assert both in holidays.US(years=2026)
    assert both in holidays.US(subdiv="NM", years=2026)

    # 2026-05-11 + 14 raw days = 2026-05-25.
    assert court_days("2026-05-11", 14).iso == "2026-05-26"
    assert court_days("2026-05-11", 14, district_state="NM").iso == "2026-05-26"


def test_i41_a_state_only_holiday_extends_a_federal_period_in_that_district():
    """New Mexico's Presidents' Day is the Friday after Thanksgiving, which the
    federal calendar treats as an ordinary working day. A 14-day period from
    2026-11-12 ends on Thanksgiving and rolls to Friday 2026-11-27 federally —
    but the District of New Mexico is shut that Friday, so under
    9006(a)(6)(C) it rolls on across the weekend to Monday 2026-11-30."""
    friday = date(2026, 11, 27)
    assert friday not in holidays.US(years=2026)
    assert friday in holidays.US(subdiv="NM", years=2026)

    assert court_days("2026-11-12", 14).iso == "2026-11-27"
    assert court_days("2026-11-12", 14, district_state="NM").iso == "2026-11-30"


@pytest.mark.parametrize("code", ["ZZ", "nm", "new mexico", "US", "N M", "NMX"])
def test_i41_an_unrecognized_district_state_is_refused_by_name(code):
    """Fail closed, and say which code was refused. Silently ignoring an
    unrecognized subdivision would compute a federal-only deadline while the
    caller believed they had asked for their district's — the error that has no
    symptom until the filing is rejected."""
    with pytest.raises(UnparseableDate) as exc:
        court_days("2026-03-17", 14, district_state=code)
    assert repr(code) in str(exc.value) or code in str(exc.value), str(exc.value)


def test_i41_the_district_state_codes_that_do_work_are_pinned():
    """`holidays` accepts an exact-cased full subdivision name as well as the
    USPS code, and refuses every other casing of either. That is its
    behaviour, not ours, and it is the kind of thing a caller discovers by
    getting a refusal in production — so pin both sides of it here: `"NM"` and
    `"New Mexico"` are the same calendar, `"nm"` and `"new mexico"` are
    refusals, and the docstring's advice ("a USPS state code") is the half
    that always works."""
    assert (court_days("2026-11-12", 14, district_state="NM").iso
            == court_days("2026-11-12", 14, district_state="New Mexico").iso
            == "2026-11-30")


@pytest.mark.parametrize("code", ["", "   ", "\t"])
def test_i41_an_empty_district_state_is_refused_not_read_as_no_state(code):
    """`holidays.US(subdiv="")` does **not** raise — it quietly returns the
    plain federal calendar. So an empty string must be stopped before it gets
    there, or `district_state=""` from an unfilled form field would mean
    "federal only" while reading as "my district's calendar"."""
    with pytest.raises(UnparseableDate) as exc:
        court_days("2026-03-17", 14, district_state=code)
    assert "district_state" in str(exc.value)


# ── add_mail_days · the state addition applies to the re-roll too ────────────

def test_i41_mail_days_take_a_district_state_because_the_re_roll_is_under_a():
    """6(d)/9006(f) adds its days "after the period would otherwise expire
    under (a)" — which makes the added days themselves computed under (a), and
    (a)(6)(C) is part of (a).

    Without this, the composition the bankruptcy pack needs computes a closed
    day: a 14-day period from 2026-11-10 in the District of New Mexico ends
    Tuesday 2026-11-24, and +3 lands on Friday 2026-11-27 — a federal working
    day and an NM court holiday. The federal-only answer is that Friday; the
    correct one is Monday 2026-11-30.
    """
    end = court_days("2026-11-10", 14, district_state="NM")
    assert end.iso == "2026-11-24"
    assert add_mail_days(end).iso == "2026-11-27"                        # federal only
    assert add_mail_days(end, district_state="NM").iso == "2026-11-30"   # the district's


def test_i41_mail_days_refuse_a_district_state_beside_an_explicit_calendar():
    """The same mutual exclusion `court_days` enforces, for the same reason:
    an explicit calendar already decides what is closed."""
    with pytest.raises(UnparseableDate) as exc:
        add_mail_days(
            "2026-11-24", district_state="NM",
            holiday_calendar=frozenset({date(2026, 11, 27)}),
        )
    assert "mutually exclusive" in str(exc.value)


def test_i41_mail_days_refuse_an_unrecognized_district_state():
    with pytest.raises(UnparseableDate):
        add_mail_days("2026-11-24", district_state="ZZ")


def test_i41_the_backward_count_still_has_no_district_state_after_all_that():
    """`add_mail_days` gaining the parameter must not be read as licence for
    `court_days_before` to gain it. Mail days are always *added*, so there is
    no direction to get wrong; a backward count is nothing but direction."""
    assert "district_state" not in inspect.signature(court_days_before).parameters
    assert "district_state" in inspect.signature(court_days).parameters
    assert "district_state" in inspect.signature(add_mail_days).parameters
    assert "district_state" not in inspect.signature(business_days).parameters
    with pytest.raises(TypeError):
        court_days_before("2026-08-10", 7, district_state="NM")  # type: ignore[call-arg]


# ── the holiday_calendar seam, on all four functions ────────────────────────

def test_i41_an_explicit_calendar_replaces_the_calendar_on_every_function():
    """The build pass tested this seam on `court_days` only. All four functions
    document the same behaviour — the caller's calendar replaces the
    jurisdiction's and the `RULES` status check is bypassed — and three of them
    had nobody checking."""
    fake = replace(RULES["US-federal"], jurisdiction="US-fake",
                   status=RuleStatus.UNCERTAIN, mail_status=RuleStatus.UNCERTAIN)
    RULES["US-fake"] = fake
    try:
        closed = frozenset(holidays.US(years=range(2025, 2029)))
        kw = dict(jurisdiction="US-fake", holiday_calendar=closed)
        assert court_days("2026-08-04", 21, **kw).iso == court_days("2026-08-04", 21).iso
        assert (court_days_before("2027-01-05", 3, **kw).iso
                == court_days_before("2027-01-05", 3).iso == "2026-12-31")
        assert business_days("2026-11-23", 4, **kw).iso == business_days("2026-11-23", 4).iso

        # `add_mail_days` is the deliberate exception and is asserted
        # separately below: its seam replaces the calendar but does NOT
        # bypass the status check, because the figure it adds still comes
        # from the rule.
        with pytest.raises(UnparseableDate) as exc:
            add_mail_days("2026-07-01", **kw)
        assert str(exc.value).startswith("UNCERTAIN:"), str(exc.value)

        # And it really is the caller's calendar: an EMPTY one leaves the
        # Christmas landing alone, where the jurisdiction's would roll it.
        empty = dict(jurisdiction="US-fake", holiday_calendar=frozenset())
        assert court_days("2026-12-24", 1, **empty).iso == "2026-12-25"
        assert court_days("2026-12-24", 1).iso == "2026-12-28"
    finally:
        del RULES["US-fake"]


def test_i41_mail_days_do_not_let_a_calendar_buy_out_the_status_check():
    """The asymmetry stated on its own, because it is the one place this
    module's four seams are not the same shape and a reader will assume they
    are.

    `court_days`, `court_days_before` and `business_days` take the period from
    the caller; hand them a calendar as well and nothing of the rule survives
    into the answer, so an UNCERTAIN status has nothing left to be uncertain
    about. `add_mail_days` takes its period — the 3 — from `rule.mail_days`.
    A caller who supplies a calendar has supplied half the inputs and is still
    trusting the unverified half, so the refusal stands. Fail closed beats
    seam symmetry, and the docstring now says so; this is the test that keeps
    the two agreeing.
    """
    fake = replace(RULES["US-federal"], jurisdiction="US-fake",
                   status=RuleStatus.UNCERTAIN, mail_status=RuleStatus.UNCERTAIN)
    RULES["US-fake"] = fake
    try:
        cal = frozenset(holidays.US(years=2026))
        # three seams open …
        assert court_days("2026-08-04", 3, jurisdiction="US-fake", holiday_calendar=cal)
        assert court_days_before("2026-08-04", 3, jurisdiction="US-fake", holiday_calendar=cal)
        assert business_days("2026-08-04", 3, jurisdiction="US-fake", holiday_calendar=cal)
        # … and the fourth closed.
        with pytest.raises(UnparseableDate) as exc:
            add_mail_days("2026-08-04", jurisdiction="US-fake", holiday_calendar=cal)
        assert "UNCERTAIN:" in str(exc.value) and "US-fake" in str(exc.value)
    finally:
        del RULES["US-fake"]


def test_i41_an_explicit_calendar_does_not_make_the_weekend_open():
    """6(a)(1)(C) names "a Saturday, a Sunday, or a legal holiday" as three
    things and only the third is a calendar. `holiday_calendar=frozenset()`
    means "no holidays", not "nothing is closed" — a caller who read it the
    other way would be handed a Saturday deadline."""
    empty: frozenset = frozenset()
    assert court_days("2026-08-07", 1, holiday_calendar=empty).iso == "2026-08-10"
    assert court_days_before("2026-08-10", 1, holiday_calendar=empty).iso == "2026-08-07"
    assert business_days("2026-08-07", 1, holiday_calendar=empty).iso == "2026-08-10"
    # Wed 2026-08-05 + 3 = Sat 2026-08-08, closed by the RULE, not by any
    # calendar -> rolls to Mon 2026-08-10.
    assert add_mail_days("2026-08-05", holiday_calendar=empty).iso == "2026-08-10"


# ── fail closed on an unknown jurisdiction, on every function ───────────────

@pytest.mark.parametrize("call", [
    lambda j: court_days("2026-08-04", 14, jurisdiction=j),
    lambda j: court_days_before("2026-08-04", 14, jurisdiction=j),
    lambda j: add_mail_days("2026-08-04", jurisdiction=j),
    lambda j: business_days("2026-08-04", 14, jurisdiction=j),
], ids=["court_days", "court_days_before", "add_mail_days", "business_days"])
@pytest.mark.parametrize("unknown", ["US-WA", "US-TX", "US-CA", "federal", "US_FEDERAL"])
def test_i41_an_unknown_jurisdiction_is_refused_by_name_listing_what_exists(call, unknown):
    """I-11 on all four doors, not just the one the corpus knocks on. The
    refusal must name the jurisdiction asked for AND the set that is
    implemented. `US-NM` and `US-OR` landed in E1-dates-b (see the tests
    below this one) and are no longer good examples of "unknown" — a
    genuinely unimplemented state (`US-WA`, `US-TX`) makes the same point
    "no counting rules for 'US-WA'" with no list leaves the caller unable
    to tell a typo from a gap."""
    with pytest.raises(UnparseableDate) as exc:
        call(unknown)
    message = str(exc.value)
    assert unknown in message, message
    for implemented in JURISDICTIONS:
        assert implemented in message, message


# ── I-1 / I-2 / I-3 · the new functions did not open a second door ──────────

def test_i1_i2_i3_the_counting_functions_add_no_second_parser_and_one_type():
    """The three Phase 1 invariants, re-asserted across the four counting
    functions rather than across the parser alone.

    E1-dates-a added four public entry points, and an entry point is exactly
    where BUG-1 and BUG-4 got in: a second edge that validates a little less
    than the first. So, structurally:

    * **I-2** — `dates.py` grew no second parser. Every date shape still
      reaches `_parse` through `_as_date`, and the module still contains
      exactly one set of anchored patterns. `datetime.strptime` and
      `date.fromisoformat` are banned package-wide by scans already in this
      file; what those cannot see is a *hand-rolled* second parser, so the
      count of compiled patterns is pinned here.
    * **I-1** — every one of the four returns a `Deadline` and accepts the
      same three input shapes, so a computed date crosses the next boundary as
      the one type and nothing downstream is ever handed a string.
    * **I-3** — `overdue` is still `days_until < 0` and both still derive from
      the single stored `date`, on results these functions produced as much as
      on parsed ones.
    """
    from homestead.keep import dates as dates_module

    # I-2 · one parser. Five module-level compiled patterns — four date shapes
    # and the slashed-form detector — and no more.
    compiled = [name for name, value in vars(dates_module).items()
                if isinstance(value, re.Pattern)]
    assert sorted(compiled) == [
        "_DAY_FIRST", "_ISO_DATE", "_ISO_DATETIME", "_MONTH_FIRST", "_SLASHED",
    ], compiled

    tree = ast.parse(Path(dates_module.__file__).read_text())
    date_ctors = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "date"
    ]
    assert len(date_ctors) == 1, (
        "date(y, m, d) is built in exactly one place, `_build`, which is what "
        "makes 'no such calendar day' a single refusal rather than a family of "
        f"different exceptions. Found {len(date_ctors)}."
    )

    # I-1 · one crossing type, and the same three input shapes on all four.
    results = {
        "court_days": court_days("2026-08-04", 14),
        "court_days_before": court_days_before("2026-08-24", 14),
        "add_mail_days": add_mail_days("2026-08-18"),
        "business_days": business_days("2026-08-04", 10),
    }
    for name, got in results.items():
        assert type(got) is Deadline, f"{name} returned {type(got)!r}"
        assert parse_deadline(got.iso).iso == got.iso, name

    for call in (
        lambda d: court_days(d, 14),
        lambda d: court_days_before(d, 14),
        lambda d: add_mail_days(d),
        lambda d: business_days(d, 14),
    ):
        answers = {call(shape).iso for shape in (
            "2026-08-04", "August 4, 2026", date(2026, 8, 4),
            parse_deadline("2026-08-04"),
        )}
        assert len(answers) == 1, answers

    # I-3 · overdue is still derived, on a computed Deadline too.
    computed = court_days(parse_deadline("2026-08-04", "2026-09-01"), 14)
    assert computed.iso == "2026-08-18"
    assert computed.reference == date(2026, 9, 1)      # carried, not invented
    assert computed.days_until == -14
    assert computed.overdue is True
    assert computed.overdue is (computed.days_until < 0)
    assert "overdue" not in vars(computed)             # a property, not a field


# ═════════════════════════════════════════════════════════════════════════════
# E1-dates-b · US-NM and US-OR — the second and third jurisdictions
# ═════════════════════════════════════════════════════════════════════════════
#
# `US-federal` shipped one `status` per row because every branch of FRCP 6 /
# FRBP 9006 rested on the same secondary-restatement basis. `US-NM` and
# `US-OR` do not: each is VERIFIED-secondary on its forward branch (and, for
# `US-OR` only, its short-period branch too) and UNCERTAIN on backward and
# mail — nothing tried from this environment settles either. Tried and
# blocked, both build and audit pass: supremecourt.nmcourts.gov,
# law.justia.com, nmonesource.com and oregon.public.law are all refused by
# the egress proxy (`EGRESS_BLOCKED`) before the request leaves the box —
# see `RULES["US-NM"]` and `RULES["US-OR"]`'s citation strings for exactly
# which branch that leaves VERIFIED and which it leaves refusing.


def test_jurisdictions_is_still_derived_from_rules():
    """The E1-dates-a version of this check (`test_jurisdictions_is_derived_
    from_rules_not_hand_kept`) pins the *mechanism* (`tuple(RULES)`); this one
    pins the *result* the plan promised — `US-NM` and `US-OR` land, in that
    order, and nothing else sneaks in."""
    assert JURISDICTIONS == ("US-federal", "US-NM", "US-OR")
    assert JURISDICTIONS == tuple(RULES)


def test_nm_eleven_day_period_counts_every_day_and_rolls():
    """Rule 1-006(A) NMRA, VERIFIED-secondary for periods of 11 days or more:
    count every day, roll the last day forward off a Saturday, Sunday or
    legal holiday — checked against NM's own calendar (federal ∪ NM), not
    the federal one.

    Fri 2026-11-13 + 11 raw days = Tue 2026-11-24, an ordinary Tuesday in
    both calendars — nothing to roll, and NOT less than `short_period_max`
    (11), so this is the ordinary branch, not the short-period one.
    """
    assert date(2026, 11, 13).weekday() == 4                    # a Friday
    assert court_days("2026-11-13", 11, jurisdiction="US-NM").iso == "2026-11-24"

    # A case where the ordinary roll actually moves something: Wed
    # 2026-11-12 + 14 raw days = Thu 2026-11-26, Thanksgiving in EVERY
    # calendar -> rolls forward. In NM the very next day, Fri 2026-11-27, is
    # ALSO closed (NM's own Presidents' Day — see the test below) -> rolls
    # again, across the weekend, to Mon 2026-11-30. The federal-only answer
    # for the same period stops one roll earlier, at that Friday.
    assert court_days("2026-11-12", 14, jurisdiction="US-NM").iso == "2026-11-30"
    assert court_days("2026-11-12", 14, jurisdiction="US-federal").iso == "2026-11-27"


def test_nm_presidents_day_is_the_friday_after_thanksgiving():
    """New Mexico keeps Presidents' Day on the Friday after Thanksgiving
    instead of the third Monday in February (NMSA 1978 § 12-5-2), and the
    `US-NM` row's calendar must say both halves of that: the Friday closed,
    the February Monday OPEN."""
    friday = date(2026, 11, 27)
    assert friday.weekday() == 4
    assert friday not in holidays.US(years=2026)      # not a federal holiday
    assert friday in RULES["US-NM"].calendar()        # but New Mexico's is


def test_nm_and_or_calendars_are_the_states_own_not_a_union_with_the_federal_one():
    """**The calendar a state counting rule reads is that state's legal
    holidays, and nothing else.**

    `US-NM` (Rule 1-006 NMRA) and `US-OR` (ORCP 10) are state-court rules.
    The federal list has no standing in a state district court, and unioning
    it in would close days those courts are open on — a spurious closure
    computes a deadline that is too LATE, which is a missed filing, not a
    rounding error. The union belongs only to FRBP 9006(a)(6)(C), where a
    *federal* court sitting in a state adds *that* state's holidays, and
    that is `_district_calendar` (exercised by
    `test_i41_a_district_state_calendar_may_only_add_closures_never_remove_
    one`), reached through `court_days(..., district_state=...)`.

    Two concrete days, both readable from `holidays` 0.104's own
    subdivision data (New Mexico is named in that package's
    Washington's-Birthday exclusion set and gets a Friday-after-Thanksgiving
    "Presidents' Day" instead; Oregon is absent from its Columbus Day
    subdivision list and its source comments cite ORS 187 for exactly that):

    * **2027-02-15**, the third Monday in February. A federal holiday. New
      Mexico does not observe it, so a New Mexico court is OPEN.
    * **2026-10-12**, Columbus Day. A federal holiday. ORS 187.010 does not
      list it, so an Oregon court is OPEN.

    If either of these becomes closed again, some calendar has been unioned
    with the federal one and every NM/OR deadline that lands near it is
    silently late.
    """
    feb_monday, columbus = date(2027, 2, 15), date(2026, 10, 12)
    assert feb_monday in holidays.US(years=2027)      # federal: closed
    assert columbus in holidays.US(years=2026)        # federal: closed

    assert feb_monday not in RULES["US-NM"].calendar(), (
        "US-NM must read holidays.US(subdiv='NM') ALONE — New Mexico "
        "observes no third-Monday-in-February holiday (NMSA 12-5-2)"
    )
    assert columbus not in RULES["US-OR"].calendar(), (
        "US-OR must read holidays.US(subdiv='OR') ALONE — ORS 187.010 "
        "does not list Columbus Day"
    )

    # Oregon DOES keep the February Monday, on its own list, under its own
    # name — so dropping the union must not be read as "state lists are
    # always shorter". Each state answers for itself.
    assert date(2027, 2, 15) in RULES["US-OR"].calendar()

    # And the arithmetic follows the calendar, not just the membership test.
    assert court_days("2027-02-01", 14, jurisdiction="US-NM").iso == "2027-02-15"
    assert court_days("2027-02-01", 14, jurisdiction="US-federal").iso == "2027-02-16"
    assert court_days("2026-10-01", 11, jurisdiction="US-OR").iso == "2026-10-12"
    assert court_days("2026-10-01", 11, jurisdiction="US-federal").iso == "2026-10-13"


def test_district_state_is_refused_on_a_state_jurisdiction():
    """FRBP 9006(a)(6)(C) / FRCP 6(a)(6)(C) is a **federal** rule about a
    **federal** district court sitting in a state. There is no counterpart
    in Rule 1-006 NMRA or ORCP 10, so `district_state=` has no meaning on
    `US-NM`/`US-OR` — and silently unioning some second sovereign's
    holidays into a state court's calendar (which is what the parameter did
    before this test) is the same spurious-closure harm the calendars
    above are about, with the added twist that the caller has probably
    confused `jurisdiction="US-NM"` (a state court) with
    `jurisdiction="US-federal", district_state="NM"` (a federal one).
    Fail closed (I-11) and say which is which.

    Driven off `district_state_source is None` rather than a hardcoded
    jurisdiction name, so a future state row is covered the day it lands.
    """
    checked = 0
    for name, rule in RULES.items():
        if rule.district_state_source is not None:
            continue
        for call in (
            lambda j: court_days("2026-08-04", 20, jurisdiction=j, district_state="NM"),
            lambda j: add_mail_days("2026-08-04", jurisdiction=j, district_state="NM"),
        ):
            with pytest.raises(UnparseableDate) as exc:
                call(name)
            message = str(exc.value)
            assert name in message, message
            assert "district-state" in message, message
            assert "US-federal" in message, message
            checked += 1
    assert checked == 4, (
        "expected US-NM and US-OR to refuse district_state on both "
        f"court_days and add_mail_days; got {checked} refusals"
    )

    # The federal row, which does have the rule, still takes it.
    assert court_days("2026-11-24", 3, district_state="NM").iso == "2026-11-30"


def test_nm_short_period_boundary_is_strictly_below_eleven():
    """`short_period_max=11` means periods of **11 days or more** take the
    ordinary branch and periods of **10 or fewer** take the short one. The
    plan's sentence is "<11-day periods exclude closures" and "the ≥11-day
    forward branch is verified", so 10 and 11 must answer differently in
    kind, not just in value — and because NM's short branch is UNCERTAIN,
    "differently in kind" is observable as *a date versus a refusal*.

    This is the off-by-one that a `<=` for a `<` would hide: with `n <=
    short_period_max` the 11-day period would refuse too, and the one
    branch the plan says is verified would be unreachable.
    """
    assert RULES["US-NM"].short_period_max == 11

    assert court_days("2026-11-13", 11, jurisdiction="US-NM").iso == "2026-11-24"
    assert court_days("2026-11-13", 12, jurisdiction="US-NM").iso == "2026-11-25"

    for n in (0, 1, 10):
        with pytest.raises(UnparseableDate) as exc:
            court_days("2026-11-13", n, jurisdiction="US-NM")
        assert str(exc.value).startswith("UNCERTAIN:"), n


def test_or_short_period_boundary_is_strictly_below_seven():
    """The same boundary question for `US-OR`, where BOTH branches are
    VERIFIED — so here it is observable as two different dates rather than
    a date versus a refusal, which is the stronger form of the check.

    Mon 2027-02-08: `n=7` is ordinary — 7 raw days to Mon 2027-02-15,
    Oregon's Presidents Day, which rolls to Tue 02-16. `n=6` is short —
    Tue 9 (1), Wed 10 (2), Thu 11 (3), Fri 12 (4), [weekend], [Mon 15
    Presidents Day skipped while counting], Tue 16 (5), Wed 17 (6) →
    2027-02-17. One day apart, from one day of `n` across the boundary.
    """
    assert RULES["US-OR"].short_period_max == 7
    assert court_days("2027-02-08", 7, jurisdiction="US-OR").iso == "2027-02-16"
    assert court_days("2027-02-08", 6, jurisdiction="US-OR").iso == "2027-02-17"

    # The short branch never needs a roll at the end: `_count_open_days`
    # lands on an open day by construction, so there is no exclude-while-
    # counting-THEN-roll double application to get wrong.
    for n in range(0, 7):
        landed = court_days("2027-02-11", n, jurisdiction="US-OR").date
        assert landed.weekday() < 5
        assert landed not in RULES["US-OR"].calendar()


def test_nm_short_period_is_uncertain_and_refuses_by_name():
    """`short_period_max=11` is set (NM's boundary is known from secondary
    summaries) but `short_period_status` is UNCERTAIN — none of the three
    tried sources (the NMRA rule PDF, the NMSA statute, nmonesource) loads
    from this environment. I-11: refuse the short branch rather than guess
    at the exact exclusion set, even though the boundary number itself is
    not in doubt."""
    with pytest.raises(UnparseableDate) as exc:
        court_days("2026-11-16", 5, jurisdiction="US-NM")
    message = str(exc.value)
    assert message.startswith("UNCERTAIN:")
    assert "US-NM" in message
    assert re.search(r"\.(gov|com|org|do|law)\b", message), message


@pytest.mark.xfail(
    strict=True,
    reason="US-NM short-period rule UNCERTAIN until Rule 1-006 text is quoted",
)
def test_nm_short_period_excludes_weekends_and_holidays_when_verified():
    """The case this module WOULD compute if `RULES["US-NM"].short_period_
    status` were VERIFIED: a period under 11 days excludes intermediate
    Saturdays, Sundays and legal holidays while counting (the `business_days`
    shape), rather than counting them and only rolling the last day.

    Mon 2026-11-16 + 8 OPEN days, skipping Thanksgiving (Thu 11/26) AND NM's
    own Presidents' Day (Fri 11/27) as well as both intervening weekends:
    Tue 17 (1), Wed 18 (2), Thu 19 (3), Fri 20 (4), [Sat/Sun skip], Mon 23
    (5), Tue 24 (6), Wed 25 (7), [Thu 26 Thanksgiving skip], [Fri 27
    Presidents' Day skip], [Sat/Sun skip], Mon 30 (8) -> landing 2026-11-30.

    Today this raises `UnparseableDate` (UNCERTAIN) instead, which is why
    this test is `xfail(strict=True)`: the day `short_period_status` flips to
    VERIFIED, this assertion starts passing, `strict=True` turns that XPASS
    into a failure, and whoever flipped it is told to delete this marker.
    """
    assert court_days("2026-11-16", 8, jurisdiction="US-NM").iso == "2026-11-30"


def test_nm_backward_and_mail_are_uncertain_and_refuse_by_name():
    """Neither branch is stated in anything this module could read — I-11,
    refuse rather than assume New Mexico mirrors FRCP 6(a)(5) or the federal
    mail-days figure's re-roll behaviour."""
    with pytest.raises(UnparseableDate) as exc:
        court_days_before("2026-11-16", 5, jurisdiction="US-NM")
    assert str(exc.value).startswith("UNCERTAIN:") and "US-NM" in str(exc.value)

    with pytest.raises(UnparseableDate) as exc:
        add_mail_days(court_days("2026-11-13", 11, jurisdiction="US-NM"), jurisdiction="US-NM")
    assert str(exc.value).startswith("UNCERTAIN:") and "US-NM" in str(exc.value)


def test_or_seven_day_period_counts_every_day():
    """ORCP 10 A, VERIFIED-secondary at or above the 7-day boundary: count
    every day, including intermediate closures, and roll only the last one.

    Tue 2026-11-24 + 7 raw days = Tue 2026-12-01, which spans Thanksgiving
    (Thu 2026-11-26) as an INTERMEDIATE day — counted like any other, not
    skipped — and lands on an open Tuesday, so nothing rolls.
    """
    assert date(2026, 11, 24).weekday() == 1                    # a Tuesday
    assert court_days("2026-11-24", 7, jurisdiction="US-OR").iso == "2026-12-01"


def test_or_six_day_period_excludes_intermediate_closures():
    """The same start, one day shorter and on the other side of ORCP 10 A's
    7-day boundary: `short_period_max=7`, VERIFIED-secondary, excludes
    Thanksgiving and both intervening weekends WHILE counting.

    Tue 2026-11-24 + 6 OPEN days: Wed 25 (1), [Thu 26 Thanksgiving skip],
    Fri 27 (2), [Sat/Sun skip], Mon 30 (3), Tue Dec 1 (4), Wed Dec 2 (5),
    Thu Dec 3 (6) -> landing 2026-12-03 — two days LATER than the seven-day
    ordinary answer above, which is the whole point of the exclusion: it
    protects the number of *open* days, not the number of calendar days.
    """
    assert court_days("2026-11-24", 6, jurisdiction="US-OR").iso == "2026-12-03"


def test_or_presidents_day_third_monday_of_february_is_closed():
    """Unlike New Mexico, Oregon keeps Presidents Day on its ordinary
    third-Monday-in-February date — it is on ORS 187.010's own list, so
    `holidays.US(subdiv="OR")` closes it with no help from the federal
    calendar (`_or_calendar` unions nothing)."""
    day = date(2026, 2, 16)
    assert day.weekday() == 0
    assert day in RULES["US-OR"].calendar()
    assert court_days("2026-02-02", 14, jurisdiction="US-OR").iso == "2026-02-17"


def test_or_backward_is_uncertain_and_mail_names_the_letter_uncertainty():
    """Backward: not stated in anything read here, same as NM. Mail: ORCP
    10 C's addition is reported secondarily, but the section LETTER itself
    may have moved in a biennial Council on Court Procedures amendment since
    *Harvey v. Christie* (2010) — the refusal names that specifically, not
    just "not verified.\""""
    with pytest.raises(UnparseableDate) as exc:
        court_days_before("2026-11-24", 5, jurisdiction="US-OR")
    assert str(exc.value).startswith("UNCERTAIN:") and "US-OR" in str(exc.value)

    with pytest.raises(UnparseableDate) as exc:
        add_mail_days("2026-08-10", jurisdiction="US-OR")
    message = str(exc.value)
    assert message.startswith("UNCERTAIN:") and "US-OR" in message
    assert "letter" in message.lower()


def test_us_federal_with_district_state_nm_and_us_nm_agree_on_long_forward_periods_and_differ_on_short():
    """The jurisdiction-confusion attack the audit is named for: `"US-federal"`
    with `district_state="NM"` is a **federal** case pending in the District
    of New Mexico; `"US-NM"` is a **New Mexico state district court**. They
    are not interchangeable, and this test pins both reasons.

    They read different calendars. The federal side is federal ∪ NM
    (9006(a)(6)(C)); the state side is NM alone. They therefore disagree on
    the third Monday in February, which New Mexico does not observe — see
    `test_nm_and_or_calendars_are_the_states_own_not_a_union_with_the_
    federal_one`. Over a stretch with no such day in it they agree exactly,
    which is the loop below: both apply the identical ordinary FRCP-shaped
    roll and nothing distinguishes the calendars there.

    Below it they DIFFER in kind, not just in value: `"US-federal"` has
    `short_period_max=None`, so `district_state="NM"` still computes the
    ordinary answer for a 5-day period — federal law has no short-period
    concept to consult. `"US-NM"` has `short_period_max=11`, so the same
    5-day period is short enough to require the (UNCERTAIN) short branch,
    and refuses instead of silently falling back to the ordinary shape. A
    caller who confused the two jurisdictions would get a confident wrong
    answer for the short period, not a refusal that flags the confusion —
    which is exactly why they must stay separate rows in `RULES`.
    """
    for n in (11, 14, 21):
        agree_start = "2026-11-02"
        federal_side = court_days(agree_start, n, district_state="NM")
        nm_side = court_days(agree_start, n, jurisdiction="US-NM")
        assert federal_side.iso == nm_side.iso, (n, federal_side.iso, nm_side.iso)

    # …and differ where the calendars do: 2027-02-01 + 14 lands on Mon
    # 2027-02-15, Washington's Birthday. The federal court in Albuquerque is
    # shut and rolls to the Tuesday; the state court down the road is open.
    assert court_days("2027-02-01", 14, district_state="NM").iso == "2027-02-16"
    assert court_days("2027-02-01", 14, jurisdiction="US-NM").iso == "2027-02-15"

    short_start = "2026-11-16"
    federal_short = court_days(short_start, 5, district_state="NM")
    assert federal_short.iso == "2026-11-23"          # a real, ordinary answer

    with pytest.raises(UnparseableDate) as exc:
        court_days(short_start, 5, jurisdiction="US-NM")
    assert str(exc.value).startswith("UNCERTAIN:")


def test_a_holiday_calendar_override_keeps_the_jurisdictions_counting_rule():
    """A `holiday_calendar` override replaces WHICH DAYS ARE CLOSED, never
    WHICH ALGORITHM RUNS. Supply a calendar to `US-OR` and the short-period
    SHAPE still applies — `short_period_max=7` still comes from
    `RULES["US-OR"]`, only the closed days come from the caller.

    Mon 2026-11-16, `n=3`, with an artificial single-weekday closure on
    2026-11-18 (not a real holiday — a stand-in for a county closure):

    * SHORT shape (what must run, since 3 < 7): Tue 17 (open, 1),
      [Wed 18 closed by the override, skip], Thu 19 (open, 2), Fri 20
      (open, 3) -> landing 2026-11-20.
    * ORDINARY shape (what would run if the override silently discarded the
      counting rule too): 2026-11-16 + 3 raw days = Fri 2026-11-19, not
      closed by the override -> landing 2026-11-19, UNCHANGED.

    The two disagree, so which one actually ran is observable — and it is
    the short one.
    """
    closed = frozenset({date(2026, 11, 18)})
    got = court_days("2026-11-16", 3, jurisdiction="US-OR", holiday_calendar=closed)
    assert got.iso == "2026-11-20", (
        "the override replaced the calendar but the ordinary (roll-only) "
        "shape ran instead of OR's short-period shape — the counting rule "
        "was replaced too, which the seam must not do"
    )


def test_an_override_does_not_buy_out_an_uncertain_short_period_branch():
    """**The seam's one exception, and it runs the same way `add_mail_days`'s
    does.**

    `holiday_calendar` lets a caller own the answer on the ORDINARY branch:
    they supplied `n` and they supplied the closed days, so nothing of the
    rule is left in the result and its `status` has nothing to say. That is
    E1-dates-a's ruling and it stands.

    The SHORT branch is not like that. There the rule is still doing the
    work — `short_period_max` itself, and "exclude intermediate Saturdays,
    Sundays and legal holidays *while counting*" — and neither of those
    arrives with the caller's calendar. `US-NM`'s own
    `short_period_source` says in as many words that it is "refusing rather
    than guessing at the exact boundary and exclusion set"; computing on
    that boundary and that exclusion set because a calendar was supplied
    would be guessing at both anyway, one argument later. I-11.

    As shipped, this combination returned a date. It now refuses, and the
    refusal points at `business_days` — the identical arithmetic with no
    jurisdiction's short-period rule claimed for it, which is what a caller
    who genuinely owns this answer wants.
    """
    closed = frozenset({date(2026, 11, 18)})

    with pytest.raises(UnparseableDate) as exc:
        court_days("2026-11-16", 3, jurisdiction="US-NM", holiday_calendar=closed)
    message = str(exc.value)
    assert message.startswith("UNCERTAIN:"), message
    assert "short-period counting" in message and "US-NM" in message, message

    # The escape hatch the refusal names: same days, same arithmetic, no
    # claim that New Mexico's short-period rule is what produced it.
    assert business_days(
        "2026-11-16", 3, jurisdiction="US-NM", holiday_calendar=closed
    ).iso == "2026-11-20"

    # And the ordinary branch is untouched — an override still buys out the
    # forward status exactly as E1-dates-a decided.
    fake = replace(RULES["US-federal"], jurisdiction="US-fake",
                   status=RuleStatus.UNCERTAIN)
    RULES["US-fake"] = fake
    try:
        assert court_days(
            "2026-11-16", 14, jurisdiction="US-fake", holiday_calendar=closed
        ).iso == "2026-11-30"
    finally:
        del RULES["US-fake"]


def test_every_uncertain_branch_refuses_by_name_with_its_url():
    """Every branch this module has not verified fails closed (I-11), and
    the refusal names both the jurisdiction AND a URL a human can go read —
    not just "not verified," which gives no next step. Self-discovering
    rather than hardcoded to NM/OR by name, so a future UNCERTAIN row is
    covered the moment it lands."""
    branches = (
        ("short_period_status", "short_period_source",
         lambda j, rule: court_days("2026-08-04", rule.short_period_max - 1, jurisdiction=j)),
        ("backward_status", "backward_source",
         lambda j, rule: court_days_before("2026-08-04", 5, jurisdiction=j)),
        ("mail_status", "mail_days_source",
         lambda j, rule: add_mail_days("2026-08-04", jurisdiction=j)),
    )
    checked = 0
    for name, rule in RULES.items():
        for status_attr, source_attr, call in branches:
            if status_attr == "short_period_status" and rule.short_period_max is None:
                continue
            if getattr(rule, status_attr) is not RuleStatus.UNCERTAIN:
                continue
            with pytest.raises(UnparseableDate) as exc:
                call(name, rule)
            message = str(exc.value)
            assert message.startswith("UNCERTAIN:"), message
            assert name in message, message
            assert getattr(rule, source_attr) in message, message
            assert re.search(r"\.(gov|com|org|do|law)\b", message), message
            checked += 1
    assert checked >= 5, (
        f"expected at least NM's short/backward/mail and OR's backward/mail "
        f"branches to be UNCERTAIN and checked here; only {checked} were"
    )
