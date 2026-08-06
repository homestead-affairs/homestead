# Getting to something you can actually use

Status: **A plan, not a commitment.** Nothing here is built. Bite sizes are
estimates; every "done when" is a check somebody can run rather than a feeling.

The question this answers: what stands between today and *the operator can open
the app, put a custody matter in it, and see it behave correctly* — and,
separately, what stands between that and *somebody else can test it*. Those are
different questions with different blockers, and only the first is engineering.

---

## What exists today, measured

The engine is real and unusually well verified: **1704 passed / 6 xfailed**,
adversarial corpora written by hands that did not read the implementation, and a
mutation harness. Five modules under `homestead/keep/`:

| module | what it gives | callers outside itself + tests |
|---|---|---|
| `rungs` | the gate: `may_render`, `decide`, `serve`, `serve_all`, `ambient_rows`, `Classified`, `classify_schema` | **none** |
| `surfaces` | `Surface`, `SurfaceFacts`, `facts` | `rungs` only |
| `paths` | `home`, `app_data`, `matter_dir`, `record_dir`, `drafts_dir`, `logs_dir`, `ensure` | **none** |
| `logs` | `VisibleLog` (closed `Event` enum), `IntegrityLog` (append-only, hash-chained, off-file head anchor) | **none** |
| `dates` | `parse_deadline`, `Deadline`, `court_days` | **none** |

And `homestead/app/__main__.py`: a Phase 0 cover screen that opens a window
saying *"Nothing is open."* Grepping the package for `tkinter`, `sqlite`,
`argparse` or a second `main` hits that one file.

**So the shape of the gap is not "the safety model is unbuilt."** It is that
every piece is built, tested, and connected to nothing. There is no store, no
schema, and no surface that calls `serve()`. `rungs.py` says this about itself
and it is the most important sentence for planning:

> A gate wired to one entry point is not a gate, and at Phase 2 it is wired to
> none.

## A correction owed on this morning's finding

`docs/FINDING-the-ledger-exists.md` says the ledger this repo defers to is built,
in Nestor. True, and **incomplete in a way that matters here: this repo has one
too.** `logs.IntegrityLog` is *"append-only and hash-chained, with an off-file
head anchor"* — `head()`, `append()`, `verify(expected_head)`. That is the same
mechanism as Nestor's, including the off-file anchor that willow-mcp #280 turned
out to be missing.

So "the ledger is Phase 3+ and unbuilt", which every decision brief in this
series leaned on, was wrong twice over. What does not exist is **anything calling
it**. `Event` already has an `EXPORTED` member — the egress event has a name and
no writer.

That shrinks the ledger work from a phase to a bite, and it moves the
"other people can test it" gate much closer than the briefs assumed. The finding
should be annotated rather than rewritten; it was right about Nestor and wrong
only in stopping there.

---

## The bites, in order

Each is independently landable, and each has a check rather than a claim. The
order is chosen so the gate is wired *before* there is much to render — the
opposite order ships the failure once and then retrofits.

### 1 · The store — records survive a restart

The smallest thing that persists a `Classified` and gives it back. `paths` already
decides where it goes (`matter_dir`, `record_dir`, `ensure`); nothing decides how.

The rung travels **with** the datum or the whole model is decorative on reload —
a store that returns a payload without its rung has silently declassified it, and
`compose` is `max` precisely so aggregation can never lower one.

*Done when:* a record written, the process exited, the record read back with the
same rung; and a stored row with a missing or unreadable rung reads `L5` on the
way out (I-11 at the storage boundary, not just at the gate).

### 2 · The custody pack, and `classify_schema` called for the first time

One pack, custody only — three prove nothing that one does not. Fields with
declared rungs, loaded through `classify_schema` **at import**, so an
unclassified field is a build failure rather than a runtime surprise.

This is the bite that retires the criticism in
`DECISION-unclassified-field-instrument.md`: today the refusal is a lock on an
empty room, and Phase 3's amended exit says the room must have something in it.

*Done when:* the pack imports, `classify_schema` accepts it, and deleting one
field's rung fails the build with that field named.

