# Phase 2 — rungs and the surface table

`homestead/keep/surfaces.py` (new) and `homestead/keep/rungs.py` (extended): the
decision function every later render must route through, and the classification
that makes an unclassified field a build failure.

**Suite: 1501 passed / 8 failed / 6 xfailed.** Every failure is in the
independent corpus, and all eight are one disagreement in eight
parametrizations. It is named in *The disagreement* below and it is not fixed,
because I think the spec is on my side and I would rather be told so than quietly
be right. Excluding the corpus: **455 passed / 6 xfailed**, up from 406/10 —
four of the four vanished xfails are the promoted contract tests, and the fifth
is `homestead.keep.surfaces` leaving `UNBUILT`.

Written by **two hands that did not read each other**, the same split as Phase 1.
This half did not open `tests/test_surfaces_corpus.py`. It appeared on disk
mid-session and pytest printed fragments of three of its assertions into my
console when the whole suite ran; those fragments are why two API decisions
changed, and both changes are declared below rather than absorbed.

---

## What landed

| | |
|---|---|
| `Surface` | Four surfaces, **five members** — S1 splits into `S1_LIST` and `S1_DETAIL` because the difference between the panes is the whole of I-35. Plus `S2_PROMPT`, `S3_AGENT`, `S4_EGRESS`. |
| `FACTS` | What is true of a surface without reference to any rung: what it is, whether it is *ambient*, whether it *leaves the machine*. Complete or the module does not import. |
| `_CEILING` | The crossing, as **two rungs per surface** rather than twenty-five cells. |
| `may_render(rung, surface, *, purpose)` | May the **payload** go? A threshold comparison, nothing else. |
| `decide(...) → Disposition` | `RENDER` / `DERIVE` / `DENY`. `workflow._fact_blocked`'s successor. |
| `Classified` / `Served` / `serve` / `serve_all` | The chokepoint shape: score a datum, hand back only what may go. |
| `AmbientRow` / `ambient_rows` | The list pane's render path. A rung and a line of text, and no third field. |
| `context_rung(items)` | I-12 pointed at a prompt: the `max` of the whole window, retrieved neighbours included. |
| `classify_schema(schema)` | I-11's build half. Refuses, and names every offending field. |

### The one design decision worth arguing about

**The crossing is a threshold, not a table.** Each surface carries two rungs —
the highest whose payload renders with no purpose declared, and the highest with
one — and `may_render` compares against whichever applies. Ten authored numbers
instead of twenty-five cells.

That is BUG-5's answer, and the reason is BUG-5's mechanism. `_fact_blocked`
returned `status == "needs_source"`, so `do_not_use` — the **stronger**
rejection — walked past the guard into the drafting packet and the model prompt
while the Review Facts screen said *"Excluded from drafting."* A guard checked a
weaker condition and the stronger case was the one that did not work. A
twenty-five-cell table is where that hides, because every cell is an independent
thing an author can get wrong in exactly one place.

Against a threshold it is not a rule anyone has to remember:

* **if a rung is refused on a surface, every higher rung is refused there**, by
  arithmetic, for every surface at once;
* **`L5` is refused everywhere because no ceiling is `L5`** — not because five
  rows say `never`;
* **the list pane cannot be given an `L4` payload** because it is ambient and an
  ambient ceiling of `L4` or above is an `ImportError`;
* **a purpose can only lift** — a table where one lowers is an `ImportError`;
* **a surface added to the enum and forgotten in either table** is an
  `ImportError`, which is BUG-6's shape closed at the door.

`_check_crossing()` runs when the module imports, so all five are build failures.

### The transcription, and where it is a judgement call

| Surface | no purpose | with purpose | from the spec's crossing table |
|---|---|---|---|
| `S1_LIST` | `L3` | `L3` | `L4` is *derived*, and I-35 says purpose does not lift it |
| `S1_DETAIL` | `L4` | `L4` | opening the pane **is** the declaration (decided 2026-08-04, by widget not dialog) |
| `S2_PROMPT` | `L2` | `L2` | `L3` derived; `L4` derived **no exception**; nothing lifts |
| `S3_AGENT` | `L2` | `L4` | `L3` derived; `L4` derived unless purpose |
| `S4_EGRESS` | `L2` | `L4` | `L3` explicit act; `L4` explicit act + purpose |

