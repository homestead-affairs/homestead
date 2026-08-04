"""One `Deadline` type, one strict parser, and the FRCP 6(a) counting rules.

**A missed deadline is not a bug ticket; it is harm.** Everything below is
shaped by that, and by four defects that already happened in the application
this one replaces.

* **I-1 — one type, parsed once, at the edge.** `Deadline` is the only thing
  that crosses a module boundary. Nothing downstream re-parses, re-slices or
  re-compares a date string, because nothing downstream is given one.

* **I-2 — parse strictly or refuse.** BUG-1 sliced the input to ten characters
  *before* trying the long-form formats it declared it supported, so
  `"May 5 2026"` (exactly ten) parsed and `"May 5, 2026"` (eleven) returned
  `None`. The same date, one comma apart, opposite answers — which is why it
  survived casual testing for as long as it did. **Every pattern here is
  anchored to the whole string. There is no prefix, no slice, no `[:10]`.**

* **I-3 — one source for every derived fact.** BUG-3 computed `days_until` by
  parsing and `overdue` by comparing raw strings, so one item carried
  `days_until = -91` and `overdue = False` at the same time (`"M" > "2"` in
  ASCII). Here `overdue` is `days_until < 0` and `days_until` is arithmetic on
  `self.date`. They cannot disagree because there is only one of them.

* **I-5 — no free text.** BUG-4's snooze field took whatever was typed and
  string-compared it: `"next week"` hid an urgent deadline until the year 2099,
  `"08/11/2026"` did nothing at all, and there was no un-snooze anywhere in the
  codebase. A date this module cannot read becomes a **visible refusal** —
  never a guess, never a silent `None`.

**Refusing is the feature.** `UnparseableDate` carries the accepted forms in
its message so a refusal tells the user what to type instead.

---

## What the parser accepts

| Form | Example |
|---|---|
| ISO calendar date | `2026-08-10`, and unpadded `2026-8-4` |
| ISO date-time (date part taken, time and offset discarded) | `2026-08-10T09:00:00`, `2026-08-10 09:00`, `...T09:00:00+00:00`, `...Z` |
| Month name, day, year | `August 10, 2026`, `Aug 10 2026`, `Sept. 1st, 2026` |
| Day, month name, year | `1 July 2026`, `1st Jul. 2026` |

Month names are matched against an **explicit English table**, not `%B`.
CPython's `_strptime` builds its month names from `calendar.month_name`, keyed
on `locale.getlocale(LC_TIME)` — so a `%B` format set is not a fixed format
set, it is a per-machine one, and "the same string parses here and refuses
there" is BUG-1's data-dependence in a different coordinate. Case is ignored;
an abbreviation may carry a trailing period; a day may carry an ordinal suffix.

## What it refuses — all of it by raising, none of it by returning `None`

* **Partial dates.** `"2026"`, `"June"`, `"30"`, `"August 2026"`. `dateutil`
  fills these in from *today* — `'2026'` → `2026-08-04`, `'June'` →
  `2026-06-04` — which is BUG-1 inverted and worse: a confident wrong date
  instead of a lost one. `dateutil.parser` is not imported here and a test
  asserts no module in this package imports it.
* **Natural language.** `"next week"`, `"Monday"`, `"TBD"`, `"see order"`,
  `"on or before Aug 1"`, `"12/31/2026 or sooner"`.
* **All-numeric slashed forms** — `03/04/2026`, `08/11/2026`, `12/31/2026`.
  `%m/%d/%Y` and `%d/%m/%Y` are indistinguishable, and refusing only the
  genuinely ambiguous ones (`03/04`) while accepting the rest (`12/31`) would
  re-create exactly the data-dependent split that let BUG-1 live: one format,
  two behaviours, decided by the value. The whole family is refused, uniformly,
  and the refusal names ISO as the form to use.
* **Impossible days.** `2026-02-30`, `February 30, 2026`, `2026-13-01`.
* **Anything with trailing or leading matter.** `"2026-08-10 (per order)"`.
* **Anything that is not a string**, including `None` — a missing deadline is
  the exact shape BUG-1 produced, and it must arrive as a refusal rather than
  as a different exception type the caller may have forgotten to catch.

Two-digit years are not accepted in any form: `26-08-10` has no reading this
module is willing to pick.

## What it does not do

* No timezone reasoning. A deadline is a **court day**, not an instant. When an
  ISO date-time carries a time or an offset, both are discarded and the date is
  taken **as written** — `2026-08-10T23:00:00-05:00` is 2026-08-10 here, even
  though it is 2026-08-11 in UTC. If a caller needs the UTC day, it must
  convert before it parses.
* No relative dates, no recurrence, no durations, no "business days from now".
* `days_until` is whole days between two calendar dates. It does not know what
  time of day a filing closes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Container

import holidays

__all__ = [
    "Deadline",
    "UnparseableDate",
    "parse_deadline",
    "court_days",
    "ACCEPTED_FORMS",
    "JURISDICTIONS",
]


class UnparseableDate(ValueError):
    """A date this module refuses to guess at.

    One exception type for every refusal — a wrong value, a wrong type, an
    impossible day, an ambiguous format. A caller that handles refusal handles
    all of it, and cannot accidentally handle three quarters of it.
    """


#: Shown to a human when a refusal happens. A refusal that does not say what
#: would have worked is just a dead end with a stack trace attached.
ACCEPTED_FORMS: tuple[str, ...] = (
    "2026-08-10",
    "2026-08-10T09:00:00",
    "August 10, 2026",
    "Aug 10 2026",
    "10 August 2026",
)

_MONTHS: dict[str, int] = {}
for _i, (_full, _abbr) in enumerate(
    [
        ("january", "jan"), ("february", "feb"), ("march", "mar"),
        ("april", "apr"), ("may", "may"), ("june", "jun"),
        ("july", "jul"), ("august", "aug"), ("september", "sep"),
        ("october", "oct"), ("november", "nov"), ("december", "dec"),
    ],
    start=1,
):
    _MONTHS[_full] = _i
    _MONTHS[_abbr] = _i
_MONTHS["sept"] = 9          # the one four-letter abbreviation people write
del _i, _full, _abbr

_ORD = r"(?:st|nd|rd|th)?"

# Every pattern is anchored at both ends. That anchoring *is* the BUG-1 fix:
# a string with anything extra in it is refused rather than trimmed to fit.
_ISO_DATE = re.compile(r"\A(\d{4})-(\d{1,2})-(\d{1,2})\Z")
_ISO_DATETIME = re.compile(
    r"\A(\d{4})-(\d{2})-(\d{2})"                    # padded: machines pad
    r"[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"     # time, seconds optional
    r"(?:[Zz]|[+-]\d{2}:?\d{2})?\Z"                 # offset, discarded
)
_MONTH_FIRST = re.compile(
    rf"\A([A-Za-z]{{3,9}})\.?\s+(\d{{1,2}}){_ORD},?\s+(\d{{4}})\Z", re.IGNORECASE
)
_DAY_FIRST = re.compile(
    rf"\A(\d{{1,2}}){_ORD}\s+([A-Za-z]{{3,9}})\.?,?\s+(\d{{4}})\Z", re.IGNORECASE
)


_SLASHED = re.compile(r"\A\d{1,4}[/.]\d{1,2}[/.]\d{1,4}\Z")


def _refuse(text: Any, why: str) -> UnparseableDate:
    message = (
        f"refusing {text!r}: {why}. A deadline must be exact — accepted forms "
        f"are {', '.join(ACCEPTED_FORMS)}."
    )
    if isinstance(text, str) and _SLASHED.match(text.strip()):
        message += (
            " Slashed numeric dates are refused as a family: 03/04/2026 is "
            "March 4th or April 3rd depending on who typed it, and accepting "
            "only the unambiguous ones would put one format with two "
            "behaviours back in the parser. Write it as 2026-03-04."
        )
    return UnparseableDate(message)


def _build(text: str, year: int, month: int, day: int) -> date:
    """Values that matched a shape, checked against the calendar."""
    try:
        return date(year, month, day)
    except ValueError as exc:                # Feb 30, month 13, day 0 …
        raise _refuse(text, f"no such calendar day ({exc})") from None


def _parse(text: Any) -> date:
    """The whole parser. Returns a `date` or raises; never returns `None`."""
    if isinstance(text, bool) or not isinstance(text, str):
        raise _refuse(text, f"a deadline must be text, not {type(text).__name__}")

    s = text.strip()
    if not s:
        raise _refuse(text, "empty")

    m = _ISO_DATE.match(s) or _ISO_DATETIME.match(s)
    if m:
        return _build(s, int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = _MONTH_FIRST.match(s)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month is None:
            raise _refuse(text, f"{m.group(1)!r} is not a month")
        return _build(s, int(m.group(3)), month, int(m.group(2)))

    m = _DAY_FIRST.match(s)
    if m:
        month = _MONTHS.get(m.group(2).lower())
        if month is None:
            raise _refuse(text, f"{m.group(2)!r} is not a month")
        return _build(s, int(m.group(3)), month, int(m.group(1)))

    raise _refuse(text, "no accepted date format matches the whole string")


def _as_date(value: Any, *, what: str) -> date:
    """A `date` from a `Deadline`, a `date`, or a string this module accepts.

    `datetime` is refused rather than truncated. It is a `date` subclass, so
    accepting it would let a value carrying a time and an offset sit in a field
    documented as a calendar day — and `.iso` would quietly grow a `T09:00:00`.
    """
    if isinstance(value, Deadline):
        return value.date
    if isinstance(value, datetime):
        raise _refuse(value, f"{what} is a calendar day, not an instant")
    if isinstance(value, date):
        return value
    return _parse(value)


@dataclass(frozen=True, order=True)
class Deadline:
    """A court date, parsed once, immutable, and the source of its own facts.

    `date` is the only stored fact. `iso`, `days_until` and `overdue` are all
    computed from it on every read, so there is no second copy to drift out of
    step with the first — which is precisely what BUG-3 was.

    `reference` is the "today" this deadline reckons against. It exists so a
    test, a briefing, or a rendered queue can be **deterministic**: pass the day
    you mean and the answer does not depend on when the process happened to
    run. When it is `None`, `days_until` reads the machine clock at call time —
    so a long-lived `Deadline` with no reference correctly becomes overdue
    while it sits there.

    `reference` is excluded from equality and ordering: two deadlines on the
    same day are the same deadline, however they were reckoned. Sorting a list
    of them sorts by date.
    """

    date: date
    reference: date | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        for name in ("date", "reference"):
            value = getattr(self, name)
            if value is None and name == "reference":
                continue
            if isinstance(value, datetime) or not isinstance(value, date):
                raise _refuse(
                    value, f"{name} must be a datetime.date (a calendar day)"
                )

    # ── the derived facts, all from `self.date` ──────────────────────────────

    @property
    def iso(self) -> str:
        """`YYYY-MM-DD`. The only spelling this application writes down."""
        return self.date.isoformat()

    @property
    def days_until(self) -> int:
        """Whole days from the reference day to the deadline. Negative if past.

        `0` means the deadline is today, which is **not** overdue: the day of a
        deadline is a day on which you can still act.
        """
        return (self.date - self._reference_day()).days

    @property
    def overdue(self) -> bool:
        """`days_until < 0`, and nothing else, ever.

        Not a string comparison (BUG-3), not a second parse (BUG-1), not a
        separately-stored flag that a writer can forget to update.
        """
        return self.days_until < 0

    def _reference_day(self) -> date:
        return self.reference if self.reference is not None else date.today()

    def against(self, today: Any) -> "Deadline":
        """The same day, reckoned against a different one. Returns a new value."""
        return Deadline(self.date, _as_date(today, what="today"))

    def __str__(self) -> str:
        return self.iso

    @classmethod
    def from_text(cls, text: Any, today: Any = None) -> "Deadline":
        """Parse at the edge. `today` fixes the reckoning day for determinism.

        `today` takes the same forms as `text` (or a `date`, or `None` for the
        machine clock) and is parsed by the same function — there is one parser
        in this module and no input reaches a second one.
        """
        return parse_deadline(text, today)


def parse_deadline(text: Any, today: Any = None) -> Deadline:
    """Strict parse, or `UnparseableDate`. The edge of the whole application.

    See the module docstring for the accepted set and the refused set. There is
    no permissive mode, no `default=`, and no `None` return: a deadline that
    cannot be read is a refusal the user must see, because the alternative —
    silently losing it, or silently inventing it — is how a hard court date
    ends up at the bottom of a queue.
    """
    return Deadline(
        _parse(text),
        _as_date(today, what="today") if today is not None else None,
    )


# ── FRCP 6(a) · counting ─────────────────────────────────────────────────────

#: The jurisdictions whose rules are implemented. Anything else is refused —
#: a court-deadline engine that silently applies the wrong jurisdiction's rules
#: is worse than one that has never heard of yours.
JURISDICTIONS: tuple[str, ...] = ("US-federal",)


@lru_cache(maxsize=8)
def _federal_calendar() -> Container:
    """The eleven federal legal holidays, plus their observed days.

    `holidays.US()` populates a year the first time a date in it is tested, so
    this is built once and answers any year. It is the *national* calendar:
    FRCP 6(a)(6)(A) names exactly the federal holidays, and 6(a)(6)(B) adds days
    declared by the President or Congress, which a released calendar cannot know
    in advance.

    Observed days matter and are included: 2026-07-04 falls on a Saturday, so
    Friday 2026-07-03 is the legal holiday and federal courthouses are shut.

    One shared object, populated lazily and cached. Nothing here mutates it and
    nothing outside this module is handed it, because a caller that assigned a
    key into it would be editing the calendar every other caller reads.
    """
    return holidays.US()


def _closed_set(calendar: Any) -> Container:
    """Normalize an injected calendar, or leave it alone if it knows its job.

    A plain collection of dates is the obvious thing for a caller to pass, and
    `date(2026, 8, 11) in ["2026-08-11"]` is `False` — a local closure the
    caller believed they had declared, silently ignored, producing a deadline
    that is one day too early with nothing to show for it. So concrete
    collections are re-read through the same parser, which either converts the
    members or refuses them. Anything else (a `holidays` calendar, a dict, a
    custom object) is used as given: it already answers `in` for a `date`, and
    materializing it would force a lazy calendar to answer for no years at all.
    """
    if isinstance(calendar, (set, frozenset, list, tuple)):
        return frozenset(_as_date(x, what="a closure day") for x in calendar)
    return calendar


def _calendar_for(jurisdiction: str) -> Container:
    if jurisdiction not in JURISDICTIONS:
        raise UnparseableDate(
            f"no counting rules for {jurisdiction!r}. Implemented: "
            f"{', '.join(JURISDICTIONS)}. Pass holiday_calendar= to supply "
            f"your own, and own the answer."
        )
    return _federal_calendar()


def _is_closed(day: date, calendar: Container) -> bool:
    return day.weekday() >= 5 or day in calendar


def court_days(
    start: Any,
    n: int,
    *,
    jurisdiction: str = "US-federal",
    holiday_calendar: Container | None = None,
) -> Deadline:
    """`n` days from `start` under **FRCP 6(a)(1)**, rolled under **6(a)(6)**.

    Exactly three sentences of rule, implemented exactly:

    * **6(a)(1)(A)** — exclude the day of the event that triggers the period.
      `start + 1 day` is day one.
    * **6(a)(1)(B)** — count every day, **including** intermediate Saturdays,
      Sundays and legal holidays.
    * **6(a)(1)(C)** — include the last day; but if the last day is a Saturday,
      a Sunday or a legal holiday, the period runs to the next day that is none
      of those. **6(a)(6)** is what "legal holiday" means.

    **The name says days, and it means calendar days.** This is *not* a
    business-day or "court day" counter. `court_days(start, 5)` is five
    calendar days with a roll at the end, not five open days — the pre-2009
    FRCP short-period rule that skipped weekends while counting was repealed,
    but its state analogues (California CCP §12a and §1005, and others) are
    alive and are **not implemented here**. Asking this function for a
    California court-day period gives a confidently wrong answer.

    What else is deliberately absent, because claiming it would be worse than
    lacking it:

    * **6(a)(2)** periods stated in hours, and **6(a)(4)**'s end-of-day rules.
    * **6(a)(3)** extension when the clerk's office is inaccessible.
    * **6(a)(5)** backward computation. A negative `n` is refused rather than
      guessed: for a period measured *backward* from a hearing, the roll runs
      backward too, and getting that direction wrong moves a deadline the wrong
      way past a weekend. It is a real rule and it deserves its own tested
      implementation, not a sign flip on this one.
    * **6(d)**'s three added days for service by mail, and every state analogue.
      Service method is not an input here.
    * **6(a)(6)(C)** state-declared holidays, which count for periods measured
      after an event in the state where the district court sits. `jurisdiction`
      is federal-only for that reason; a state overlay goes in
      `holiday_calendar`.

    **The calendar is a national holiday list, not a court calendar, and the
    answer is a computed suggestion — not an authority.** Individual
    courthouses close for judicial conferences, county holidays, furloughs and
    weather, and a day declared a holiday by the President mid-year is not in
    an already-released calendar. Both directions of calendar error cause harm:
    a missing closure computes a deadline that is too early and the filing is
    rejected; a spurious closure computes one that is too late and the deadline
    is missed. Confirm against the court's own calendar before relying on it.

    `holiday_calendar` is the seam for that: anything supporting
    `date in calendar` — `holidays.US(subdiv="MA")`, a `frozenset` of dates, or
    a wrapper adding local closures. A plain `set`, `list`, `frozenset` or
    `tuple` is re-read through this module's parser, so a list of ISO strings
    works and a list of unparseable ones is refused rather than silently
    matching nothing. When it is supplied it **replaces** the jurisdiction's
    calendar entirely and `jurisdiction` becomes a label the caller owns;
    nothing else in this module reads it.

    `start` may be a `Deadline`, a `date`, or any text `parse_deadline` accepts.
    A `Deadline`'s reference day is carried through, so a computed deadline
    stays as deterministic as the one it was computed from.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise UnparseableDate(
            f"a period is a whole number of days, not {type(n).__name__}"
        )
    if n < 0:
        raise UnparseableDate(
            f"refusing to count {n} days backward: FRCP 6(a)(5) rolls backward "
            "off a weekend or holiday, not forward, and that rule is not "
            "implemented here"
        )

    if not isinstance(jurisdiction, str) or not jurisdiction.strip():
        raise UnparseableDate("jurisdiction must be a non-empty string")
    calendar = (
        _closed_set(holiday_calendar) if holiday_calendar is not None
        else _calendar_for(jurisdiction)
    )

    begin = _as_date(start, what="start")
    reference = start.reference if isinstance(start, Deadline) else None

    try:
        day = begin + timedelta(days=n)
        while _is_closed(day, calendar):
            day += timedelta(days=1)
    except OverflowError:
        raise UnparseableDate(
            f"{n} days from {begin.isoformat()} falls outside the calendar "
            "this application can represent"
        ) from None

    return Deadline(day, reference)
