"""I-1 … I-5 — the date corpus. Written by a hand that has not seen the code.

Phase 0 was audited twice and both passes found tests enforcing weaker
properties than they claimed; one scan missed the exact leak it was written to
prevent. The cause was structural — the same hand wrote the code and the test,
so the test learned the code's shape. This file is the independent half of
Phase 1: the implementation was written concurrently and separately, and
neither author read the other.

It starts red. `homestead.keep.dates` does not exist when this file lands, so
collection fails loudly rather than skipping quietly — a skipped corpus is a
corpus that cannot fail, and the plan says the tests come first and start red.

**The four defects this corpus exists to make impossible**, from
`apps/law-gazelle/docs/bug_list.md`:

* **BUG-1** — `_days_until` sliced the input to ten characters *before* trying
  the long-form formats it declared. `"May 5 2026"` is exactly ten characters,
  so it parsed; `"May 5, 2026"` is eleven and returned `None`. The same date,
  one comma apart, opposite answers. The failure was **data-dependent**, which
  is why it survived casual testing, and a `None` deadline sorted below items
  due in a month.
* **BUG-2** — the same truncated string handed to `date.fromisoformat`, which
  is strict, so the milestone banner, the briefing packet and the TUI refresh
  raised `ValueError` on any long-form date.
* **BUG-3** — `overdue` was computed by lexicographic **string** comparison
  while `days_until` parsed. One item carried `days_until = -91` and
  `overdue = False` at the same time. Two fields describing one fact
  disagreed, and both were wrong in different directions.
* **BUG-4** — free-text dates were stored unvalidated. `"next week"` snoozed
  an urgent deadline until 2099; `"08/11/2026"` snoozed it not at all.

**And the inverse defect**, from `apps/law-gazelle/docs/sourcing_report.md`:
`dateutil.parser.parse` does not fail on a partial date, it **invents** one
from today — `'2026'` → 2026-08-04, `'June'` → 2026-06-04, `'30'` →
2026-08-30. That is worse than BUG-1: BUG-1 loses a deadline, this returns a
confident wrong one. So a large part of this corpus asserts **refusal**.
Refusing is the feature.

**Holiday source.** FRCP 6(a)(6) counting is checked against the eleven federal
holidays *and their observed shifts*, taken from the `holidays` package
(vacanza/holidays, **MIT**, v0.102, the DEPEND verdict in the sourcing report).
Rather than import it as the oracle — which would mean testing an
implementation against its own dependency — the dates are frozen into
`FEDERAL_HOLIDAYS` below, and a separate cross-check test asserts that table
still matches `holidays.US` whenever the package is installed.

Reference date throughout: **2026-08-04**, the same date the bug hunt used, so
every worked example here can be read against the bug list directly. Nothing in
this file consults the real clock.
"""
from __future__ import annotations

import ast
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from homestead.keep.dates import Deadline, court_days, parse_deadline

ROOT = Path(__file__).resolve().parent.parent
KEEP = ROOT / "homestead" / "keep"

# The bug hunt's reference date. Every "today" in this file is this string.
TODAY = "2026-08-04"          # a Tuesday
TODAY_D = date(2026, 8, 4)

try:                                            # cross-check only, never the oracle
    import holidays as _holidays
except ImportError:                             # pragma: no cover - env dependent
    _holidays = None


# ── the holiday table ────────────────────────────────────────────────────────
# US federal legal holidays per FRCP 6(a)(6)(A) / 5 U.S.C. § 6103, including the
# *observed* day when the holiday falls on a weekend — 2026-07-03 (Independence
# Day, because the 4th is a Saturday), 2027-12-24 (Christmas), 2027-12-31 (New
# Year's Day 2028). Frozen from `holidays` 0.102; `test_holiday_table_still_
# matches_the_holidays_package` re-verifies it.
FEDERAL_HOLIDAYS = frozenset(
    date.fromisoformat(s) for s in (
        # 2025
        "2025-01-01", "2025-01-20", "2025-02-17", "2025-05-26", "2025-06-19",
        "2025-07-04", "2025-09-01", "2025-10-13", "2025-11-11", "2025-11-27",
        "2025-12-25",
        # 2026
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-05-25", "2026-06-19",
        "2026-07-03", "2026-07-04", "2026-09-07", "2026-10-12", "2026-11-11",
        "2026-11-26", "2026-12-25",
        # 2027
        "2027-01-01", "2027-01-18", "2027-02-15", "2027-05-31", "2027-06-18",
        "2027-06-19", "2027-07-04", "2027-07-05", "2027-09-06", "2027-10-11",
        "2027-11-11", "2027-11-25", "2027-12-24", "2027-12-25", "2027-12-31",
        # 2028
        "2028-01-01", "2028-01-17", "2028-02-21", "2028-05-29", "2028-06-19",
        "2028-07-04", "2028-09-04", "2028-10-09", "2028-11-10", "2028-11-11",
        "2028-11-23", "2028-12-25",
        # 2029
        "2029-01-01", "2029-01-15", "2029-02-19", "2029-05-28", "2029-06-19",
        "2029-07-04", "2029-09-03", "2029-10-08", "2029-11-11", "2029-11-12",
        "2029-11-22", "2029-12-25",
        # 2030
        "2030-01-01", "2030-01-21", "2030-02-18", "2030-05-27", "2030-06-19",
        "2030-07-04", "2030-09-02", "2030-10-14", "2030-11-11", "2030-11-28",
        "2030-12-25",
    )
)

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def _rollable(d: date) -> bool:
    """Saturday, Sunday or legal holiday — the three things 6(a)(1)(C) rolls off."""
    return d.weekday() >= 5 or d in FEDERAL_HOLIDAYS


def _walk(start: str, end: str, step: int = 1):
    d, last = date.fromisoformat(start), date.fromisoformat(end)
    while d <= last:
        yield d
        d += timedelta(days=step)


def _long(d: date, comma: bool = True, pad: bool = False) -> str:
    """Build a long-form date without `strftime`, so `%B` locale cannot decide
    whether this suite passes."""
    day = f"{d.day:02d}" if pad else str(d.day)
    return f"{MONTHS[d.month - 1]} {day}{',' if comma else ''} {d.year}"


