"""One `Deadline` type, one strict parser, and the FRCP 6(a) counting rules.

Four counting functions read one rule table: `court_days` (forward, FRCP
6(a)(1)), `court_days_before` (backward, 6(a)(5)), `add_mail_days`
(6(d)/9006(f)) and `business_days`. See `RULES` and `RuleStatus` — a rule this
module has not checked is refused, never guessed at.

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

    `short_period_max` is `None` for a jurisdiction that counts every period
    the same way (the FRCP/FRBP shape since the 2009 amendment); a
    jurisdiction whose short periods exclude intermediate closures sets it to
    the largest period, in days, that applies to. `mail_days` /
    `mail_days_source` are the separate FRCP 6(d) / FRBP 9006(f) citation — a
    jurisdiction can have one branch settled and the other not.
    """

    jurisdiction: str
    source: str
    short_period_max: int | None
    mail_days: int | None
    mail_days_source: str
    status: RuleStatus
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
        short_period_max=None,
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
        status=RuleStatus.VERIFIED,
        calendar=_federal_calendar,
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


def _require_verified(rule: CountingRule, *, needs: str, source: str) -> None:
    """Fail closed (I-11): `UNCERTAIN: ...`, naming the jurisdiction and the
    citation the caller would otherwise be trusting unchecked."""
    if rule.status is not RuleStatus.VERIFIED:
        raise UnparseableDate(
            f"UNCERTAIN: {needs} for {rule.jurisdiction} is not verified "
            f"against a primary source — {source}. Refusing rather than "
            "guessing: pass holiday_calendar= and own the answer yourself, or "
            "wait for the rule to be verified."
        )


def _verified_rule(jurisdiction: Any, *, needs: str, mail: bool = False) -> CountingRule:
    """`_rule_for` plus the I-11 status check. `mail=True` checks (and names,
    on refusal) `mail_days_source` instead of `source` — the two branches of
    one rule are verified independently."""
    rule = _rule_for(jurisdiction)
    _require_verified(rule, needs=needs, source=rule.mail_days_source if mail else rule.source)
    return rule


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

    **The name says days, and it means calendar days.** This is *not* a
    business-day or "court day" counter. `court_days(start, 5)` is five
    calendar days with a roll at the end, not five open days — the pre-2009
    FRCP short-period rule that skipped weekends while counting was repealed
    for federal periods (`RULES["US-federal"].short_period_max is None`), but
    its state analogues are alive elsewhere and are not this jurisdiction's
    rule. Use `business_days` for a counter that skips intermediate closures.

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
    backward count.

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
    nothing else in this module reads it, and the jurisdiction's `RULES` row
    (and its `status`) is not consulted at all.

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
    else:
        rule = _verified_rule(jurisdiction, needs="forward counting")
        calendar = (
            _district_calendar(rule, district_state) if district_state is not None
            else rule.calendar()
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
    calendar and bypasses the `RULES` status check. `end` takes the same
    forms as `start` there.
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

    calendar = (
        _closed_set(holiday_calendar) if holiday_calendar is not None
        else _verified_rule(jurisdiction, needs="backward counting").calendar()
    )

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
    (`mail_days_source`) is not `RuleStatus.VERIFIED`, regardless of whether
    its counting branch is — and refuses if the rule records no figure at all
    (`mail_days is None`); a verified "there is no mail rule" is not a number
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
    `district_state` you passed to `court_days`.

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

    rule = _verified_rule(jurisdiction, needs="the added-mail-days rule", mail=True)
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

    This is the counter `court_days` deliberately is not: FRCP 6(a)(1)(B) /
    FRBP 9006(a)(1)(B) count intermediate closures rather than skip them.
    `business_days` is the other shape a "days" period can take — the pre-2009
    short-period shape, and the one this module's future NM/OR short-period
    rules are expected to need — kept as a general-purpose counter rather than
    a bespoke loop per jurisdiction.

    `start` is excluded (6(a)(1)(A)'s framing) and `n` open days are counted
    forward; the landing day is always open by construction, so there is no
    separate roll step. `n=0` means "`start` itself," rolled forward if
    `start` is closed — same degenerate case as `court_days`.

    Forward only: `n` must be non-negative, since there is no established
    backward business-day rule the way `court_days_before` encodes one for
    calendar days. `jurisdiction`, `holiday_calendar` and the `RULES` status
    check behave exactly as on `court_days`.
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

    calendar = (
        _closed_set(holiday_calendar) if holiday_calendar is not None
        else _verified_rule(jurisdiction, needs="business-day counting").calendar()
    )

    begin = _as_date(start, what="start")
    reference = start.reference if isinstance(start, Deadline) else None

    try:
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
    except OverflowError:
        raise UnparseableDate(
            f"{n} business days from {begin.isoformat()} falls outside the "
            "calendar this application can represent"
        ) from None

    return Deadline(day, reference)
