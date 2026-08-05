# `AGENT_RETRIEVAL` — decision brief

Status: **B, C and D all done. Closed 2026-08-05.**

- **B** — member renamed `AGENT_RETRIEVAL` → `ANSWERING` (value
  `"agent_retrieval"` → `"answering"`). Suite **1609 / 6 xfailed**, unchanged.
  That it changed nothing is the argument in § *The mechanical fact*, not a
  disappointment: a rename that cannot move an answer cannot be a remedy for an
  answer that was wrong.
- **D** — `S3_AGENT` ceiling `(L2, L4)` → `(L2, L2)`, ratified by the operator
  after the walkthrough below. S4 unchanged. Suite **1621 / 6 xfailed**.
- **C** — the trust-tier fix (P-1) is filed, still open, and is what would
  reopen the column.

**Proposed and ratified by different hands**, which this repo requires and which
mattered here more than usual: the same hand that proposed D also refuted its
own first remedy, so a self-ratified D would have been one author grading two of
their own arguments against each other.

Raised as the first open item on PR #5, in these terms: `AGENT_RETRIEVAL` is a
*surface act*, which is the exact reasoning that correctly kept `"operator
opened the record"` out of the set. `S3_AGENT` **is** agent retrieval, so
declaring it there is declaring the surface you are already standing on — a
tautology that buys `L4`. Suggested remedy: drop it, or rename it to the act.

Working that through against the code changes the question. The brief below
records why, because the remedy as proposed does not do what it was proposed to
do.

---

## The mechanical fact the remedy has to survive

`may_render` never reads *which* member was declared.

```python
declared = _declared(purpose)          # -> bool
plain, with_purpose = _CEILING[target] # two columns, not seven
ceiling = with_purpose if declared else plain
```

`_declared` returns a `bool`. The ceiling table has two columns. No production
path reads a member's value — `Purpose.` appears in `rungs.py` only inside
docstrings and one error message. This is deliberate and it is pinned: the
"no member is ranked above another" sweep asserts the six interchangeable
across the whole rung × surface grid.

**Therefore dropping `AGENT_RETRIEVAL` removes no capability.** An MCP call site
that wants `L4` on `S3_AGENT` declares `Purpose.DRAFTING` instead and gets the
identical lift, from the identical single line, with no test failing.

The prediction in the objection — *the member every MCP call site will hardcode
within a month* — is correct. Removal does not falsify it. It changes **which**
constant gets hardcoded, and it makes the hardcoded one **untrue**: an agent
answering an operator's question is not drafting and not filing. A tautology in
a ledger line is uninformative. A falsehood in a ledger line is worse than
uninformative, because it reads as evidence.

That is the argument against the remedy as proposed, and it is an argument the
member's own defence does not get to skip either — see D.

## What is actually load-bearing

`S3_AGENT: (Rung.L2, Rung.L4)`, as it stood when this was written. The purpose
column on S3 was the whole unlock: two rungs of lift on the one surface the
module's own docs describe as having **no human in the loop**, granted by a
boolean that any of six constants sets. It is now `(Rung.L2, Rung.L2)` — this
paragraph is the diagnosis that closing it came from, kept in the tense it was
written in.

The enum closed the *set* of strings that can set that boolean. It did not make
setting it mean anything, and PR #5 already states as an invariant that it
cannot: *`may_render` gains no safety from membership; the value is
auditability, and that is Phase 3+.*

There is no ledger yet. So on S3 today the purpose column buys `L4` against an
auditability guarantee that is not built. That is the decision worth making.
The member-name question is downstream of it and much smaller.

## Options

**A — Drop `AGENT_RETRIEVAL`.**
Removes no capability (above). Leaves agent retrieval with no truthful member,
so every legitimate agent call declares an act it is not performing. Trades an
uninformative ledger line for a false one. **Not recommended.**

**B — Rename to the act: `ANSWERING` or `BRIEFING`. — DONE, `ANSWERING`.**
Keeps a truthful member for the real case. Narrows the tautology without
closing it — S3 *is* the answering surface, so "answering" is still close to
naming where you stand. No capability change, no ceiling-table change, one
member spelling and its pinned-set test. Cheap and honest, and it does not
pretend to be the fix.

Landed across `rungs.py`, both pinned-set tests, the three corpus files and
`PHASE2-SURFACES.md`. Two things were **not** rewritten to match: the published
set is recorded as `AGENT_RETRIEVAL`-renamed rather than restated as though
`ANSWERING` had always been there, and the § 3 open-question paragraph keeps its
original argument with the rename appended. A dated document edited to agree
with the present loses the ability to say what the project used to believe —
the same rule that kept `phase2_corpus_report.md` § 4.5 standing.

**C — Keep it; file the real fix at the trust tier.**
This is already the repo's own position: PHASE2-SURFACES.md § "One open question
this raises and does not answer" says the enum cannot fix a member attached to a
surface with no human in the loop, and that *what fixes it is S3's trust tier,
which is still not represented anywhere* (P-1, still open). Correct, and not
mutually exclusive with B.

