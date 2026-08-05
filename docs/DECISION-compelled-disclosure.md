# A compelled disclosure — decision brief

Status: **Proposed. Nothing done.** No existing file in this repo was changed to
write this. Every measurement below was taken in scratch copies of the tree and
the copies were kept, not merged; the working tree was `git status`-clean of my
edits before and after.

**Proposed here, to be ratified by another hand** — `verified_by ≠ author`, as
with `DECISION-agent-retrieval.md`. This brief recommends; the operator decides.
It matters here for the ordinary reason and for one extra: the recommendation
below turns on a product judgement about whether a household ever fields
discovery, and that is not a thing I can measure.

Raised as the third open item on PR #5, in these terms:

> **Possibly missing: a *compelled* disclosure** — a subpoena, a mandated
> report. `FILING` stretches to cover it, but a compelled disclosure and a
> voluntary filing are different acts in a ledger, and that difference is what a
> ledger is for.

Both halves survive. The first is truer than it was put — `FILING` does not
*stretch* to cover a subpoena response, it already covers it by its own written
gloss — and the second is exactly right about *what kind* of question this is,
which turns out to settle less than it sounds like it settles. The measurements
are below and they move the question rather than answering it.

---

## The mechanical facts, measured

### 1 · A seventh member changes no answer. Zero cells, out of twenty-five.

`may_render` reads *whether* a purpose was declared and never *which*:

```python
declared = _declared(purpose)          # -> bool  (rungs.py:597)
plain, with_purpose = _CEILING[target] # two columns, not seven
ceiling = with_purpose if declared else plain
```

Fired, in a scratch copy carrying a seventh member, over the whole grid:

```
cells compared:                          25
cells where COMPELLED differs from FILING: 0
cells where the seven members disagree:    0
```

Both `may_render` and `decide`. There is no rung, on any surface, on which
declaring a new member produces an answer that `Purpose.FILING` would not have
produced. **A seventh member buys exactly what the other six buy, which is one
boolean, and it buys it on one surface.**

### 2 · That one surface is S4, and only S4.

`_CEILING` as it stands today (`rungs.py:500`), read rather than remembered:

| surface | plain | with a purpose | lifts? |
|---|---|---|---|
| `S1_LIST` | `L3` | `L3` | no |
| `S1_DETAIL` | `L4` | `L4` | no |
| `S2_PROMPT` | `L2` | `L2` | no |
| `S3_AGENT` | `L2` | `L2` | **no — closed 2026-08-05** |
| `S4_EGRESS` | `L2` | `L4` | yes |

Any analysis written against "a purpose lifts on S3 and S4" predates
`1559d37` and is stale. The surface a purpose still moves is egress, whose
caller the module's own comment describes as *an operator performing an explicit
act on their own record*.

### 3 · So the pinned test's stated reason for existing is mechanically false.

`test_the_purpose_enum_is_the_six_that_were_published`
(`tests/test_invariants_surfaces.py:647`) justifies the pin like this:

> A seventh member is a lift nobody ratified: it is one more call site that can
> unlock `L4` on egress.

Measured, that is not so. A call site that wants `L4` on `S4_EGRESS` today
declares `Purpose.DRAFTING` and gets it. A seventh member is not *one more* call
site that can unlock `L4`; it is the same call site with a different word in it.
The set being closed bounds the **vocabulary**, not the **capability** — and
`may_render` gains no safety from membership is the repo's own sentence for
exactly this.

**The pin is still right. Its stated reason is not.** This is the same shape as
the last brief's finding, arriving one level up: an argument about the gate that
is really an argument about the ledger. Under the annotate-don't-rewrite rule
that docstring should get a dated correction rather than a rewrite, whichever
option below is taken — including "none of them".

### 4 · Therefore this is a ledger question and not a gate question, and the
### ledger does not exist.

Nothing in `homestead.keep` writes a ledger line. `rungs.py`'s own *What it does
not do* says so: *"It does not ledger."* Phase 3+.

