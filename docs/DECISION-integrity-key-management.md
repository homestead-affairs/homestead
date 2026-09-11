# The integrity key: no escrow, no server, one file — decision brief

Status: **Proposed.**
author: the build seat
verified_by:

**Proposed here, to be ratified by another hand** — `verified_by ≠ author`, as
with the decision briefs before it. This one recommends a specific, narrow
shape for a key an operator can lose forever; that is exactly the kind of
claim that most needs a second pair of eyes before it ships.

Raised by Wave 5 of `docs/PLAN-affairs-face.md` (decision 6, open item 8):
*"IntegrityLog: keyed HMAC chain first (no dependency), then Phase 4 sealing
behind extra `sealed`"* and *"Integrity key loss = ledger unreadable once
sealed → keying first, sealing second, no escrow."* This bite is the first
half. `homestead/keep/logs.py`'s own docstring names the gap this closes: an
on-machine anchor "detects accident, not an adversary" because a forged chain
plus a matching anchor, both written by the same hand that can reach
everything on this machine, verifies clean.

## 1 · What the key changes, and what it does not

`IntegrityLog.verify()` walks the chain and checks it against a head anchor.
Unkeyed, both the per-line hash (`line_hash`) and the anchor are plain
SHA-256 over plaintext at a predictable path — nothing but read access is
needed to recompute either, so an attacker who can rewrite the log can also
rewrite the anchor to match, and `verify()` reports a clean chain over a
forged one. That is the pre-existing, documented threat model, and it does
not go away for a log that never opts in.

For a log that does: `IntegrityLog` gains an optional 32-byte key, and both
the line hash and the anchor become `hmac.new(key, ..., sha256)` instead of a
bare digest. Forging a consistent chain now requires the key file, which does
**not** live next to the log or the anchor it seals — see §3. An attacker who
can edit the log and the anchor still cannot produce a matching HMAC without
also reading the key. This closes exactly the gap the module docstring names;
it does not:

* **make the log unreadable.** Content is still plaintext JSON lines. Sealing
  that (AES-256-GCM, `keep/sealed.py`) is Phase 4 (E6), a separate extra
  (`cryptography`), and a separate decision. Losing the key here loses the
  ability to *verify* the keyed segment, not the ability to *read* it.
* **change anything about a log that never gets a key.** No key file, no
  behavior change — see §2. `IntegrityLog`'s public `append`/`head`/`verify`
  signatures and the on-disk line format for an unkeyed log are unchanged
  bit-for-bit, because a sibling bite (sync) reads `head()` and appends
  through the same class without knowing keying exists.

## 2 · Three states, not two — `keyed: bool | None`

`IntegrityLog(..., key: bytes | None = None, keyed: bool | None = None)`:

* `keyed=None` (default) — **auto**. Keyed iff `paths.anchors_dir() /
  "integrity.key"` exists and decodes as 32 bytes of hex; unkeyed otherwise.
  A checkout that has never run `homestead integrity init-key` behaves
  exactly as it did before this bite — no key file exists, so every log stays
  unkeyed, silently and by construction, not by a flag someone remembered to
  pass.
* `keyed=True` — **require** the key. A missing or malformed key file is
  `IntegrityKeyError` at construction (I-11: fail closed, refuse by name,
  never fall back to unkeyed because the file happened to be absent).
* `keyed=False` — **force unkeyed**, even with a key file present. For a
  caller with a specific reason to read the pre-key segment of a log without
  the key on hand — auditing the chain up to the boundary row (§4), say.

`key=<bytes>` bypasses the file entirely with a caller-supplied key (tests,
mainly). Passing both `key` and `keyed=False` is a contradiction and is
refused rather than silently resolved either way.

Two states (a plain boolean) cannot express "auto" without conflating it with
one of the other two, and conflating it was rejected: a boolean defaulting to
`False` would mean every *existing* keyed log becomes unkeyed the moment a
caller forgets the flag, and a boolean defaulting to `True` would mean every
fresh `IntegrityLog()` in the test suite starts demanding a key that does not
exist. `None` as its own state is the only shape where "nothing was decided
either way" does not collapse into one of the two things a caller might
actually have meant.

## 3 · One key, at a fixed path, never escrowed

`paths.anchors_dir() / "integrity.key"` — one file, one household, matching
the anchor's own placement (willow-mcp #280: off the log's own tree, so
wiping `logs_dir()` or `exports_dir()` does not take the witness with it).
Not per-log, per-matter, or per-module: a household that loses its one key
loses verifiability for every keyed segment at once, which is the honest
statement of what "no escrow" means, not a surprise discovered piecemeal.

**No escrow, by design, not by omission.** The plan's own words: *"key
management for a person in crisis is a product decision, and a user who loses
the key loses the record permanently"* (now: loses the ability to verify,
since sealing is still Phase 4). A recovery mechanism — a second copy held by
this application, a server-side backup, a recovery question — is itself a
second way to obtain the key, and a second way to obtain the key is a second
way an adversary who shares the machine (F-5) obtains it too. The one honest
answer available to an application with no server and no second device is:
the operator keeps the key, physically, off the machine, the same way
`verify(expected_head=...)` already asks them to keep a head off the machine.
`homestead integrity init-key` prints only the path it wrote the key to
(§5) — never the key itself — because the operator copying it from a stdout
scrollback is a worse habit to encourage than reading it once from the file.

`init_key()` writes with `os.O_CREAT | os.O_EXCL | os.O_WRONLY`: a second
call never overwrites the first, closing off the one failure mode worse than
losing a key — silently rotating it out from under whatever it already seals,
with nothing to say the old chain's HMAC no longer matches anything the new
key can produce.

## 4 · Why a boundary row instead of refusing to key an existing log

