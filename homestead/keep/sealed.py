"""Phase 4 (E6) — sealing an `IntegrityLog`'s lines, per-line AES-256-GCM.

Wave 6 of `docs/PLAN-affairs-face.md` (decision 6, open item 8): "keyed HMAC
chain first (no dependency), then Phase 4 sealing behind extra `sealed`
(`cryptography`; pure-Python AEAD is not an option)." E5 (`keep/logs.py`)
closed the forged-chain-plus-matching-anchor gap for a log that opts in to a
key. It never claimed to make the log unreadable — the module's own
docstring says so — and this bite is the part that does: a keyed log's lines
are still plaintext JSON on disk, readable to anyone with filesystem access
(F-5's residual, restated). Sealing does not change F-5 (a shared OS account
is still not securable by an application); it changes what "filesystem
access" gets you for the sealed segment, from "the content" to "ciphertext
this application refuses to open without the key."

**`cryptography` is an optional extra (`sealed`), never a required
dependency (I-27).** Every name from it is imported inside a function, never
at module load — `require_available()` is the one place that probe lives, so
`import homestead.keep.sealed` succeeds on a checkout that never installed
`homestead-affairs[sealed]`, and only the first attempt to actually seal or
unseal a line fails, by name, naming the extra rather than a bare
`ModuleNotFoundError` a caller has to guess the fix for. `keep/store.py`'s
`PostgresAdapter` (`MissingFleetExtra`, E4-postgres-fleet) is the precedent
this follows.

## Why HKDF, not the raw key, for the AES key

One key file (`anchors_dir()/integrity.key`) already has a job: it is the
raw HMAC-SHA256 key `keep/logs.py` uses to keyed-hash every line. Sealing
needs a *second*, independent secret to encrypt with — using the same 32
bytes for both HMAC and AES-GCM would mean any weakness discovered in one
use leaks into the other, and there is a well-known, cheap way to avoid that:
derive an independent subkey with HKDF-SHA256 (RFC 5869) rather than mint a
second file to lose. `derive_subkey` takes **no salt** (`salt=None`, which
HKDF defines as a string of zero bytes, not "no derivation") and a **fixed**
`info=b"homestead integrity sealed v1"` — the domain-separation label that
makes this specific derivation ("the AES-GCM key for homestead's sealed
integrity log, version 1 of the scheme") unable to collide with some future
subkey derived from the same raw key for an unrelated purpose. There is
nothing to make unpredictable with a salt: the raw key is already 256 bits
of `secrets.token_hex`, generated once, and HKDF's extract step exists to
concentrate entropy out of a *weak or reused* input keying material, which
this is not. A fixed public label plus a high-entropy input key is the
documented "no salt" case in RFC 5869 §3.1, not a corner cut.

## Why the AAD binds `prev`, and why that is the whole point

Each sealed line's Associated Authenticated Data is the previous line's
hash — the same value AES-GCM's caller already has in hand as `prev`,
because it is the value being chained. Binding it as AAD (authenticated,
not encrypted) means a sealed line's ciphertext only decrypts successfully
*at the position the chain says it belongs* — move it to sit after a
different `prev` and `AESGCM.decrypt` raises `InvalidTag` before anything
about its plaintext is even attempted. This is what "a sealed line cannot be
moved" means concretely: reordering lines, splicing a sealed line from one
log into another (even one keyed with the *same* key), or replaying an old
line into a new position all break authentication, not just the outer
prev-chain check `keep/logs.py`'s `verify()` already does for a plaintext
chain — the AAD check is a *second*, cryptographic assertion of the same
fact, one an attacker without the key cannot forge past even if they can
edit the file freely (F-5's residual, again: they can still truncate to a
valid earlier point, which is the same gap E5 already documents for
"anyone who can rewrite everything on this machine").

## Ciphertext line format, and why the chain hash lives outside it

```json
{"sealed": 1, "nonce": "<24 hex chars>", "ct": "<hex>",
 "prev": "<the previous line's hash>", "hash": "<this line's keyed hash>"}
```

`hash` is `keep/logs.py`'s own `line_hash(plaintext_entry, key)` — the exact
value this line would have contributed to the chain had it never been
encrypted — computed **before** sealing and carried alongside the
ciphertext, in the clear. That is deliberate: it is what lets
`IntegrityLog.verify(decrypt=False)` walk the whole chain, check every
`prev`/`hash` link, and catch a truncated tail against the anchor, **without
touching the `cryptography` extra at all** — a household missing the
`sealed` extra (but still holding its one key: every sealed log is keyed
first, and the keyed boundary rows need that key regardless of `decrypt`)
can still ask "does this file's structure hold together," which is a real,
useful, weaker question than "is the content authentic." `IntegrityLog`
states the difference explicitly rather than letting the weaker answer pass
as the stronger one (see `describe_verification`). Decrypting
(`decrypt=True`, the default) adds the
strictly stronger check: recover the plaintext, recompute its keyed hash,
and require it to equal the `hash` field verbatim — because `hash` itself is
**not** protected by GCM's authentication tag (it never enters the
ciphertext or the AAD), so without this second comparison a tampered `hash`
field would pass every check `decrypt=False` makes while claiming a
plaintext the ciphertext cannot actually produce.

## The nonce

96 bits (`NONCE_BYTES = 12`), fresh from `os.urandom` for every line, never
derived from the line's position or content. AES-GCM's security collapses if
a (key, nonce) pair is ever reused — two ciphertexts under the same nonce
leak the XOR of their plaintexts and let an attacker forge the authentication
tag outright — so reuse is the one failure mode this module cannot recover
from after the fact, only avoid before. At the scale one household's
integrity log ever reaches (thousands of lines, not billions), a random
96-bit nonce's collision probability is the birthday bound on 2^96, which is
not a number this codebase's threat model needs to do better than.
`tests/test_invariants_sealed.py` seals 10,000 lines and asserts every nonce
is distinct — a property this module gets from the operating system's CSPRNG,
not from anything clever here, and the test exists so a future edit that
swaps `os.urandom` for something predictable is caught rather than trusted.
"""
from __future__ import annotations

