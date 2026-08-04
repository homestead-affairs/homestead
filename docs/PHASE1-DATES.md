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
3. **Backward counting** (FRCP 6(a)(5) — periods measured *before* an event
   roll backward off a weekend, not forward). Currently refused outright rather
   than guessed, which is right for now: a sign flip here moves a deadline the
   wrong way past a weekend. But service and notice deadlines are counted
   backward routinely, so refusal is a gap, not a resolution.

Non-federal jurisdictions are refused the same way and for the same reason —
silently applying federal rules to a California court-day period is a wrong
answer with no visible cause. The calendar is injectable
(`holiday_calendar=frozenset(...)`) so local closures need no edit to this
module.