Two notes on the transcription:

* **S3 and S4 have identical ceilings.** That is not a copy-paste. What differs
  between them in the spec is the *trust tier* and the *ledger entry*, and this
  module enforces neither, so the honest ceiling is the same and the difference
  is a gap rather than a value.
* **`L3` on S2/S3 gets no purpose lift here**, which follows the crossing table.
  The `L3` prose says *"on S2/S3/S4 it is NULL … unless an explicit act says
  otherwise."* Those two sentences do not agree, and the doc says the table is
  where the mapping lives, so the table won. **This is a product decision, and
  it is named again below.**

---

## What it refuses

* **An unclassified field, at schema-definition time.** `classify_schema` raises
  `UnclassifiedField`, naming **every** offending field rather than the first —
  a build failure that names one of four costs four build cycles, and the fourth
  gets classified in a hurry. An integer rung gets its own reason, because `3` is
  not a typo for `L3`, it is I-14's cross-scale confusion arriving as data.
* **An unclassified value at runtime**, twice over: `Classified` cannot be
  constructed without a real `Rung`, and if one reaches `may_render`/`decide`
  anyway it reads `L5` and is not served.
* **An empty schema.** A classifier that ran and found nothing is absence, and
  absence fails closed. A judgement call, and the argument is that a schema
  object with no fields is far more often a definition that picked nothing up
  than a record with nothing in it.
* **A `Classified` at `L3` or `L4` with no derived form.** BUG-5's other half:
  law-gazelle's screen said "Excluded from drafting" over a packet that still
  carried the atom, and the mismatch was possible because the exclusion had no
  representation of what to show instead. The set of rungs this applies to is
  *derived from the ceiling table*, not typed in.
* **A purpose the code could recognise by value.** An AST scan asserts that in
  the whole of `rungs.py` the name `purpose` is only ever *passed on*; comparing
  it, matching it or indexing it fails the suite. `_declared` is the single
  exemption and all it looks at is whether the string has anything in it.
* **A blank purpose.** `""`, `"   "`, `True`, `1`, a list — the absence of a
  purpose arriving in the shape of one — lifts nothing.
* **Anything in the surface slot that is not a `Surface` member.** See below.

### Denial is absence, not a flag

`serve_all` **drops** what it denies. No placeholder, no count, no ordering gap
that reconstructs one. A `do_not_use` fact is not in the drafting packet marked;
it is not in the drafting packet. `L5`'s own definition is that *rendering it
would reveal a refusal*, so a rendered "1 item withheld" is the thing the rung
forbids. `serve()` singular does tell its caller that a denial happened — it is
in-process, not a rendering — and it carries nothing about the subject.

---

## Scans verified by firing

Phase 0's lesson was that a scan which has never fired is theatre, and two of its
scans were. Fifteen injections, each applied to a copy of the tree, suite run,
reverted:

| Injected | Fired |
|---|---|
| An unclassified module-level `*_SCHEMA` in the package | `test_i11_no_schema_in_this_package_is_unclassified` |
| A **half**-classified mapping not named `_SCHEMA` (some fields carry `Rung`, one does not) | same |
| An `L4` ceiling on the ambient list pane | `ImportError` at collection |
| An `L5` ceiling on egress | `ImportError` |
| A surface added to the enum, forgotten in `FACTS` | `ImportError` |
| A surface added with facts, forgotten in `_CEILING` | `ImportError` |
| A purpose that lowers a ceiling / an integer ceiling | `RuntimeError`, both |
| **BUG-5 transplanted** — a guard that refuses `L3` and lets `L4`/`L5` past | 12 tests, incl. all four promoted contract tests |
| `_read_rung` returning `L1` on an unreadable value | 3 tests |
| A `declassify(rung, years_since_close=1)` | `test_nothing_here_lowers_a_rung_and_nothing_here_takes_a_date` |
| `may_render` growing a `today=` parameter | same |
| `serve_all` marking denials instead of dropping them | 4 tests |
| `Classified` no longer requiring a derived form | 1 test |
| `AmbientRow` growing a `payload` field | `test_i35_an_ambient_row_has_nowhere_to_put_a_payload` |
| `surfaces` put back into `UNBUILT` while the module exists | `test_pending_liveness` (R-6, second occasion) |