import json
from typing import Any

from .logs import IntegritySealError, _canonical, line_hash

__all__ = [
    "seal_line", "unseal_line", "derive_subkey", "require_available",
    "SealTamperError", "NONCE_BYTES", "HKDF_INFO",
]

#: The domain-separation label for the one HKDF derivation this module makes.
#: Fixed and public — see the module docstring's "Why HKDF" section. Never
#: reused for a different derivation from the same raw key.
HKDF_INFO = b"homestead integrity sealed v1"

#: 96 bits — AES-GCM's own recommended nonce size, not a value chosen here.
NONCE_BYTES = 12


class SealTamperError(Exception):
    """A sealed line failed to authenticate: the GCM tag did not verify (the
    ciphertext, its AAD, or its position relative to `prev` was altered), or
    the decrypted plaintext's own keyed hash does not match the line's
    `hash` field (the field GCM's tag does not cover — see the module
    docstring). Caught by `IntegrityLog.verify()` and turned into `False` —
    a finding about the log, not "cannot tell." Never raised for a missing
    key or a missing extra; that is `IntegritySealError`.
    """


def _require_cryptography() -> tuple[Any, Any, Any, Any]:
    """The one place this module reaches for `cryptography`, and the only
    place `import cryptography...` appears anywhere in it — never at module
    load (I-27): a checkout without the `sealed` extra still imports this
    whole module, and only fails, by name, the moment sealing or unsealing
    is actually attempted."""
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    except ImportError as e:
        raise IntegritySealError(
            "this log is sealed; install homestead-affairs[sealed] to read "
            'or write it (pip install "homestead-affairs[sealed]")'
        ) from e
    return AESGCM, HKDF, hashes, InvalidTag


