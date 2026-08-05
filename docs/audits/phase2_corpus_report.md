# Phase 2 corpus — report from the blind half

> Saved by the orchestrator: the agent could not write this file itself. Its
> §1 disclosure was independently verified against the agent transcript —
> see "Verification" at the foot of this file.

## 1 · Disclosure first: I ran the corpus against the implementation

The brief said I was in an isolated worktree. I was not — `git worktree list`
in `/workspace/homestead` shows exactly one checkout, and that checkout is
where both agents are working. I wrote my file into `tests/` there (my file,
mine alone), and when I ran `pytest tests/test_surfaces_corpus.py` to confirm
it lands **red**, it did not: `homestead/keep/surfaces.py` already existed and
1,043 of 1,054 cases passed.

What I did and did not do about it:

- **I never opened `surfaces.py`, the extended `rungs.py`,
  `test_invariants_surfaces.py`, or `test_invariants_pending.py`.** No source
  of the other agent's was read at any point. I read only the *committed*
  `rungs.py` (via `git show HEAD:`), `logs.py`, `paths.py`, `dates.py`,
  `test_dates_corpus.py`, and the two `test_invariants_{logs,paths}.py`.
- **The corpus was finished and frozen before that run**, and had already been
  validated against my own mock. **I changed no assertion, in either
  direction, in response to what I observed.** The three disagreements in §5
  are reported, not resolved.
- What I saw was pytest failure *names* and one-line assertion messages —
  enough to report §5 accurately, not enough for the corpus to have learned
  the code's shape.

On the strictest reading this corpus does not qualify as one that provably
never met the implementation. On the reading that matters it does: every
assertion was written from `homestead-rungs.md`, the build plan, the bug list
and the published contract, and none was written or weakened from the code.

## 2 · How I checked the corpus was worth landing

Since I could not land it red and watch it go green, I did the equivalent
offline in `scratchpad/phase2_corpus/dryrun/` — a throwaway tree with a mock
`rungs.py`/`surfaces.py` I wrote myself from the spec:

1. **Satisfiability: 1,054 / 1,054 pass** against a mock implementing my
   reading of the crossing table. The corpus is not self-contradictory and
   does not demand something no implementation can give.
2. **Mutation testing (`mutate.py`): 29 realistic single-defect mutants, 29
   killed, 0 survivors.** Including: deny-everything; allow-everything;
   `may_render` returning `None` to mean "derived"; the list pane serving `L4`
   once a purpose is declared; `L4` reaching the prompt; `L5` escaping into
   the detail pane; `L5` escaping onto egress; a non-monotone S3 column;
   `compose` taking `min` / returning its first input / silently dropping
   unreadable inputs; `compose()` returning `L1`; an integer rung coerced to a
   rung; an unclassified field defaulting to `L1` **or to `L5`**; a classifier
   that swallows its exception; a name-based fallback; a normalizing
   (`.upper()`) rung parser; a catch-all `Surface.INTERNAL`; an `IntEnum`
   `Surface`; a clock read in the decision path; a bare-integer rung
   comparison; `purpose` going positional; and a `force=` parameter.

Two mutants worth calling out. **"Unclassified defaults to `L5` at build time"
is killed** — I-11 has two clauses and the fail-closed runtime one is not
permission to skip the build-time one. And **the non-monotone S3 column was
found by the corpus in my own mock**, before I ran anything else. See §4.1.

## 3 · What the corpus asserts

Twelve sections in the file.