So a seventh member added today is a word added to a vocabulary in which no
sentence has yet been written. That is the whole of what it does. It is not
nothing — see § *Which way the deadline runs* — but it is worth being exact
about how little it is before pricing it.

---

## Does "a compelled disclosure" pass the set's own membership test?

The test on record: **these six are acts, not categories and not widgets.**
`"medical"` was excluded as a data *category* (the rung carries it); `"operator
opened the record"` was excluded as a *surface act* (`S1_DETAIL` carries it).

### Against `FILING` — the premise is understated, not overstated

`FILING`'s gloss in `rungs.py:211` is:

```python
FILING = "filing"                    # submitting it to a court or agency
```

A subpoena response is submitted to a court, or to a party in a matter before
one. A mandated report is submitted to an agency. **Both are inside `FILING`'s
stated scope as written.** `FILING` does not stretch to cover them; it already
names them, and it names a voluntary filing with the identical words.

That relocates the gap. The distinction is not the destination and not the
operation — it is **who set the act in motion**. And the current gloss cannot
express that, because it describes only the destination.

### Against `EXPORT` — clearly distinct

`EXPORT` is *"the operator taking their own record out"*. A compelled
disclosure is not the operator taking; it is someone else taking, with the
operator as the hand that moves. Different act, not a near miss.

### Against `SUBJECT_ACCESS` — the closest neighbour, and the argument *for*

`SUBJECT_ACCESS` is *"a statutory subject-access request"*. Strip it to its
mechanics and it is an export: the same records leaving by the same surface. It
is a separate member because a **statute** stands behind it and someone other
than the operator invoked that statute.

That is the same distinction, in the same direction, as compelled versus
voluntary. Which means the set's real membership rule is not quite the one it
states. It is closer to:

> **an act, individuated by the legal posture that says who it answers to.**

`REDISCLOSURE` fits that reading too — 42 CFR Part 2 permitted re-disclosure is
a disclosure distinguished from every other disclosure by the regime standing
behind it, not by anything the bytes do differently.

**Under the rule the set actually follows, a compelled disclosure qualifies as
cleanly as `SUBJECT_ACCESS` does.** That is the strongest thing that can be said
for a seventh member, and it is stronger than the way the question put it.

### The honest objection to my own point

`COMPELLED` is an adjective. It names a **modality** of an act, not an act —
and admitting a modality would put a *fourth* kind of thing in a slot that was
closed precisely because free text let three kinds in and could not tell them
apart. Categories, surface acts, acts, and now adverbs.

The objection is answerable, but only by naming, and only carefully. See
§ *Naming*. It is not answerable by `COMPELLED` on its own, which would be
`AGENT_RETRIEVAL`'s failure wearing the opposite costume: that member named
where you were standing; a bare `COMPELLED` names how you got there and never
says what you did.

### One act or two?

A subpoena response and a mandated report are not one act.

- **Production under process** — a demand in a matter the operator is *party*
  to. Discovery, a subpoena duces tecum, a court order. Realistic for this
  application: a household in a family matter or a bankruptcy is routinely
  required to produce records.
- **A mandated report** — a duty imposed by status, owed whether or not any
  matter exists. Realistic for a clinician or a teacher. **Not** realistic for
  a household operator keeping their own records, which is who this application
  is for.

Collapsing the two under one member repeats, one level down, the complaint the
question raises about `FILING`. Splitting them costs the same as not splitting
them (measured below). But the second one names an act this application's
operator does not perform, and a member for an act nobody performs is the
speculation the counter-case is about.

### The evidence I did not expect to find

`"court order"` is already in this repo, twice, as the archetypal
plausible-but-refused purpose string — `tests/test_invariants_surfaces.py:109`,
alongside `"medical"` and `"operator opened the record"`, and
`tests/test_purpose_corpus.py:323`. `PHASE2-SURFACES.md:238` records that a
`may_render` special-casing the single string `"court order"` **passed the
entire suite** in the first pass, and that finding is why two of the strongest
tests in the corpus exist.