def require_available() -> None:
    """Raise `IntegritySealError`, naming the extra, if `cryptography` is
    not importable; return silently otherwise. The cheap probe
    `IntegrityLog(sealed=True)` and `IntegrityLog.seal()` use *before* doing
    any I/O, so sealing never starts, writes part of a line, and only then
    fails — a refusal here leaves the log exactly as it was.
    """
    _require_cryptography()


def derive_subkey(raw_key: bytes) -> bytes:
    """HKDF-SHA256(raw_key, salt=None, info=HKDF_INFO, length=32) — the AES
    key, independent of the raw key `keep/logs.py` uses directly for HMAC.
    See the module docstring's "Why HKDF" section for why no salt and a
    fixed info label are the right choice here, not a corner cut.
    """
    _, HKDF, hashes, _ = _require_cryptography()
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=HKDF_INFO
    ).derive(raw_key)


def seal_line(entry: dict[str, Any], *, key: bytes, prev: str) -> dict[str, Any]:
    """Encrypt one plaintext entry — which must already carry its own
    `"prev"` field, the value `AAD` binds — into the ciphertext line format.
    `key` is the raw 32-byte integrity key; the AES subkey is derived here,
    not by the caller, so there is exactly one place that derivation happens.

    Returns the wrapper dict `IntegrityLog.append()` writes verbatim as the
    line: `{"sealed": 1, "nonce", "ct", "prev", "hash"}`. `hash` is
    `line_hash(entry, key)` — the value this line contributes to the chain,
    computed over the plaintext before it is encrypted, so the chain can
    still be walked without the key (see the module docstring).
    """
    import os

    AESGCM, _, _, _ = _require_cryptography()
    subkey = derive_subkey(key)
    digest = line_hash(entry, key)
    nonce = os.urandom(NONCE_BYTES)
    plaintext = _canonical(entry).encode("utf-8")
    ct = AESGCM(subkey).encrypt(nonce, plaintext, prev.encode("ascii"))
    return {
        "sealed": 1,
        "nonce": nonce.hex(),
        "ct": ct.hex(),
        "prev": prev,
        "hash": digest,
    }


def unseal_line(line: dict[str, Any], *, key: bytes) -> dict[str, Any]:
    """Decrypt and authenticate one sealed line back to its plaintext entry.

    Three ways this refuses:

    * `cryptography` absent — `IntegritySealError`, naming the extra
      (`_require_cryptography`).
    * the GCM tag does not verify (wrong key, tampered ciphertext, or a
      `prev`/AAD that does not match what this line was actually sealed
      under — the "moved to another position" attack) — `SealTamperError`.
    * the tag verifies but the recovered plaintext's own keyed hash does not
      match the line's `hash` field (a tampered `hash`, which the tag does
      not cover — see the module docstring) — `SealTamperError`.

    Never returns a partial or best-effort result: any of the above raises
    rather than handing back plaintext that has not fully checked out.
    """
    import hmac

    AESGCM, _, _, InvalidTag = _require_cryptography()
    try:
        nonce = bytes.fromhex(line["nonce"])
        ct = bytes.fromhex(line["ct"])
        prev = str(line["prev"])
    except (KeyError, ValueError) as e:
        raise SealTamperError(f"not a sealed line: {e}") from e

    subkey = derive_subkey(key)
    try:
        plaintext = AESGCM(subkey).decrypt(nonce, ct, prev.encode("ascii"))
    except InvalidTag as e:
        raise SealTamperError(
            "a sealed line failed to authenticate — wrong key, tampered "
            "ciphertext, or moved to a position its AAD does not match"
        ) from e

    try:
        entry: dict[str, Any] = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise SealTamperError(
            "a sealed line decrypted to bytes that are not the JSON entry "
            "it claims to be"
        ) from e

    if not hmac.compare_digest(line_hash(entry, key), str(line.get("hash", ""))):
        raise SealTamperError(
            "a sealed line's recovered plaintext does not match its own "
            "hash field"
        )
    return entry