| § | Claim | Source |
|---|---|---|
| 1 | Five rungs `L1`–`L5`, strings never integers; no bare-integer comparison in the Phase 2 source (AST scan); neither enum is an `IntEnum` | I-14 |
| 2 | Surface is the closed set of four; S1 is exactly two panes; every member matches `S[1-4]_…`; no `INTERNAL`/`ANY`/`DEFAULT` catch-all | the four surfaces |
| 3 | The four published-contract groups, restated | `test_invariants_pending.py` |
| 4 | Every `(rung × surface × purpose)` cell returns a real `bool`; **refusal is monotone up the ladder**; permitted-surface sets only shrink; the exact permitted sets at `purpose=None`; blank purposes unlock nothing; a declared purpose never *removes* a permission | BUG-5, crossing table |
| 5 | `L5` served by no argument on any surface — 44 purpose strings × every surface, plus 14 non-string purposes including an `__eq__`-always-`True` object; no `force`/`override`/`bypass` parameter; `purpose` keyword-only with no permissive default | I-13 |
| 6 | The whole S2 column for every purpose; S2 never more permissive than S1 | "S2 is a rendering" |
| 7 | `compose` is `max` over all pairs and all triples, associative, commutative, idempotent, never lowers, returns a `Rung`; `compose()` is `L5`; **a composed rung meets `may_render` exactly as its `max` would** (every combination up to 3, every surface); junk never composes to a low rung; junk mixed with real rungs is not silently dropped | I-12, I-11 |
| 8 | 11 flavours of unclassified and 12 of misdeclared all fail the build; the failure names the field; one bad field among 30 fails; **no classification is ever inferred from the field name**; a classifier that errors denies; an unenumerable schema does not classify clean | I-11 |
| 9 | Nothing that is not a `Rung`/`Surface` is ever rendered (safety half, unconditional); refusal is loud (loudness half, separate); the two spellings of one rung never disagree; deterministic and stateless | I-14, BUG-7 |
| 10 | No clock parameter and no clock call in `rungs.py`/`surfaces.py`; a closed matter keeps its rung; any declassification-shaped callable must demand more than a rung; aggregation is not a declassifier | "time does not declassify" |
| 11 | Worked examples end to end — the workers' comp Today card, the prescription record, whole-matter composition for all three matter types, the case number that is `L1` in bankruptcy and `L3` in custody, **a prompt as the `max` of its context window including a retrieved neighbour**, the BUG-5 drafting packet, the I-31 cover screen, the `L3` parenting schedule, F-4's exfiltrated address as `L4` on `S4` | rung model |
| 12 | Corpus self-guards: table sizes, cross-product size, and **that something is `True` on every surface**, so `return False` cannot pass | Phase 0 audit |

**The design choice worth defending.** Every type-discipline test is split in
two: a *safety* half asserted unconditionally (`is not True`) and a *loudness*
half asserted separately (`pytest.raises`). A disagreement about how to refuse
cannot cost the guarantee that it refuses.

**Why the sweep is exhaustive rather than sampled.**
`test_bug5_a_refused_rung_refuses_every_rung_above_it` runs over every surface
× 12 purposes and checks all ten rung pairs in each — because BUG-5 was one
cell, in one guard, with the screen next to it saying the opposite.

## 4 · Where the spec is ambiguous or self-contradictory

### 4.1 · The crossing table is non-monotone at S3, read literally — this is the finding

| | S3 · agent (MCP) |
|---|---|
| `L3` | **derived**, ≥ Steady |
| `L4` | **derived**, ≥ Veteran + purpose |

Cell-by-cell, `L3` on S3 has **no unlock at all** while `L4` on S3 has one
("+ purpose"). A lower rung refused where a higher rung is served — **BUG-5's
exact shape, in the normative table, on the surface that is an automated
agent.** I wrote my mock from that literal reading and the corpus killed it
immediately.

It is a reading error rather than a real inversion, but only if you bring
outside knowledge: the `L3` prose says *"On S2/S3/S4 it is `NULL` and a
derived form is served in its place, **unless an explicit act says
otherwise**"*, supplying the unlock the table's cell omits. Two statements in
different registers, and one of them alone produces a non-monotone table.

**Assumed:** both cells unlock, so monotonicity holds. **Recommended:** edit
`homestead-rungs.md` so every cell states its own unlock, or say explicitly
that the table is monotone by construction. A reader who implements from the
table alone writes the inversion.

### 4.2 · `L3` on `S2` — does a purpose unlock it?