# ═════════════════════════════════════════════════════════════════════════════
# 1 · The formats that must parse — BUG-1's own evidence block
# ═════════════════════════════════════════════════════════════════════════════

# Verbatim from bug_list.md § BUG-1 "Confirmed:", plus the two long forms named
# in the BUG-2 reproduction. Five of these six returned None in law-gazelle.
BUG1_FORMS = [
    ("2026-08-10", "2026-08-10"),        # the only one that worked
    ("August 10, 2026", "2026-08-10"),   # [:10] = 'August 10,'
    ("July 1, 2026", "2026-07-01"),      # [:10] = 'July 1, 20'
    ("January 1, 2027", "2027-01-01"),   # [:10] = 'January 1,'
    ("May 5, 2026", "2026-05-05"),       # [:10] = 'May 5, 202'
    ("May 5 2026", "2026-05-05"),        # exactly 10 chars — parsed by accident
]


@pytest.mark.parametrize("text,iso", BUG1_FORMS, ids=[t for t, _ in BUG1_FORMS])
def test_bug1_every_form_in_the_bug_report_parses(text, iso):
    """BUG-1: `_days_until` declared `%B %d, %Y` and `%B %d %Y` and then sliced
    to ten characters first, so both were dead code for every real value."""
    assert parse_deadline(text).iso == iso


def test_bug1_the_comma_cannot_change_the_answer():
    """BUG-1's sharpest edge: `"May 5 2026"` is ten characters and parsed;
    `"May 5, 2026"` is eleven and returned None. The same deadline, written
    with and without a comma, gave opposite answers."""
    with_comma = parse_deadline("May 5, 2026").iso
    without = parse_deadline("May 5 2026").iso
    assert with_comma == without == "2026-05-05", (
        "a comma is punctuation, not data. If these differ, something is "
        "measuring the length of the string instead of reading it."
    )


@pytest.mark.parametrize("day", list(range(1, 32)))
def test_bug1_length_sweep_every_day_of_a_long_month(day):
    """BUG-1 was data-dependent — it turned on string *length*, so testing one
    or two long-form dates finds nothing. Every day of a long month, with and
    without the comma and with and without zero padding, is 9-19 characters and
    all of them must land on the same date."""
    d = date(2026, 8, day)
    for text in (_long(d), _long(d, comma=False),
                 _long(d, pad=True), _long(d, comma=False, pad=True)):
        assert parse_deadline(text).iso == d.isoformat(), text


@pytest.mark.parametrize("month", list(range(1, 13)))
def test_bug1_length_sweep_every_month_name(month):
    """`"May 5 2026"` is 10 and `"September 30, 2026"` is 18. A truncation bug
    is a bug about month-name length, so every month name is exercised."""
    d = date(2027, month, 15)
    assert parse_deadline(_long(d)).iso == d.isoformat()
    assert parse_deadline(_long(d, comma=False)).iso == d.isoformat()


# The rest of the sourcing report's verified ACCEPTS list. Split from the block
# above so a disagreement about the *extent* of the format set does not look
# like a truncation failure.
EXTENDED_FORMS = [
    ("Aug 10, 2026", "2026-08-10"),
    ("Aug 10 2026", "2026-08-10"),
    ("1 Jul 2026", "2026-07-01"),
    ("1 July 2026", "2026-07-01"),
    ("May 05, 2026", "2026-05-05"),
    ("September 30, 2026", "2026-09-30"),
    ("2026-8-4", "2026-08-04"),               # unpadded ISO, from BUG-3's table
    ("  July 1, 2026  ", "2026-07-01"),       # operator-entered leading space
    ("\tMay 5, 2026\n", "2026-05-05"),
]


@pytest.mark.parametrize("text,iso", EXTENDED_FORMS, ids=[repr(t) for t, _ in EXTENDED_FORMS])
def test_i2_extended_accepted_forms(text, iso):
    """I-2: the strict `strptime` set verified in the sourcing report against
    11 real fixtures. `'2026-8-4'` is from BUG-3's own confirmed output, so it
    is real operator data, not a hypothetical."""
    assert parse_deadline(text).iso == iso


@pytest.mark.parametrize("text,iso", [
    ("2026-07-01T00:00:00", "2026-07-01"),
    ("2026-08-10T09:00:00+00:00", "2026-08-10"),
])
def test_i2_iso_with_a_time_component(text, iso):
    """The one place truncation was *defensible* — and therefore the place to
    pin the boundary explicitly, so nobody reintroduces `[:10]` for it. The
    right instrument is `datetime.fromisoformat`, which reads the whole string.

    API note: if the implementation deliberately refuses times, this test is
    the disagreement, and it is cheaper to have it now.
    """
    assert parse_deadline(text).iso == iso


# ═════════════════════════════════════════════════════════════════════════════
# 2 · Truncation detectors — the sharpest tests in the phase
# ═════════════════════════════════════════════════════════════════════════════

# Each of these has valid-looking first ten characters and is garbage as a
# whole. A parser that slices — *including one that tries the full string first
# and falls back to `[:10]`* — returns a confident wrong date. The correct
# answer for all of them is refusal.
TRUNCATION_TRAPS = [
    "May 5 20261",            # [:10] == 'May 5 2026'  -> 2026-05-05
    "2026-08-104",            # [:10] == '2026-08-10'  -> 2026-08-10
    "2026-08-1099",
    "2026-08-10 or sooner",   # [:10] == '2026-08-10'
    "2026-08-10 (extended)",
    "2026-08-10; see order",
    "2026-08-10 / 2026-09-01",
    "2026-08-10\n2026-09-01",
    "12/31/2026 or sooner",   # from the sourcing report's REJECTS list
    "May 5 2026 or sooner",
]