**One injection got through, and finding it is the reason to do this.** A
`may_render` that returned `True` for the single purpose string `"court order"`
passed the entire suite, because every purpose test iterated a list I had typed.
An exhaustive-looking test that is exhaustive only over a hand-written list is
precisely what both Phase 0 audits found. Two tests were added in response — a
519-case sample over random and plausible-magic strings, and the AST scan that
makes a recognised purpose value unrepresentable rather than merely absent — and
the injection now fires both, along with a variant routed through a set
membership test that the sampling test alone would have missed.

## The pending file did its job, and it has a limit

`homestead.keep.surfaces` was in `UNBUILT`. `test_pending_liveness` failed the
moment the module existed and would not go green until the four Phase 2 tests
were promoted out into `tests/test_invariants_surfaces.py`, unmarked. Verified by
putting it back: the guard fails by name.

**The defect in the pending file is fixed, and it was not a typo.**
`test_i11_unclassified_field_is_a_build_failure` was marked
`@pending("homestead.keep.registry", "classify_schema is Phase 2")` while
importing `classify_schema` from `homestead.keep.rungs`. Its real dependency was
`rungs.classify_schema`; `registry` is Phase 3.

The cause is a limit in R-6 itself. `UNBUILT` asserts that a **module** does not
exist, and `find_spec` answers for modules, not for symbols inside them. `rungs`
has existed since Phase 0, so a Phase 2 addition *to* `rungs` had no honest home
in the dict — and the test borrowed a Phase 3 one. Two consequences are live:
a reason string can be wrong in a way nothing detects, and such a test goes
XPASS-strict when its symbol lands, which fails but does not name the module.
Phase 3 adds functions to modules that already exist; if it wants symbol-granular
pending marks, `UNBUILT` is the thing to widen. Written up in the file itself.

---

## The disagreement with the corpus

> **RESOLVED 2026-08-05 by the operator: it denies. The spec says so.**
>
> **What decided it.** I-11, in as many words: *"if one reaches runtime
> unclassified anyway it **reads `L5` and is not served**."* That is a
> rendering decision, not an exception. `may_render` answers "may this be
> shown"; an unreadable rung reads `L5`, and `L5` is not shown. Raising would
> contradict the sentence the invariant is written in. The implementation is
> correct and unchanged.
>
> Neither agent could settle this and neither should have. Proposing and
> ratifying do not rest in the same hand, and that is exactly what happened
> here: two authors proposed, a third party ratified.
>
> **The corpus's argument was not wrong about the risk, so it is carried
> rather than discarded.** `3` is not an unclassified field, it is a type
> confusion, and I-14 exists precisely because `3` means something on the
> *other* scale — `Rookie(1) → Steady(2) → Veteran(3)`, ascending privilege,
> so a `1` arriving where a rung is expected is the *least trusted* principal
> and would coerce to the *least restricted* datum. A quiet `False` shows the
> operator a blank pane and the developer a working gate, and the fix reached
> for is a cast at the call site — which is how a `1` becomes an `L1`.
>
> **So the risk moved upstream and a test now pins it there.**
> `test_i14_the_same_non_rungs_are_refused_loudly_upstream` asserts that
> `classify_schema` and `Classified` raise `UnclassifiedField` on the same
> eight values — deliberately the same eight, so the pair reads as one
> decision: **loud on the way in, closed at the point of render.** The quiet
> denial is defensible *only* while that holds, and a load-bearing claim with
> no test is the defect this project keeps finding. Verified by injecting an
> integer-to-rung coercion, which is I-14's exact catastrophe: it trips 24
> tests, including the safety sweep on egress.
>
> **The asymmetry is deliberate, not an oversight.** `classify_schema`,
> `Classified` and the *surface* argument all raise. A surface is a call-site
> property that can never arrive from data, so an unreadable one is a
> programmer error and should be loud. A rung **is** a data property, so an
> unreadable one is the condition I-11 legislates for. Loud on type, closed on
> data.
>
> The full reasoning on both sides is kept in the test docstring rather than
> deleted, because a resolved question that leaves no trace gets re-opened by
> the next person. Suite: **1517 passed / 6 xfailed.**
>
> *The original note, written while it was still open, follows.*
>
> ---
>
> The implementation agent inferred the corpus's position from a test name
> without ever reading it. Having read both, that inference was right on every
> point. The corpus's own docstring also **anticipates the argument above and
> rebuts it**, written before it had seen any of this code.
>
> Two hands that never met, each with a reasoned position, each having
> anticipated the other. **That is the signal this method is built to
> produce**, and it was not for either author — or for the orchestrator — to
> settle by editing the other's file.
>
> **The safety guarantee never depended on the outcome.**
> `test_i14_nothing_that_is_not_a_rung_is_ever_rendered` sweeps 28 bad values
> × every surface × two purposes and passed throughout. Nothing that is not a
> `Rung` is ever served either way. What was at stake was only whether a
> developer finds out — and the answer is that they find out upstream.

