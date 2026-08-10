# The export act, and where the head anchor lives

Bite 5 of `docs/PLAN-first-runnable.md` — *wire the logs, and the ledger with
them.* The mechanism (`keep/logs.py`) was built and connected to nothing; this
bite decides **what gets written** and **where the head that vouches for it is
kept**. Two decisions, each recorded here with its reason so the next seat does
not re-open it without addressing the reason.

## 1 · What "an export" is

There is no network egress on this face (I-17, S4, I-30 — nothing binds or
dials). So an export is not a socket. It is **the operator taking their own
record out** — a written artifact, on their own machine, for a reason they
state. That is exactly the S4 spec row: *"explicit act + purpose + ledgered."*

`keep/export.py` is that act, as a library function and not a UI:

* It is gated through `serve(item, Surface.S4_EGRESS, purpose=…)` — the one
  door (I-16). It reaches no payload of its own; it receives `Served.value`
  already scored, like every other consumer. The chokepoint scan
  (`tests/test_invariants_chokepoint.py`) holds that, and `export.py` passes it.
* It **requires a declared purpose.** At the gate, `purpose=None` is not an
  error — it is the ordinary read with the plain ceiling. An *export* is not an
  ordinary read: it is by definition an explicit, purposeful act, so `None` is
  refused **here**, at the export layer, with `ExportRefused`. This narrows the
  gate's rule for one act rather than changing it; a malformed (non-`None`,
  non-member) purpose still raises `UndeclaredPurpose` from the gate itself.
* It writes **exactly one** `IntegrityLog` entry — the provable record — naming
  the declared `Purpose`, the reference, the rung and the disposition. **No
  record content.** It is a reference (I-15): `matter / item_type / item_id /
  purpose / rung / disposition`, never the payload or the derived form.
* It writes **one** `VisibleLog` entry — `Event.EXPORTED` (a closed enum member,
  R-7: no free-text field to leak through) and a reference tuple. No content.
* The **artifact** — the record actually leaving — is written to
  `paths.exports_dir()`. That file carries the content, because that is what an
  export *is*; the two logs do not. Content leaves in the artifact and nowhere
  near a log.
* Nothing crosses at `L5`: `serve()` returns `DENY`, and the act refuses
  (`ExportRefused`) **before** it writes to either log. A refused export is not
  ledgered as an export — there was no export.

`Event.EXPORTED` had a name and no writer (the plan's own words). It has one now.
This does **not** build `homestead.keep.egress` — the *network* send that I-17's
pending test (`test_i17_no_egress_without_an_explicit_per_call_act`) still holds
open. An export-to-file and a network `send()` are two acts on the same surface;
the first is built here, the second stays pending and `send()` stays
`PermissionError` by default. That is the smallest surface that wires the ledger,
which is what the bite asked for.

## 2 · Where the head anchor lives — the willow-mcp #280 argument

`IntegrityLog`'s only real closure against an adversary is
`verify(expected_head=…)` with a head the operator recorded **off the machine**.
The on-file chain plus an on-machine anchor detects *accident* — truncation, a
tail rewrite — not someone who edits both. The module docstring says this
plainly (F-5: a shared OS account is not securable by an application), and this
decision does not pretend otherwise.

What #280 is actually about is narrower and achievable: **do not store the head
next to the thing it vouches for.** If the anchor sits in the same directory as
the log, then whatever clears that directory clears the evidence *and* its
witness in one stroke, and the truncation verifies clean. So the export ledger's
anchor lives in **`paths.anchors_dir()`** — a tree separate from both
`paths.logs_dir()` (where the chain is) and `paths.exports_dir()` (where the
export writes). Truncating the logs, or wiping the export tree, no longer takes
the anchor with it; `verify()` catches it.

This is **not** a claim that the app cannot reach the anchor. On a single-account
machine there is no such location, and claiming one would be the theatre the
bites-1-3 audit exists to catch. The honest statement is: the anchor is
*independent of the storage it vouches for*, and the real closure is the
off-machine head. To make that operational, `export_record()` **returns the
head** in its receipt, so the operator has the one value worth writing down
somewhere this machine cannot reach. #280's mistake was having nowhere to put it;
here the receipt is that place.

`IntegrityLog.__init__` gained an optional `anchor_path` for this — backward
compatible: with no argument the anchor is still `path.with_suffix(".head")`
beside the log, so every existing caller and test is unchanged. `export.ledger()`
is the one place that relocates it.

## What this bite deliberately does not do

* **Encrypt the ledger.** Phase 4, on `IntegrityLog`'s own record. Unchanged.
* **Build the network `send()`.** Stays pending under I-17.
* **Render the integrity log.** It never has a `read()`; the visible log is the
  operator's window, and it carries references only.
* **Promote anything out of `test_invariants_pending.py`.** No module in the
  `UNBUILT` set was built — `homestead.keep.export` is new and was never listed.
  `test_pending_liveness` stays green.
