# The integrity key: no escrow, no server, one file — decision brief

Status: **Ratified with amendments, 2026-09-11.** The shape stands — one key,
one path, `O_EXCL`, no escrow, a three-state `keyed` knob, a boundary row —
and **one central claim did not hold as written and is corrected here**: §1
said a forger who can rewrite the log and the anchor "still cannot produce a
matching HMAC without also reading the key," which is true and beside the
point, because they do not need to. They delete the boundary row, re-chain the
survivors with the public SHA-256 they can compute, and offer a log that was
never keyed. The audit reproduced that attack, it verified clean against a
verifier *holding the key*, and it is now closed as far as anything on this
machine can close it (§4a) with the residual pinned by a test rather than
described. Two smaller claims were also corrected: §5 described a planted CLI
test that did not exist (it does now), and the AST guard it names checked only
functions spelled `verify` while every digest `verify()` compares is computed
one call deeper.
author: the build seat
verified_by: the audit seat, 2026-09-11

*Status as proposed, kept:* **Proposed.** — with the note below, which is the
right instinct and was worth acting on.

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
**not** live next to the log or the anchor it seals — see §3. ~~An attacker who
can edit the log and the anchor still cannot produce a matching HMAC without
also reading the key. This closes exactly the gap the module docstring
names~~ **Corrected at ratification:** true, and not the whole question — an
attacker who cannot forge an HMAC can *remove* the reason one is expected.
What closes the gap is §4a, not the HMAC alone. This does not:

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

## 4a · The downgrade, the marker beside the key, and the residual

**Added at ratification**, because the audit's first attack got through.

A boundary row is a row in a file the attacker is already rewriting. Delete
it, re-link the surviving lines with plain SHA-256 — which needs no key — and
write a bare-hex anchor, and `verify()` sees a log that never turned keyed and
reports it clean. Holding the key does not help: nothing in the log any longer
claims a key was ever involved. Truncating to the pre-boundary prefix is the
same attack with less typing. Both were reproduced against the proposed
implementation and both verified clean.

So the turning point is written in a **second place**, beside the key rather
than inside the log: `paths.anchors_dir() / "integrity.keyed"`, one
`0600` line per log, `<sha256 of the log's resolved path> <a commitment to the
boundary row's keyed hash>`. Three choices in that line, each for a reason:

* **a digest of the path, not the path**, so the marker discloses nothing
  about what the household keeps or where;
* **the boundary row, not merely the fact of one**, so that re-keying a
  downgraded log with an ordinary next `append()` cannot launder the alarm
  away — the marker records *which* row, and a fresh one does not match;
* **a commitment (`sha256("homestead-integrity-boundary:" + h)`), not `h`.**
  Recording the keyed hash verbatim would publish, in a world-readable-shaped
  bare-hex file, exactly the head an attacker needs to truncate every keyed
  line and write a matching `hmac:` anchor. A downgrade guard that opens a
  truncation oracle is a bad trade; the commitment is checkable by anyone who
  can recompute the hash (which needs the key) and useless to anyone who
  cannot. Found by re-reading the first version of this guard adversarially,
  and pinned (`test_the_marker_is_not_an_anchor_an_attacker_can_copy`). `verify()` then answers a log whose
marker line outlived its boundary row with **`False`** — a finding about the
log — and not with `IntegrityKeyError`, which stays reserved for "the key
needed to even ask the question is missing or broken."

**What this deliberately does not do**, stated because it is the part that
matters: the marker is one more file on the same machine. An attacker who
deletes the key, deletes the marker and truncates the log to its pre-boundary
prefix leaves something indistinguishable from a log that was never keyed —
because that is now exactly what it is. F-5 is unchanged: a shared OS account
is not securable by an application, and the key's *absence* cannot be made
distinguishable from never-having-keyed by any file the same hand can reach.
This residual is the pre-E5 threat model for an unkeyed prefix, no better and
no worse, and it is pinned as a passing test
(`test_the_residual_key_and_marker_gone_and_truncated_verifies_clean`) so that
a later bite claiming to have closed it has to change that test on purpose.
The one real closure is unchanged and is named in `logs.py`'s own docstring:
`verify(expected_head=...)` against a head the operator recorded off the
machine.