**Prior art for the half `classify_schema` cannot do — see below.** It checks
that a rung was *declared*, not that it was declared *well*, and there is a
sixty-nine-line PII matcher in `willow-2.0` already aimed at the same categories
this ladder cares about. Advisory only, and it belongs to this bite rather than
to a later one, because the moment a pack exists is the moment a wrong rung in it
becomes possible.

### 3 · The chokepoint — one door, and it is hard to walk past

I-16 wants one authorization point covering every surface. `serve()` and
`ambient_rows()` are the *shape* of one; nothing compels a caller to use them.

Make `Classified.payload` awkward to reach and `serve()` the obvious path, then
hold it with a test that greps the surface layer for direct `.payload` access —
the same trick the corpus already uses to hold `_declared` honest.

*Done when:* every read of a record in `homestead/app/` goes through `serve` or
`ambient_rows`, and a test fails if a new one doesn't.

### 4 · The two S1 surfaces — a list you can see and an item you can open

`ambient_rows` for the list (a rung and a line of text, no third field), `serve`
with `S1_DETAIL` for the pane. Opening the pane **is** the purpose declaration —
that was decided 2026-08-04, by widget rather than dialog, so there is no
ceremony to build.

The resting state stays a cover: I-21 says the record is not drawn before a human
asks, and the Phase 0 file already gets that right.

*Done when:* a custody matter with an `L1`, an `L3` and an `L4` field renders —
list shows the derived form for what it may not carry, detail shows the `L4`
payload, and no `L5` appears anywhere in either.

### 5 · Wire the logs — and the ledger with them

`VisibleLog` on the operator-visible acts (its `Event` enum is already closed, so
there is no free-text field to leak through — that was R-7). `IntegrityLog` on
the acts that need to be provable, starting with `EXPORTED`.

Small, because the mechanism exists. The work is deciding *what* gets written and
holding the head anchor somewhere the app cannot reach — which is exactly the
argument made to willow-mcp in #280, applied here before there is anything to
regret.

*Done when:* an export writes one `IntegrityLog` entry naming the purpose
declared, `verify(expected_head)` catches a hand-edited entry, and the visible
log shows the act with no record content in it.

---

## Prior art, searched — and one lead worth taking

Rule 11 of the store's `CLAUDE.md`: search before writing, and record what the
search found so the next seat does not pay for it twice. This is that record,
including the negative result, which is the more useful half.

### The journal app in `willow-1.9` / `willow-2.0` — not reusable, and the reason is load-bearing

`willow-2.0` has a personal journal: a `journal_entries` Postgres table
(`migrations/20260524_journal_entries.sql`), `agents/hanuman/bin/journal_watcher.py`
polling it for a `::saga` tag, and `journal_responder.py` sending the entry to a
model and storing replies in JSONB. `willow-1.9` has no journal.

Architecturally incompatible on the obvious axis — Postgres, a daemon, and a poll
loop, against an app whose plan says *"no TUI, no HTTP, no listening socket"* and
a store whose whole premise is no ports and no servers.

But the disqualifying part is the responder, not the database. **It sends private
entry content to a model.** That is the precise shape `S2_PROMPT` exists to
refuse: capped at `L2`, nothing lifts it, on the stated reasoning that *if a local
model needs the diagnosis to do its job, that is a signal the job is wrong*. F-3
and F-4 were private note content reaching a prompt by a route nobody designed.
Porting the responder would re-import the bug this entire ladder was built after.

Recorded rather than left as a hunch, so nobody re-derives "could we lift the
journal?" and reaches the same no more slowly.

### `willow-2.0/apps/nest/pipeline/scrub.py` — **worth taking, as an advisory**

Sixty-nine lines of pattern-based PII detection: SSN, EIN, phone, credit card,
account number, DOB, email, routing number, case number. Its own docstring already
takes the right stance — *"Flags matches in the store record — does NOT modify the
original file. Scrub is informational: it tells you what's there so you can decide
what to do with it."*