The `L3 · S2` cell is a flat **derived**, where `L3 · S4` says "explicit act,
ledgered" and `L4 · S1` says "derived unless purpose". The table spells out an
unlock wherever there is one; this cell has none. The `L3` prose implies there
is one. **Assumed:** the table wins — `L3` never reaches a model prompt as a
payload, purpose or no purpose. Docstring says so and says why.

### 4.3 · `may_render` cannot express the trust tier or the ledger

Three cells are gated on things the signature does not carry: `≥
Rookie/Steady/Veteran` (S3) and "ledgered" (S4). So `may_render(L4, S3_*,
purpose="medical")` answers a *weaker* question than the cell. The corpus
deliberately does **not** pin those two cells with a purpose present; it pins
everything around them (monotonicity, the `L1`/`L2` rows, the whole `L5` row,
both `L4` hard stops, and `⊆ {S1_DETAIL} ∪ S3 ∪ S4`).

**Named risk:** if `may_render` returns `True` there and the trust check lives
at a different call site, I-16's "one authorization chokepoint" has two
chokepoints — and F-2 is the finding that a gate wired to one entry point is
not a gate.

### 4.4 · An empty schema

`classify_schema({})` is not asserted either way. It is the shape a broken
loader produces, and "the build passed because nothing was checked" is a real
failure mode — but an empty schema is also just an empty schema.
`_UnenumerableSchema` covers the dangerous half.

### 4.5 · `Rung` is a `str` subclass, so a rung is also a valid `purpose`

`may_render(r, s, purpose=Rung.L1)` type-checks, and `isinstance(purpose, str)`
cannot see the transposition. The corpus asserts only that it gets **no
special power**: `purpose=Rung.L1` does exactly what `purpose="L1"` does and
never moves the rung being scored.

## 5 · Three disagreements observed against the implementation

Reported, not resolved. **I changed nothing because of these.** 1,043 / 1,054
pass; all 11 failures are these three.

1. **`purpose` is `POSITIONAL_OR_KEYWORD`, not keyword-only.** The corpus
   asserts keyword-only: the contract always writes `purpose=`, and one
   chokepoint read positionally at one call site and by keyword at another is
   two readings of one gate. Engineering call, cheap either way.
   *(1 failure.)*

2. **A non-`Rung` first argument is denied quietly rather than refused
   loudly** — `3`, `1`, `0`, `-1`, `None`, `1.0`, a list, a dict. **The safety
   half passes**: none ever returns `True`, so I-14's catastrophe (a trust
   tier read as a rung) does not happen. The corpus asserts `raise`, and the
   docstring states the belief: a silent `False` for a mis-typed rung shows
   the operator a blank pane and the developer a working gate, and the fix
   reached for is a cast at the call site — which is how a `1` becomes an
   `L1`. *(8 failures.)*

3. **`may_render(rung, "S1_LIST", purpose=…)` returns `True`.** The exact
   member *name* as a bare string is accepted as a surface. `"s1_list"`,
   `"S1"`, `"screen"` and the other eleven bad surfaces are all correctly
   refused — only the enum's own spelling gets through, which is what a
   `str`-Enum does under a dict lookup. **This is the substantive one of the
   three.** The surface argument decides *which column of the table applies*;
   if an unvalidated string from a config file, a JSON payload or an MCP tool
   argument can select `S1_DETAIL` — the most permissive column — while the
   render lands on S2 or S4, the chokepoint has been steered from outside.
   `Rung` has the same leniency by the same mechanism and there it is
   defensible (I-14 says a rung *is* a string). For `Surface` there is no such
   argument: a surface is not a string, it is one of four render paths.
   *(2 failures.)*

## 6 · Product decisions — for a human, not for either agent

**P-1 · Does a declared purpose unlock an `L4` payload to an automated agent
(S3) at all?** The table gates it on `≥ Veteran` trust *and* a purpose; the
`L4` prose says only "On S3 and S4 it requires an explicit purpose". S3 is the
MCP stdio entry point — a subprocess, with no eyes to be walked past and no
judgement about what it forwards. `L5`'s text is explicit that "never"
includes "the operator's own agents"; `L4`'s is not. **Not an engineering
question.** It decides whether a household's diagnosis can be read by a tool
the operator pointed at their own record, and it shapes what a Phase 6 agent
can ever be built to do.

