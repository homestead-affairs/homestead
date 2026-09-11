"""One `Deadline` type, one strict parser, and the FRCP 6(a) counting rules.

Four counting functions read one rule table: `court_days` (forward, FRCP
6(a)(1)), `court_days_before` (backward, 6(a)(5)), `add_mail_days`
(6(d)/9006(f)) and `business_days`. See `RULES` and `RuleStatus` — a rule this
module has not checked is refused, never guessed at.

**Three jurisdictions, not one.** `US-federal` (FRBP 9006(a) = FRCP 6(a)),
`US-NM` (Rule 1-006 NMRA; NMSA 12-2A-7) and `US-OR` (ORCP 10 A/C).
`JURISDICTIONS` is `tuple(RULES)`, so the list and the table cannot disagree;
`docs/PHASE1-DATES.md` carries the per-branch verification status, and every
`UNCERTAIN` branch refuses rather than computing. *(Annotated 2026-09-11,
X7-drift audit: the opening line says "the FRCP 6(a) counting rules" and said
nothing else from 0.3.0 onward, while `RULES` grew its two state rows in
0.6.0. The line stays as written — it is true of the federal row and it is
what this module was when it was one jurisdiction wide.)*

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
* No relative dates, no recurrence, no durations. **No "business days from
  now" as a *parsed* form** — `business_days(start, n)` computes one, but
  nothing here reads the phrase out of a text field. That distinction is the
  whole of BUG-4: the counting functions take a validated date and an integer,
  never a string a litigant typed.
* `days_until` is whole days between two calendar dates. It does not know what
  time of day a filing closes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from functools import lru_cache
from typing import Any, Callable, Container

import holidays

__all__ = [
    "Deadline",
    "UnparseableDate",
    "parse_deadline",
    "RuleStatus",
    "CountingRule",
    "RULES",
    "court_days",
    "court_days_before",
    "add_mail_days",
    "business_days",
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


# ── FRCP 6(a) / FRBP 9006 · counting rules ───────────────────────────────────
#
# **Sourcing note, read before trusting `status`.** Every primary text has
# been tried twice from this environment — once when the table was built and
# again on audit (2026-09-11) — and every one of them is refused by the
# organization's egress proxy before the request leaves the box:
# law.cornell.edu (LII), uscourts.gov, govinfo.gov (GPO), uscode.house.gov,
# supremecourt.gov, and the rules-reference mirrors as well. The refusal is
# the network's, not the source's.
#
# `US-federal` therefore ships `VERIFIED` on converging independent secondary
# restatements, and **each row's `source` string says so in its own words** —
# see the PROVENANCE sentence at the end of `source` and `mail_days_source`
# below, and `RuleStatus`'s docstring for what `VERIFIED` does and does not
# promise. That disclosure travels with the value: a caller that renders or
# cites `RULES[...].source` cannot end up quoting this table as if it had read
# the rule. FRCP 6(a) / FRBP 9006(a) is settled, uncontested text — unlike the
# NM and OR rows this table is about to grow, where the plan already expects
# UNCERTAIN. Replace the PROVENANCE sentence with a primary quotation the
# first time one can be read; do not delete it without one.


class RuleStatus(str, Enum):
    """Whether a `CountingRule`'s text has been checked — and against what.

    `VERIFIED` means the row's counting text was checked against the rule as
    written **and the row's `source` string says where that text was read**.
    It is not, on its own, a claim of a primary source: when the primary text
    cannot be reached from the build environment, `source` must name the
    secondary basis and the date it was checked, so that a reader who needs
    the primary knows they still have to go and read it. `US-federal` is
    exactly such a row — its `source` ends in a PROVENANCE sentence, and that
    sentence is the honest half of its `VERIFIED`.

    A row may never be `VERIFIED` on a `source` that does not say where its
    text came from. That rule is the only thing this enum is for, and
    `test_i41_verified_rows_disclose_where_their_text_came_from` enforces it.

    `UNCERTAIN` means "not checked," not "probably right" — every counting
    function below refuses rather than compute from a rule marked this way.
    I-11 (fail closed) applied to legal citations.

    A `str` enum for rendering only. Nothing in this module compares a status
    to a string: the check is `is RuleStatus.VERIFIED`, an identity test that
    a stray equal string cannot pass. Its two values are disjoint from every
    other `str` enum in the package, so `rungs._check_the_str_enums_cannot_be_
    confused` has nothing to learn about it — see
    `test_i41_rule_status_cannot_be_confused_with_the_gate_enums`.
    """

    VERIFIED = "verified"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class CountingRule:
    """One jurisdiction's whole counting rule: what it cites, and how it counts.

    `calendar` is a zero-argument callable so building one (and paying
    `holidays.US()`'s per-year lazy-population cost) is deferred to the first
    date actually asked about — see `_federal_calendar`.

    **Four branches, four independent statuses.** `US-federal` shipped
    (E1-dates-a) with one `status` covering everything, because every branch
    of FRCP 6 / FRBP 9006 happened to rest on the same secondary-restatement
    basis. `US-NM` and `US-OR` (E1-dates-b) do not: a state's forward-counting
    rule can be corroborated by several converging summaries of a 2024
    amendment while its backward-counting and mail-service rules are not
    stated in anything this module could read. So each branch below carries
    its own `RuleStatus` and its own citation string, and a caller asking for
    one branch is refused or served on that branch's own evidence — never on
    whether some *other* branch of the same rule happens to be settled:

    * `status` / `source` — the ordinary forward branch (FRCP 6(a)(1)/(6);
      periods of `short_period_max` days or more, or every period when
      `short_period_max` is `None`).
    * `short_period_status` / `short_period_source` — periods **strictly
      less than** `short_period_max` days, which exclude intermediate
      Saturdays, Sundays and legal holidays while counting rather than
      merely rolling the last day (the shape `business_days` already
      implements — see `court_days`). `short_period_max` is `None` for a
      jurisdiction that counts every period the same way (the FRCP/FRBP
      shape since the 2009 Time-Computation amendment repealed the
      pre-2009 short-period exclusion); a jurisdiction whose short periods
      still exclude intermediate closures sets it to the largest period,
      in days, that rule applies to.
    * `backward_status` / `backward_source` — FRCP 6(a)(5) / FRBP
      9006(a)(5), a period measured *before* an event.
    * `mail_days` / `mail_days_source` / `mail_status` — FRCP 6(d) / FRBP
      9006(f), added to an already-rolled end.

    `district_state_source` is not a branch and carries no status: it is the
    citation for FRCP 6(a)(6)(C) / FRBP 9006(a)(6)(C)'s *state-where-the-
    court-sits* addition, and it is `None` for a jurisdiction that has no
    such rule. Adding one state's holidays to another sovereign's court
    calendar is a **federal** rule about **federal** district courts; a state
    court applies its own state's holidays and nothing else (see the note
    above `_nm_calendar`). So `court_days`/`add_mail_days` refuse
    `district_state=` on any row whose `district_state_source` is `None`,
    rather than silently unioning a calendar no rule authorizes.

    A row may be `VERIFIED` on some branches and `UNCERTAIN` on others; each
    counting function below checks only the branch(es) it needs.
    """

    jurisdiction: str
    source: str
    status: RuleStatus
    short_period_max: int | None
    short_period_source: str
    short_period_status: RuleStatus
    backward_source: str
    backward_status: RuleStatus
    mail_days: int | None
    mail_days_source: str
    mail_status: RuleStatus
    district_state_source: str | None
    calendar: Callable[[], Container]


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


class _MergedCalendar:
    """Answers `in` against two calendars without merging or mutating either
    — `holidays.US()` populates itself lazily, per year, so a `frozenset`
    union up front would force both sources to answer for every year at once."""

    __slots__ = ("_a", "_b")

    def __init__(self, a: Container, b: Container) -> None:
        self._a = a
        self._b = b

    def __contains__(self, day: object) -> bool:
        return day in self._a or day in self._b


@lru_cache(maxsize=64)
def _state_calendar(state: str) -> Container:
    """`holidays.US(subdiv=state)`, built once. Its `NotImplementedError` for
    an unrecognized code becomes a named refusal instead of a traceback
    surfacing a dependency the caller may not know is involved."""
    try:
        return holidays.US(subdiv=state)
    except NotImplementedError as exc:
        raise UnparseableDate(
            f"{state!r} is not a US state or territory `holidays` recognizes "
            f"as a court subdivision: {exc}"
        ) from None


# ── a state court's calendar is the STATE's holidays, not a union ───────────
#
# `US-NM` and `US-OR` are **state** counting rules — Rule 1-006 NMRA and
# ORCP 10 — so "legal holiday" in them means the *state's* legal holidays
# (NMSA 1978 § 12-5-2; ORS 187.010/.020), and nothing else. The federal list
# has no standing in a state district court.
#
# The union with the federal calendar belongs to exactly one place and it is
# not here: FRBP 9006(a)(6)(C) / FRCP 6(a)(6)(C), where a **federal** court
# sitting in a state adds *that state's* holidays to the federal ones for a
# period measured after an event. That is `_district_calendar`, reached by
# `court_days(..., district_state="NM")`, and it stays a union.
#
# Unioning here instead would close days the state courts are open on, and a
# spurious closure computes a deadline that is too LATE — see `court_days`'s
# "Both directions of calendar error cause harm" paragraph. Concretely, on
# the `holidays` 0.104 data this module reads:
#
# * New Mexico is named in that library's Washington's-Birthday exclusion
#   set (`_populate_subdiv_holidays`: subdiv "NM" gets no third-Monday-in-
#   February holiday at all) and `_populate_subdiv_nm_public_holidays` adds
#   "Presidents' Day" one day past the fourth Thursday of November instead.
#   NM courts are therefore OPEN on 2027-02-15 and CLOSED on 2026-11-27.
#   A union re-closes that February Monday from the federal side.
# * Oregon is absent from that library's Columbus Day subdivision list, so
#   OR courts are OPEN on Columbus Day (2026-10-12); ORS 187.010 does not
#   list it. A union re-closes it. Oregon *does* keep the February Monday,
#   under its own name ("Presidents Day", 3rd Mon of Feb), so that day is
#   closed on the state list itself and needs no help from the union.
#
# PROVENANCE, 2026-09-11: the statutes themselves (NMSA 12-5-2, ORS 187.010)
# could not be read from this environment — every host tried is EGRESS_BLOCKED,
# see `RULES` below. What *was* read, and is asserted by
# `test_nm_and_or_calendars_are_the_states_own_not_a_union_with_the_federal_
# one`, is the `holidays` package's own subdivision data and the source
# comments around it, which cite ORS 187 for Oregon. That is a secondary
# basis of the same class as the rest of this table, and it is the calendar
# mechanism the plan named (`holidays.US(subdiv=…)`). Confirm against the
# court's own published calendar before relying on a computed date — that
# instruction is in `court_days`'s docstring and it is not decoration.


@lru_cache(maxsize=8)
def _nm_calendar() -> Container:
    """`holidays.US(subdiv="NM")` — New Mexico's own legal holidays, built
    once. **Not** unioned with the federal calendar; see the note above for
    why a state court's rule reads the state's list alone."""
    return _state_calendar("NM")


@lru_cache(maxsize=8)
def _or_calendar() -> Container:
    """`holidays.US(subdiv="OR")` — Oregon's own legal holidays, built once.
    **Not** unioned with the federal calendar; see the note above."""
    return _state_calendar("OR")


#: One row per implemented jurisdiction. `JURISDICTIONS` below is *derived*
#: from this dict's keys — there is no second, hand-kept list to drift out of
#: sync with it (a prior version of this module had exactly that drift risk).
RULES: dict[str, CountingRule] = {
    "US-federal": CountingRule(
        jurisdiction="US-federal",
        source=(
            "FRBP 9006(a) ≡ FRCP 6(a)(1), (5), (6): exclude the day of the "
            "triggering event; count every day, including intermediate "
            "Saturdays, Sundays and legal holidays; a period measured AFTER an "
            "event whose last day falls on one of those rolls FORWARD to the "
            "next day that is none of those (6(a)(1)(C)/9006(a)(1)(C)); a "
            "period measured BEFORE an event rolls BACKWARD instead "
            "(6(a)(5)/9006(a)(5)) — 'the \"next day\" is determined by "
            "continuing to count forward when the period is measured after an "
            "event and backward when measured before an event.' The pre-2009 "
            "short-period exclusion of intermediate weekends/holidays for "
            "periods under 11 days was repealed; the 2009 Time-Computation "
            "amendment's committee note is 'time is now computed in the same "
            "way' for every period, hence short_period_max=None below. "
            "'Legal holiday' under 6(a)(6)(A)/9006(a)(6)(A) is the eleven "
            "named federal holidays (see `_federal_calendar`); 6(a)(6)(C)/"
            "9006(a)(6)(C) adds 'any other day declared a holiday by ... the "
            "state where the district court is located' for periods measured "
            "AFTER an event only — see `court_days`'s `district_state` and "
            "`court_days_before`'s docstring for the backward exception. "
            "PROVENANCE, 2026-09-11: the wording above is quoted from "
            "converging independent secondary restatements, NOT from a "
            "primary text read here. Every primary host — law.cornell.edu "
            "(LII), uscourts.gov, govinfo.gov (GPO), uscode.house.gov, "
            "supremecourt.gov — is refused by this environment's egress "
            "proxy, on the build pass and again on audit. VERIFIED is "
            "claimed because five restatements agree clause for clause on "
            "(a)(1)(A)-(C), (a)(5) and (a)(6)(C), including the forward-only "
            "asymmetry and the 2009 Time-Computation committee note, and "
            "because this rule is settled, uncontested text. Replace this "
            "sentence with a primary quotation the first time one can be "
            "read; do not delete it without one."
        ),
        status=RuleStatus.VERIFIED,
        short_period_max=None,
        short_period_source=(
            "FRCP 6(a)'s pre-2009 short-period exclusion — periods under 11 "
            "days excluded intermediate Saturdays, Sundays and legal "
            "holidays while counting — was repealed by the 2009 "
            "Time-Computation amendment; its committee note is 'time is now "
            "computed in the same way' for every period, which is why "
            "`short_period_max=None` here: there is no separate short-period "
            "shape left to verify. PROVENANCE, 2026-09-11: the same "
            "converging-secondary-restatement basis as `source` above, "
            "unreachable from this environment for the same reason — "
            "law.cornell.edu, uscourts.gov, govinfo.gov, uscode.house.gov and "
            "supremecourt.gov are all refused by the egress proxy."
        ),
        short_period_status=RuleStatus.VERIFIED,
        backward_source=(
            "FRCP 6(a)(5) / FRBP 9006(a)(5): 'the \"next day\" is determined "
            "by continuing to count forward when the period is measured "
            "after an event and backward when measured before an event' — a "
            "period measured before an event excludes the event day, counts "
            "every day including intermediate Saturdays, Sundays and legal "
            "holidays (6(a)(1)(B), unchanged by direction), and rolls "
            "BACKWARD off a Saturday, Sunday or legal holiday landing on the "
            "last (earliest) day counted. PROVENANCE, 2026-09-11: quoted "
            "from converging independent secondary restatements, not from a "
            "primary text read here — the same blocked hosts named in "
            "`source` above (law.cornell.edu, uscourts.gov, govinfo.gov, "
            "uscode.house.gov, supremecourt.gov)."
        ),
        backward_status=RuleStatus.VERIFIED,
        mail_days=3,
        mail_days_source=(
            "FRCP 6(d) / FRBP 9006(f): when a party may or must act within a "
            "specified time after being served, and service is made under "
            "Rule 5(b)(2)(C) (mail), (D) (leaving with the clerk when the "
            "person has no known address), or (F) (other means the party "
            "consented to in writing), 3 days are added after the period "
            "would otherwise expire under (a) — i.e. after 6(a)/9006(a)'s "
            "roll has already been applied, not before it. NOT (E) — "
            "electronic service — as of the amendment effective 2016-12-01, "
            "which removed the extra 3 days for service made electronically "
            "under Rule 5(b)(2)(E). 9006(f) spells the same set as 'by mail "
            "or under Rule 5(b)(2)(D) or (F) F.R.Civ.P.'; the phrase 'would "
            "otherwise expire under Rule 9006(a)' was added precisely to say "
            "that the 3 days attach to the END the counting rules produce. "
            "PROVENANCE, 2026-09-11: quoted from converging independent "
            "secondary restatements, not from a primary text read here — see "
            "`source` above for which hosts are blocked and what VERIFIED is "
            "being claimed on."
        ),
        mail_status=RuleStatus.VERIFIED,
        district_state_source=(
            "FRCP 6(a)(6)(C) / FRBP 9006(a)(6)(C): 'legal holiday' includes "
            "'for periods that are measured after an event, any other day "
            "declared a holiday by the state where the district court is "
            "located' — a federal rule about a federal district court "
            "sitting in a state, and forward-only (hence no district_state "
            "on court_days_before). PROVENANCE, 2026-09-11: the same "
            "converging-secondary-restatement basis as `source` above, and "
            "unreachable here for the same reason — law.cornell.edu, "
            "uscourts.gov, govinfo.gov, uscode.house.gov and "
            "supremecourt.gov are all refused by this environment's egress "
            "proxy."
        ),
        calendar=_federal_calendar,
    ),
    "US-NM": CountingRule(
        jurisdiction="US-NM",
        source=(
            "Rule 1-006(A) NMRA (eff. 2024-11-01): in computing a period "
            "prescribed by rule, court order or applicable statute, exclude "
            "the day of the act or event that triggers the period; count "
            "every day, including intermediate Saturdays, Sundays and legal "
            "holidays, unless the period is less than 11 days (see "
            "`short_period_source` below); include the last day, unless it "
            "is a Saturday, Sunday or legal holiday, in which case the "
            "period runs to the next day that is none of those. NMSA 1978 "
            "§ 12-2A-7 governs computation of statutory time periods and is "
            "reported to be consistent with this shape. PROVENANCE, "
            "2026-09-11: tried supremecourt.nmcourts.gov/wp-content/uploads/"
            "sites/2/2024/11/Rule-1-006-NMRA.pdf, law.justia.com/codes/"
            "new-mexico/2021/chapter-12/article-2a/section-12-2a-7/ and "
            "nmonesource.com/nmos/nmra/en/item/5661/index.do — each refused "
            "by this environment's egress proxy (EGRESS_BLOCKED) before the "
            "request left the box. 'Legal holiday' here means NEW MEXICO's "
            "legal holidays (NMSA 1978 § 12-5-2), read from "
            "`holidays.US(subdiv=\"NM\")` alone and NOT unioned with the "
            "federal list — see the note above `_nm_calendar`. New Mexico "
            "keeps Presidents' Day on the Friday after Thanksgiving and "
            "observes no third-Monday-in-February holiday, so a federal "
            "union would close a day its district courts are open on. "
            "VERIFIED-secondary is claimed for this ≥11-day forward branch "
            "only: multiple independent secondary "
            "summaries of the 2024-11-01 amendment agree, clause for "
            "clause, that periods of 11 days or more now count every day "
            "and roll forward off a closed last day — the post-2009 federal "
            "shape. Replace this sentence with a primary quotation the "
            "first time one of the three URLs above can be read."
        ),
        status=RuleStatus.VERIFIED,
        short_period_max=11,
        short_period_source=(
            "Rule 1-006(A) NMRA is reported, by the same secondary "
            "summaries as `source` above, to keep a pre-2009-FRCP-style "
            "exclusion for periods under 11 days: intermediate Saturdays, "
            "Sundays and legal holidays are excluded from the count rather "
            "than only rolling the last day. UNCERTAIN, 2026-09-11: none of "
            "the three candidate sources loads from this environment — "
            "supremecourt.nmcourts.gov/wp-content/uploads/sites/2/2024/11/"
            "Rule-1-006-NMRA.pdf, law.justia.com/codes/new-mexico/2021/"
            "chapter-12/article-2a/section-12-2a-7/, nmonesource.com/nmos/"
            "nmra/en/item/5661/index.do — each EGRESS_BLOCKED before the "
            "request left the box. Refusing rather than guessing at the "
            "exact boundary and exclusion set; read one of the three and "
            "quote the operative sentence here to flip this to VERIFIED."
        ),
        short_period_status=RuleStatus.UNCERTAIN,
        backward_source=(
            "Not stated in anything this module could read. Every secondary "
            "summary of Rule 1-006 NMRA found so far speaks only to periods "
            "measured forward from an act or event; none confirms whether "
            "New Mexico has a rule for a period measured backward from a "
            "hearing or filing date (the FRCP 6(a)(5) shape), or what it "
            "says if it does. UNCERTAIN, 2026-09-11: the same three URLs "
            "tried for `source` above — supremecourt.nmcourts.gov/"
            "wp-content/uploads/sites/2/2024/11/Rule-1-006-NMRA.pdf, "
            "law.justia.com/codes/new-mexico/2021/chapter-12/article-2a/"
            "section-12-2a-7/, nmonesource.com/nmos/nmra/en/item/5661/"
            "index.do — are all EGRESS_BLOCKED. Refuse rather than assume "
            "New Mexico mirrors FRCP 6(a)(5); read a primary text to settle "
            "it either way."
        ),
        backward_status=RuleStatus.UNCERTAIN,
        mail_days=3,
        mail_days_source=(
            "Rule 1-006(D)-ish (secondary summaries describe a 3-day "
            "addition for service by mail); the 2024-11-01 amendment is "
            "also reported to add 3 days for service made via a court "
            "facility under Rule 1-005(C)(1)(e) NMRA. UNCERTAIN, "
            "2026-09-11: neither the figure's exact rule letter nor how the "
            "re-roll onto a closed landing day is computed is confirmed "
            "against a primary text — supremecourt.nmcourts.gov/wp-content/"
            "uploads/sites/2/2024/11/Rule-1-006-NMRA.pdf, law.justia.com/"
            "codes/new-mexico/2021/chapter-12/article-2a/section-12-2a-7/ "
            "and nmonesource.com/nmos/nmra/en/item/5661/index.do are all "
            "EGRESS_BLOCKED. Refusing the re-roll rather than guessing "
            "which calendar or roll direction governs it."
        ),
        mail_status=RuleStatus.UNCERTAIN,
        # Rule 1-006 NMRA states no counterpart to FRBP 9006(a)(6)(C): a New
        # Mexico district court reads New Mexico's legal holidays and no
        # other sovereign's. A federal case pending IN the District of New
        # Mexico is `US-federal` with district_state="NM", not this row.
        district_state_source=None,
        calendar=_nm_calendar,
    ),
    "US-OR": CountingRule(
        jurisdiction="US-OR",
        source=(
            "ORCP 10 A: in computing a period of time prescribed or allowed "
            "by these rules, by court order, or by an applicable statute, "
            "exclude the day of the act or event from which the period "
            "begins to run; count every day, including intermediate "
            "Saturdays, Sundays and legal holidays, unless the period is "
            "less than 7 days (see `short_period_source` below); include "
            "the last day, unless it is a Saturday, Sunday or legal "
            "holiday, in which case the period runs until the next day "
            "that is none of those. ORS 187.010 and 187.020 define "
            "Oregon's legal holidays, and that list — read from "
            "`holidays.US(subdiv=\"OR\")` alone, NOT unioned with the "
            "federal list (see the note above `_or_calendar`) — does not "
            "include Columbus Day, so Oregon's courts are open on the "
            "second Monday in October even though the federal courts are "
            "not. Oregon does keep the third Monday in February, under its "
            "own name. PROVENANCE, 2026-09-11: tried "
            "oregon.public.law/rules-of-civil-procedure/orcp-10-time/, "
            "refused by this environment's egress proxy (EGRESS_BLOCKED) "
            "before the request left the box. VERIFIED-secondary on "
            "converging independent secondary restatements of ORCP 10 A, "
            "which mirror the FRCP 6(a) shape for periods of 7 days or "
            "more. Replace this sentence with a primary quotation the "
            "first time oregon.public.law or another primary host can be "
            "read."
        ),
        status=RuleStatus.VERIFIED,
        short_period_max=7,
        short_period_source=(
            "ORCP 10 A's short-period clause, as secondarily restated: "
            "when the prescribed period is less than 7 days, intermediate "
            "Saturdays, Sundays and legal holidays are excluded from the "
            "computation rather than only rolling the last day — the "
            "pre-2009-FRCP shape most surviving state short-period rules "
            "share. PROVENANCE, 2026-09-11: tried oregon.public.law/"
            "rules-of-civil-procedure/orcp-10-time/ — where the rule text "
            "is reported to be quoted — refused by this environment's "
            "egress proxy (EGRESS_BLOCKED) before the request left the "
            "box. VERIFIED-secondary on converging independent secondary "
            "restatements that describe this exclusion identically. "
            "Replace this sentence with a primary quotation the first time "
            "oregon.public.law can be read."
        ),
        short_period_status=RuleStatus.VERIFIED,
        backward_source=(
            "Not stated in anything this module could read. ORCP 10's "
            "secondary restatements speak only to periods measured forward "
            "from an act or event; none confirms whether Oregon has a rule "
            "for a period measured backward from a hearing or filing date "
            "(the FRCP 6(a)(5) shape), or what it says if it does. "
            "UNCERTAIN, 2026-09-11: tried oregon.public.law/"
            "rules-of-civil-procedure/orcp-10-time/, EGRESS_BLOCKED before "
            "the request left the box. Refuse rather than assume Oregon "
            "mirrors FRCP 6(a)(5); read a primary text to settle it either "
            "way."
        ),
        backward_status=RuleStatus.UNCERTAIN,
        mail_days=3,
        mail_days_source=(
            "ORCP 10 C (letter UNCERTAIN): secondary reporting of Harvey v. "
            "Christie (Or. App. 2010) — reporter citation not confirmed "
            "here, name and year only — describes a 3-day mail addition "
            "applied under ORCP 10 C. Oregon's civil "
            "procedure rules are amended biennially by the Council on Court "
            "Procedures, and this module could not confirm from a primary "
            "text that the mail-days clause is still lettered 'C' after the "
            "amendments since 2010 — UNCERTAIN, 2026-09-11: tried "
            "oregon.public.law/rules-of-civil-procedure/orcp-10-time/, "
            "EGRESS_BLOCKED before the request left the box. Refusing to "
            "add 3 days under a section letter that might not be current; "
            "read the current rule to confirm the letter and flip this to "
            "VERIFIED."
        ),
        mail_status=RuleStatus.UNCERTAIN,
        # ORCP 10 states no counterpart to FRCP 6(a)(6)(C): an Oregon circuit
        # court reads Oregon's legal holidays and no other sovereign's. A
        # federal case pending IN the District of Oregon is `US-federal`
        # with district_state="OR", not this row.
        district_state_source=None,
        calendar=_or_calendar,
    ),
}

#: The jurisdictions whose rules are implemented. Anything else is refused —
#: a court-deadline engine that silently applies the wrong jurisdiction's rules
#: is worse than one that has never heard of yours. Derived from `RULES`, so a
#: jurisdiction cannot be added to one and forgotten in the other.
JURISDICTIONS: tuple[str, ...] = tuple(RULES)


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


def _rule_for(jurisdiction: Any) -> CountingRule:
    """The `CountingRule` for a jurisdiction, or a named refusal.

    Looks up `RULES` directly, not `JURISDICTIONS` — a rule planted into
    `RULES` at test time is found the same way a real row is.
    """
    if not isinstance(jurisdiction, str) or not jurisdiction.strip():
        raise UnparseableDate("jurisdiction must be a non-empty string")
    rule = RULES.get(jurisdiction)
    if rule is None:
        raise UnparseableDate(
            f"no counting rules for {jurisdiction!r}. Implemented: "
            f"{', '.join(JURISDICTIONS)}. Pass holiday_calendar= to supply "
            f"your own, and own the answer."
        )
    return rule


def _require_verified(rule: CountingRule, *, needs: str, status: RuleStatus, source: str) -> None:
    """Fail closed (I-11): `UNCERTAIN: ...`, naming the jurisdiction and the
    citation the caller would otherwise be trusting unchecked.

    `status` and `source` are the caller's — one `CountingRule` carries four
    independent branches (forward, short-period, backward, mail; see
    `CountingRule`'s docstring), and which one is being trusted right now is
    the caller's to say, not something this function guesses from the rule.
    """
    if status is not RuleStatus.VERIFIED:
        raise UnparseableDate(
            f"UNCERTAIN: {needs} for {rule.jurisdiction} is not verified "
            f"against a primary source — {source}. Refusing rather than "
            "guessing: pass holiday_calendar= and own the answer yourself, or "
            "wait for the rule to be verified."
        )


def _short_period_max_for(jurisdiction: Any) -> int | None:
    """The jurisdiction's short-period threshold, read without requiring the
    rule to exist or be verified.

    Used only so a `holiday_calendar` override can replace *the calendar*
    without also replacing *which counting shape applies* — see `court_days`.
    An unrecognized jurisdiction (a label the caller invented for their own
    calendar, e.g. `"US-County"`) has no rule and therefore no short-period
    shape to preserve, so this returns `None` rather than raising; the
    already-verified-or-refused path for a *known* jurisdiction with no
    override is `_rule_for`, not this.
    """
    rule = RULES.get(jurisdiction) if isinstance(jurisdiction, str) else None
    return rule.short_period_max if rule is not None else None


def _require_district_state_rule(rule: CountingRule) -> None:
    """Refuse `district_state=` on a jurisdiction that has no such rule.

    Called **before** the branch status check, not after: whether a caller
    may pass this argument at all is a question about the jurisdiction, not
    about how well-read its counting text is, and answering "UNCERTAIN: the
    added-mail-days rule for US-NM…" to someone who passed a meaningless
    argument sends them to read a rule that was never their problem.
    """
    if rule.district_state_source is None:
        raise UnparseableDate(
            f"{rule.jurisdiction} has no district-state rule: "
            "6(a)(6)(C)/9006(a)(6)(C) is a FEDERAL rule about a FEDERAL "
            "district court sitting in a state, and adds that state's "
            f"holidays to the federal ones. {rule.jurisdiction} is a state "
            "court's own counting rule and reads its own state's legal "
            "holidays only, so there is no second sovereign's calendar to "
            "add. If you meant a federal case pending in that district, "
            "pass jurisdiction='US-federal' with district_state=; if you "
            "meant a local closure, pass holiday_calendar= and own the "
            "answer."
        )


def _district_calendar(rule: CountingRule, district_state: Any) -> Container:
    """FRCP 6(a)(6)(C) / FRBP 9006(a)(6)(C): the federal calendar plus one
    state's, for a period measured *after* an event.

    Deliberately has no backward counterpart — see `court_days_before`'s
    docstring for why a state holiday must never reach a backward count.
    """
    if not isinstance(district_state, str) or not district_state.strip():
        raise UnparseableDate(
            "district_state must be a USPS state code, e.g. 'NM' or 'OR' — "
            "9006(a)(6)(C) adds the holidays of the state where the district "
            "court sits, for periods measured after an event"
        )
    return _MergedCalendar(rule.calendar(), _state_calendar(district_state))


def _is_closed(day: date, calendar: Container) -> bool:
    return day.weekday() >= 5 or day in calendar


def _count_open_days(begin: date, n: int, calendar: Container) -> date:
    """`n` open days forward from `begin` (excluded), skipping closures WHILE
    counting rather than only rolling the last one. One loop, read from two
    call sites — `business_days` and `court_days`'s short-period branch —
    so the two shapes can never silently drift apart on the same
    jurisdiction; `n=0` rolls `begin` itself forward if it is closed, the
    same degenerate case `court_days`'s ordinary branch has."""
    day = begin
    if n == 0:
        while _is_closed(day, calendar):
            day += timedelta(days=1)
    else:
        counted = 0
        while counted < n:
            day += timedelta(days=1)
            if not _is_closed(day, calendar):
                counted += 1
    return day


def court_days(
    start: Any,
    n: int,
    *,
    jurisdiction: str = "US-federal",
    holiday_calendar: Container | None = None,
    district_state: str | None = None,
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

    **The name says days, and it means calendar days — for `US-federal`.**
    `court_days(start, 5)` under `US-federal` is five calendar days with a
    roll at the end, not five open days — the pre-2009 FRCP short-period rule
    that skipped weekends while counting was repealed for federal periods
    (`RULES["US-federal"].short_period_max is None`).

    **Its state analogues are alive elsewhere, and this function implements
    them too, from the same rule table.** When `jurisdiction`'s
    `short_period_max` is not `None` and `n` is strictly less than it, this
    function switches shape: intermediate Saturdays, Sundays and legal
    holidays are *excluded while counting* — the `business_days` shape,
    reused here rather than duplicated — instead of counted and only rolled
    off the last day. `US-NM` (`short_period_max=11`) and `US-OR`
    (`short_period_max=7`) both work this way below that threshold and the
    ordinary FRCP shape at or above it; that boundary, and whether either
    branch is verified, is read from `RULES` — see `short_period_status` on
    `CountingRule`. A caller who wants the ordinary shape unconditionally,
    regardless of jurisdiction, is `business_days`'s opposite number and has
    no separate function here: it *is* what `court_days` does at or above the
    threshold, including the federal `None` case where there is no threshold
    to be below.

    What else is deliberately absent, because claiming it would be worse than
    lacking it:

    * **6(a)(2)** periods stated in hours, and **6(a)(4)**'s end-of-day rules.
    * **6(a)(3)** extension when the clerk's office is inaccessible.

    A period measured **backward** from an event — **6(a)(5)** — is the
    different function `court_days_before`, not a negative `n`: the roll
    direction is opposite. **6(d)** / **9006(f)**'s three added mail days are
    `add_mail_days`, applied to this function's *output*, never folded into
    `n` here. **6(a)(6)(C)** / **9006(a)(6)(C)** adds the legal holidays of
    the state where the district court sits, for periods measured *after* an
    event only — pass `district_state` (a USPS code, e.g. `"NM"`) to add them
    to the default calendar; combining it with `holiday_calendar` is refused
    rather than silently picking one, since the explicit calendar already
    decides what is closed. `court_days_before` accepts no `district_state`
    at all — see its docstring for why a state holiday must never reach a
    backward count. It is also refused on a **state** jurisdiction
    (`US-NM`, `US-OR`): 6(a)(6)(C) is a federal rule about a federal
    district court sitting in a state, and a state court reads its own
    state's legal holidays alone — see `CountingRule.district_state_source`
    and the note above `_nm_calendar`. A federal case pending in the
    District of New Mexico is `jurisdiction="US-federal",
    district_state="NM"`, not `jurisdiction="US-NM"`; the two are different
    courts with different calendars and different counting rules, and this
    module will not let one stand in for the other.

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
    calendar and bypasses the *ordinary* branch's `RULES` status check — but
    it does **not** replace which counting *shape* applies.
    `short_period_max` still comes from `RULES[jurisdiction]` when the
    jurisdiction is known, so `court_days("...", 5, jurisdiction="US-OR",
    holiday_calendar=my_cal)` excludes intermediate closures while counting
    (OR's short-period shape, `short_period_max=7`) rather than counting
    them and rolling once. Only for a jurisdiction with **no** row in
    `RULES` at all (a label the caller invented, e.g. `"US-County"`) is
    there no shape to preserve, and the ordinary shape is used.

    **The short-period branch's status is the one thing an override does not
    buy out**, and the reason is `add_mail_days`'s reason. On the ordinary
    branch a caller supplying both `n` and the calendar has left nothing of
    the rule in the answer, so the status has nothing to say. On the short
    branch the rule is still doing the work — the threshold itself, and
    "exclude intermediate Saturdays, Sundays and legal holidays while
    counting" — so `court_days("...", 5, jurisdiction="US-NM",
    holiday_calendar=my_cal)` **refuses** while NM's `short_period_status`
    is `UNCERTAIN`: NM's own citation says it is "refusing rather than
    guessing at the exact boundary and exclusion set," and a supplied
    calendar supplies neither of those. A caller who genuinely owns that
    answer wants `business_days(start, n, holiday_calendar=…)` — the
    identical arithmetic, with no jurisdiction's short-period rule claimed
    for it. Fail closed (I-11) beats seam symmetry, in both places.

    What it does **not** replace is Saturday and Sunday. 6(a)(1)(C) names
    "a Saturday, a Sunday, or a legal holiday" as three separate things, and
    only the third is a calendar; a weekend is closed because the rule says
    so, not because a calendar lists it. So `holiday_calendar=frozenset()`
    is "no holidays at all", not "nothing is closed" — a period landing on a
    Saturday still rolls to Monday. A jurisdiction that files on Saturdays
    would need a different counting rule, not a different calendar.

    `n=0` means "the last day is `start` itself", still subject to
    6(a)(1)(C): a zero-day period landing on a closed day rolls forward like
    any other.

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
            f"refusing to count {n} days backward: a period measured before "
            "an event rolls backward under FRCP 6(a)(5) / FRBP 9006(a)(5), "
            "which this function does not implement for a negative n — call "
            "court_days_before(end, -n, ...) instead"
        )

    if not isinstance(jurisdiction, str) or not jurisdiction.strip():
        raise UnparseableDate("jurisdiction must be a non-empty string")

    if holiday_calendar is not None:
        if district_state is not None:
            raise UnparseableDate(
                "district_state and holiday_calendar are mutually exclusive: "
                "supplying your own calendar already decides what is closed, "
                "so add the state's closures to it yourself"
            )
        calendar = _closed_set(holiday_calendar)
        short_max = _short_period_max_for(jurisdiction)
        if short_max is not None and n < short_max:
            # The one status check an override does NOT buy out, and the
            # reason is `add_mail_days`'s: a caller who hands over a calendar
            # has supplied the closed days, not the *rule*. Here the rule is
            # still doing the work — `short_max` itself, and "exclude
            # intermediate closures while counting" — so if that branch is
            # UNCERTAIN, an unverified rule is being applied to a verified
            # calendar. Fail closed (I-11). `business_days(start, n,
            # holiday_calendar=…)` is the same arithmetic with no
            # jurisdiction's short-period rule claimed for it, and is what a
            # caller who genuinely owns the answer should call.
            short_rule = RULES[jurisdiction]      # non-None short_max ⇒ present
            _require_verified(
                short_rule, needs="short-period counting",
                status=short_rule.short_period_status,
                source=short_rule.short_period_source,
            )
    else:
        rule = _rule_for(jurisdiction)
        if district_state is not None:
            _require_district_state_rule(rule)
        short_max = rule.short_period_max
        if short_max is not None and n < short_max:
            _require_verified(
                rule, needs="short-period counting",
                status=rule.short_period_status, source=rule.short_period_source,
            )
        else:
            _require_verified(
                rule, needs="forward counting",
                status=rule.status, source=rule.source,
            )
        calendar = (
            _district_calendar(rule, district_state) if district_state is not None
            else rule.calendar()
        )

    begin = _as_date(start, what="start")
    reference = start.reference if isinstance(start, Deadline) else None
    short = short_max is not None and n < short_max

    try:
        if short:
            # The `business_days` shape: closures are excluded WHILE
            # counting, not just rolled off at the end — see the module
            # docstring's "short_period_max" note on `CountingRule`. The
            # same loop `business_days` runs, via `_count_open_days`, so
            # this branch and that function can never silently disagree.
            day = _count_open_days(begin, n, calendar)
        else:
            day = begin + timedelta(days=n)
            while _is_closed(day, calendar):
                day += timedelta(days=1)
    except OverflowError:
        raise UnparseableDate(
            f"{n} days from {begin.isoformat()} falls outside the calendar "
            "this application can represent"
        ) from None

    return Deadline(day, reference)


def court_days_before(
    end: Any,
    n: int,
    *,
    jurisdiction: str = "US-federal",
    holiday_calendar: Container | None = None,
) -> Deadline:
    """`n` days **before** `end`, rolled **backward** under FRCP 6(a)(5) /
    FRBP 9006(a)(5) — the period a hearing notice, a response deadline, or an
    "at least N days before the hearing" rule measures.

    *"The 'next day' is determined by continuing to count forward when the
    period is measured after an event and backward when measured before an
    event."* Mirrored from `court_days`: the event day (`end`) is excluded;
    every day counts on the way, including intermediate weekends and
    holidays (6(a)(1)(B), unchanged by direction); and if the **last** day
    counted — the *earliest* one, since this counts backward — is a
    Saturday, Sunday or legal holiday, the period keeps running **backward**
    to the previous open day. Rolling forward instead (`court_days`'s
    direction) would land the result *after* the event it was counted back
    from — `n` days too late by construction, the defect this function
    exists to rule out.

    **Deliberately has no `district_state` parameter.** 6(a)(6)(C) /
    9006(a)(6)(C) adds the state-where-the-court-sits' holidays only for
    periods measured *after* an event — the asymmetry is the rule, not a gap.
    ABI's practitioner note "Rule 9006 Creates Trap for Date-Specific
    Deadlines" (abi.org) states it plainly: a filing due 14 days *after* an
    event whose 14th day is a state holiday moves to the next day, but a
    filing due 14 days *before* an event on that same state holiday is still
    due that day — a state holiday has no effect on a backward-counted
    period. Accepting `district_state` here would invite exactly that
    mistake, so it does not exist. (Federal holidays still apply in both
    directions; only the state addition is forward-only.)

    `n=0` is the mirror of `court_days`'s: the last day counted is `end`
    itself, and if `end` is closed the period keeps running **backward** to
    the previous open day — `court_days_before("2026-12-25", 0)` is
    2026-12-24, where `court_days("2026-12-25", 0)` is 2026-12-28. The two
    degenerate cases must not answer the same, because the whole point of
    having two functions is that the roll has a direction; a rule table with
    a 0 in it reaches this the first time it is used.

    `holiday_calendar` behaves exactly as on `court_days`, including that it
    does not make weekends open: supplied, it replaces the jurisdiction's
    calendar and bypasses the `RULES` status check — here, `backward_status`
    on `CountingRule`, checked independently of the forward branch's
    `status` (`US-NM` and `US-OR` verify forward counting on the 2024/ORCP
    text while their backward branch is `UNCERTAIN`; a caller who wants the
    forward answer is unaffected by that). `end` takes the same forms as
    `start` there.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise UnparseableDate(
            f"a period is a whole number of days, not {type(n).__name__}"
        )
    if n < 0:
        raise UnparseableDate(
            f"refusing to count {n} days: court_days_before already counts "
            "backward from end — pass the number of days before the event as "
            "a non-negative n, not a negative one"
        )

    if not isinstance(jurisdiction, str) or not jurisdiction.strip():
        raise UnparseableDate("jurisdiction must be a non-empty string")

    if holiday_calendar is not None:
        calendar = _closed_set(holiday_calendar)
    else:
        rule = _rule_for(jurisdiction)
        _require_verified(
            rule, needs="backward counting",
            status=rule.backward_status, source=rule.backward_source,
        )
        calendar = rule.calendar()

    finish = _as_date(end, what="end")
    reference = end.reference if isinstance(end, Deadline) else None

    try:
        day = finish - timedelta(days=n)
        while _is_closed(day, calendar):
            day -= timedelta(days=1)
    except OverflowError:
        raise UnparseableDate(
            f"{n} days before {finish.isoformat()} falls outside the "
            "calendar this application can represent"
        ) from None

    return Deadline(day, reference)


def add_mail_days(
    deadline: Any,
    *,
    jurisdiction: str = "US-federal",
    holiday_calendar: Container | None = None,
    district_state: str | None = None,
) -> Deadline:
    """FRCP 6(d) / FRBP 9006(f): add the jurisdiction's mail days to a
    deadline **already rolled** under `court_days` or `court_days_before`.

    "3 days are added after the period would otherwise expire under (a)" —
    the addition happens to the *rolled* end date, not the raw arithmetic
    before that roll, which is why this takes a computed `Deadline` rather
    than a `start` and an `n`. The 3 days are then rolled **forward** again
    if they land on a Saturday, Sunday or legal holiday — the 2005 committee
    note's posture: the added days are themselves computed under (a), so a
    closed landing still moves to the next open day rather than standing.

    Refuses (`"UNCERTAIN: ..."`) when the jurisdiction's mail-days branch
    (`mail_status`, checked against `mail_days_source`) is not
    `RuleStatus.VERIFIED`, regardless of whether its forward, short-period or
    backward branch is — and refuses if the rule records no figure at all
    (`mail_days is None`); a verified "there is no mail rule" is not a number
    to add.

    **`holiday_calendar` is a narrower seam here than on the other three
    functions, and the difference is deliberate.** Supplied, it replaces the
    calendar the re-roll reads — but it does **not** bypass the `RULES` status
    check the way it does on `court_days`, `court_days_before` and
    `business_days`. There, the caller supplies both the period (`n`) and the
    calendar, so nothing of the rule is left in the answer and the status has
    nothing to say. Here the *number being added* is `rule.mail_days`: a
    caller who hands over a calendar has still not supplied the figure, so an
    unverified rule is still being trusted for it and this function still
    refuses. Fail closed (I-11) beats seam symmetry. (It does not make
    weekends open either — see `court_days`.)

    **`district_state` belongs here too, and its absence was a real hole.**
    The added days are computed *under (a)* — that is what "would otherwise
    expire under Rule 6(a)/9006(a)" makes them — so 6(a)(6)(C)'s state
    addition governs the re-roll exactly as it governs `court_days`'s roll.
    Without it, `add_mail_days(court_days(x, 14, district_state="NM"))`
    re-rolls on the *federal* calendar and can hand back a day the District
    of New Mexico is shut: 2026-11-24 + 3 is Friday 2026-11-27, which is a
    federal working day and an NM court holiday (New Mexico keeps
    Presidents' Day on the Friday after Thanksgiving). Pass the same
    `district_state` you passed to `court_days` — and, as there, it is
    refused on a state jurisdiction whose `district_state_source` is
    `None`.

    This stays forward-only by construction: mail days are always *added*, so
    there is no direction to get wrong here the way there would be on
    `court_days_before`. That is also the reason 6(d)/9006(f) itself is a
    forward rule — it applies when a party must act "within a specified time
    **after being served**". Applying it to a backward-counted period is the
    caller's judgement call and this function will not stop them, but the
    state addition is not what makes that call wrong or right.

    `deadline` takes the same forms as `start` there — typically the
    `Deadline` `court_days` or `court_days_before` just returned.
    """
    if not isinstance(jurisdiction, str) or not jurisdiction.strip():
        raise UnparseableDate("jurisdiction must be a non-empty string")

    rule = _rule_for(jurisdiction)
    if district_state is not None and holiday_calendar is None:
        _require_district_state_rule(rule)
    _require_verified(
        rule, needs="the added-mail-days rule",
        status=rule.mail_status, source=rule.mail_days_source,
    )
    if rule.mail_days is None:
        raise UnparseableDate(
            f"{rule.jurisdiction} records no mail-days figure to add"
        )

    if holiday_calendar is not None:
        if district_state is not None:
            raise UnparseableDate(
                "district_state and holiday_calendar are mutually exclusive: "
                "supplying your own calendar already decides what is closed, "
                "so add the state's closures to it yourself"
            )
        calendar = _closed_set(holiday_calendar)
    else:
        calendar = (
            _district_calendar(rule, district_state) if district_state is not None
            else rule.calendar()
        )

    end = _as_date(deadline, what="deadline")
    reference = deadline.reference if isinstance(deadline, Deadline) else None

    try:
        day = end + timedelta(days=rule.mail_days)
        while _is_closed(day, calendar):
            day += timedelta(days=1)
    except OverflowError:
        raise UnparseableDate(
            f"{rule.mail_days} mail days from {end.isoformat()} falls "
            "outside the calendar this application can represent"
        ) from None

    return Deadline(day, reference)


def business_days(
    start: Any,
    n: int,
    *,
    jurisdiction: str = "US-federal",
    holiday_calendar: Container | None = None,
) -> Deadline:
    """`n` **open** days from `start` — Saturdays, Sundays and legal holidays
    are skipped *while counting*, not just rolled off at the end.

    This is the counter federal `court_days` deliberately is not: FRCP
    6(a)(1)(B) / FRBP 9006(a)(1)(B) count intermediate closures rather than
    skip them. `business_days` is the other shape a "days" period can take —
    the pre-2009 short-period shape — kept as a general-purpose counter
    rather than a bespoke loop per jurisdiction; `court_days` reuses this
    exact shape internally for `US-NM` and `US-OR` below their
    `short_period_max`, so this function and that branch of `court_days`
    always agree by construction (one loop, not two copies of it).

    `start` is excluded (6(a)(1)(A)'s framing) and `n` open days are counted
    forward; the landing day is always open by construction, so there is no
    separate roll step. `n=0` means "`start` itself," rolled forward if
    `start` is closed — same degenerate case as `court_days`.

    Forward only: `n` must be non-negative, since there is no established
    backward business-day rule the way `court_days_before` encodes one for
    calendar days. `jurisdiction`, `holiday_calendar` and the `RULES` status
    check behave exactly as on `court_days`'s ordinary (forward, `status`/
    `source`) branch — this function is not itself one of the four branches
    a `CountingRule` distinguishes; it always trusts the jurisdiction's
    ordinary forward status, regardless of that jurisdiction's short-period
    or backward status.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise UnparseableDate(
            f"a period is a whole number of days, not {type(n).__name__}"
        )
    if n < 0:
        raise UnparseableDate(
            f"refusing to count {n} business days backward: no backward "
            "business-day rule is implemented here"
        )

    if not isinstance(jurisdiction, str) or not jurisdiction.strip():
        raise UnparseableDate("jurisdiction must be a non-empty string")

    if holiday_calendar is not None:
        calendar = _closed_set(holiday_calendar)
    else:
        rule = _rule_for(jurisdiction)
        _require_verified(
            rule, needs="business-day counting",
            status=rule.status, source=rule.source,
        )
        calendar = rule.calendar()

    begin = _as_date(start, what="start")
    reference = start.reference if isinstance(start, Deadline) else None

    try:
        day = _count_open_days(begin, n, calendar)
    except OverflowError:
        raise UnparseableDate(
            f"{n} business days from {begin.isoformat()} falls outside the "
            "calendar this application can represent"
        ) from None

    return Deadline(day, reference)