Its categories line up with this ladder's, which is not a coincidence — it is the
same problem approached from the file end. `ssn` is `L5` in this corpus. A case
number is `L3` in a family matter and explicitly **not** `L1`. A DOB is `L4`,
identifying a minor. Account and routing numbers sit in `L4` territory.

**Where it fits: as a check on a declared rung, never as a classifier.** The spec
puts classification on a human who knows the matter type and jurisdiction, and
`classify_schema`'s docstring says plainly that it will *"accept `L1` for a sealed
family case number without a murmur."* That is the named gap. A matcher cannot
close it — it cannot know the matter — but it can say *this field is declared `L1`
and its content is shaped like an SSN*, which is exactly the class of error the
gap admits.

Three conditions, without which it should not be taken:

1. **It may only prompt to raise a rung, never to lower one.** `compose` is `max`
   for the same reason; a tool that can argue a datum down is a declassifier, and
   there is deliberately no function that declassifies.
2. **Advisory, never a gate.** A regex that blocks a save has quietly relocated a
   human judgement into a pattern list.
3. **Its false negatives are the dangerous direction**, so nothing it produces may
   render as "clean" — absence of a match is not evidence of absence, and I-11's
   whole posture is that absence fails closed.

### Weaker, checked and set aside

`apps/nest/router.py` splits `propose` from `route_file`, which mirrors
propose-don't-ratify — but that convention is already load-bearing here and needs
no import. The `archive`/`compost` pipeline is superseded: `safe-app-store` already
specifies tombstones carrying a forwarding pointer, which is further along than
what is in `nest`. And `store_bridge.py` is a SOIL wrapper, so bite 1 still gets
written against `paths.matter_dir` rather than lifted.

---

## What this plan deliberately does not include

- **The MCP stdio entry.** The plan puts the app first, both thin over the core.
  S3's purpose column is closed, so an agent surface built later inherits a
  narrower gate than it would have this morning — which is the right order.
- **Bankruptcy and workers' comp packs.** Phase 5. If either needs a change
  outside its own pack, the seam was wrong; that is what the second pack is for
  and it is not a reason to build it now.
- **Encryption at rest.** Scheduled for Phase 4 on `IntegrityLog`'s own record.
  It is not on the path to *you* testing this; it is on the path below.
- **Anything that makes this look like legal advice.** *"No forms-and-instructions
  product, at any version"* is standing.

## Before somebody else tests it

Engineering is not the blocker here, and it is worth separating the two so the UI
feeling finished doesn't get mistaken for readiness.

**Synthetic data only, until bite 5 lands.** The moment a second person uses this
they either enter their own real matter — custody, substance use, protective
orders, the `L4`/`L5` material the whole model is about — or they don't. Before
the ledger is wired there is no answer to *"what did this do with my records?"*,
and that is a question a person in a custody dispute is entitled to ask first.

**Two gates on this repo's own record, neither of them mine to clear.** The build
plan says *"Counsel precedes any D2 deployment"*, and D-6 records that the legal
posture is a **separate, named, outstanding item that promotion does not cover
and must not appear to** — the engineering gates check tests, imports, seams and
leaks, and check nothing about UPL. A green suite is not a green light, and the
record already says so in as many words.

**One open decision is on the path.** Whether a household operator may extend a
shipped pack — not the deferred D2 clinic case, and unanswered anywhere. Bite 2
is where it becomes concrete: if yes, an operator-added field needs a default
rung, and the argument for `L4` is that it is the highest rung still serveable to
its own owner (visible in the detail pane, never on a prompt, never to an agent,
out on egress only with a declared purpose). If no, packs are authored and bite 2
is smaller. See `DECISION-unclassified-field-instrument.md`.

---

## What I did not do

- **Built none of it.** This file is the only write.
- **Did not estimate in time.** The bites are ordered and scoped; how long each
  takes depends on who does it.
- **Did not decide the operator-extends-a-pack question**, which bite 2 will force.
- **Did not annotate `FINDING-the-ledger-exists.md`** with the correction above —
  that is a separate edit to a merged document and should be made deliberately.
- **Did not verify the packaging or CI path** for a built artifact; `--smoke`
  exists and is what CI runs, and nothing here changes it.