# A second family, found while writing this file rather than assumed: since
# 3.11 `datetime.fromisoformat` accepts *any single character* as the date/time
# separator, so `"2026-08-10-01"` reads as 2026-08-10 01:00 and `"2026-W32-1"`
# reads as an ISO week date. Neither is truncation and neither is what a
# litigant typed. A parser whose ISO branch is a bare `fromisoformat` accepts
# both silently.
ISO_LENIENCY_TRAPS = [
    "2026-08-10-01",
    "2026-08-10x09",
    "2026-W32-1",
    "2026-W32",
]


@pytest.mark.parametrize("text", TRUNCATION_TRAPS)
def test_bug1_a_valid_prefix_is_not_a_valid_date(text):
    """BUG-1, stated as the property that actually catches it. The accept
    tests above are passed by a `[:10]`-with-fallback parser; these are not.
    Ten valid leading characters followed by anything is not a deadline —
    parse the whole string or refuse it."""
    with pytest.raises(ValueError):
        parse_deadline(text)


@pytest.mark.parametrize("text", ISO_LENIENCY_TRAPS)
def test_i2_the_iso_branch_is_not_a_bare_fromisoformat(text):
    """I-2, from a leniency in the standard library rather than in the bug list.

    `datetime.fromisoformat` treats any character in position 10 as the
    date/time separator, so `"2026-08-10-01"` returns 2026-08-10 01:00 — a
    date silently recovered from a string nobody meant as one. It also reads
    ISO *week* dates, so `"2026-W32-1"` becomes 2026-08-03. Accepting a time
    component (tested above) does not require accepting these; the ISO branch
    has to say which shapes it takes.
    """
    with pytest.raises(ValueError):
        parse_deadline(text)