Those lists were written by a hand that had not read `rungs.py`. Asked for the
purpose a caller would most plausibly reach for, that hand produced a
compelled-disclosure phrase — the same one, in both files, independently of the
enum. It is not proof of a gap. It is a second, blind vote that the gap is where
the question says it is.

It also rules out one candidate name outright: see below.

---

## The cost, measured

Baseline, real tree: **1621 passed / 6 xfailed.**
All runs below in scratch copies under
`…/scratchpad/{compelled-work,two-members,gloss-only,final-name}`.

### Adding one member, `rungs.py` only

**4 failed, 1700 passed, 6 xfailed** — four test functions across **three**
files, not the two the question assumed:

| test | file:line | why it fails |
|---|---|---|
| `test_the_purpose_enum_is_the_six_that_were_published` | `test_invariants_surfaces.py:647` | pins the name→value dict |
| `test_the_six_members_are_exactly_the_six_that_were_ratified` | `test_purpose_corpus.py:160` | pins names, values, and `len(values) == 6` |
| `test_this_corpus_has_not_been_hollowed_out` | `test_purpose_corpus.py:971` | `len(Purpose) == 6`, `len(VALID_PURPOSES) == 7` |
| `test_the_corpus_has_not_been_hollowed_out` | `test_surfaces_corpus.py:1956` | same two, with the seventh-member message attached |

The two hollowing-out tests are the ones the brief-as-posed missed. They are
table-size guards, they were not written as membership pins, and they pin
membership anyway — which is the machinery working.

### Making it green

**One line in `rungs.py`; seven assertion sites across three test files** (the
four functions above contain seven lines to change, because two of them assert
both `len(Purpose)` and `len(VALID_PURPOSES)`).

Result: **1704 passed / 6 xfailed.** Zero migrations, because there is nothing
to migrate — see § *Callers*.

### What the seventh member costs the suite: nothing, and it is deliberate

Each added member brings **+83 passing test cases** with no test rewritten:

| tree | collected outcome |
|---|---|
| baseline | 1621 passed |
| + one member, pins updated | 1704 passed |
| + two members, pins updated | 1787 passed |

The sweeps derive from `tuple(Purpose)` rather than from typed lists, so a new
member is swept everywhere on arrival. That is exactly what
`PHASE2-SURFACES.md:238` says the `"court order"` injection bought, and it is
the reason the marginal cost of a member is flat rather than growing.

### Mutation score: unchanged

`docs/audits/purpose_corpus_mutate.py`, run against all three trees:

```
mutants: 29 · survivors: ['the agent surface loses its lift — L4 is unservable on S3']
```

Identical on baseline, one-member and two-member trees. The single survivor is
**pre-existing** — I fired it on the untouched repo to confirm — and is an
artifact of S3's column already being closed, so the mutant is a no-op. A
seventh member neither opens nor closes a hole in the corpus.

### Two members costs the same as one

**7 sites, 3 files, 1787 passed / 6 xfailed.** So the one-versus-two question is
decided on substance, not on price.

### Doing nothing but fixing the gloss costs zero

Rewriting `FILING`'s trailing comment and nothing else: **1621 passed /
6 xfailed**, unchanged. No test reads a member's comment.

### A cost the suite will not report

`test_all_six_members_are_interchangeable_at_the_decision_function`
(`tests/test_purpose_corpus.py:588`) **passes with seven members**, because it
iterates `Purpose`. Its name would then be false and green. That is the defect
the last brief renamed `test_the_ceiling_table_did_not_move` for — *a test whose
title denies the change it asserts is this project's signature defect* — and
this one will not announce itself. Three purpose test names say "six"; two of
them are the pins and must be edited anyway; this is the third and it is the
only one that lies silently.