A log can already have unkeyed lines in it when `init-key` runs — the
canonical export ledger, most likely, already carrying real history. Two
options: refuse to key a non-empty log (force a fresh log per key), or allow
it and mark where the change happened. Refusing was rejected: it would mean
the *existing* ledger — the one with real export history — could never be
upgraded without starting a new file and orphaning the anchor's own history,
exactly the "start over" cost sealing (E6) explicitly avoids by binding each
line's AAD to `prev` rather than re-encrypting from genesis.

So: allowed, and the first line written under a key is `{"act": "keyed", ...}`
— written by `IntegrityLog.append()` itself, lazily, the first time it runs
with a key in hand, never by `init-key` (which only makes the key file and
touches no log). `verify()` walks the chain once, tracking one index: lines
before the marker verify against the plain SHA-256 they were always hashed
with; the marker and everything after verify against the HMAC. A forged line
inserted anywhere at or after the boundary — including one built by an
attacker who does not know the boundary moved — fails, because it cannot
produce the correct HMAC without the key regardless of which side of the line
it lands on. `tests/test_invariants_integrity_keyed.py` pins this directly:
a keyed log with a line rewritten (and every following unkeyed hash and the
final anchor recomputed exactly as an attacker without the key would) fails
`verify()`; the identical attack against an unkeyed log — the pre-existing,
documented gap — still succeeds, so the test states the gain rather than
just the presence of a key.

The marker's own field name, `act`, is shared with `export.py`'s ledger
entries (`{"act": Event.EXPORTED.value, ...}`), which is a namespace an
IntegrityLog entry is otherwise free to fill with anything. `Event` is a
closed enum with no `"keyed"` member (checked, and pinned by a test), so no
real entry collides with the sentinel today; a future `Event` member must not
be named `"keyed"` for the same reason `RECORD_SYNCED` could not be reused
for "a record was entered" in an earlier bite — a name means one thing.

## 5 · Why HMAC-SHA256, and why `hmac.compare_digest` everywhere

HMAC-SHA256 over a plain keyed SHA-256 (`sha256(key || message)`) because the
naive construction is length-extension-vulnerable and HMAC is the standard,
stdlib-available answer with no new dependency (I-27: this bite adds none —
`hmac`, `hashlib`, `os`, `secrets` are all in the standard library). No
asymmetric scheme (Ed25519 signatures, say) because there is exactly one
party — the same household, on the same machine, at both write and verify
time — so there is nothing for a public/private split to buy that a shared
secret does not already provide, at the cost of a dependency this bite does
not need.

Every hash comparison in `verify()` — each line's `prev` against the running
chain, and the final head against the anchor or an `expected_head` — goes
through `hmac.compare_digest` rather than `==`/`!=`. A hash comparison is not
where a timing side-channel would help this household's specific threat
model most, but `verify()` is the one place in this codebase whose entire job
is comparing values a forger is actively trying to match, and using the
constant-time comparison everywhere in it rather than reasoning per-branch
about which comparisons are "hot" is the cheaper thing to get right once. An
AST guard in `tests/test_invariants_integrity_keyed.py` asserts no `==`/`!=`
inside `IntegrityLog.verify`, planted against a fixture that uses one, so the
guard is shown to fire rather than merely exist.

## 6 · What the CLI does and does not print

`homestead integrity init-key` creates the key and prints the **path**, never
the hex. `homestead integrity verify [--path PATH]` prints `keyed` or
`unkeyed` and the pass/fail result, never the key or a hash a forger could
use as a starting point beyond what the log's own anchor file already
exposes. Both are tested by grepping stdout and stderr for a 64-character hex
run and asserting there is none — a test that only proves something once it
is shown capable of failing (planted with a stub that does print the key).

A keyed anchor is written `hmac:<hex>` instead of a bare hex digest (item 6
of the bite): `homestead integrity verify` needs to say "keyed" or "unkeyed"
truthfully even when it has no key on hand (an operator running `verify`
before they have found the key file back, say), and the prefix is what makes
that answerable by reading the anchor alone. Reading a **keyed** anchor
without a key still refuses `verify()` by name — `IntegrityKeyError`, not a
bare `False` — because "cannot tell" and "found tampering" are different
answers this codebase has already decided (in `logs.py`'s own docstring, of
`verify()`'s pre-existing `JSONDecodeError` handling) must not be conflated.

## 7 · Windows

`os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)` is the same call
on every platform — `O_EXCL` is POSIX and Windows both — but the `0o600` mode
argument only does anything on POSIX; NTFS has no such bit. On Windows the key
file's protection is whatever ACL its parent directory (`anchors_dir()`,
under the household root) already grants, which is ordinary per-user file
permissions on a single-user machine and nothing stronger. This bite does not
attempt to set a Windows ACL — no dependency, no `pywin32`, and this codebase
has no Windows-specific code path anywhere else to extend. Documented here
rather than silently assumed, per the bite's own instruction: "document
Windows" is the answer, not a claim that 0600-equivalent protection exists
there.

## What this bite deliberately does not do

* **Encrypt anything.** The log stays plaintext JSON lines, keyed or not.
  `keep/sealed.py` (E6, Phase 4, extra `sealed`) is a separate bite and a
  separate dependency (`cryptography`).
* **Rotate or escrow the key.** There is exactly one key, at one path, made
  once. A lost key is not recoverable by this application, by design (§3).
* **Change any unkeyed log's on-disk format**, or `append`/`head`/`verify`'s
  signatures. A sibling bite (sync) depends on both staying exactly as they
  were.
* **Key the visible log.** `VisibleLog` carries references, never content,
  and was never in scope for a forgery-detection mechanism — a reference an
  attacker could forge is a much smaller problem than the content-leak F-4
  already closed for that log by a different means.
