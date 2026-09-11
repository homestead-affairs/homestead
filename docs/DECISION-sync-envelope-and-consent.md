# The sync envelope, and why its consent is per call — decision brief

Status: **Proposed.** `keep/sync.py` and `keep/household.py` are built,
`tests/test_invariants_sync.py` is green, and I-37/I-38/I-40 are promoted
out of `tests/test_invariants_pending.py`, unmarked — but nothing here is
ratified. `verified_by:` is left blank for the audit seat, per this repo's
rule that the proposing hand does not grade its own work.

author: the build seat
verified_by:

This is `E4-sync-core` (Wave 4, decision 5 of the affairs build plan). It
follows `docs/DECISION-purpose-sync.md`'s own promise: that brief added
`Purpose.SYNC` as "a word with no sentence" and named this module as the one
that would write it. This is that sentence.

## The envelope

`compose(readers, scope) -> Envelope` scores every candidate record on
`S4_EGRESS` under `Purpose.SYNC`, exactly as `keep/export.py` scores one for
`Purpose.EXPORT`, and freezes what survives:

```json
{"schema":"homestead.sync/1","household":"hh-…","composed_at":"…",
 "head":"<pre-sync IntegrityLog head>","scope":{...},
 "rows":[{"table":"sidecar","matter":"custody","item_type":"deadline",
          "item_id":"primary.hearing","rung":"L1","disposition":"render",
          "value":"2026-10-06","derived":null}],
 "count":1,"envelope_id":"<sha256 of the above, envelope_id excluded>"}
```

`envelope_id` is a hash of the canonical JSON (sorted keys, no whitespace)
of every other field. `to_bytes()`/`from_bytes()` round-trip that same
encoding; `from_bytes()` recomputes the id and refuses a mismatch by name
(`TamperedEnvelope`) rather than trusting a byte that was tampered with, on
disk or in transit. The envelope is the only thing `deliver()` ever sends —
never the live store, never a second serialization of it.

## Why a row above the ceiling is dropped, not derived (open item 5)

`SyncScope.ceiling` bounds a row *on top of* whatever `S4_EGRESS` itself
permits under a declared purpose. That second bound is doing real work: the
surface's own with-purpose ceiling is `L4` (`_CEILING[S4_EGRESS] == (L2,
L4)`, unmoved by `SYNC` — measured in `docs/DECISION-purpose-sync.md`), the
highest rung below `L5`, so `S4_EGRESS` never returns `derive` for a
declared purpose at all — every rung it does not deny, it renders in full.
Without `scope.ceiling`, an operator syncing "just the deadlines" would get
every deadline up to `L4`, in full, whether they meant to or not.

`scope.ceiling` is that missing dial. A row whose rung sits above it is
**dropped from the envelope entirely** rather than downgraded to its
derived stand-in. Deriving it instead would still be a decision about *this*
record made by the scope rather than by the classification that owns it —
`Classified.derived` already says what stands in for a datum when the gate
itself withholds the payload (I-35's re-identification judgement, made once,
at classification time); a second, scope-shaped judgement about the same
datum would be a second opinion nothing here is positioned to have. Dropping
leaves that judgement where it belongs and gives the operator an honest
count: what left, not what left disguised.

`compose()` documents which `_CEILING` cell an operator should read before
setting a ceiling above `L2`: an `L4` `SyncScope` renders `L4` data in full,
because the surface already would. `tests/test_invariants_sync.py::
test_an_l4_row_under_an_l4_ceiling_is_rendered` pins the cell so this brief
goes stale loudly if a future ratification ever moves it.

## Why `deliver()` confirms per call, not per grant

Decision 5: *sync is an operator act, never background.* `deliver()` never
remembers a prior confirmation and never reads an ambient flag — every call
shows a `Wire` and asks. Two destinations, two shapes of the same rule:

- **`url`** goes through `egress.send`, which already refuses with no
  confirmation and shows the exact bytes that would leave. Reusing it rather
  than re-deciding the same question is `docs/PLAN-affairs-face.md`'s own
  instruction — the sync act inherits `EgressRefused` verbatim.
- **`drop_dir`** is shown a `Wire(method="FILE", url=<path>, body=<byte
  count>)` — the destination and the size, never a row. The envelope's
  content was already composed and is the caller's to have inspected before
  calling `deliver`; this confirm asks whether to write it, not what is in
  it, which is why it differs from the network leg's full-content preview:
  a file drop's content was fixed at compose time and is already on this
  machine, while `egress.send`'s preview is the only place a network
  payload is ever shown before it leaves.

A refused or missing confirm raises `EgressRefused` before either log is
touched (I-37). An envelope already present in the `IntegrityLog` is refused
with `AlreadyDelivered` *before* a confirm is even shown (I-38 — "ledgered
once"); the file leg's `O_EXCL` create is the structural backstop if two
calls race past that check.

## The household id, shared per OS account (F-5, open item 6)

`household.household_id()` mints `hh-<16 hex>` once, under `paths.home()`,
with an exclusive create — a losing second creator reads the winner's id
back rather than overwriting it (I-9's shape). It refuses a malformed file
by name rather than regenerating one (I-11): a fresh id would fork the
household's identity against a fleet store that already has rows keyed by
the original.

It is **not** one id per person. `paths.home()` is one root per
`$HOMESTEAD_HOME`, or one per OS user when unset — not one per person
typing at the keyboard. Two people sharing an account share one household
id, exactly as they already share one `IntegrityLog` and one export tree.
This is accepted, not fixed, for the reason `keep/logs.py`'s own docstring
already gives for the same shape: a shared OS account has no wall an
application can build, and a second file a determined sharer can also read
would not be a real wall either.

## I-37 / I-38 / I-40, promoted

Provisional since `tests/test_invariants_pending.py`'s 2026-09-11 reseed
(`E1-pending`), now built and tested in `tests/test_invariants_sync.py`:

- **I-37** — sync is an operator-authored act; a refused confirm ledgers
  nothing.
- **I-38** — an envelope is ledgered once, with references only.
- **I-40** — an unnamed scope syncs nothing; there is no `"all"` matter.

## What this deliberately does not include

- **No fleet adapter, no ingest.** `store.PostgresAdapter` and
  `keep/fleet_cli.py` are `E4-postgres-fleet`, which depends on this bite.
- **No `HOMESTEAD_FLEET_URL`.** Reading a destination from the environment
  inside the function that ledgers the act would make the destination
  ambient; Wave 5's module CLI takes it as a plain argument. A destination
  is a place to send to, never a permission to send.
- **No ranking of `Purpose.SYNC` against other members**, and no new
  `_CEILING` cell — `docs/DECISION-purpose-sync.md` measured zero cells
  move, and this bite does not reopen that.