def test_bug1_no_ten_character_slice_appears_in_the_date_module():
    """BUG-1's literal signature, scanned for the way the store scans for raw
    SOIL reads. `deadline[:10]` at `case_store.py:76` is the whole defect, and
    `datetime.fromisoformat` reads ISO-with-time without any slicing, so there
    is no legitimate reason for the constant 10 to bound a slice here.

    This is a belt to the behavioural braces above, not a substitute for them.
    """
    offenders = []
    for mod in sorted(KEEP.rglob("*.py")):
        if "__pycache__" in mod.parts:
            continue
        for node in ast.walk(ast.parse(mod.read_text())):
            if isinstance(node, ast.Slice):
                for bound in (node.lower, node.upper):
                    if isinstance(bound, ast.Constant) and bound.value == 10:
                        offenders.append(f"{mod.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, (
        "a ten-character slice in the date path is BUG-1 verbatim: it made "
        f"'May 5 2026' parse and 'May 5, 2026' return None. Found: {offenders}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 3 · Everything that must be REFUSED
# ═════════════════════════════════════════════════════════════════════════════

# `dateutil.parser.parse` returns a date for every entry in the first four
# groups, invented from today. Each comment records what it would have returned
# on 2026-08-04 — that is the wrong answer this corpus exists to forbid.
PARTIAL = [
    "2026",              # dateutil -> 2026-08-04   (today's month AND day)
    "June",              # dateutil -> 2026-06-04   (today's day)
    "30",                # dateutil -> 2026-08-30   (today's month)
    "Monday",            # dateutil -> 2026-08-10   (the next Monday)
    "Aug",
    "August 2026",
    "2026-08",
    "08/2026",
    "5 May",
    "May 5",
    "1st",
    "2026-",
    "-08-10",
]

NATURAL_LANGUAGE = [
    "next week",         # BUG-4: snoozed an urgent deadline until 2099
    "tomorrow",          # BUG-4: same
    "today",
    "yesterday",
    "asap",
    "ASAP",
    "TBD",
    "tbd",
    "see order",
    "on or before Aug 1",
    "when the court rules",
    "end of the month",
    "in 30 days",
    "30 days from service",
    "n/a",
    "none",
    "unknown",
    "pending",
]

# The sourcing report puts '%m/%d/%Y' in the format list and then says, in the
# same section, that '03/04/2026' is indistinguishable from '%d/%m/%Y' and the
# better answer is to make the user disambiguate once and store ISO. I-2 and
# I-5 both point the same way: the edge validates, it does not guess. So the
# corpus takes the stricter reading — a bare slash form is refused.
AMBIGUOUS_NUMERIC = [
    "08/11/2026",        # BUG-4: this one silently did nothing at all
    "11/08/2026",        # the same day, or a different one — nobody can say
    "03/04/2026",
    "2026/08/11",
    "08-11-2026",
    "11.08.2026",
    "8/11/26",
]

EMPTY = ["", " ", "   ", "\t", "\n", "\t \n "]

IMPOSSIBLE = [
    "2026-02-30",
    "2026-13-01",
    "2026-00-10",
    "2026-08-32",
    "February 30, 2026",
    "Smarch 4, 2026",
    "0000-00-00",
    "9999-99-99",
]

REFUSED = PARTIAL + NATURAL_LANGUAGE + AMBIGUOUS_NUMERIC + EMPTY + IMPOSSIBLE


@pytest.mark.parametrize("text", REFUSED, ids=[repr(t) for t in REFUSED])
def test_i2_i5_refusal_is_the_feature(text):
    """I-2, I-5, BUG-4. Two failures meet here. BUG-4 stored free text and
    string-compared it, so `"next week"` hid a hard deadline forever and
    `"08/11/2026"` was a silent no-op. `dateutil` would have been worse: it
    invents the missing components from today and hands back a plausible wrong
    date the user then acts on. Neither losing the deadline nor guessing it is
    acceptable — the edge refuses, loudly, with `ValueError`."""
    with pytest.raises(ValueError):
        parse_deadline(text)


def test_i2_none_is_refused_not_treated_as_absent():
    """`_days_until` opened with `if not deadline: return None`, so a missing
    deadline and an unparseable one were the same value downstream and the
    queue sorted both to 9999. I-8 says unparseable input becomes a recorded
    gap, never a silent empty — which requires the parser to raise here."""
    with pytest.raises(ValueError):
        parse_deadline(None)


@pytest.mark.parametrize("value", [20260810, 2026, 0, 3.5, True, ["2026-08-10"],
                                   {"date": "2026-08-10"}, ("2026", "08", "10")])
def test_i1_a_non_string_is_refused(value):
    """I-1: a date crosses a boundary as a `Deadline`, never as anything a
    format string might be coaxed into accepting."""
    with pytest.raises((ValueError, TypeError)):
        parse_deadline(value)


@pytest.mark.parametrize("text", PARTIAL)
def test_i2_a_partial_date_is_never_completed_from_today(text):
    """The sourcing report's re-verified finding, asserted as behaviour rather
    than as a rule about imports. `dateutil.parser.parse('2026')` returns
    2026-08-04 — today's month and day silently filled in. If a parse result
    ever depends on what day it is, this fails for every value of `today`."""
    for today in ("2026-08-04", "2025-01-31", "2027-06-19", "2028-02-29"):
        with pytest.raises(ValueError):
            Deadline.from_text(text, today=today)


def test_i2_parsing_does_not_depend_on_today():
    """The same property from the other side: for input that *is* valid, the
    answer is a function of the input alone. `today` sets the frame of
    reference for `days_until`; it must never reach the parse."""
    for text, iso in BUG1_FORMS + EXTENDED_FORMS:
        answers = {Deadline.from_text(text, today=t).iso
                   for t in ("2020-01-01", "2026-08-04", "2099-12-31")}
        assert answers == {iso}, f"{text!r} parsed differently on different days"


def test_i2_the_core_does_not_import_a_guessing_parser():
    """I-2 as a source-level invariant, in the register the store already uses.

    `sys.modules` cannot answer this — `holidays` legitimately depends on
    `python-dateutil`, so `dateutil` is in the process either way. What matters
    is that no file in `homestead.keep` reaches for it, or for `dateparser`,
    whose entire value proposition (natural-language flexibility) is hostile to
    a court-deadline core. The sourcing report asks for exactly this test.
    """
    banned = {"dateutil", "dateparser", "pendulum", "arrow", "parsedatetime",
              "maya", "natty"}
    offenders = {}
    for mod in sorted(KEEP.rglob("*.py")):
        if "__pycache__" in mod.parts:
            continue
        found = set()
        for node in ast.walk(ast.parse(mod.read_text())):
            if isinstance(node, ast.Import):
                found |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
        if banned & found:
            offenders[str(mod.relative_to(ROOT))] = sorted(banned & found)
    assert not offenders, (
        "these parsers invent missing components instead of failing: "
        f"{offenders}. dateutil.parser.parse('2026') is 2026-08-04."
    )


def test_i5_an_invalid_today_is_refused_too():
    """I-5: *every* input takes a validated date, including the frame of
    reference. BUG-4's `is_snoozed` compared a stored value to
    `date.today().isoformat()` as strings — an implementation that string-
    compares has no reason to validate either side."""
    for bad in ("next week", "", "2026-13-01", "August 4, 2026 or so",
                "08/11/2026", 20260804, ["2026-08-04"]):
        with pytest.raises((ValueError, TypeError)):
            Deadline.from_text("2026-08-10", today=bad)


def test_i1_the_two_parse_entry_points_cannot_disagree():
    """I-1: parsing happens once, at the edge. Two entry points that parse
    separately is the shape that produced BUG-3 — `days_until` parsed and
    `overdue` did not, and the two answers were both wrong differently."""
    for text, iso in BUG1_FORMS + EXTENDED_FORMS:
        assert parse_deadline(text).iso == Deadline.from_text(text, today=TODAY).iso == iso
    for text in REFUSED + TRUNCATION_TRAPS + ISO_LENIENCY_TRAPS:
        with pytest.raises(ValueError):
            parse_deadline(text)
        with pytest.raises(ValueError):
            Deadline.from_text(text, today=TODAY)


# ═════════════════════════════════════════════════════════════════════════════
# 4 · BUG-3 — the two fields that disagreed
# ═════════════════════════════════════════════════════════════════════════════

def test_bug3_the_exact_item_from_the_bug_report():
    """BUG-3, verbatim: one item carried `days_until = -91` and
    `overdue = False` at the same time, because `days_until` parsed the value
    while `overdue` compared `'May 5, 2026' < '2026-08-04'` — False, since
    `'M'` (0x4D) sorts after `'2'` (0x32). A deadline 91 days past rendered as
    "Due Soon"."""
    d = Deadline.from_text("May 5, 2026", today=TODAY)
    assert d.days_until == -91
    assert d.overdue is True


# Each pair is a raw string whose ASCII order against '2026-08-04' contradicts
# its chronological order. These are the cases a string comparison gets wrong.
LEXICOGRAPHIC_TRAPS = [
    ("May 5, 2026", "2026-05-05", -91, True),    # strcmp says not overdue
    ("May 5 2026", "2026-05-05", -91, True),     # strcmp says not overdue
    ("July 1, 2026", "2026-07-01", -34, True),   # strcmp says not overdue
    ("August 10, 2026", "2026-08-10", 6, False),
    ("1 Sep 2026", "2026-09-01", 28, False),     # strcmp says OVERDUE
    ("1 Jan 2027", "2027-01-01", 150, False),    # strcmp says OVERDUE
    ("January 1, 2027", "2027-01-01", 150, False),
    ("2026-8-4", "2026-08-04", 0, False),        # unpadded; strcmp is luck
]


@pytest.mark.parametrize("text,iso,days,overdue", LEXICOGRAPHIC_TRAPS,
                         ids=[t for t, _, _, _ in LEXICOGRAPHIC_TRAPS])
def test_i3_never_compare_dates_as_strings(text, iso, days, overdue):
    """I-3 / BUG-3. `'1 Sep 2026' < '2026-08-04'` is True because `'1'` sorts
    before `'2'`, so a lexicographic `overdue` calls a date four weeks in the
    future overdue; `'May 5, 2026'` fails the other way. Both directions are
    here, because a test with only past dates is passed by an implementation
    that always returns True."""
    d = Deadline.from_text(text, today=TODAY)
    assert d.iso == iso
    assert d.days_until == days
    assert d.overdue is overdue


def test_i3_overdue_is_a_real_bool_not_a_none():
    """The detail that stopped law-gazelle repairing itself: `urgent_queue`'s
    guard was `if item.get("overdue") is None`, and the broken value was
    `False`, not `None`. So the repair path never ran."""
    d = Deadline.from_text("2026-08-10", today=TODAY)
    assert isinstance(d.overdue, bool)
    assert d.overdue is False
    assert isinstance(d.days_until, int) and not isinstance(d.days_until, bool)


@pytest.mark.parametrize("offset", list(range(-400, 401, 7)) + [-1, 0, 1])
def test_i3_the_two_fields_agree_across_a_year_either_side(offset):
    """I-3 stated as the property, not as a case: `overdue` is *derived* from
    the parsed value, so the two fields describing one fact cannot disagree —
    for any date, on either side of today, in any accepted format."""
    target = TODAY_D + timedelta(days=offset)
    for text in (target.isoformat(), _long(target), _long(target, comma=False)):
        d = Deadline.from_text(text, today=TODAY)
        assert d.iso == target.isoformat(), text
        assert d.days_until == offset, text
        assert d.overdue is (offset < 0), text


def test_i3_due_today_is_not_overdue():
    """The boundary, pinned so it cannot drift. Zero days remaining is the last
    day to act, not a missed deadline — and an off-by-one here tells a litigant
    they have already failed."""
    d = Deadline.from_text(TODAY, today=TODAY)
    assert d.days_until == 0
    assert d.overdue is False
    assert Deadline.from_text("2026-08-03", today=TODAY).overdue is True
    assert Deadline.from_text("2026-08-05", today=TODAY).overdue is False


def test_bug1_and_bug3_one_deadline_written_six_ways_gives_one_answer():
    """The two bugs' combined effect, from BUG-1's end-to-end reproduction:
    `'2026-07-01'` sorted first in the urgent queue as `overdue`, while
    `'July 1, 2026'` — the same deadline — sorted fifth as `ready_to_draft`.
    Format is presentation. It cannot change urgency."""
    forms = ["2026-07-01", "July 1, 2026", "July 1 2026", "Jul 1, 2026",
             "1 July 2026", "2026-07-01T00:00:00"]
    answers = {(Deadline.from_text(f, today=TODAY).iso,
                Deadline.from_text(f, today=TODAY).days_until,
                Deadline.from_text(f, today=TODAY).overdue) for f in forms}
    assert answers == {("2026-07-01", -34, True)}, answers


def test_i1_a_deadline_round_trips_through_its_own_iso():
    """I-1: `iso` is the canonical spelling, so re-parsing it must be identity.
    If it is not, the value changes every time it crosses a boundary."""
    for offset in range(-500, 501, 13):
        target = TODAY_D + timedelta(days=offset)
        first = Deadline.from_text(_long(target), today=TODAY)
        second = Deadline.from_text(first.iso, today=TODAY)
        assert second.iso == first.iso == target.isoformat()
        assert second.days_until == first.days_until
        assert second.overdue is first.overdue


# ═════════════════════════════════════════════════════════════════════════════
# 5 · FRCP 6(a) counting — I-4
# ═════════════════════════════════════════════════════════════════════════════
#
#   6(a)(1)(A)  exclude the day of the event that triggers the period
#   6(a)(1)(B)  count every day, INCLUDING intermediate Saturdays, Sundays and
#               legal holidays
#   6(a)(1)(C)  include the last day, but if it is a Saturday, Sunday or legal
#               holiday, the period continues to run until the next day that is
#               none of those
#   6(a)(6)(A)  "legal holiday" = the eleven named federal holidays
#
# There is no open-source Python court-deadline engine (sourcing report, § 2),
# so this is code we own, and every case below is a hand-worked example.

def cd(start, n, **kw) -> str:
    """`court_days` returns a `Deadline`; these assertions are about its date."""
    result = court_days(start, n, **kw)
    assert isinstance(result, Deadline), f"court_days returned {type(result)!r}"
    return result.iso


def test_i4_the_day_of_the_event_is_not_counted():
    """FRCP 6(a)(1)(A). One day from Tuesday is Wednesday, not Tuesday."""
    assert cd("2026-08-04", 1) == "2026-08-05"      # Tue -> Wed
    assert cd("2026-08-03", 14) == "2026-08-17"     # Mon -> Mon, both business days


def test_i4_intermediate_weekends_are_counted():
    """FRCP 6(a)(1)(B). For a period stated in days, the weekend in the middle
    counts. Thursday + 5 is the following Tuesday — an implementation that
    skips weekends *while* counting returns 2026-08-13 and is two days late on
    every deadline it computes."""
    assert cd("2026-08-06", 5) == "2026-08-11"      # Thu -> Tue, over Sat+Sun
    assert cd("2026-08-10", 21) == "2026-08-31"     # over three weekends
    assert cd("2026-12-19", 14) == "2027-01-04"     # the sourcing report's example


def test_i4_intermediate_holidays_are_counted():
    """FRCP 6(a)(1)(B) again, the half that is easier to get wrong: a holiday
    inside the period is a counted day. Only the *last* day is special."""
    # 2026-11-11 (Veterans Day, Wed) and 2026-11-26 (Thanksgiving) both fall
    # strictly inside these periods, and neither adds a day.
    assert cd("2026-11-09", 4) == "2026-11-13"      # Mon -> Fri, over Veterans Day
    assert cd("2026-11-23", 5) == "2026-11-30"      # Mon -> raw Sat -> Mon


@pytest.mark.parametrize("start,n,expected,why", [
    ("2026-08-04", 4, "2026-08-10", "lands Saturday -> Monday"),
    ("2026-08-04", 5, "2026-08-10", "lands Sunday -> Monday"),
    ("2026-08-04", 6, "2026-08-10", "lands Monday -> unchanged"),
])
def test_i4_the_last_day_rolls_forward_off_a_weekend(start, n, expected, why):
    """FRCP 6(a)(1)(C). Three different periods collapse onto the same Monday —
    which is correct, and is also why a test with a single period proves
    nothing about the roll."""
    assert cd(start, n) == expected, why


@pytest.mark.parametrize("start,n,expected,holiday", [
    ("2026-11-04", 7, "2026-11-12", "Veterans Day, Wed 2026-11-11"),
    ("2026-11-19", 7, "2026-11-27", "Thanksgiving, Thu 2026-11-26"),
    ("2026-05-22", 3, "2026-05-26", "Memorial Day, Mon 2026-05-25"),
    ("2026-01-12", 7, "2026-01-20", "MLK Day, Mon 2026-01-19"),
    ("2026-09-03", 4, "2026-09-08", "Labor Day, Mon 2026-09-07"),
])
def test_i4_the_last_day_rolls_forward_off_a_weekday_holiday(start, n, expected, holiday):
    """FRCP 6(a)(1)(C) + 6(a)(6)(A). A holiday that falls midweek is invisible
    to any weekend-only roll, and the deadline computed is a day early — which
    for a filing deadline means the courthouse is shut."""
    assert cd(start, n) == expected, holiday


@pytest.mark.parametrize("start,n,expected,why", [
    # Independence Day 2026 is a Saturday, so Friday the 3rd is the legal
    # holiday. Landing on it must roll past Sat and Sun to Monday the 6th.
    ("2026-06-29", 4, "2026-07-06", "July 4 2026 is Sat -> observed Fri Jul 3"),
    # Juneteenth 2027 is a Saturday -> observed Friday 2027-06-18.
    ("2027-06-11", 7, "2027-06-21", "Juneteenth 2027 is Sat -> observed Fri"),
    # Christmas 2027 is a Saturday -> observed Friday 2027-12-24.
    ("2027-12-17", 7, "2027-12-27", "Christmas 2027 is Sat -> observed Fri"),
    # New Year's Day 2028 is a Saturday -> observed Friday 2027-12-31.
    ("2027-12-24", 7, "2028-01-03", "New Year 2028 is Sat -> observed Fri, and a year boundary"),
    # Independence Day 2027 is a Sunday -> observed Monday 2027-07-05.
    ("2027-06-28", 7, "2027-07-06", "July 4 2027 is Sun -> observed Mon Jul 5"),
    # Veterans Day 2028 is a Saturday -> observed Friday 2028-11-10.
    ("2028-11-03", 7, "2028-11-13", "Veterans Day 2028 is Sat -> observed Fri"),
    # Veterans Day 2029 is a Sunday -> observed Monday 2029-11-12.
    ("2029-11-05", 7, "2029-11-13", "Veterans Day 2029 is Sun -> observed Mon"),
])
def test_i4_holidays_that_shift_when_they_fall_on_a_weekend(start, n, expected, why):
    """The reason the sourcing report chose `holidays` over a hand-written list.
    A hardcoded "July 4" set sees Friday 2026-07-03 as an ordinary working day
    and returns it — a deadline for a day the court is closed, computed by the
    tool whose only job is not to do that."""
    assert cd(start, n) == expected, why


@pytest.mark.parametrize("start,n,expected", [
    ("2026-12-19", 14, "2027-01-04"),
    ("2026-12-24", 8, "2027-01-04"),      # raw Fri 2027-01-01 is New Year's Day
    ("2026-12-28", 4, "2027-01-04"),      # the same landing, a different period
    ("2027-12-24", 7, "2028-01-03"),      # raw Fri 2027-12-31 is New Year observed
    ("2025-12-26", 6, "2026-01-02"),      # raw Thu 2026-01-01 -> Fri 2026-01-02
])
def test_i4_year_boundaries(start, n, expected):
    """A period that crosses New Year lands in the densest holiday cluster in
    the calendar, and it is where an off-by-one in the roll shows up as a
    multi-day error rather than a one-day one."""
    assert cd(start, n) == expected


def test_i4_dec_31_is_not_automatically_a_holiday():
    """The counter-case to the one above. 2026-12-31 is a Thursday and an
    ordinary working day; only *2027*-12-31 is a legal holiday, and only
    because New Year's Day 2028 falls on a Saturday. An implementation that
    hardcodes "the last day of the year" fails here."""
    assert cd("2026-12-30", 1) == "2026-12-31"
    assert cd("2027-12-30", 1) == "2028-01-03"


@pytest.mark.parametrize("start,n,expected", [
    ("2028-02-28", 1, "2028-02-29"),      # leap day exists and is a Tuesday
    ("2028-02-27", 2, "2028-02-29"),
    ("2028-02-28", 2, "2028-03-01"),
    ("2024-02-28", 1, "2024-02-29"),
    ("2027-02-26", 3, "2027-03-01"),      # no leap day: Fri + 3 = Mon Mar 1
    ("2026-02-27", 2, "2026-03-02"),      # raw Sun 2026-03-01 -> Mon
    ("2028-02-01", 29, "2028-03-01"),     # 29 days across February in a leap year
    ("2027-02-01", 29, "2027-03-02"),     # the same period, one year earlier
])
def test_i4_leap_years(start, n, expected):
    """February is the one month where "plus N days" and "plus N days" differ
    by a year. Both directions across 2028-02-29 and its absence in 2027."""
    assert cd(start, n) == expected


@pytest.mark.parametrize("start,expected,why", [
    ("2026-08-04", "2026-08-04", "a Tuesday — unchanged"),
    ("2026-08-08", "2026-08-10", "a Saturday — rolls to Monday"),
    ("2026-08-09", "2026-08-10", "a Sunday"),
    ("2026-07-03", "2026-07-06", "Independence Day observed, then a weekend"),
    ("2027-12-31", "2028-01-03", "New Year observed, then a weekend, across the year"),
    ("2026-12-25", "2026-12-28", "Christmas Friday, then a weekend"),
])
def test_i4_a_period_of_zero(start, expected, why):
    """n=0 means "the last day is the start day", so 6(a)(1)(C) still applies:
    a zero-day period landing on a Saturday still rolls. This is the degenerate
    case a `while` loop written as `do…while` gets wrong, and it is reachable
    the moment any rule table contains a 0."""
    assert cd(start, 0) == expected, why


def test_i4_backward_counting_never_rolls_the_wrong_way():
    """FRCP 6(a)(1)(C) applied to a period counted *backward* from a hearing —
    e.g. 6(c)(1)'s "at least 14 days before the hearing". The roll goes
    backward too: a filing due on a Saturday is due the preceding Friday,
    because moving it forward would make it late.

    **Open API question, and deliberately permissive about it**: refusing a
    negative period outright is a defensible answer. Rolling it forward is not,
    and that is what the four-line loop in the sourcing report does — it would
    return 2026-08-10 for the first case, a date *after* the hearing it is
    counted back from. If backward counting is unsupported it must be
    unsupported uniformly, not half-implemented.
    """
    cases = [
        ("2026-08-12", -4, "2026-08-07"),    # raw Sat 2026-08-08 -> back to Fri
        ("2026-07-06", -3, "2026-07-02"),    # raw Fri Jul 3 is a holiday -> Thu
        ("2026-11-16", -5, "2026-11-10"),    # raw Wed 2026-11-11 Veterans Day
        ("2028-01-03", -3, "2027-12-30"),    # raw Fri 2027-12-31 observed
        ("2026-08-10", -7, "2026-08-03"),    # raw Mon — nothing to roll
    ]
    refused, computed = [], []
    for start, n, expected in cases:
        try:
            got = court_days(start, n)
        except (ValueError, NotImplementedError) as exc:
            refused.append((start, n, type(exc).__name__))
            continue
        computed.append((start, n))
        assert got.iso == expected, (
            f"court_days({start!r}, {n}) == {got.iso!r}, expected {expected!r}. "
            "A backward period that rolls forward lands after the event it was "
            "counted back from."
        )
    assert not (refused and computed), (
        f"negative periods must be uniformly supported or uniformly refused; "
        f"refused={refused} computed={computed}"
    )


def test_i4_an_unknown_jurisdiction_is_refused_not_silently_federal():
    """I-4 + the sourcing report's honest downside: `holidays` is a national
    calendar, not a court calendar, and treating it as authoritative for a
    jurisdiction whose rules were never encoded computes a confidently wrong
    deadline. Fail closed — the whole design point of the `jurisdiction`
    parameter is that it is *not* a decoration.

    **API note**: if only `"US-federal"` exists in Phase 1, this still holds —
    an unknown key raises rather than falling through to the default.
    """
    for bad in ("US-CA", "CA-superior", "", "federal", "US_FEDERAL", None, 42):
        with pytest.raises((ValueError, KeyError, TypeError)):
            court_days("2026-08-04", 14, jurisdiction=bad)


def test_i4_jurisdiction_is_keyword_only():
    """Pinned from the agreed signature. A positional third argument would let
    `court_days(start, 14, cal)` mean something different in two call sites."""
    with pytest.raises(TypeError):
        court_days("2026-08-04", 14, "US-federal")


def test_i4_court_days_refuses_the_same_garbage_the_parser_does():
    """I-1 and I-5 do not stop at one function. A counting call is an edge too,
    and BUG-4's snooze field is the proof that the second edge is the one that
    gets forgotten."""
    for bad in ("next week", "2026", "", "08/11/2026", "2026-02-30", None):
        with pytest.raises((ValueError, TypeError)):
            court_days(bad, 14)


def test_i4_court_days_refuses_a_non_integer_period():
    """`14.0` and `"14"` are how an unvalidated form field arrives."""
    for bad in ("14", 14.5, None, [14]):
        with pytest.raises((ValueError, TypeError)):
            court_days("2026-08-04", bad)


def test_i1_court_days_result_is_a_deadline_that_re_enters_cleanly():
    """I-1: the result crosses the next boundary as a `Deadline`, and its `iso`
    re-parses to itself — so chaining two rules cannot lose or shift a day."""
    first = court_days("2026-08-04", 14)
    assert parse_deadline(first.iso).iso == first.iso
    assert cd(first.iso, 3) == cd("2026-08-18", 3)


def test_i1_court_days_accepts_a_deadline_as_its_start():
    """I-1 says a date never crosses a module boundary as a string, which makes
    `court_days(some_deadline, 14)` the shape the invariant actually wants —
    FRCP 6(d)'s +3 days for mail service is applied to the output of 6(a).

    **API question**, flagged: if the seam is string-only this fails, and the
    disagreement is worth having now rather than at the first stacked rule.
    """
    start = parse_deadline("2026-08-04")
    assert court_days(start, 14).iso == "2026-08-18"


# ═════════════════════════════════════════════════════════════════════════════
# 6 · Property-based sanity
# ═════════════════════════════════════════════════════════════════════════════

def test_property_iso_round_trip_is_identity_over_five_years():
    """Every date in 2025-2029, through `parse_deadline` and back out of `iso`.
    Fixed cases cannot cover a month-length or padding bug; this can."""
    for d in _walk("2025-01-01", "2029-12-31"):
        assert parse_deadline(d.isoformat()).iso == d.isoformat()


def test_property_long_form_round_trip_is_identity_over_two_years():
    """The same sweep in the format BUG-1 destroyed — 730 dates whose string
    lengths run from 11 to 19 characters. A truncating parser fails on roughly
    every one of them; the original suite had a handful of fixed cases and
    happened to pick a ten-character one."""
    for d in _walk("2026-01-01", "2027-12-31"):
        assert parse_deadline(_long(d)).iso == d.isoformat()
        assert parse_deadline(_long(d, comma=False)).iso == d.isoformat()


def test_property_days_until_is_monotone_and_exact():
    """`days_until` is a difference, so it increases by exactly one per day and
    never repeats. A parser that loses precision — or an `overdue` computed any
    other way — shows up as a plateau or a jump."""
    previous = None
    for d in _walk("2025-06-01", "2027-06-01"):
        dl = Deadline.from_text(d.isoformat(), today=TODAY)
        assert dl.days_until == (d - TODAY_D).days
        if previous is not None:
            assert dl.days_until == previous + 1
        previous = dl.days_until
        assert dl.overdue is (dl.days_until < 0)


def test_property_court_days_never_lands_on_a_weekend_or_a_holiday():
    """FRCP 6(a)(1)(C) as a universal: whatever the start and whatever the
    period, the answer is a day the courthouse is open. Includes n=0, which is
    where the roll is easiest to skip."""
    for start in _walk("2026-01-01", "2029-12-31", step=5):
        for n in (0, 1, 3, 7, 14, 21, 30):
            got = date.fromisoformat(cd(start.isoformat(), n))
            assert not _rollable(got), (
                f"court_days({start}, {n}) == {got} "
                f"({got.strftime('%A')}"
                f"{', a federal holiday' if got in FEDERAL_HOLIDAYS else ''})"
            )


def test_property_the_roll_is_forward_and_minimal():
    """6(a)(1)(C) says the period "continues to run until the next day" that is
    not a Saturday, Sunday or holiday — so the answer is never before the raw
    end date, and never past the first open day after it. A roll of four days
    or more is only reachable at Christmas 2027, and any answer that skips an
    open day is a deadline reported later than it is."""
    for start in _walk("2026-01-01", "2029-12-31", step=3):
        for n in (0, 5, 14):
            raw = start + timedelta(days=n)
            got = date.fromisoformat(cd(start.isoformat(), n))
            assert got >= raw, f"rolled backward: {start} + {n} -> {got}"
            walker = raw
            while _rollable(walker):
                walker += timedelta(days=1)
            assert got == walker, (
                f"court_days({start}, {n}) == {got}; the next open day after "
                f"{raw} is {walker}"
            )


def test_property_an_open_last_day_is_returned_untouched():
    """The other half of 6(a)(1)(B): if the raw end date is already an open
    day, *nothing* happens to it. This is the single test that a business-day
    implementation cannot pass — it moves dates the rule leaves alone."""
    checked = 0
    for start in _walk("2026-01-01", "2028-12-31", step=2):
        for n in (1, 7, 10, 30):
            raw = start + timedelta(days=n)
            if _rollable(raw):
                continue
            assert cd(start.isoformat(), n) == raw.isoformat(), (
                f"{start} + {n} days is {raw} ({raw.strftime('%A')}), an open "
                "day. Intermediate weekends and holidays are counted, not skipped."
            )
            checked += 1
    assert checked > 1200, f"sweep degenerated to {checked} cases"


def test_property_court_days_is_monotone_in_the_period():
    """A longer period never yields an earlier date. Trivially true of correct
    arithmetic, and the first thing to break when the roll and the addition are
    interleaved."""
    for start in ("2026-01-01", "2026-06-29", "2026-12-19", "2027-12-17",
                  "2028-02-27", "2029-11-05"):
        previous = None
        for n in range(0, 45):
            got = date.fromisoformat(cd(start, n))
            if previous is not None:
                assert got >= previous, f"court_days({start}, {n}) went backward"
            previous = got


def test_property_zero_is_a_fixed_point():
    """`court_days(court_days(d, 0), 0)` is `court_days(d, 0)`. If it is not,
    the roll is being applied to something other than the last day."""
    for start in _walk("2026-06-01", "2028-06-01", step=11):
        once = cd(start.isoformat(), 0)
        assert cd(once, 0) == once


def test_property_every_accepted_format_agrees_with_every_other():
    """I-1 across the whole corpus: the parser is a function onto dates, not
    onto formats. Six spellings of 400 dates, one answer each."""
    for d in _walk("2026-01-01", "2027-02-04", step=1):
        spellings = [d.isoformat(), _long(d), _long(d, comma=False),
                     _long(d, pad=True), f"{d.day} {MONTHS[d.month - 1]} {d.year}",
                     f"{d.isoformat()}T00:00:00"]
        answers = {parse_deadline(s).iso for s in spellings}
        assert answers == {d.isoformat()}, (d, answers)


# ═════════════════════════════════════════════════════════════════════════════
# 7 · The corpus's own guards
# ═════════════════════════════════════════════════════════════════════════════

def test_holiday_table_still_matches_the_holidays_package():
    """The frozen `FEDERAL_HOLIDAYS` table above is this file's oracle, so it
    needs its own check. `holidays` (MIT, v0.102) is the source it was taken
    from; if a future release corrects an observed-day rule, this fails here
    rather than as a mysterious counting failure."""
    if _holidays is None:
        pytest.fail(
            "the `holidays` package is not installed. I-4 names it as the "
            "holiday source and I-27 says declared dependencies are true — a "
            "court-deadline engine whose calendar is missing must not be a "
            "quietly skipped test."
        )
    years = range(2025, 2031)
    lo, hi = date(2025, 1, 1), date(2030, 12, 31)
    live = {d for d in _holidays.US(years=years) if lo <= d <= hi}
    assert live == set(FEDERAL_HOLIDAYS), {
        "in holidays, not in table": sorted(live - set(FEDERAL_HOLIDAYS)),
        "in table, not in holidays": sorted(set(FEDERAL_HOLIDAYS) - live),
    }


def test_the_corpus_has_not_been_hollowed_out():
    """Phase 0's audit found tests that had quietly stopped enforcing what they
    claimed. A table trimmed to two rows is the cheapest way for that to happen
    again, so the tables assert their own size — and the accept and refuse sets
    assert they never overlap, which is what a "fix" that widens the format
    list until the suite passes would produce."""
    accepted = {t for t, _ in BUG1_FORMS + EXTENDED_FORMS}
    refused = set(REFUSED) | set(TRUNCATION_TRAPS) | set(ISO_LENIENCY_TRAPS)
    assert len(BUG1_FORMS) == 6
    assert len(EXTENDED_FORMS) >= 9
    assert len(REFUSED) >= 50
    assert len(TRUNCATION_TRAPS) >= 10
    assert len(ISO_LENIENCY_TRAPS) >= 4
    assert len(LEXICOGRAPHIC_TRAPS) >= 8
    assert not accepted & refused, accepted & refused
    assert len(FEDERAL_HOLIDAYS) >= 70