The blunter rule considered first — "a bare-hex anchor while a key file exists
is a finding" — was rejected and is pinned as a behaviour the code must *not*
have (`test_a_legacy_log_untouched_since_init_key_still_verifies_clean`). It
is the normal state of every pre-key log between `init-key` and that log's own
next append, so it would refuse exactly the legacy logs this bite promises not
to disturb.

## 4b · A keyed log holds one row no caller wrote

The boundary row is a line in the log, so anything that counts or iterates a
ledger's lines sees it. `keep/sync.py` establishes "ledgered once" (I-38) that
way, and its tests assert exact line counts; run against a keyed household,
two of them fail on `2 == 1` while `deliver` and `_already_delivered`
themselves are correct (both already filter on `act`). `BOUNDARY_ACT` is
exported for exactly this, and the rule is: **a consumer counting ledger rows
skips `entry.get("act") == BOUNDARY_ACT`.** Fixing those two assertions
belongs to the sync bite, not here — the engine cannot reach into a branch
that has not merged — and the contract is pinned on this side by
`test_a_keyed_log_holds_one_row_no_caller_wrote`.

## 4c · What reads as a key file

`bytes.fromhex`'s answer, not a stricter one: surrounding whitespace stripped,
uppercase accepted, whitespace between byte pairs accepted — all three name
the same 32 bytes, and an operator restoring the key by hand from a printed
copy should not be refused over the case of a letter. Anything that does not
name exactly 32 bytes (63, 65 or 66 hex characters; an empty file; anything
non-hex) is refused by name. A **missing** file is not an error at all — that
is just an unkeyed household. All eight cases are pinned.

