# `REDISCLOSURE` — decision brief

Status: **Proposed. Nothing done.** No file in this repo was changed to write
this; every measurement below was taken in a scratch copy and discarded.

**Proposed here, to be ratified by another hand** — `verified_by ≠ author`, as
with `DECISION-agent-retrieval.md`. This brief recommends; the operator decides.
It matters here for the same reason it mattered there: the hand that measured
the options also argues one of them is a trap, and a self-ratified answer would
be one author grading their own arithmetic.

Raised as the second open item on PR #5, in these terms:

> **`REDISCLOSURE` is named for an act it can never perform.** A 42 CFR Part 2
> record is `L5` in the corpus's own worked example, and `L5` has no override
> anywhere. Faithful to I-13; worth confirming it is intended.

The first half of that is true and I verified it by firing. The second half does
not follow, and working out why moves the finding onto a different object — not
the member, and not the enum.

---

## The premise, tested

**The `L5` classification is real.** `tests/test_surfaces_corpus.py:1738`:

```python
    "prescription_record": Rung.L5,   # 42 CFR Part 2
```

and `tests/test_surfaces_corpus.py:1786`,
`test_worked_example_the_prescription_record_reaches_nothing`, sweeps it against
every surface and every valid purpose, `REDISCLOSURE` named explicitly at
`:1802`. Fired independently: `may_render(L5, s, purpose=REDISCLOSURE)` is
`False` and `decide` is `DENY` on all five surfaces. I-13 holds. Nothing in this
brief proposes touching that.

**But the inference from it fails three separate ways, each measured.**

### 1 · The member is not scoped to Part 2, and the corpus already knows it

`homestead/keep/rungs.py:214` reads `# 42 CFR Part 2-**style** permitted
re-disclosure`. Part 2 is named as the exemplar, not the scope — and the corpus
uses the member accordingly. `test_worked_example_f4_the_address_that_left_the_house`
(`tests/test_surfaces_corpus.py:1939`) reasons about a **relocated home
address**, which has no connection to Part 2 whatever:

> the call site cannot say "verify these citations", because the closed set does
> not contain that act. It has to claim `EXPORT` or `FILING` or `REDISCLOSURE`
> to get an `L4` out, and each of those is a sentence somebody can be held to in
> a ledger.

That is the corpus, written blind, treating `REDISCLOSURE` as one of three live
egress acts. The objection reads the comment as the member's definition; the
corpus reads it as an example.

### 2 · The act is performable, and I performed it

`_CEILING` as it stands (`rungs.py:500`), transcribed by firing rather than by
reading:

```
S1_LIST     plain=L3 with_purpose=L3 inert
S1_DETAIL   plain=L4 with_purpose=L4 inert
S2_PROMPT   plain=L2 with_purpose=L2 inert
S3_AGENT    plain=L2 with_purpose=L2 inert     # closed 2026-08-05
S4_EGRESS   plain=L2 with_purpose=L4 LIFTS
```

Sweeping all 25 `(surface, rung)` cells, `purpose=REDISCLOSURE` differs from
`purpose=None` in exactly two:

```
S4_EGRESS  L3   derive -> render
S4_EGRESS  L4   derive -> render
```

And an actual `serve()` against an `L4` substance-use datum:

```
purpose=None          -> derive  value='a substance-use treatment record exists in this matter'
purpose=REDISCLOSURE  -> render  value='diagnosis: opioid use disorder, in treatment since 2024-03'
```

This is not dead code. It is exactly as live as `DRAFTING`, on the one surface
where any purpose is live at all.

### 3 · The property alleged is not distinguishing

The objection's shape is *its canonical statutory datum is `L5`, so the member
is decorative*. Fired against the other members and the corpus's own `L5` rows:

| member | canonical datum the statute is about | rung | reachable |
|---|---|---|---|
| `SUBJECT_ACCESS` | an SSN — a subject-access request canonically covers it | `L5` | no |
| `EXPORT` | export-ledger key material | `L5` | no |
| `FILING` | allegations under a protective order | `L5` | no |
| `REDISCLOSURE` | a prescription record | `L5` | no |