Eight of the corpus's parametrizations fail, and they are one test:
`test_i14_a_non_rung_is_refused_loudly_rather_than_denied_quietly`, over
`None`, `0`, `1`, `-1`, `3`, `1.0` and two objects.

I did not read the corpus, so this is inferred from the test's name and from
which of my behaviours differ: **the corpus wants a non-`Rung` in the rung slot
of the decision function to raise; mine denies.** `classify_schema` and
`Classified` already raise on every one of those values, so the disagreement is
about `may_render` / `decide` specifically. **The reviewer should confirm that
reading before acting on it.**

**I did not change it, and here is why.** The spec says, in as many words:

> *Absence fails closed, twice over. An unclassified field is a **build
> failure**, not a default. If one reaches runtime unclassified anyway **it
> reads `L5` and is not served**. A classifier that errors returns `unknown` and
> **denies** — never `L1`.*

and I-11 repeats it: *"At runtime an unclassified field reads `L5` and is not
served. A classifier that errors denies."* "Reads `L5` and is not served" is a
rendering decision, not an exception, and "errors … denies" says the answer in
the error case is still denial rather than propagation.

The practical version: a list pane drawing fifty rows should not die on the one
unclassified row, and the fix a Phase 4 author reaches for when it does is a
`try/except` around the permission check — which is how a fail-closed answer
becomes a fail-open one. The corpus's concern is real (a quiet `False` hides the
defect) and it is answered upstream rather than here: an unclassified value
cannot get into the chokepoint at all, because `serve()` takes a `Classified` and
`Classified` refuses a rung it cannot read.

**This is an engineering decision with a spec answer, not a product decision, so
I have made it and named it rather than escalating it.** If the reviewer reads
the spec the other way, the change is two lines in `_read_rung`'s callers and
one test of mine flips.

### Two things I *did* change after seeing failure names

Declared because the method's whole value is that the hands stayed separate, and
these are the places where information crossed.

1. **`purpose` is keyword-only** on `may_render`, `decide`, `serve`, `serve_all`.
   The published contract only ever passes it by keyword, so nothing is lost, and
   a positional third argument to a permission function is a foot-gun —
   `may_render(rung, surface, some_flag)` reads fine and means something else.