**D — Close S3's purpose column until the ledger exists. — DONE, S3 only.**
`S3_AGENT: (Rung.L2, Rung.L2)`. The only option that actually removes the
unlock rather than renaming the key to it. It is the option that matches the
stated invariant: if the purpose column's value is auditability and
auditability is Phase 3+, then the column was unbacked on the one surface where
it lifted two rungs.

**It withholds; it does not deny.** `decide()` returns `DENY` only for `L5` and
an unreadable rung, so `L3` and `L4` on S3 come back `DERIVE` — the standing-in
sentence rather than silence. An agent that may not see the record can still be
told a medical-records response is due on the 15th. That is what made the
closure affordable, and it is the difference between this and a much larger
decision nobody made.

**Measured before it was chosen, not after.** Flipping the cell and running the
suite: 26 failures, 1583 passing, confined to two files. All four import guards
still pass — equal columns are legal (S2 already had them), no ceiling is `L5`,
a purpose still never lowers one, the ambient check is untouched. `_NEEDS_DERIVED`
is computed from the minimum *plain* ceiling, already `L2`, so it stayed
`{L3, L4}` and `Classified` demands a derived form for exactly the same rungs.
Nothing cascaded.

**The failures were the decision announcing itself.** They included
`test_the_ceiling_table_did_not_move` and
`test_every_member_lifts_the_ceiling_on_s3_and_s4` — tests that exist to certify
the purpose enum moved no answer. D falsifies them deliberately. The first was
renamed (`..._matches_an_independent_transcription`) because the table did move
and a test whose title denies the change it asserts is this project's
signature defect; the second was narrowed to S4 and its S3 half **inverted**
rather than dropped, into `test_no_member_lifts_anything_on_s3` and
`test_s3_derives_rather_than_denies_what_it_no_longer_renders`. A closed column
that nothing asserts is a column the next author reopens by accident.

**Verified by firing.** Reopening the cell to `(L2, L4)` trips 33 tests across
seven test functions, including all three new guards. Final suite: **1621 passed
/ 6 xfailed.**

**One thing got quietly weaker and is written down rather than absorbed.**
`_session_leak` can no longer observe a purpose cache on S3, because with both
columns equal there is no answer a cache could move. That is acceptable only
because the same closure removes what a cache there would have bought — the
exposure and the observability went together. Widening its surface loop also
exposed a real defect in the helper: sampling the undeclared answer *inside* the
loop meant that against a stateful callable the cache was already primed by the
second surface, so it compared a poisoned reading against itself and reported
nothing. The baseline is now taken before anything is declared, and the check
now catches a declaration made on one surface moving another surface's answer —
which is how the leak actually arrives.

**S4 was left open, deliberately.** Closing both would make `Purpose` inert
everywhere and reduce it to a pure ledger label — coherent, and arguably where
it is heading, but a larger decision than this one. S4's caller is an operator
performing an explicit act on their own record, which is what the spec row means
by *"explicit act + purpose + ledgered"*; S3's caller is a tool invocation. So
closing S3 alone does not invent an asymmetry, it starts expressing one the spec
already makes and the table could not say.

## Recommendation — as put, and as taken

**B + C now, D as the question that should actually be put.** D was put, and
taken, on S3 alone.

B is a one-line honesty fix that costs nothing and should not be mistaken for a
remedy. C is where the fix lives and the repo already says so. D is the decision
with consequences, and this was the cheapest moment it would ever be available:
**there were no callers yet.** No production code outside `rungs.py` calls
`may_render`, `decide`, `serve` or `serve_all` — Phase 4 is unwritten, so D cost
26 test assertions and zero migrations. Every month it had been deferred, it
would have been paid for in call sites instead.

## Reopening

The same one cell, `S3_AGENT`, back to `(Rung.L2, Rung.L4)` — plus the three
guards that would then correctly fail. The bar is C: S3 carrying a trust tier
(P-1), and S4's ledger existing to copy. Until both, the lift would be
conditioned on a tier this module cannot read, which is a lift conditioned on
nothing.

The asymmetry of being wrong is the argument, and it survives the decision:
wrong in the closed direction costs derived text where a payload would have
served, and an agent still gets the standing-in sentence. Wrong in the open
direction leaves `L4` reachable on an unattended surface behind a hardcoded
constant.

## What was gated on which answer

- ~~B alone: member rename, its pinned-set test, three doc mentions. Small.~~
  Done. It was small, and it was small for the reason that makes it not a fix.
- ~~D: ceiling table, the byte-identical claim, and the S3 rows of the corpus.
  Not startable without a ratification, and not startable by the hand that
  proposed it.~~ Ratified and done. The estimate held: one cell, both pinned
  transcriptions, and 26 assertions across two files. The byte-identical claim
  was the intended casualty — it was a claim about the *enum*, and it is
  preserved as that rather than deleted.
