# `AGENT_RETRIEVAL` — decision brief

Status: **open.** Proposed here, not ratified. Nothing in this brief is
implemented; the enum is unchanged on `main`.

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

`S3_AGENT: (Rung.L2, Rung.L4)`. The purpose column on S3 is the whole unlock.
Two rungs of lift on the one surface the module's own docs describe as having
**no human in the loop**, granted by a boolean that any of six constants sets.

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

**B — Rename to the act: `ANSWERING` or `BRIEFING`.**
Keeps a truthful member for the real case. Narrows the tautology without
closing it — S3 *is* the answering surface, so "answering" is still close to
naming where you stand. No capability change, no ceiling-table change, one
member spelling and its pinned-set test. Cheap and honest, and it does not
pretend to be the fix.

**C — Keep it; file the real fix at the trust tier.**
This is already the repo's own position: PHASE2-SURFACES.md § "One open question
this raises and does not answer" says the enum cannot fix a member attached to a
surface with no human in the loop, and that *what fixes it is S3's trust tier,
which is still not represented anywhere* (P-1, still open). Correct, and not
mutually exclusive with B.

**D — Close S3's purpose column until the ledger exists.**
`S3_AGENT: (Rung.L2, Rung.L2)`. The only option that actually removes the
unlock rather than renaming the key to it. Costs S3 the ability to reach `L4`
at all, breaks the byte-identical ceiling table, and moves a substantial number
of corpus assertions. It is the option that matches the stated invariant: if the
purpose column's value is auditability and auditability is Phase 3+, then the
column is currently unbacked on the one surface where it lifts two rungs.

## Recommendation

**B + C now, D as the question that should actually be put.**

B is a one-line honesty fix that costs nothing and should not be mistaken for a
remedy. C is where the fix lives and the repo already says so. D is the decision
with consequences, and this is the cheapest moment it will ever be available:
**there are no callers yet.** No production code outside `rungs.py` calls
`may_render`, `decide`, `serve` or `serve_all` — Phase 4 is unwritten. Every
month D is deferred, it gets paid for in call sites.

## What is gated on which answer

- B alone: member rename, its pinned-set test, three doc mentions. Small.
- D: ceiling table, the byte-identical claim, and the S3 rows of the corpus.
  Not startable without a ratification, and not startable by the hand that
  proposed it.