Four of six members have a canonical datum at `L5` they cannot reach. That is
not a defect in four members; it is I-13 working. **`L5` is the rung that no act
justifies** — that is the whole content of the rung, and a member whose act
happens to have a well-known `L5` instance is not thereby a member that can
never act.

**Also fired:** across the whole `rung × surface` grid there is **not one cell**
where any two members give different answers. `REDISCLOSURE` is
indistinguishable from `DRAFTING` everywhere, which is the property
`PHASE2-SURFACES.md` pins and `DECISION-agent-retrieval.md` § *The mechanical
fact* argues from. It cuts both ways and is applied both ways below.

---

## What the finding is actually about

The strongest version of the objection is not about the member. It is that
**"a 42 CFR Part 2 record is `L5`" is being read as a rule when the corpus's own
source states it as an example — and the governing text points the other way.**

Three passages in `safe-app-store/docs/homestead-rungs.md`, which
`rungs.py:467` names as *the only place the mapping is stated*:

- **`:151`** — the class→rung table is prefaced *"Illustrative, not exhaustive;
  the procedure below governs."* Both Part 2 rows (`:160`, `:168`) are in that
  table.
- **`:108`–`:112`** — `L4`'s own definition: *"Health, money, discipline,
  likeness are the familiar four; here they also include minors' data,
  **substance-use records (42 CFR Part 2)**, immigration status, and privileged
  communications."* Part 2 is named as an `L4` **category**.
- **`:138`–`:144`** — `L5`'s definition is a four-clause test (reveal a refusal,
  expose privileged strategy, disclose key material, breach a sealing order) and
  its `Includes:` list is *`do_not_use` and why; the content of a sealed record;
  export-ledger key material; anything under a protective order.* **Part 2 is
  not in it.** Part 2 is a disclosure-consent regime, not a sealing order.

So the same document places Part 2 material at `L4` by rung definition and at
`L5` by illustrative table, and says the procedure governs. Run the procedure
(`:175`–`:180`) on a substance-use treatment record: step 3 says *carries a
category the law follows* → `L4`; step 4 asks whether rendering breaches a
sealing order, and for a Part 2 record simpliciter it does not.