2. **The surface slot takes a `Surface` member and nothing else.** It previously
   coerced valid string spellings. Both are safe — a *wrong* string raised either
   way — so this was a taste call with no safety difference, and the stricter
   position is the one R-7 already argued for in this repo: `VisibleLog.record`'s
   first argument was a free string, that is where note content leaked, and it
   became a closed enum. `Surface` is a `str` enum so its value reads as itself
   in a log line, not so a permission check will accept a bare string in the
   argument that decides what crosses a boundary.

---

## What this does **not** cover

Stated because the gap is the useful part, and because Phase 0 failed for
claiming more than it enforced.

* **It is not a chokepoint.** I-16 wants one authorization point covering the
  TUI, MCP, model calls and egress. `serve()` and `ambient_rows()` are the
  *shape* of one; nothing compels a caller to use them. A Phase 4 renderer that
  reads `Classified.payload` directly is stopped by nothing in this package.
  **A gate wired to one entry point is not a gate, and this one is wired to
  none.** `AmbientRow` is the exception and the pattern to copy: it makes the
  wrong thing unrepresentable *for anything typed to take it*, which is a
  property of the type rather than a promise about callers.
* **No trust tier.** The spec's crossing table also carries WillowGate's
  `Rookie / Steady / Veteran` — S3 needs `≥ Veteran` for `L4`. None of it is
  represented. **`may_render() is True` is not an authorization**; it has not
  checked who is asking.
* **No ledger.** `L3` and `L4` on S4 require an explicit act *recorded*. Nothing
  here writes, and nothing here refuses because a write did not happen.
* **No declassification, and therefore no ledgered act to record one.** There is
  deliberately no function that lowers a rung. When one lands it belongs
  elsewhere, with a name and a date, and
  `test_nothing_here_lowers_a_rung_and_nothing_here_takes_a_date` should be
  updated deliberately rather than deleted quietly.
* **`classify_schema` does not check that a rung is *right*.** It will accept
  `L1` for a sealed family-court case number without a murmur. The spec's step 5
  — record the matter type and jurisdiction, because the *same field* is `L1` in
  a bankruptcy and `L3` in a family matter — needs the registry (I-23, Phase 3).
  A declaration may carry that metadata today and the classifier will read
  through it; nothing requires it.
* **The schema scan has a known hole, and there is a test that says so.** It
  triggers on a module-level mapping named `*_SCHEMA` **or** containing a `Rung`
  among its values. A mapping that is a schema in intent, is not named
  `*_SCHEMA`, and declares every field with a bare integer trips neither. The
  control that does not depend on a convention is that defining a schema *calls*
  `classify_schema`, and an unclassified field then stops the import — verified
  end to end in a subprocess. The scan is a second net with a hole in it.
* **`derived` is not checked for safety and cannot be.** Nothing here can tell
  whether *"a recurring parenting-time obligation on Tue/Thu"* leaks less than
  the schedule it replaces. That is the re-identification judgement the spec puts
  on a human; this only insists a human made one.
* **The re-identification check itself is not implemented.** `L2` is the rung an
  aggregate reaches *after* that check, and until it passes it inherits the
  `max` of its inputs. `compose` gives the inheritance; nobody performs the
  check. I-31 is Phase 4.
* **No `L4` timeout.** I-32 — a reveal expires back to derived — needs a running
  surface. `S1_DETAIL` here says *may*, not *for how long*.
* **Nothing renders.** Phase 4 builds the windows.

---

## Product decisions — **ratified 2026-08-05**

> These were written as "settled by default rather than by decision." They are
> now decided, by the operator, with reasons. The original text is kept below
> each ruling, because the argument is the part worth having later — a decision
> whose reasoning is deleted gets re-litigated by the next person holding the
> file.
>
> **Only one of these is implemented.** The rest are rulings that need code,
> and the code is scheduled rather than done. Saying a thing is decided is not
> the same as the thing being true, which is the failure mode this whole
> project is organised around.

| # | Ruling | State |
|---|---|---|
| 1 | `L3` gets **no** purpose lift on S2. The table wins. | already true |
| 2 | The indicator may **not** say `L5 present` on an ambient surface. | needs Phase 4 |
| 3 | A purpose is a **closed enum**, not free text. | **not implemented — see the cost below** |
| 4 | An empty schema stays an **error**. | already true |
| 5 | A purpose is **per-call, never per-session**. | already true, now stated |

