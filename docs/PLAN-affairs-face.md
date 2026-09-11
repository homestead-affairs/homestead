# The affairs build-out — this repo's copy (Wave 7, X7-drift-engine)

Status: **A partial copy, engine bites only, struck through as they land.**
The full plan — households, all three modules, all eight waves — lives at
`/root/.claude/plans/so-lets-plan-it-sparkling-shell.md`
("Homestead · Affairs — full build-out of law and ledger for one real
household"), a file this repo does not have and is not the place to vendor
whole: `homestead-law`, `homestead-ledger` and `homestead-health` are
separate checkouts this bite cannot read, and copying their bites here would
let two copies of "is L2b-instances landed" drift apart, which is the exact
failure this document's own guard exists to prevent. What follows is the
subset this repo *can* verify from its own git history — every engine bite
(Wave 1's `E1-*`, Wave 4's `E4-*`, Wave 5's `E5-integrity-keyed`, Wave 6's
`E6-integrity-encrypt`, Wave 7's `E7-public-log-reader` and
`E7b-fleet-structured-values`) and the release checkpoints (`ORCH-R1..R4`) —
struck through with the PR that landed it and the release that shipped it,
both read off `git log`, never asserted from memory. Module bites (`W0-*`,
`L*`, `G*`, `H*`, `ORCH-0/2/8`, all of Wave 8) are named where the plan names
them, for orientation, and are **not struck here**: this repo cannot see
whether they landed, and a strike this repo could not verify would be worse
than no mark at all.

`docs/PHASE1-DATES.md`, `docs/DECISION-purpose-sync.md` and this repo's other
`DECISION-`/`PHASE`-prefixed documents already hold the detailed, dated
record of *how* each engine bite landed — what it changed, what an audit
found, what got corrected. This document's job is narrower and different:
one line of "landed or not, and where," so a reader (or the orchestrator's
own dry run of the Wave 7 meta-scan) can answer "is E5 in yet?" without
reading nine files.

---

## What actually happened to the release cadence, first

The plan's own text (§ *Orchestrator runbook*) describes four batched release
checkpoints — **R1** after Wave 1, **R2** after Wave 4, **R3** after Wave 5,
**R4** after Wave 6. That is not what this repo's `git log` shows. Every
engine bite that landed cut its own release — ten releases, `0.3.0` through
`0.12.0`, one per merged feature PR — `0.12.0` shipped behind
`E7-public-log-reader` (PR #68) the same day this document was written, after
this bite's own worktree fast-forwarded onto it (`origin/main` moved by the
release-please merge alone, no competing code — `git diff --stat` confirmed
only `CHANGELOG.md` and `.release-please-manifest.json` changed). Two
consequences worth stating plainly rather than papering over by force-fitting
the batching the plan described:

* **`ORCH-R1`'s own text — "merge (dates-b after dates-a, retarget base);
  release 0.3.0" — did not happen in that order.** `0.3.0` shipped after
  `E1-hygiene` and `E1-pack-contract` only; `E1-dates-a` and `E1-dates-b`
  landed two and three releases later (`0.5.0`, `0.6.0`). Module bites
  pinning `>=0.3.0` for Wave 2 would have been pinning a floor that did not
  yet carry the dates rule table the plan's own Wave 3 law bites need — a
  real sequencing gap, not a paperwork one, if any module bite actually
  floored on `0.3.0` expecting `court_days_before`/`add_mail_days` to exist.
  Not this repo's finding to chase into the module checkouts, so it is
  recorded here rather than silently smoothed over by striking `ORCH-R1` as
  if the plan's sequence had been followed.
* **The batched `R2`/`R3`/`R4` checkpoints are struck below against the
  release that is closest in spirit** (the one shipping the last bite of
  that wave, per this repo's history), not against a release-please tag
  literally named `R2`. Release-please cuts a version per qualifying commit
  type, not per wave, so "the Wave 4 release" is this document's own
  reading of the log, not a tag anyone chose.

| release | PR | shipped |
|---|---|---|
| 0.3.0 | [#49](https://github.com/homestead-affairs/homestead/pull/49) | `E1-hygiene` (#47), `E1-pack-contract` (#48) |
| 0.4.0 | [#52](https://github.com/homestead-affairs/homestead/pull/52) | `E1-pending` (#50), `E1-purpose-sync` (#51) |
| 0.5.0 | [#55](https://github.com/homestead-affairs/homestead/pull/55) | `E1-procedure` (#53), `E1-dates-a` (#54) |
| 0.6.0 | [#57](https://github.com/homestead-affairs/homestead/pull/57) | `E1-dates-b` (#56) |
| 0.7.0 | [#59](https://github.com/homestead-affairs/homestead/pull/59) | `E4-cover-distribution` (#58) |
| 0.8.0 | [#61](https://github.com/homestead-affairs/homestead/pull/61) | `E4-sync-core` (#60) |
| 0.9.0 | [#63](https://github.com/homestead-affairs/homestead/pull/63) | `E4-postgres-fleet` (#62) |
| 0.10.0 | [#65](https://github.com/homestead-affairs/homestead/pull/65) | `E5-integrity-keyed` (#64) |
| 0.11.0 | [#67](https://github.com/homestead-affairs/homestead/pull/67) | `E6-integrity-encrypt` (#66) |
| 0.12.0 | [#68](https://github.com/homestead-affairs/homestead/pull/68) | `E7-public-log-reader` |

---

## Wave 1 — engine foundations

- ~~**E1-hygiene** `fix:` — console script `homestead` (drop `homestead-law`);
  registry docstrings + README say custody and bankruptcy are registered;
  `docs/releasing.md` (willow-ci App token, owner `homestead-affairs`; PAT
  struck through); `Event.RECORD_ADDED`.~~ **Landed: PR
  [#47](https://github.com/homestead-affairs/homestead/pull/47), release
  0.3.0.**
- ~~**E1-procedure** `docs:` — `docs/homestead-rungs-procedure.md`, marked
  RECONSTRUCTED, the five steps, the money table, the derived-form rule,
  I-1…I-36 one-liners, I-37+ reserved.~~ **Landed: PR
  [#53](https://github.com/homestead-affairs/homestead/pull/53), release
  0.5.0.**
- ~~**E1-pack-contract** `feat:` — `JURISDICTIONS` tuple and `"derived"` key
  on engine packs; `rungs.derived_of(schema, field)`; `MatterType.
  jurisdictions`; `_validate` requires `JURISDICTION in JURISDICTIONS`
  (plant).~~ **Landed: PR
  [#48](https://github.com/homestead-affairs/homestead/pull/48), release
  0.3.0.**
- ~~**E1-purpose-sync** `feat:` — `Purpose.SYNC`; update the count-named pins
  per `docs/DECISION-compelled-disclosure.md`'s measured list; assert zero
  `_CEILING` cells move; `docs/DECISION-purpose-sync.md` (proposed; audit
  ratifies).~~ **Landed: PR
  [#51](https://github.com/homestead-affairs/homestead/pull/51), release
  0.4.0. Ratified same release — `docs/DECISION-purpose-sync.md`,
  `verified_by: the audit seat, 2026-09-11`.**
- ~~**E1-dates-a** `feat:` — in `keep/dates.py`: `RuleStatus`, `CountingRule`,
  `RULES` with the `US-federal` row; `JURISDICTIONS = tuple(RULES)`;
  `court_days_before` (9006(a)(5), rolls backward), `add_mail_days`
  (9006(f)/6(d)), `business_days`, `court_days(..., district_state=)`
  forward-only.~~ **Landed: PR
  [#54](https://github.com/homestead-affairs/homestead/pull/54), release
  0.5.0.**
- ~~**E1-dates-b** `feat:`, base E1-dates-a — `US-NM` (Rule 1-006 NMRA
  2024-11-01; NMSA 12-2A-7) and `US-OR` (ORCP 10 A/C) with
  `holidays.US(subdiv=…)` calendars cached; NM short/backward/mail branches
  ship UNCERTAIN → refuse.~~ **Landed: PR
  [#56](https://github.com/homestead-affairs/homestead/pull/56), release
  0.6.0.**
- ~~**E1-pending** `test:` — `UNBUILT` seeded with `homestead.keep.sync`,
  `keep.household`, `keep.fleet_cli`, `app.reveal`; pending I-37 (sync needs
  confirm), I-38 (envelope ledgered once, references only), I-39 (fleet
  ingest never listens, lazy psycopg), I-40 (unnamed scope syncs nothing),
  I-32, I-33.~~ **Landed: PR
  [#50](https://github.com/homestead-affairs/homestead/pull/50), release
  0.4.0.** Reseeded live, unmarked, as each named module landed —
  `keep.sync`/`keep.household` (E4-sync-core) and `keep.fleet_cli`
  (E4-postgres-fleet); only `app.reveal` (I-32/I-33) is still in `UNBUILT`
  at the time of this bite.
- ~~**ORCH-R1**: merge (dates-b after dates-a, retarget base); release
  0.3.0; confirm on PyPI.~~ **0.3.0 shipped (PR
  [#49](https://github.com/homestead-affairs/homestead/pull/49)) — but see
  § *What actually happened to the release cadence* above: `dates-a`/
  `dates-b` were not yet merged when it cut.**

## Wave 4 — sync in the engine; fleet; cover distribution

- ~~**E4-sync-core** engine `feat:` — `keep/household.py` (`household.id` →
  `hh-<16 hex>`, O_EXCL); `keep/sync.py`: `SyncScope`, `compose()`,
  `Envelope`, `deliver(envelope, *, confirm, url=None, drop_dir=None)`;
  `docs/DECISION-sync-envelope-and-consent.md`. Promote I-37/38/40.~~
  **Landed: PR [#60](https://github.com/homestead-affairs/homestead/pull/60),
  release 0.8.0.**
- ~~**E4-postgres-fleet** engine `feat:`, depends E4-sync-core — extra
  `fleet = ["psycopg[binary]>=3.1,<4"]`; `store.PostgresAdapter`;
  `keep/fleet_cli.py` `homestead-fleet ingest`.~~ **Landed: PR
  [#62](https://github.com/homestead-affairs/homestead/pull/62), release
  0.9.0.**
- ~~**E4-cover-distribution** engine `feat:` — `cover_counts(matters, *,
  by_matter=None, **counts)`; with a distribution, Gate 2 requires ≥2
  matters each contributing ≥1.~~ **Landed: PR
  [#58](https://github.com/homestead-affairs/homestead/pull/58), release
  0.7.0.**
- **ORCH-R2**: engine release 0.4.0 *(as planned; in practice the last Wave 4
  bite, `E4-postgres-fleet`, shipped as 0.9.0 — see the cadence note above)*.

## Wave 5 — keyed integrity

- ~~**E5-integrity-keyed** engine `feat:` — `IntegrityLog` optional
  HMAC-SHA256 key at `anchors_dir()/integrity.key` (`homestead integrity
  init-key`, O_EXCL, 0600 on POSIX); unkeyed legacy logs still verify; forged
  chain+anchor now fails with a key (plant); `hmac.compare_digest`.~~
  **Landed: PR [#64](https://github.com/homestead-affairs/homestead/pull/64),
  release 0.10.0.**
- **ORCH-R3**: release 0.5.0 *(as planned; in practice `E5-integrity-keyed`
  shipped as 0.10.0)*.

## Wave 6 — Phase 4 sealing

- ~~**E6-integrity-encrypt** engine `feat:`, depends E5 — extra `sealed =
  ["cryptography>=42,<47"]`; `keep/sealed.py` AES-256-GCM per line, key via
  HKDF from `integrity.key`, AAD binds `prev`, 96-bit random nonce;
  `IntegrityLog(sealed=True)`; `verify()` decrypts; without the extra or key:
  refuse, never plaintext fallback; `docs/DECISION-integrity-key-management.md`
  (no escrow; operator keeps the key with the head).~~ **Landed: PR
  [#66](https://github.com/homestead-affairs/homestead/pull/66), release
  0.11.0.**
- **ORCH-R4**: release 0.6.0; modules bump floors *(as planned; in practice
  `E6-integrity-encrypt` shipped as 0.11.0)*.

## Wave 7 — drift and closure sweep

- ~~**E7-public-log-reader** engine `feat:` (proposed by the H6 audit,
  2026-09-11) — `IntegrityLog._entries()` given a public name whose signature
  carries the refusal (`read_entries(*, decrypt=True)`), `_entries()` kept as
  a deprecated alias for one minor, `test_sealed_log_has_no_public_read_
  method` narrowed from "no public reader" to "no public reader that can
  return a short or plaintext-fallback answer."~~ **Landed: PR
  [#68](https://github.com/homestead-affairs/homestead/pull/68), release
  0.12.0. Confirm on PyPI before the next wave's module bites float a floor
  against it.**
- **E7b-fleet-structured-values** engine `feat:` (found by the G5-sync
  audit, 2026-09-11) — the fleet's `canonical`/`sidecar` DDL stores `value`
  as `TEXT`, and `fleet_cli._validate_rows` refuses any row whose served
  value is a mapping (a ledger `transfers` pair is L2 `{counterpart, from,
  to}`); settle the contract as `JSONB` (or canonical-JSON text). **Not
  landed** as of this bite (`ff33787`) — being built concurrently in this
  same worktree's sibling checkout on `claude/fleet-structured-values`
  (`keep/fleet_cli.py`, `keep/store.py`, `docs/DECISION-fleet-ingest.md`),
  which this bite does not touch. Left unstruck.
- **X7-drift-\<repo\>** (this bite, engine leg) — `tests/test_docs_drift.py`,
  `tests/test_scans_fire.py`, the README status table, and this document.
  Not struck here: a document does not mark its own landing before the PR
  that lands it exists.

## Wave 8 — the grant, the accelerator, and the business

Depends on Wave 3 (module bites this repo cannot see) and `G2b`. No engine
bite in this wave — `E8-jurisdictions-de-or-corp` is explicitly optional
("only if a verified rule appears") and no code under `homestead/keep/dates.py`
adds a `US-DE` row as of `ff33787`, so it is unstruck and, per the plan's own
text, may end up a `docs:`-only bite rather than a `feat:` at all.

---

## Module and cross-repo bites — named, not struck

Everything below lives in `homestead-law`, `homestead-ledger`,
`homestead-health`, or is a cross-repo orchestration step (`ORCH-0`,
`ORCH-2`, `ORCH-8`, and the module halves of `ORCH-R1..R4`). This repo's own
git history says nothing about whether they landed, so — per the rule stated
at the top of this document — none of the following is struck by this bite:
`W0-LAW`, `W0-LEDGER`, `W0-HEALTH`; `H2-cap`, `L2a-pack-contract`,
`L2c-second-pack-readiness`, `G2a-account-packs`, `G2c-importer-dates`;
`L2b-instances`, `L3-custody-relocation`, `L3-bankruptcy-ch13`,
`L3-workers-comp`, `L3-deadline-templates`, `G2b-account-instances`,
`G3-cadence-paidby`; `G4-overlay`, `G4-transfers`, `G4-budget`,
`G4-schedules-export`, `L4-surfaces`; `L5-sync`, `G5-sync`; `H6-sealed-reader`;
`H7-floor-0.12`; `L8-grant`, `L8-venture`, `L8-surfaces`, `G8-business-books`.
A reader who has the other three checkouts open can strike these directly
against their own `git log`, the same way this document struck the engine
half.