**This does not make the `L5` row wrong, and I am not proposing to move it.**
Over-classifying fails closed, which is this repo's whole direction of error,
and the corpus is explicit that the row is deliberate (`:1786`: *"This is the
one row where 'the operator holds everything' stops being true, and it stops
being true deliberately"*). What it makes wrong is the **generalisation** —
*every Part 2 datum is `L5`, therefore `REDISCLOSURE` is inert* — which is the
step the objection takes. The spec's own step 5 is the standing refutation of
that move: *the same field is `L1` in a bankruptcy and `L3` in a family matter*.
A regime does not classify; a datum in a matter does.

## So which finding is it?

Not **dead code** — measured, two live cells, § 2.

Not **misnamed** — and this is where it differs sharply from `AGENT_RETRIEVAL`.
That member named a *surface* (`S3_AGENT` **is** agent retrieval), which is the
`"operator opened the record"` error sitting inside the set that paragraph was
defending. `REDISCLOSURE` names an **act**, which is what the enum's own docstring
demands of a member (`rungs.py:180`: *"These six are acts, not categories and not
widgets"*). It is arguably the best-fitting member in the set: re-disclosure —
passing a record onward — *is* an egress, and `S4_EGRESS` is the one surface
where a purpose lifts anything.

It is **one comment overstating a member's scope**, plus a classification
example being cited as a rule. Both are documentation faults. Neither is an
enum-membership fault.

## Does dropping it remove any capability?

No — by exactly the test `DECISION-agent-retrieval.md` applied to
`AGENT_RETRIEVAL`, and I re-ran it rather than citing it. No member is ranked;
`_declared` returns a `bool`; the ceiling table has two columns. A caller
wanting `L4` on `S4_EGRESS` declares `Purpose.EXPORT` and gets the identical
lift from the identical line.

**And that is the argument against dropping it, not for.** `rungs.py:212`
defines `EXPORT` as *"the operator taking their own record out."* A
re-disclosure is not that: it is passing on a record you received under someone
else's permission. Drop `REDISCLOSURE` and the re-disclosing caller must write
`EXPORT` into the ledger, which is **false** — and the previous brief's sentence
governs unchanged: *a tautology in a ledger line is uninformative; a falsehood
in a ledger line is worse than uninformative, because it reads as evidence.*
Here it is worse still than it was for `ANSWERING`, because `EXPORT`'s own
comment states the distinction the false declaration would be erasing.

## On "every member is just a ledger label"

The enum's stated value is auditability, and auditability is Phase 3+; there is
no ledger. On that reasoning every member is a ledger label and none of the six
is safer than the others. True, and it does not single this one out.

What *would* single a member out is being a label **nobody could ever truthfully
apply**. That is the claim the objection needs and it is the claim that failed:
a re-disclosure of an `L3` or `L4` datum onto `S4` is an ordinary act, it is
performable today (§ 2), and it is the only member that names it. A member that
never changes an answer *and* has no truthful occasion is dead weight. A member
that never changes an answer *relative to its five siblings* but names a real,
distinct act is doing the one job the enum has until Phase 3 arrives.

---

## Options, with measured costs

Baseline on `main`, both real tree and scratch copy: **1621 passed / 6 xfailed**,
1627 collected.

**A — Drop `REDISCLOSURE`.**
Measured: **6 failures across 3 files**, suite **1532 passed / 6 failed / 6
xfailed**.
- `tests/test_purpose_corpus.py::test_the_six_members_are_exactly_the_six_that_were_ratified`
- `tests/test_invariants_surfaces.py::test_the_purpose_enum_is_the_six_that_were_published`
- both `..._has_not_been_hollowed_out` guards (`len(Purpose) == 6`)
- `tests/test_surfaces_corpus.py::test_worked_example_the_prescription_record_reaches_nothing`
- `tests/test_invariants_surfaces.py::test_i14_an_integer_never_becomes_a_rung_by_being_compared`

**Two things the count hides and the brief should not.** First, collection drops
**1627 → 1544**: *83 parametrisations stop running*, because the sweeps
parametrise on `VALID_PURPOSES`. The two hollowed-out guards are what catch
that, and they caught it — the corpus doing precisely the job Phase 0's audit
built it for. Second, the I-14 test fails with `AttributeError: REDISCLOSURE`,
not an assertion: it hardcodes this member as its representative purpose while
testing something unrelated. That is the failure most likely to be "fixed" by
substituting another member without reading, leaving 82 parametrisations gone
and one guard to notice.
Removes no capability. Leaves re-disclosure with no truthful member.
**Not recommended.**

**B — Re-comment the member; leave the code alone.**
Replace `# 42 CFR Part 2-style permitted re-disclosure` with wording that names
the act and cites Part 2 as an exemplar rather than a definition — e.g.
*"passing on a record received under a disclosure permission (42 CFR Part 2 is
the exemplar, not the scope)"*.
Measured: **0 failures**, suite **1621 / 6 xfailed**, byte-for-byte the
baseline. The pinned-set tests pin names and values, not comments.
Cheap, honest, and — exactly as with the `ANSWERING` rename — **it should not be
mistaken for a remedy.** It fixes the sentence that generated the objection.
**Recommended.**

**C — File the classification question; change nothing in the enum.**
Record that `homestead-rungs.md` places Part 2 at `L4` by rung definition
(`:112`) and at `L5` by illustrative table (`:160`, `:168`) with the table marked
*illustrative* (`:151`), and that a Part 2 **datum's** rung is a per-matter
step-1-to-4 judgement rather than a property of the regime.
Measured cost: **zero** — no code, no tests.
This is where the finding actually lives. **Recommended, alongside B.**

**D — Reclassify `prescription_record` `L5` → `L4`.**
Measured: **2 failures**, suite **1619 passed / 2 failed / 6 xfailed** —
`test_worked_example_the_prescription_record_reaches_nothing` and the
workers-comp arm of `test_worked_example_a_whole_matter_composes_to_its_worst_field`.
Listed because it is the remedy the framing implies, and **its low test cost is
precisely why it must not be chosen on test cost.** It moves one row in the
fail-open direction, on the row the corpus says is deliberate, to make a member
look busier. The asymmetry of being wrong: wrong in the closed direction costs
the operator a derived sentence about a treatment record; wrong in the open
direction puts a substance-use diagnosis on an egress behind a hardcoded
constant. **Not recommended.**

**E — Close `S4`'s purpose column too: `S4_EGRESS (L2, L2)`.**
Measured: **27 failures across 11 test functions in 2 files**, suite **1594
passed**. Failing functions include `test_every_member_lifts_the_ceiling_on_s4`,
`test_the_ceiling_table_matches_an_independent_transcription`,
`test_purpose_is_accepted_on_all_five_surfaces_and_inert_on_four`, and the
per-call/leak family.
This is the decision `DECISION-agent-retrieval.md` § *"S4 was left open,
deliberately"* declined to put, and it is **the only option under which the
objection as raised becomes true** — of all six members at once, not this one.
Included so the brief is honest about where the pressure really is: if
`Purpose` is decorative, that is a fact about the S4 column, not about
`REDISCLOSURE`. Out of scope for this decision and much larger than it.
**Not recommended here; noted as the real question behind the question.**

## Recommendation

**B + C. No change to membership, no change to the crossing, no change to any
classification.**

The premise's factual half holds and its inferential half does not. The member
performs its act on `S4_EGRESS` at `L3` and `L4`; it is the only member that
names that act; dropping it would force a false ledger line under `EXPORT`; and
the "canonical datum is `L5`" property it was faulted for is shared by three
other members and is I-13 working as designed.

What is genuinely wrong is smaller and is prose: a comment that reads as a scope
when it was meant as an example, and a worked-example row being cited as a rule
against a spec whose own `L4` clause names the same regime.

**Confirming intent, which is what the objection asked for:** yes — on the
evidence, the member is intended, it is exercisable, and its name is the kind of
name the enum's docstring asks for. What was not intended, as far as anything
written down shows, is the comment being read as the member's definition.

## What is gated on which answer

- **B** — one comment line in `rungs.py`. Zero tests. Startable immediately on
  ratification; not startable by this hand alone.
- **C** — a paragraph here and, if the operator wants it upstream, a note in
  `safe-app-store/docs/homestead-rungs.md` § `L5` distinguishing the regime from
  the datum. That file is outside this repo and outside this brief's write
  scope. Zero tests.
- **A** — needs a ratification this brief argues against. 6 test functions, 3
  files, 83 parametrisations, and a decision about what the re-disclosing caller
  writes in the ledger instead.
- **D** — a classification decision, not a code decision. Needs whoever owns
  `homestead-rungs.md`. 2 tests, and the wrong direction of error.
- **E** — a crossing decision of the same weight as the `S3` closure, and it
  should be filed on its own terms rather than smuggled in under a member's
  name. Its bar is the mirror of `S3`'s: the ledger existing, which is Phase 3+.

## What I did not do

- **Nothing in the repo was edited.** This file is the only write. `git status`
  was clean before and after; another agent is working in the same tree.
- Every experiment ran in a scratch copy, verified to import its own
  `rungs.py` rather than the real tree's, and every mutation was reverted and
  the copy re-run green (**1621 / 6 xfailed**) before the next.
- **I did not rewrite any dated claim.** `tests/test_purpose_corpus.py:401`–`403`
  — *"The one that stings is `REDISCLOSURE`: 42 CFR Part 2 permits a
  re-disclosure, and permitting an act is not lowering a rung"* — is **correct**
  and should stand as written; § 3 above extends it rather than replacing it.
  `PHASE2-SURFACES.md`'s membership paragraph is likewise left alone; if B
  lands it should be **annotated**, not restated as though the comment had
  always read that way.
- I did not open the ledger question, the trust-tier question (P-1), or `S4`'s
  column beyond measuring option E.
- I did not verify that `L4` is the *right* rung for any real Part 2 datum. That
  is a classification judgement the spec puts on a human, `classify_schema`
  explicitly does not check it (`rungs.py:857`), and it needs the Phase 3
  registry.