### 1 — `L3` on S2: refuse, and the reason is not "the table says so"

**Ruling: keep refusing.** But the reason matters more than the ruling, because
"the table says so" will not survive contact with a user who wants to ask their
own local model about their own child by name.

What an operator actually loses is narrower than it looks. **Drafting is not
affected** — `L3` on **S4** already permits an explicit ledgered act, so a
motion can carry a real name. What they lose is *asking the model about a named
person*, and for that the derived form is nearly always sufficient: a model does
not need `"A.R."` to reason about a Tuesday/Thursday schedule.

The honest mechanism is **pseudonymise → reason → re-attach downstream**. If
that path exists, `L3` never needs to reach S2 and the cost rounds to zero. If
it does not exist, the cost is real and is being paid silently.

**So this ruling carries a build item**: re-attachment after model output,
Phase 4 or 5. Until that lands, the refusal is enforced but the sentence
justifying it is not yet true.

### 2 — the indicator may not say `L5 present`, and that generalises

**Ruling: no on an ambient surface; permitted on one the operator deliberately
opened.** `"derived · L4 present"` stays legal on the cover — that an `L4`
exists is not itself protected at `L5`.

The principle underneath is worth more than the ruling, and belongs with the
invariants rather than in a list of open questions:

> **A refusal is information at the rung of the thing refused.**

That is I-35 generalised. I-35 says an ambient surface cannot carry an `L4`
*payload*; this says it cannot carry the *fact of an `L5`* either. On a shared
machine, "something is sealed here" tells the person behind the chair that a
record is being kept from them — F-1's reader — and `L5`'s own definition is
that it is never rendered. In a pane the operator deliberately opened, the same
disclosure is fine, by exactly the by-widget logic that settled the `L4`
question on 2026-08-04.

`serve_all` currently leaves no trace, which was the safe default. It is now the
decided behaviour for ambient surfaces.

### 3 — a purpose is a closed enum. **Decided, and deliberately not yet done.**

**Ruling: closed enum.** The tension this was filed under is mostly not real.
"No ceremony tax" was decided about **S1's detail pane**, where opening the pane
*is* the declaration and `purpose` lifts nothing. Read the ceiling table:

```
S1_LIST    (L3, L3)   purpose inert
S1_DETAIL  (L4, L4)   purpose inert
S2_PROMPT  (L2, L2)   purpose inert
S3_AGENT   (L2, L4)   purpose lifts
S4_EGRESS  (L2, L4)   purpose lifts
```

A purpose only changes an answer on **S3 and S4**, and neither caller is a
person typing into a box — one is an MCP tool invocation, the other an export.
A call site names its purpose from a closed set at no cost to anybody in crisis.
It is also what makes S4's spec row implementable: *"explicit act + purpose +
ledgered"* cannot be honoured with a free string, because you can write one to a
ledger but you cannot audit it.

**A suggestion made while ruling on this was wrong, and is withdrawn.** The
proposal that `S1_DETAIL` should take no `purpose` parameter at all — so an
inert argument cannot be passed hopefully — would break the corpus's most
valuable sweep, which passes every purpose to every surface to prove that
*nothing* unlocks `L5` anywhere. Destroying a live safety test to prevent a
lesser error is a bad trade. `purpose` stays accepted on all five surfaces and
inert on three, and the enum plus an inertness test carry the weight instead.

**Why it is not implemented.** The mechanism was built and measured, then
reverted. Making `_declared` require a `Purpose` member fails **637
parametrisations across 42 test functions** — 275 of them in one sweep — because
the corpus is parameterised on free-text purposes throughout. Most of that is
fixture-level rather than hand-written assertions, and a faithful translation
exists: split the lists into valid purposes (the enum members plus `None`) for
the cell sweeps, and rejected purposes (the old adversarial strings) for a new
test asserting they are not accepted at all — which is *stronger* than what
they prove today.