Add it to any add-a-member option: **8 sites, 3 files, one of which is a rename
the suite cannot ask for.**

### Doc sites, not counted above

Eleven lines in `docs/` say "six" or "a seventh member", including
`PHASE2-SURFACES.md:62`, `:223`, `:572`, `:633–646`. Under archive-don't-delete
and annotate-don't-rewrite these take dated annotations, not edits. They are the
operator's to write, because they record what the project believed on
2026-08-05 and I am not the hand that ratifies a change to that.

### Callers

**There are none.** Verified rather than assumed: no call to `may_render`,
`decide`, `serve`, `serve_all` or `ambient_rows` exists anywhere in
`homestead/` outside `rungs.py`. `homestead/app/__main__.py` imports `rungs`
inside `--smoke` to prove packaging survived and never calls it. Phase 4 is
unwritten.

---

## Which way the deadline runs — and why the last brief's argument does not
## transfer

`DECISION-agent-retrieval.md` closed S3's column *now* on an explicit
cheapest-moment argument: **there were no callers yet**, so D cost 26 assertions
and zero migrations, and *every month it had been deferred, it would have been
paid for in call sites instead.*

That argument does not carry here, and the measurements are why.

D removed a **capability**. A capability's removal cost grows with the number of
call sites relying on it, so the cost curve was rising and the decision had a
real deadline.

A seventh member adds no capability — 0 cells out of 25, measured. Its cost is
seven assertion sites plus a rename, and that number **does not grow with call
sites**, because members are interchangeable at the gate and no call site can
come to depend on one for an answer. The suite absorbs new members at +83 cases
with no edits. **The cost curve is flat.** So "do it now while it's cheap" is
refuted by measurement: it will be exactly this cheap later.

What *is* irreversible is different, and it is real. The moment the ledger
exists and a caller writes the first line for a compelled production, that line
says `filing`. Nothing distinguishes it afterwards from a voluntary filing —
not by inspection, not by migration, not ever. A missing distinction in a ledger
is the one kind of cost that cannot be paid in arrears.

**So there is a deadline, and it is not today. It is the first ledger write.**
That is a fact about Phase 3, not about this brief, and it should be pinned to
Phase 3 rather than to whoever happens to be reading PR #5.

The counter, honestly: since the cost is flat and small, deferring saves
nothing either. Deferral buys only the right not to spend a ratification on an
act nobody has performed. Adding buys only that the vocabulary is right before
anyone writes against it. With costs equal, the tiebreak is which error is
worse — an unused member (a line nobody declares; visible, harmless, and
deletable) against a missing member at the moment one is needed (a permanently
ambiguous ledger line). The asymmetry favours adding.

And the counter to *that*: the same asymmetry admits an unbounded number of
members, since any act one might someday perform is cheap to add and expensive
to have omitted. The set's value is that it is small and closed. An argument
that would admit a seventh would admit a twelfth.

I do not think either side of that wins on measurement. It is a judgement, and
it is the operator's.

---

## Options

**A — Add nothing; leave `FILING` as it stands.**
Cost: **zero**, measured. Leaves `FILING` silently spanning voluntary and
compelled submission with a gloss that mentions neither. Every future reader
re-derives the ambiguity from scratch. **Not recommended on its own** — not
because it is wrong but because it is not a decision, it is the absence of one,
and PR #5 asked.

**B — Narrow `FILING`'s gloss and record the question against the ledger.**
Cost: **zero**, measured (1621 / 6 xfailed, unchanged). Change the comment to
say what `FILING` means and what it does not distinguish, and file the member
question as gated on Phase 3's ledger schema. This is the option that matches
what the module already does with P-1: name the gap, say what would close it,
and do not invent an authority to close it early. The ledger, when it exists,
can carry a **basis** — a docket number, a statute, the process itself — which
no enum member can. A member says *compelled*; a ledger row can say *which
subpoena*.
Risk: nothing compels the ledger to have that field, and a free-text basis field
is R-7's shape all over again. Between the first ledger write and the day
someone notices, compelled productions are recorded as voluntary filings.