`anchors_dir()` is created by `paths.ensure` if `init-key` is the first thing
to need it — an ordinary `mkdir` under the umask, 0755 on a default POSIX box,
deliberately not tightened: the anchor it holds is meant to be *copyable off
the machine*, and the key inside it carries `0o600` whatever the umask says
(pinned with the umask cleared, so the mode is the code's and not the
environment's). `O_EXCL` also refuses a **symlink** standing at the key path,
dangling or not, and never follows it — the way a writer would arrange for the
key to land somewhere they can read it. The refusal says "something already
exists", not "a key already exists", because at that point we do not know
which.

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
~~inside `IntegrityLog.verify`~~ **Corrected at ratification:** anywhere in
`logs.py` on an operand *named* like a digest. Scoped to functions spelled
`verify` it checked less than it claimed — `verify()` delegates every hash it
compares to `_hash_at`, `line_hash` and `_recorded_boundary`, so a bare `==`
moved one call deep passed the guard while making the exact change the guard
forbids. The operand-name filter is what keeps the wider walk from being
blanket: `entry.get("act") == BOUNDARY_ACT` compares a sentinel, not a digest,
and is pinned as a case that must *not* fire. Planted three ways — a bare
equality in `verify`, one in a helper `verify` calls, and the sentinel
comparison that must stay legal — so the guard is shown to fire, shown to
reach past `verify`, and shown not to over-reach.

## 6 · What the CLI does and does not print

`homestead integrity init-key` creates the key and prints the **path**, never
the hex. `homestead integrity verify [--path PATH]` prints `keyed` or
`unkeyed` and the pass/fail result, never the key or a hash a forger could
use as a starting point beyond what the log's own anchor file already
exposes. Both are tested by grepping stdout and stderr for a 64-character hex
run and asserting there is none — a test that only proves something once it is
shown capable of failing. ~~(planted with a stub that does print the key)~~
**Corrected at ratification:** no such plant existed; the grep had never
matched anything. It now does, against a line that prints a key and against
the real line that prints only a path
(`test_the_hex_grep_used_by_the_cli_tests_is_shown_to_fire`).

**Exit codes**, because `verify()` gives three answers and a cron job reading
"cannot tell" as "tampered" is the failure this separation exists to prevent:
**0** clean, **1** the chain or the anchor does not hold, **2** a command line
that does not parse, **3** refused by name (`IntegrityKeyError`). Added at
ratification — refusal and failure shared `1`, which threw away the very
distinction §6's next paragraph insists on. An argument `verify` does not
understand is a usage error and never a silent fall-through to the default
ledger: `verify --pat /some/log` answering "ok" about a log the operator did
not name is the worst thing this command can do (I-11 — refuse, never
default).

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

## 8 · Sealing (E6, Phase 4)

Status: **Proposed, 2026-09-11.** — ~~awaiting ratification~~ **Ratified by
the audit seat, 2026-09-11**, with three downgrade findings fixed on the
branch before ratifying (see "The downgrade this section first missed",
below); the cryptographic construction below — HKDF-SHA256 domain-separated
subkey, AES-256-GCM, a fresh 96-bit `os.urandom` nonce per line, AAD bound to
`prev`, and an **HMAC** (never a bare SHA) for the `hash` field that rides in
the clear — was re-derived independently and is ruled sound as described.
author: the build seat
verified_by: the audit seat, 2026-09-11 (audit fixes: `ff6c374`)

Added by the sibling bite this document promised in §"There is no
encryption" and item 8 of `docs/PLAN-affairs-face.md`'s open items: "keying
first, sealing second, no escrow." Keying (§1–§7, ratified) closes the
forged-chain-plus-matching-anchor gap for a log that opts in. It never made
the log unreadable — every line stays plaintext JSON on disk, and this
section's own opening line said so. Sealing is the part that does, for a
household that chooses it, in `keep/sealed.py`.

**One key, two independent subkeys, not two keys.** The household already
has exactly one secret to lose (§3): `anchors_dir()/integrity.key`, 32 raw
bytes. Sealing needs a *different* key from the one HMAC uses — reusing the
same 32 bytes for both HMAC-SHA256 and AES-256-GCM is the kind of key reuse
cryptographic practice avoids on principle, not because a specific attack
against this pairing is known — so `keep/sealed.py:derive_subkey` runs
HKDF-SHA256 over the raw key with **no salt** and a **fixed**
`info=b"homestead integrity sealed v1"`. No salt because HKDF's salt exists
to concentrate entropy out of a weak or reused input key, and the raw key is
already 256 bits from `secrets.token_hex`, generated once; a fixed label
because it is the thing that keeps this specific derivation ("the AES key
for homestead's sealed log, scheme v1") from ever colliding with some later,
unrelated subkey drawn from the same file. Losing the key loses both the
HMAC chain's verifiability *and* the sealed segment's readability at once —
stated plainly, not discovered piecemeal, because there was never a second
file to separately lose.

**AAD binds `prev`.** Each sealed line's Associated Authenticated Data is
the previous line's hash — so a line only decrypts at the position the
chain says it belongs, and a splice, reorder, or replay breaks
authentication before anything about the plaintext is even attempted. This
is *in addition to*, not instead of, the plaintext `prev`-chain check
`verify()` already made for keying: an attacker who also relabels every
downstream `prev`/`hash` field can pass that structural check without the
key (see "chain verified, contents not authenticated" below), but cannot
produce a matching GCM tag for a `prev` the ciphertext was not actually
sealed under.

**The boundary row, again.** Exactly the keying mechanism (§4), one layer
up: `{"act": "sealed", ...}` — plaintext, keyed-hashed like any line before
it, written by `IntegrityLog.seal()` (`homestead integrity seal`) or lazily
by the first `append()` on an instance constructed `sealed=True`. Lines
before it are whatever they already were (plaintext keyed or unkeyed);
sealing turns on there, not for a log's whole history, for the same reason
keying does not require starting a fresh log (§4): a household's real
export ledger already has history, and it is not owned twice over. The
turning point is recorded beside the key
(`anchors_dir()/integrity.sealed`), the identical shape as
`integrity.keyed` (`_record_boundary`/`_recorded_boundary` now take a
`marker_path`, shared by both), and `verify()` treats a missing sealed
boundary row behind a recorded marker as a downgrade — `False`, not a clean
unsealed read — the same way §4a treats a missing keyed one.

**No plaintext fallback, ever.** `IntegrityLog(sealed=True)` refuses at
construction (`IntegritySealError`, naming whichever is missing) if the key
is absent or the `cryptography` extra is not installed — never a silent
write of an unencrypted line where a sealed one was asked for.
`append()`/`verify()`/`read_entries()` (named `_entries()` until E7 gave it
a public name — see §9) carry the identical refusal for a log
*auto-detected* as sealed (the marker says so) but missing what it needs at
the moment ciphertext is actually touched. The one place this is
deliberately **not** eager: `IntegrityLog()`'s plain auto-construction
(`sealed=None`) never raises for a missing key or extra, so that
`verify(decrypt=False)` — which never needs the `cryptography` extra, only
the key, via stdlib `hmac`, for the keyed boundary rows every sealed log
carries; a log with no key at all cannot be verified either way, unchanged
from E5 — remains reachable on a sealed log even without
`homestead-affairs[sealed]` installed. That single exception is why
`decrypt` exists as its own keyword rather than folding
into `sealed`/`keyed`.

**"Chain verified, contents not authenticated."** A sealed line's `hash`
field (the keyed hash of its plaintext, computed before encryption) rides
in the clear beside the ciphertext, so the `prev`/`hash` chain — and the
final anchor comparison — can be walked without decrypting anything
(`verify(decrypt=False)`). That proves the file's *shape* holds: nothing
truncated, nothing whose declared links do not connect. It proves nothing
about whether the content behind a `hash` is genuine, because `hash` is not
covered by any GCM tag. `verify()` defaults to `decrypt=True`, which adds
exactly that missing check, and `describe_verification()` puts the
distinction into words rather than letting the weaker pass read as
identical to the stronger one — the literal instruction in item 3 of the
E6 bite: never report a sealed log clean by hashing ciphertext alone
without saying so.

**The downgrade this section first missed.** Three ways to turn sealing
*off* again were open when this section was first written, and all three are
now closed with a planted test each (`tests/test_invariants_sealed.py`):

* `IntegrityLog(path, sealed=False)` on a sealed log appended a plaintext
  line after the sealed boundary row. It chained correctly, `verify()`
  returned `True`, and the content was on disk in the clear. ~~`sealed=False`
  is now a **read-side** escape hatch only: `append()` refuses by name
  (`IntegritySealError`) on any log carrying the boundary row.~~ **Amended
  2026-09-11 (§9, E7 audit):** `append()` refuses by name on any log carrying
  the boundary row — that part stands — but "a read-side escape hatch" was
  too generous by exactly one reader. `read_entries(decrypt=False)` honoured
  the argument and served the pre-seal plaintext rows as if they were the
  log. `sealed=False` is now a **write-side promise only** ("do not put me on
  the sealed side of this file"); every reader asks the file's own witnesses
  (`_sealing_witnessed`), never the constructor argument.
* Deleting `anchors/integrity.sealed` made auto-detection (`sealed=None`)
  answer "not sealed", so the next `append()` wrote plaintext. Auto-detection
  now reads the log's own `{"act": "sealed"}` row as well as the marker —
  that row is chained and keyed, so removing it needs the key, which is the
  whole point. Either witness is enough; both must be gone.
* A plaintext line written straight onto the end by someone holding the key
  was invisible to `verify()` — it is a perfectly good chain link. `verify()`
  now reports any non-sealed line after the sealed boundary as `False`. This
  check needs no key, so it is a finding, never "cannot tell."

The ordering rule underneath all three: **a log only ever turns more sealed,
never less.** There is no unsealing, and there is no writing plaintext past
the point where sealing began.

**No escrow, still.** Nothing here changes §3's answer. A lost key was
already unverifiable-not-recoverable for a keyed log; for a sealed one it is
now **unreadable**, not merely unverifiable — the honest cost of the
tradeoff the plan named at open item 8 ("Integrity key loss = ledger
unreadable once sealed"). No second copy is introduced by this bite for the
same reason §3 gives none: a second way to obtain the key is a second way
the person sharing the machine (F-5) obtains it too.

**Windows.** Nothing in §7 changes. `cryptography`'s AES-GCM and HKDF
implementations are pure-library code with no platform-specific key
storage of their own — sealing does not touch the filesystem any
differently than keying already did, so §7's ACL discussion is the whole of
what this section has to add: none.

**The nonce-reuse test.** AES-GCM's security assumption is that a (key,
nonce) pair is never reused; `seal_line` draws a fresh 96-bit nonce from
`os.urandom` per line. `tests/test_invariants_sealed.py` seals 10,000 lines
and asserts every nonce is distinct — a property of the operating system's
CSPRNG this bite depends on rather than invents, pinned so a future edit
that makes the nonce derived or predictable is caught.

## 9 · Public reader (E7)

Status: **Proposed, 2026-09-11.** — ~~awaiting ratification~~ **Ratified by
the audit seat, 2026-09-11**, with two short-answer findings fixed on the
branch before ratifying (see "The two short answers this section first
missed", below). The shape stands: one public reader, the refusal in its
signature, the old name kept for one minor.
author: the build seat
verified_by: the audit seat, 2026-09-11 (audit fixes: `94c3459`)

Raised by the H6 audit (2026-09-11): `homestead_health`'s `LivingLane.
replacements()` read `living.jsonl` with a bare `json.loads`, so a sealed
log answered "never replaced" instead of refusing — I-11's silent-wrong-
answer shape, reached because the log's one reader had no public name.
`_entries()` was already that reader in every way that mattered
(`keep/sync.py`'s `_already_delivered`, and a documented seam in
`homestead_health`); the underscore hid a name callers already used, not a
boundary — so this bite gives it one: `IntegrityLog.read_entries(*,
decrypt=True)`, same method, public. `_entries()` stays for one minor as a
deprecated alias (`warnings.warn`, identical yield).

**What did not change is the thing §8 and F-6 actually care about.** A
public name is not a weaker reader — `read_entries()` still refuses by name
rather than serving a sealed log's content without the key or the extra,
and a corrupt line raises instead of quietly ending early:
`list(log.read_entries())` raises, never returns a short list. `decrypt=
False` — the structural parallel of `verify(decrypt=False)` — was, before
this bite, a silent partial view: it walked past every sealed line with a
bare `continue` and returned the plaintext prefix as if it were the whole
log. That is now a refusal: `decrypt=False` on a ~~log this instance
considers sealed~~ **log whose file carries either witness of sealing**
raises before yielding a single entry, because the only two honest answers
to "what does this log hold, without the key" are "everything" or "I cannot
tell you," never "some of it, unmarked."

**`test_sealed_log_has_no_public_read_method` is narrowed accordingly**,
from "no public reader" (which `read_entries()` now falsifies by name) to
the property it existed to protect: no public reader that can return a
short answer or a plaintext fallback for a sealed log. `read`, `render`,
`tail`, `show`, and a bare `entries` stay forbidden — none of them carries
a signature that could say what it refused. `read_entries` is allowed
because its keyword argument is exactly that place.

**The alias is removed in 0.13.0.** This bite cuts 0.12.0 and "one minor"
is the next one; a removal nobody wrote a date on is a removal that never
happens. The number is in three places that are checked against each other
— `IntegrityLog._entries()`'s docstring, this paragraph, and
`tests/test_invariants_logs.py::test_the_entries_alias_is_gone_by_its_named_
removal_version`, which reads the changelog's top release heading and starts
failing the moment it reaches 0.13.0 with the alias still present.
`DeprecationWarning` is silent by default, so nothing would otherwise ever
notice the window had closed. Checked while ratifying: none of the four
repos turns warnings into errors (no `filterwarnings = error`, no `-W
error`, no `PYTHONWARNINGS` in any `pyproject.toml`, CI workflow or
`conftest.py`), so the alias warns and nothing downstream breaks on it in
the meantime.

**The two short answers this section first missed.** Both were reachable on
the version proposed above, and both are now closed with a planted test each
(`tests/test_invariants_sealed.py`):

* **`sealed=False` bought a plaintext prefix.** The refusal read
  `self.sealed` — the constructor argument — so
  `IntegrityLog(path, sealed=False).read_entries(decrypt=False)` on a sealed
  log returned the pre-seal rows and stopped, with nothing in the return
  value saying the rest existed. One keyword argument away from every
  caller, and it needed no key. The refusal now reads the file's own
  witnesses (the marker and the `{"act": "sealed"}` row —
  `_sealing_witnessed`), which is precisely what E6's audit made `append()`
  do about the same argument. A sealed line met with `decrypt=False` and
  *neither* witness present (a hand-built file) refuses too, rather than
  being skipped.
* **A truncated log read as a whole one.** Every surviving line of a
  truncated log chains and decrypts perfectly; the anchor is the only
  witness that there were more, and `read_entries()` never consulted it, so
  chopping the last line off made the method answer as if that line had
  never been written — `H6-sealed-reader`'s "never replaced" with a
  different first step. The walk now ends at `_require_whole`, which
  compares the head it just walked against the anchor and raises
  `IntegrityIncompleteError` (the third refusal: not "cannot ask", but
  "asked, and the answer would have been short"). `verify()` reports the
  same file as `False` — a finding — and that stays the way to ask for one.
  No anchor, no claim: a log nobody ever anchored still reads.

The rule underneath both, and the thing `test_sealed_log_has_no_public_read_
method` is now narrowed to: **the only way for a public reader to hand back
fewer entries than the log holds is a refusal.** Nothing in the signature,
and no argument at construction, may turn that into a short list instead.

**Health's `ledger_seam.py`** (a separate repo, H6-sealed-reader) becomes a
one-line pass-through to this method once its floor reaches the release
carrying it — not this bite's change, noted because it is the reader the
H6 finding was actually about. Its `getattr(log, "_entries", None)` probe
keeps working through the deprecation window and refuses by name
(`LedgerUnreadable`) after it, which is the behaviour it already tests for.


* ~~**Encrypt anything.** The log stays plaintext JSON lines, keyed or not.
  `keep/sealed.py` (E6, Phase 4, extra `sealed`) is a separate bite and a
  separate dependency (`cryptography`).~~ **Done, 2026-09-11 (E6, §8
  above).** A *sealed* log's lines are ciphertext; an unsealed or
  keyed-only log is unaffected — its on-disk format is unchanged (see the
  next bullet).
* **Rotate or escrow the key.** There is exactly one key, at one path, made
  once. A lost key is not recoverable by this application, by design (§3).
* **Make the key's absence distinguishable from never-having-keyed**, once
  the log has been truncated to its pre-boundary prefix and the marker
  deleted. §4a says why no file on this machine can, and pins it.
* **Change any unkeyed log's on-disk format**, or `append`/`head`/`verify`'s
  signatures. A sibling bite (sync) depends on both staying exactly as they
  were.
* **Key the visible log.** `VisibleLog` carries references, never content,
  and was never in scope for a forgery-detection mechanism — a reference an
  attacker could forge is a much smaller problem than the content-leak F-4
  already closed for that log by a different means.
