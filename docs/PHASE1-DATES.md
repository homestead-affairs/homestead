# Phase 1 — dates

`homestead/keep/dates.py`, the one place in this package that turns text into a
date. **Suite: 406 passed / 10 xfailed**, up from 30/13 at the end of Phase 0
remediation.

Written by **two hands that did not read each other**: the corpus
(`tests/test_dates_corpus.py`, 341 cases) and the implementation were produced
concurrently and separately. That split is the direct answer to the Phase 0
audit finding — both passes found tests enforcing weaker properties than they
claimed, and the cause was structural: one hand wrote the code and the test, so
the test learned the code's shape.

It worked. The corpus landed red on a module that did not exist, and the
implementation had to meet it rather than describe itself.

---

## What it refuses, which is the feature

Four documented law-gazelle defects and one inverse defect drove every line:

| | The failure | How it is now impossible |
|---|---|---|
| **BUG-1** | `_days_until` truncated to ten characters *before* trying long-form formats. `"May 5 2026"` is exactly ten and parsed; `"May 5, 2026"` is eleven and returned `None`. | Nothing truncates. Patterns are anchored and match the **whole** string. `test_i2_nothing_is_truncated_before_parsing`. |
| **BUG-2** | The same truncated string handed to `date.fromisoformat`, which is strict, so three call sites raised on any long-form date. | `fromisoformat` is banned package-wide by AST scan — *including inside `dates.py`*. |
| **BUG-3** | `overdue` by lexicographic **string** comparison while `days_until` parsed. One item carried `days_until = -91` and `overdue = False` simultaneously. | Both derive from one stored `date`. They cannot be computed separately, so they cannot disagree. |
| **BUG-4** | Free-text dates stored unvalidated: `"next week"` snoozed to 2099, `"08/11/2026"` snoozed not at all. | Validation is at the edge. Storage never sees a string. |
| **inverse** | `dateutil.parser.parse` does not fail on a partial date — it **invents** from today (`'2026'` → today's year-month, `'June'` → this month). Worse than BUG-1: a confident wrong deadline instead of a lost one. | `dateutil` is import-banned. It is present transitively via `holidays`, which is what makes the scan load-bearing rather than decorative. |

`strptime` is banned for a reason worth keeping written down: `%B` resolves
month names through the process `LC_TIME` locale — CPython's `_strptime` builds
`f_month` from `calendar.month_name` and caches on
`locale.getlocale(LC_TIME)` — so a `%B` format set is a **per-machine** format
set. Verified at CPython source, not assumed. The replacement is an explicit
English month table.

**Accepted today:** extended ISO (`2026-08-10`) and long-form month dates
(`August 10, 2026`, `Aug 10 2026`, `10 August 2026`). **Refused:** everything
else, with a message naming what would have worked.

## The dependency

`holidays>=0.102,<1.0` — the first real dependency in this repo. MIT, verified
from the installed distribution's **own metadata** rather than from a report
about it, so a license change in a future upgrade fails here instead of in
someone's diligence review. FRCP 6(a)(6) defines "legal holiday" as the federal
holidays; this is that calendar. The counting rules are ours, because no
open-source Python court-deadline engine exists to depend on.

It brings `python-dateutil` (dual Apache-2.0 / BSD-3) which brings `six` (MIT).
Both are importable in any working checkout without being declared anywhere —
an ambient dependency, which is the shape I-27 exists to forbid. So I-27 was
split:

* `test_i27_the_core_needs_nothing_but_the_standard_library` — narrowed to what
  it actually checks. Its docstring said "the package imports with nothing
  installed but the standard library," which Phase 1 made false.
* `test_i27_every_third_party_import_is_declared` — **new**, and the general
  claim the old docstring was making without checking. Maps import names to
  distribution names through installed metadata rather than assuming they match
  (`dateutil` ships in `python-dateutil`). Positive control: injecting
  `import six` fails it, naming the module and the distribution.

## Scans verified by firing, not by passing

Every ban above was injected and confirmed to fail the suite —
`datetime.strptime`, `date.fromisoformat`, `from dateutil.parser import parse`,
`import dateutil.parser`, and `import six`. Phase 0's lesson was that a scan
which has never fired is theatre, and two of its scans were.

## The pending file did its job

`homestead.keep.dates` was in `UNBUILT`. `test_pending_liveness` failed the
moment the module existed and would not go green again until the three date
tests were promoted out of `test_invariants_pending.py` into
`test_invariants_dates.py`, unmarked. That is R-6 working on its first real
occasion — the guard against a pending test that xfails forever for a reason
nobody checks.

---

## Open — deliberately not decided by either agent

These are product decisions about **what a deadline is allowed to look like**,
and both hands correctly declined to settle them alone:

1. **Slash forms** (`08/11/2026`). Currently refused. `08/11/2026` is BUG-4's
   own example and is genuinely ambiguous — 11 August in most of the world,
   8 November in the US. Refusing is defensible; a US-only app accepting it
   with a stated convention is also defensible. **Refusing a date a user
   typed correctly is a real cost**, and it is the cost we are currently
   paying by default rather than by decision.
2. **Basic ISO** (`20260810`). Currently refused. Unambiguous, and cheap to
   accept. The argument for continuing to refuse is that every accepted format
   is a format the corpus must cover forever.
3. ~~**Backward counting** (FRCP 6(a)(5) — periods measured *before* an event
   roll backward off a weekend, not forward). Currently refused outright rather
   than guessed, which is right for now: a sign flip here moves a deadline the
   wrong way past a weekend. But service and notice deadlines are counted
   backward routinely, so refusal is a gap, not a resolution.~~
   **Settled 2026-09-11** — `court_days_before` implements 6(a)(5). See the
   section below.

Non-federal jurisdictions are refused the same way and for the same reason —
silently applying federal rules to a California court-day period is a wrong
answer with no visible cause. The calendar is injectable
(`holiday_calendar=frozenset(...)`) so local closures need no edit to this
module.

---

## The rule table, and the three counters beside it — 2026-09-11

`dates.py` stopped being "one forward counter" and became a **rule table with
four counting functions reading it**. Added in E1-dates-a, ahead of the NM and
OR rows E1-dates-b brings:

| | What it is | Rule |
|---|---|---|
| `court_days(start, n, *, jurisdiction, holiday_calendar, district_state)` | The forward counter Phase 1 already had, plus the state-holiday addition | FRCP 6(a)(1), rolled under 6(a)(6); `district_state` is 6(a)(6)(C) |
| `court_days_before(end, n, *, jurisdiction, holiday_calendar)` | `n` days **before** an event, rolled **backward** | FRCP 6(a)(5) / FRBP 9006(a)(5) |
| `add_mail_days(deadline, *, jurisdiction, holiday_calendar, district_state)` | The 3 added days, applied to an **already-rolled** end and rolled again | FRCP 6(d) / FRBP 9006(f) |
| `business_days(start, n, *, jurisdiction, holiday_calendar)` | `n` **open** days — closures skipped *while* counting | Not a federal rule; the shape the NM/OR short-period rules need |

`RULES` holds one `CountingRule` per jurisdiction and `JURISDICTIONS =
tuple(RULES)` is derived from it, so the implemented set cannot drift from the
table it describes. `RuleStatus.UNCERTAIN` on a row makes every function that
would need it **refuse** — `UnparseableDate("UNCERTAIN: …")` naming the
jurisdiction and the citation — rather than compute. That is I-11 applied to a
legal citation, and it is planted and fired, not assumed.

**Three asymmetries, each of which is the rule and not a gap.**

* `court_days_before` has **no `district_state` parameter at all**.
  6(a)(6)(C) adds the district state's holidays for periods measured *after*
  an event only; a filing due 14 days *before* an event that falls on a state
  holiday is still due that day. A parameter here would invite applying the
  addition in the direction the rule excludes, so there is none — and a
  keyword call raises `TypeError`.
* `add_mail_days` **does** take one, because "3 days are added after the
  period would otherwise expire under (a)" makes the added days themselves
  computed under (a), and (a)(6)(C) is part of (a). Without it the composition
  the bankruptcy pack needs returns a closed day: a 14-day period from
  2026-11-10 in D.N.M. ends Tuesday 2026-11-24, and +3 is Friday 2026-11-27 —
  a federal working day, and an NM court holiday, because New Mexico keeps
  Presidents' Day on the Friday after Thanksgiving.
* `holiday_calendar` bypasses the `RULES` status check on three functions and
  **not** on `add_mail_days`. The other three take their period from the
  caller, so a caller-supplied calendar leaves nothing of the rule in the
  answer. `add_mail_days` takes its period — the 3 — from `rule.mail_days`, so
  a caller who supplies a calendar is still trusting the unverified half.
  Fail closed beats seam symmetry.

A `district_state` calendar is **merged with** the federal one, never
substituted for it. `holidays.US(subdiv=…)` is not a superset of
`holidays.US()`: New Mexico's drops 2026-02-16, Washington's Birthday, a day
every federal courthouse in the district is shut. Substituting would compute
that Monday as a deadline. `test_i41_a_district_state_calendar_may_only_add_
closures_never_remove_one` pins it.

### What `VERIFIED` means on the `US-federal` row, and what it does not

**The primary text of FRCP 6 and FRBP 9006 cannot be read from this build
environment.** law.cornell.edu (LII), uscourts.gov, govinfo.gov (GPO),
uscode.house.gov and supremecourt.gov are all refused by the organization's
egress proxy — tried on the build pass and again on the 2026-09-11 audit pass,
and refused before the request leaves the box. The refusal is the network's,
not the source's.

The row ships `VERIFIED` anyway, on converging independent secondary
restatements that agree clause for clause on 6(a)(1)(A)–(C), 6(a)(5) and
6(a)(6)(C) — including the forward/backward asymmetry and the 2009
Time-Computation committee note — and on 6(d)/9006(f) including the 2016
amendment that removed the three extra days for electronic service. FRCP 6(a)
is settled, uncontested text; the NM and OR rows, where the plan already
expects `UNCERTAIN`, are not.

What makes that defensible rather than a quiet upgrade is that **the
disclosure travels with the value**. Both citation strings on the row end in a
dated `PROVENANCE:` sentence naming the basis and the blocked hosts, so a
refusal message, or a stored deadline's instruction from Wave 3 onward, cannot
quote this table as though someone had the rule open in front of them.
`RuleStatus`'s docstring says `VERIFIED` means "checked, and the `source` says
against what" — not "primary" — and
`test_i41_verified_rows_disclose_where_their_text_came_from` refuses any
`VERIFIED` row whose citation omits it, with a planted row proving the check
fires. Replace the PROVENANCE sentence with a primary quotation the first time
one can be read; do not delete it without one.

### The corpus grew a second hand-worked section

`tests/test_dates_corpus.py` § 8 (builder) and § 9 (audit) are hand-worked
cases with the weekday arithmetic written above each row, cross-checked
against a second oracle shaped differently from the implementation — a sorted
list of open days with `bisect` rather than a day-at-a-time loop — so an
off-by-one shows up as a disagreement rather than as agreement by shared
construction. § 9 covers what § 8 does not reach: a backward count landing on
a Monday holiday (where rolling the wrong way is four days wrong, not one), a
backward count spanning Thanksgiving, a backward count across a leap day, `+3`
mail days from a Friday onto a Monday holiday, `business_days` across both
Christmas and New Year in an observed-on-Friday year, and the backward `n=0`
degenerate case — which must *not* answer what the forward one answers, since
the direction of the roll is the only reason there are two functions.

---

## US-NM and US-OR — 2026-09-11 (E1-dates-b)

`RULES` grew to three rows: `JURISDICTIONS == ("US-federal", "US-NM",
"US-OR")`, still `tuple(RULES)`. `CountingRule` grew from one `status` per
row to four independent `(status, source)` pairs — forward, short-period,
backward, mail — because a state's forward-counting rule can be corroborated
while its backward and mail rules are not stated in anything read here. The
federal row was refactored to the same shape, all four branches `VERIFIED`;
its computed answers are byte-identical (the unchanged federal corpus still
passes with no value changed).

Every URL below was tried on 2026-09-11 and every one is refused by the
egress proxy (`EGRESS_BLOCKED`) before the request leaves the box:
`supremecourt.nmcourts.gov/…/Rule-1-006-NMRA.pdf`, `law.justia.com/codes/
new-mexico/…/section-12-2a-7/`, `nmonesource.com/nmos/nmra/…`, `oregon.
public.law/rules-of-civil-procedure/orcp-10-time/`.

| jurisdiction | forward (≥ threshold) | short period | backward | mail |
|---|---|---|---|---|
| `US-NM` | Rule 1-006(A) NMRA (eff. 2024-11-01) — VERIFIED-secondary, ≥ 11 days | `short_period_max=11` — **UNCERTAIN** | **UNCERTAIN** | 3 days recorded, **UNCERTAIN** |
| `US-OR` | ORCP 10 A — VERIFIED-secondary, ≥ 7 days | `short_period_max=7` — VERIFIED-secondary | **UNCERTAIN** | 3 days recorded (ORCP 10 C, letter UNCERTAIN), **UNCERTAIN** |

Three things worth knowing before touching this table again:

* The short-period shape is `business_days`'s loop (`_count_open_days`), not
  a second copy of it — `court_days` picks it whenever `n` is strictly below
  `RULES[jurisdiction].short_period_max`, so the two can never drift apart.
* A `holiday_calendar` override replaces the calendar, never which shape
  runs: `short_period_max` still comes from `RULES[jurisdiction]` even when
  the caller supplies their own calendar — see
  `test_a_holiday_calendar_override_keeps_the_jurisdictions_counting_rule`.
* `"US-federal"` + `district_state="NM"` and `"US-NM"` read the identical
  union calendar and agree exactly at or above NM's 11-day threshold, but
  only `"US-NM"` has a short-period concept — below it the federal call
  still computes while `"US-NM"` refuses. Confusing the two jurisdictions
  produces a confident wrong answer, not a refusal, which is why they stay
  separate rows (`test_us_federal_with_district_state_nm_and_us_nm_agree_
  on_long_forward_periods_and_differ_on_short`).

`test_nm_short_period_excludes_weekends_and_holidays_when_verified` is
`xfail(strict=True)`: it asserts the answer this module would compute if
NM's short-period branch were `VERIFIED`. The day someone reads Rule 1-006
NMRA's short-period text and flips `short_period_status`, this assertion
starts passing and `strict=True` fails the suite until the marker is removed.