**C — Add one member, `COMPELLED_DISCLOSURE`, and narrow `FILING` in the same
change.**
Cost measured: **1 line in `rungs.py`, 7 assertion sites across 3 test files, 1
silent rename. 1621 → 1704 passed / 6 xfailed. Mutation score unchanged (29
mutants, 28 killed, 1 pre-existing survivor). Zero migrations.**
Buys: a truthful ledger vocabulary before the first ledger line is written, on
the `SUBJECT_ACCESS` precedent. Buys nothing mechanically — 0/25 cells move, and
the brief should say so out loud wherever this lands.
**The `FILING` half is not optional.** Adding `COMPELLED_DISCLOSURE` while
`FILING` still reads *"submitting it to a court or agency"* leaves two members
both truthfully describing a subpoena response. Two truthful members for one act
is a ledger with two spellings for one thing —
`test_the_enum_refuses_every_spelling_that_is_not_a_member_value` exists to
prevent that at the string level and nothing prevents it at the member level.

**D — Add two, `COMPELLED_PRODUCTION` and `MANDATED_REPORT`.**
Cost measured: **identical shape — 7 sites, 3 files. 1621 → 1787 passed / 6
xfailed. Mutation score unchanged.**
Distinguishes the two acts the question conflates, which is a real distinction.
**Not recommended**, and not on price: a mandated report is a duty imposed by
professional status, and this application's operator is a household keeping
their own records. It is a member for an act this product's user does not
perform. If a mandated-reporter deployment ever exists, it can be added then, at
the same flat cost.

**E — Rank the members so `COMPELLED_DISCLOSURE` means something at the gate.**
**Not recommended, and close to unimplementable.** Ranking needs a trust tier
and a ledger, neither of which this module has, and `rungs.py:444` says so:
*"a table treating `EXPORT` as weightier than `ANSWERING` would be inventing an
authority it has not got."* Listed because it is the option that would make a
seventh member mechanically load-bearing, and naming why it cannot be taken is
the argument that this is a ledger question and stays one.

---

## Naming, if a member is added

The act is *producing records because process required it*. Candidates, fired
against `test_there_is_no_catch_all_purpose` (`tests/test_purpose_corpus.py:196`)
and the `Rung`/`Surface`/`Purpose` disjointness guard (`rungs.py:218`):

| candidate | verdict |
|---|---|
| `COMPELLED_DISCLOSURE` | passes both guards. Names the **act** (disclosing) and its posture. **Recommended.** |
| `COMPELLED_PRODUCTION` | passes both. "Production" is the exact term of art. Less legible in a ledger line a household operator reads. |
| `FORCED_DISCLOSURE` | **trips `test_there_is_no_catch_all_purpose`** — the banned regex contains `FORCE`. Measured, not guessed. |
| `SUBPOENA`, `COURT_ORDER` | pass the guards and **fail the set's own test**: they name the *instrument*, which is a thing, exactly as `"medical"` is a thing. `"court order"` is additionally the corpus's canonical refused string in two files; adopting it as a member would make the repo's most-cited rejected example into an accepted one. |
| `COMPELLED` alone | passes the guards, fails on naming: an adjective with no act attached. The mirror of `AGENT_RETRIEVAL`. |
| `REPORTING`, `DISCLOSURE` | too broad; a voluntary disclosure is one, and the whole point is the distinction. |

`COMPELLED_DISCLOSURE = "compelled_disclosure"`. Verified disjoint from every
`Rung` and `Surface` value, so the import guard stays quiet; verified against the
catch-all regex; and it names the act rather than the surface, which is the one
mistake this series has already made once.

