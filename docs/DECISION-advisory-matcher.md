# The advisory content matcher — `keep/advise`

Status: **Built.** `homestead/keep/advise.py`, tested in
`tests/test_invariants_advise.py`.

## What it is, and the gap it fills

`classify_schema` checks that a field *declared* a rung, not that it declared one
*well*. Its own docstring concedes it will "accept `L1` for a sealed family case
number without a murmur." That gap is a human's to close — the matter and
jurisdiction are not derivable from a field name — but there is one class of
error a machine can see: **content shaped for a higher rung than the field was
declared.** A field declared `L1` whose value is an SSN is exactly that.

`advise(declared, content)` reports those, and only those. It is the guard the
`notes = L4` decision was left leaning on: the audit
(`docs/audits/bites-1-3-remediation.md`, finding #5) noted that free operator
text declared `L4` routinely holds `L5`-worthy content, and that the closure for
it is an advisory matcher. This is that matcher.

## The three conditions it is built to

These come from the prior-art note in `docs/PLAN-first-runnable.md` (the
`nest/scrub.py` review), and each is a test, not a promise.

1. **It may only argue a rung *up*, never down.** A concern is reported only when
   the implied rung is strictly higher than the declared one. There is no path
   that argues a datum down — `compose` is `max` for the same reason, and a tool
   that could lower a rung is a declassifier, of which there is deliberately
   none. `advise` uses `compose` itself to compare rungs, so it cannot disagree
   with the gate about which is higher.

2. **Advisory, never a gate.** `advise` returns concerns and raises nothing; it
   blocks no write. `Sidecar.advise` is a *read-only* check the operator runs
   over a stored record, and a test asserts `put()` never consults it — a matcher
   that could stop a save would have relocated a human judgement into a pattern
   list.

3. **Its silence is not a clean bill.** An empty result means *no pattern here
   matched*, never *this content is safe*. There is no `is_clean`, no boolean
   verdict — a test asserts the module exposes none — because a false negative is
   the dangerous direction and absence must fail toward suspicion (I-11).

Two more properties fall out of the same posture:

- **It never echoes what it matched (I-15).** An `Advisory` carries the category
  and the rungs, never the matched text — an advisory quoting the SSN it found
  would be the leak it exists to prevent.
- **It reaches no `.payload`.** It takes content as a plain string, so it is
  neither the gate nor the store and the chokepoint holds; the store, which
  legitimately holds a record's content, is what passes it in.

## The patterns, and I-18

Nine categories, each an **anchored** pattern with an implied rung: `ssn` → L5;
`credit_card`, `dob`, `bank` → L4; `phone`, `email`, `ein` → L3. The rungs are the
model's.

I-18 — *any pattern that could match PII is anchored and tested against PII
negatives* — is the load-bearing discipline, and F-3 is why: a citation regex
that matched `1420 Maple 87501` and missed `347 F.3d 1120`. The test suite holds
each pattern to a benign set it must *not* fire on — an address, a ZIP+4, a
hearing date, a docket entry, a citation, a case number, a parenting schedule —
as hard as to the PII it must catch.

Two categories are matched only **in context** (`DOB:`, `routing`/`account`)
rather than by bare format, because a bare date is a hearing date (`L1`) far more
often than a birth date, and flagging every date would push the `L1` fields up
and drown the signal. This is the one place the "false positives are safe"
reasoning is deliberately not followed to its end: safe for disclosure, yes, but
alert fatigue is its own failure, and a matcher nobody reads catches nothing.

## What it does not do, and what is left

- **It does not classify.** A shape is not a matter. It cannot know that a case
  number is `L1` in a bankruptcy and `L3` in a family matter — that is step 5,
  the human's, and needs the registry (I-23, still pending).
- **It is not wired into a surface yet.** `Sidecar.advise` gives the operator a
  read-only check; surfacing advisories in the authoring UI (so a wrong rung is
  caught *as the operator declares it*, in the pane where they declared it — the
  "loud on type, in the pane they added it" shape) is a later view bite.
- **Bare-format bank and DOB, and un-separated SSNs, are not caught.** The
  patterns catch the written-the-way-people-write-it forms; the honest bound on
  what silence means is `CATEGORIES`, and condition 3 is why silence is never a
  verdict.
