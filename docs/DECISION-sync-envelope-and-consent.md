# The sync envelope, and why its consent is per call — decision brief

Status: ~~**Proposed.**~~ **Ratified**, with the amendments recorded below in
§ "Amended by the audit". `keep/sync.py` and `keep/household.py` are built,
`tests/test_invariants_sync.py` is green, and I-37/I-38/I-40 are promoted
out of `tests/test_invariants_pending.py`, unmarked. The invariant numbers
I-37, I-38 and I-40 are ratified at those numbers (the plan's decision 10).

author: the build seat
verified_by: E4-sync-core audit, 2026-09-11

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
- **`drop_dir`** — an **absolute** directory the caller names — is shown a
  `Wire(method="FILE", url=<path>, body=<byte count>)`: the destination and
  the size, never a row. The envelope's
  content was already composed and is the caller's to have inspected before
  calling `deliver`; this confirm asks whether to write it, not what is in
  it, which is why it differs from the network leg's full-content preview:
  a file drop's content was fixed at compose time and is already on this
  machine, while `egress.send`'s preview is the only place a network
  payload is ever shown before it leaves.

A confirm must return **`True`**. Truthiness is not consent: the confirm a
Wave 5 CLI most naturally writes is `lambda w: input("send? [y/N] ")`, and
that returns `"n"` for *no*, which is truthy. `deliver()` normalises its own
confirm to `is True` on both legs — a pass-through wrapper, so the confirm is
still shown once and only once, by `egress.send` on the URL leg and by
`deliver` on the file leg. `keep/egress.py`'s own truthy contract is I-17's
and is left alone; a caller that wants the stricter rule gets it from here.

A refused or missing confirm raises `EgressRefused` before either log is
touched, before the destination directory is created, and before anything is
written (I-37). An envelope already present in the `IntegrityLog` is refused
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

## The crash window (ruled by the audit, 2026-09-11)

`deliver()` writes in this order, and `tests/test_invariants_sync.py::
test_the_write_order_is_destination_then_integrity_then_visible` pins it:

1. the destination — the `O_EXCL` file, or `egress.send`;
2. one `IntegrityLog` row;
3. one `VisibleLog` row.

A crash between 1 and 2 leaves an envelope **delivered and unledgered**. That
is a real residual and it is accepted rather than closed, for three reasons.

*The other order is a worse lie.* Writing a `pending` row before the send and
finalising after would make the opposite failure possible — a ledger claiming
an act that never left the machine — which is the one thing a log whose whole
job is to prove what left must not do. Given a choice of which way an audit
trail may be wrong, it may be *incomplete*, never *inventive*.

*It would also cost the shape I-38 pins.* `IntegrityLog` is append-only: a
pending row cannot be amended, only followed by a second row. I-38's promoted
test asserts **one** entry per delivered envelope, and `Event` is a closed
enum — a new act kind is not a thing to add to close a window this narrow.

*Both legs already narrow it.* On the file leg the `O_EXCL` create is the
structural backstop: a retry of the same envelope finds `<envelope_id>.json`
already there and raises `AlreadyDelivered` rather than dropping it twice
(pinned by the same test). On the URL leg a retry does re-send, and the
duplicate is caught on the far side — `E4-postgres-fleet`'s ingest refuses a
re-ingested `envelope_id`, which is the same content-addressing doing the
work at the other end.

A crash between 2 and 3 loses the `VisibleLog` line only; the provable log has
the act, and a retry is correctly refused as already ledgered.

## Amended by the audit, 2026-09-11

Each of these reproduces something the built module did; each has a test that
fails against the pre-audit file.

1. **Envelope rows are sorted** by `(table, matter, item_type, item_id)`.
   They were in store-iteration order, and that is not one order:
   `FileAdapter` sorts `<item_id>.json` filenames while `SQLiteAdapter` sorts
   `item_id` columns, so ids holding a `.` or a `-` came back differently and
   one store composed through two backings produced two `envelope_id`s for
   identical rows — with `AlreadyDelivered` unable to see the second was the
   first. `scope` order is deliberately *not* sorted: it is what the operator
   named, in the order they named it, and it is consent rather than data.
2. **`from_bytes()` checks the shape, not only the hash.** A matching id
   proves the bytes were not edited after composition; it proves nothing about
   whether they were ever an envelope, because an id computed over rubbish
   matches its rubbish. Forgeries carrying a correct sha256 and `count=99`
   over one row, `schema="homestead.sync/99"`, and `rows` as an object rather
   than an array were all accepted — the last silently becoming a one-tuple of
   a dict *key*. Each is now refused by name. Key order and whitespace are
   still accepted, and must be: `from_bytes` verifies the canonical form, not
   the wire bytes, which is what lets `egress.send`'s own serialization (same
   sorting, different separators) round-trip through it.
3. **`confirm` must return `True`** — see above.
4. **A relative `drop_dir` is refused by name.** `paths.ensure` resolves a
   relative path against `paths.home()` and `open()` resolves it against the
   process's cwd, so a relative `drop_dir` created one directory and wrote
   into another — or into nothing. The `destination` the ledger records is the
   record of where an envelope went; only an absolute path is that in every
   cwd. A drop *outside* `paths.home()` stays refused by `paths.ensure`'s own
   containment rule: this bite inherits that rule rather than widening it, and
   a sync to removable media is a deliberate widening for someone else to
   propose, not a side effect of a `drop_dir=` argument.
5. **`default_drop_dir()`** is `exports_dir()/sync/` — the path the plan names,
   now a function a caller can ask for rather than a default `deliver()`
   applies. The docstring claimed `drop_dir` defaulted to it, and the branch
   that would have done so was unreachable behind the exactly-one-destination
   guard. A destination that appears because none was given is a destination
   the confirm did not choose and the operator never named.
6. **A refused confirm creates nothing**, the directory included.
7. **An unreadable `IntegrityLog` line refuses by name.** `_already_delivered`
   let a `JSONDecodeError` out of `deliver`; a log that cannot be read cannot
   be shown not to hold this envelope already, so the act does not happen
   (I-11). The message names the line number, never the line.

## Residuals recorded, not fixed

- **File modes.** The drop is `0644` and its directory `0755`, which is what
  `paths.ensure`'s `mkdir` and an `open(..., "x")` give everywhere in this
  repo — `keep/export.py`'s artifact, the store, the logs. The envelope is the
  most concentrated of those, but a lone `0600` here would suggest a tree that
  is protected when the record it was composed from sits at `0644` beside it.
  A mode posture is a repo-wide bite, and this one does not start it halfway.
  `household.id` is `0644` for the same reason: it is a pseudonymous handle,
  and F-5 already says a shared OS account has no wall an application builds.
- **`compose()` on a corrupt ledger.** It reads the pre-sync head through
  `IntegrityLog.head()`, which raises on a half-written final line. That is
  `keep/logs.py`'s contract, shared with `keep/export.py`, and is not
  redefined from here.
- **The wire asymmetry is deliberate and is the ruling.** The URL leg's
  confirm is shown the whole envelope, because `egress.send`'s preview is the
  only place a network payload is ever seen before it leaves. The file leg's
  is shown a path and a byte count, because the bytes are already on this
  machine, were fixed at compose time, and the question being asked is
  *whether to write them*, not *what is in them*. A caller that wants to show
  the content has `Envelope.to_bytes()` and owes the operator nothing this
  function can compel.