Note the substring relation to `REDISCLOSURE`. Values are distinct and nothing
in `rungs.py` does prefix matching on a purpose — `_declared` is `isinstance`
only — so it is a readability question, not a correctness one. Fired: green.

---

## Recommendation — proposed, not ratified

**B unconditionally. C if the operator judges that this application's operator
will field discovery.**

B is free, measured, and correct on its own terms whatever happens to C: the
`FILING` gloss currently names a destination and silently spans two postures,
and that is true today with no ledger and no callers. It is the smallest true
thing that can be said and it costs nothing to say it.

C rests on the `SUBJECT_ACCESS` precedent, which I think is the real argument
and is stronger than the one the question made. The set already individuates by
legal posture; `SUBJECT_ACCESS` is an `EXPORT` with a statute behind it and gets
its own member for that reason alone. A compelled production is a `FILING` with
process behind it. Refusing it while keeping `SUBJECT_ACCESS` is not a principled
line, it is the line that happened to get drawn on 2026-08-05.

What C turns on, and what I cannot measure: whether a household using this
application is ever required to produce records. If a family matter or a
bankruptcy is in scope — and `classify_schema`'s own docstring says a case
number is `L1` in a bankruptcy and `L3` in a family matter, so both are — then
discovery is in scope, and C is right. **That is the operator's call and it is
the whole of the decision.**

**C should not be taken on a cheapest-moment argument.** The last brief's
cheapest-moment argument was correct and does not apply here; § *Which way the
deadline runs* measures why. If C is taken it should be taken because the
vocabulary is wrong, not because it is on sale.

**D is not recommended.** **E is not available.** **A alone is not a decision.**

---

## What is gated on which answer

- **B alone**: one comment in `rungs.py`. Zero tests. Nothing downstream.
- **C**: one member, 7 assertion sites in 3 test files, plus renaming
  `test_all_six_members_are_interchangeable_at_the_decision_function`, plus
  dated annotations to eleven doc lines. Not startable without a ratification,
  and not startable by the hand that proposed it. Measured green at 1704 / 6
  xfailed.
- **Not gated on P-1.** The trust tier is S3's problem and S3's column is
  closed. This is S4 alone, whose caller is an operator acting on their own
  record.
- **Gated on the Phase 3 ledger schema, in the other direction**: if the ledger
  carries a free-text `basis` naming the process, C's value drops sharply — but
  a free-text field in the row that records why a boundary was crossed is R-7's
  shape and would itself need a ratification. Whichever way that goes, it should
  be decided *with* C rather than after it.
- **The real deadline for C is the first ledger write**, not this brief. If C is
  deferred, defer it *to* Phase 3 explicitly rather than to nobody.
- **Independent of all of the above**: the pinned test's stated rationale in
  `tests/test_invariants_surfaces.py:647` — *"one more call site that can unlock
  `L4` on egress"* — is mechanically false and should get a dated annotation
  even if nothing else here is taken.

---

## What I did not do

- **Edited no existing file.** The only write to this repo is this document.
  Nothing committed, nothing pushed. Another agent is working in this tree
  concurrently and `docs/DECISION-redisclosure.md` is theirs, not mine.
- **Did not ratify anything.** `verified_by ≠ author`.
- **Did not decide the product question** of whether this application's operator
  fields discovery or is a mandated reporter, which is what C actually turns on.
- **Did not update the eleven doc sites** that say "six" or "a seventh member".
  They are dated records of what the project believed on 2026-08-05 and they get
  annotations from the ratifying hand, not edits from the proposing one.
- **Did not measure the packaging or CI path.** Every number here is
  `pytest -q` and `docs/audits/purpose_corpus_mutate.py` on a scratch copy.
- **Did not consider a Phase 4 caller's ergonomics**, because there is no Phase 4
  caller — verified, not assumed.
- **Did not test a member whose value collides with a `Rung` or `Surface`.** The
  import guard covers it and `PHASE2-SURFACES.md:222` already records that
  outcome as an `ImportError` at collection.