But that translation would be performed by the same hand that wrote the
implementation, on 1,700 lines of corpus written blind precisely so that would
not happen. The enum's safety properties would then be attested only by tests
adjusted until they passed. **The decision is ratified; the implementation
should go through the same two-hand method as Phases 1 and 2.**

**Membership is a further product question and is still open.** Six members
drawn from the acts the documents already name is the proposal:
`DRAFTING`, `FILING`, `EXPORT`, `SUBJECT_ACCESS`, `REDISCLOSURE`,
`AGENT_RETRIEVAL`. Two entries from the blind corpus's own plausible list are
deliberately absent, and the reason is itself the argument for the enum:
`"medical"` is a data **category** and `"operator opened the record"` is a
**surface act**. Free text invited all three kinds of thing into one slot.

### 4 — an empty schema stays an error

**Ruling: keep it fail-closed.** A record type with zero classified fields is a
broken loader far more often than a real case. One improvement is worth making:
the error should distinguish *no fields at all* from *fields, none classified*,
because those are different bugs and today they read the same.

### 5 — a purpose is per-call, never per-session

**Ruling: per-call.** This is already the behaviour, but by accident of
statelessness rather than by decision — which is exactly the gap this section
exists to close. It should become a stated invariant with a test, so that a
later phase adding a session cache has to argue with it rather than route
around it.

Together with the enum it closes the failure the corpus agent predicted: that
every call site hardcodes one purpose within a month, after which `L4` on S3/S4
is unlocked unconditionally and the ceremony is decorative.

### Not on the original list, and probably the largest of them

**S3 and S4 have identical ceilings** — `(L2, L4)` both. The transcription is
accurate and the doc is honest that what separates them is the trust tier and
the ledger, neither of which this module enforces. But they are very different
acts: a local subprocess reading a record, versus data leaving the machine
permanently. **Today `may_render` cannot tell them apart**, and everything built
on it inherits that. It is invisible precisely because the transcription is
faithful.

---

## The original text of these decisions, kept

1. **Does `L3` get a purpose lift on S2 and S3?** The crossing table says no
   (`derived`, flat). The `L3` prose says *"unless an explicit act says
   otherwise."* I followed the table, so today an operator who deliberately asks
   the local model about a named person gets the derived form with no way to
   say *"yes, I mean that person."* That is defensible and it is also a real
   cost. **Whoever owns the model decides which of the two sentences is the
   rule.**

2. **May the rung indicator say that something is sealed?** I-33 wants one
   indicator per surface — *"showing derived · L4 present."* The question is
   whether it may also read *"L5 present."* Saying so tells the operator their
   record is not fully shown; it also **reveals a refusal**, which is `L5`'s own
   definition of what must not be rendered, and on a shared machine it tells the
   person behind the chair that something is being kept from them. `serve_all`
   currently leaves no trace at all, which is the safe default and is not a
   decision anyone made. **The safety doc's F-1 reader is who this is about.**

3. **May a purpose be free text?** `_declared` accepts any non-blank string and
   the code is forbidden from reading it. That keeps a magic value
   unrepresentable, and it means the purpose is uncheckable, unlogged and
   unbounded — a user types `"x"` and gets the same lift as `"medical"`. The
   alternative is a closed enum, which is R-7's answer to the same shape and
   costs a dialog exactly where the "no ceremony tax" decision said not to put
   one. **The two decisions pull against each other and the tension is real.**

4. **Is an empty schema an error?** Currently yes, fail-closed. A record type
   with genuinely no classified fields cannot be expressed.

5. **What happens to a purpose declared once — does it persist?** Not asked and
   not answered. `may_render` is stateless, so today every call re-declares.
   I-32 says a *reveal* expires; nothing says whether a *purpose* does, and the
   difference decides whether one "medical" click unlocks a session or a widget.

6. **Carried forward from Phase 1, still open:** slash date forms, basic ISO,
   backward counting.