**P-2 · Is a purpose a free string, or a closed enum?** Today it is free text.
The corpus does not object — but free text is exactly what F-4 and BUG-4 are
about, and a purpose that is never validated, recorded or audited gets filled
in with `"drafting"` by every call site within a month, at which point `L4` on
S3/S4 is unlocked unconditionally and the ceremony is decorative. A closed
enum (`Event` in `logs.py` is the house precedent, and exists for this reason)
or a ledgering requirement would change that. **Product, because the
alternative to a closed enum is a workflow where the operator types a reason —
and someone has to decide whether a person in crisis should be asked to.**

**P-3 · Is a build failure the right instrument for an unclassified field in a
matter pack a *user* can add?** I-11 says build failure, and the corpus
enforces it hard. Right for shipped schemas. Different question for a matter
type a user or clinic defines later (the deferred D2 case): a build failure is
not available to them, and the fallback — "reads `L5` and is not served" —
means their new field silently shows nothing with no explanation. **Decide now
whether user-defined fields are in scope, because "fail the build" and "fail
the user" are different products.**

## 7 · What I could not verify

- **That the corpus lands red.** It did not — §1. Satisfiability plus 29/29
  mutation kills are what I have instead.
- **The `classify_schema` return shape.** Not in the contract. The positive
  tests probe five plausible field-spec spellings and fail loudly if none is
  accepted rather than passing vacuously; `_rung_from` reads several return
  shapes and calls `pytest.fail` on one it cannot read. A failure there is a
  shape disagreement — the fix is to add the real spelling to `_spellings`,
  **not** to relax the negative tests around it, which are not shape-tolerant.
- **Trust tiers and the ledger** (§4.3) — outside this signature entirely.
- **I-32 and I-33** are Phase 4 surface behaviour. The corpus does assert no
  clock is read in `rungs.py`/`surfaces.py`; if a real expiry timer later
  lands in `surfaces.py`, `test_no_clock_is_read_inside_the_phase_2_source`
  fails and its docstring explains the scope so it can be narrowed
  deliberately rather than deleted.
- **I-15** is enforced by `logs.py`'s closed `Event` enum and tested in
  `test_invariants_logs.py`. The rung half — `L3`/`L4` never reaching S2 as a
  payload — is covered here; the log half is not this file's.
- **That no other module bypasses `may_render`.** That is I-16, needing a
  call-site scan over a surface layer that does not exist until Phase 4.
  Nothing in Phase 2 can tell you the chokepoint is the only door.

---

## Verification (orchestrator, 2026-08-05)

The §1 disclosure was checked against the agent's own transcript rather than
accepted on report:

- `git worktree list` in `/workspace/homestead` returns **one** checkout. The
  `isolation: worktree` request produced no separate worktree. The agent is
  right and the orchestrator's claim of a filesystem boundary was false.
- The only `Read` calls in the whole run were `homestead-rungs.md` and
  `homestead-law-build-plan.md`. Everything else came through `git show HEAD:`
  — the **committed** `rungs.py`, not the working-tree copy the implementation
  agent was editing.
- No tool call anywhere in the run opened `homestead/keep/surfaces.py`,
  `tests/test_invariants_surfaces.py`, or `tests/test_invariants_pending.py`.
  The single `surfaces.py` it wrote is its own labelled mock under
  `scratchpad/phase2_corpus/dryrun/`.
- **Ordering holds.** Every write/edit of `test_surfaces_corpus.py` occurs at
  transcript lines 63, 66, 68, 93 and 95; the first run against the real
  implementation is at line 123. There are no edits after it. The corpus was
  frozen before it ever met the code.

The independence of this corpus rests on the agent's discipline, which is
verified, and not on the mechanism it was promised, which did not exist.
