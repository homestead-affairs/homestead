"""Two logs, because one log cannot serve both readers.

F-6 named the tension and it does not dissolve: a supervising attorney, LSC
Part 1636, and any breach-notification clock all require an audit trail — and
the person sharing the machine reads that trail with one keypress. A single log
either fails the lawyer or exposes the user.

So there are two, with different powers:

* **`VisibleLog`** — what the operator can see. It carries **references, never
  content**. F-4: law-gazelle's `add_note` copied the first eighty characters of
  every private note into its activity log, and the last eight rows of that log
  went into every model prompt. Note → log → prompt, and `a` opened it from the
  main screen. `event` is a **closed enum** and `ref` is a tuple of identifiers,
  so there is no parameter anywhere on this class that accepts free text.

* **`IntegrityLog`** — hash-chained, append-only, and **named for what it
  does**. It was called `SealedLog` until the Phase 0 audits pointed out that
  nothing about it was sealed. Renamed rather than defended, because a name is
  a claim and this one outran its mechanism.

  **What it catches** — and this is the whole list:

  - **In-place edits** of any line the chain runs past. Real and tested.
  - **Truncation and tail rewrites**, via the head anchor: the chain tip is
    written to a *separate* file after each append, so shortening the log
    without also editing the anchor is caught.

  **What it does not catch**, stated because the gap is the useful part:

  - ~~Anyone who edits **both** the log and its anchor. `line_hash` is an
    unkeyed public SHA-256 over plaintext at a predictable path, so a forged
    chain plus a matching anchor verifies clean.~~ **Closed 2026-09-11 (E5) for
    a log that opts in.** `IntegrityLog` now takes an optional HMAC-SHA256 key
    at `paths.anchors_dir()/integrity.key` (`homestead integrity init-key`).
    Keyed, `line_hash` is `hmac.new(key, ..., sha256)` instead of a bare
    digest, so a forger who can read and rewrite both the log and the anchor —
    everything on this machine — still cannot produce a valid chain without
    the key file too. What they *can* do is **downgrade**: delete the
    `{"act": "keyed"}` boundary row, re-chain the survivors with plain
    SHA-256, write a bare-hex anchor, and offer a log that never turned keyed.
    That is why the turning point is also recorded beside the key
    (`MARKER_FILENAME`, `_recorded_boundary`) and a log whose marker line
    survives its boundary row fails `verify()`. The marker is one more file on
    the same machine, so deleting the marker *and* the key *and* truncating to
    the pre-boundary prefix still verifies clean — the residual, unchanged
    from the pre-key threat model and stated in the DECISION rather than
    papered over. Unkeyed logs (no key ever created, or `keyed=False`)
    keep the exact gap described above; nothing about a legacy log's on-disk
    format changes. See `docs/DECISION-integrity-key-management.md`. **An
    on-machine anchor detects accident, not an adversary** — there is no
    location on this machine the writer cannot reach, which is the same truth
    as F-5: a shared OS account is not securable by an application. The key
    changes what "an adversary" means, not where the key can hide: it sits
    beside the anchor, off the log's own tree, never escrowed (Open item 8) —
    an operator who loses it has an unverifiable keyed segment, not an
    unreadable one (sealing that segment is Phase 4, E6).
  - The only real closure for an **unkeyed** log is `verify(expected_head=...)`
    with a head the operator recorded **off the machine**. `head()` is public
    so that is possible; nothing forces it.

  ~~**There is no encryption** — that stays a deliberate **Phase 4** item
  (E6, `keep/sealed.py`), not an oversight.~~ **Closed 2026-09-11 (E6), for a
  log that opts in.** `IntegrityLog` now takes `sealed=True` (or auto-detects
  a log `homestead integrity seal` already turned): from the sealed boundary
  row on, every line is AES-256-GCM ciphertext (`keep/sealed.py`), keyed off
  the same `integrity.key` by HKDF rather than a second secret. `~~and no
  key~~` (struck 2026-09-11, E5): the key above closes the forged-chain gap;
  keying alone does not make the log unreadable to whoever has filesystem
  access — sealing does, for the segment written after it turns on. F-6
  recommended hash-chained *and* encrypted; a household that never runs
  `homestead integrity seal` keeps the E5 posture exactly (a user who loses
  the key loses the ability to verify, not to read); one that does trades up
  to E6's, where losing the key loses the ability to read the sealed segment
  too — no escrow, stated in `docs/DECISION-integrity-key-management.md`
  §8, not discovered later. Decided 2026-08-04: rename and anchor first, key
  next (E5), encrypt last (E6, this bite).

  ~~The absence of a `read()` method is a **naming convention, not a
  control**.~~ **Narrowed 2026-09-11 (E7):** there is now a public reader,
  `read_entries()` — `_entries()` was already the door every in-package
  caller used (`keep/sync.py`, and a documented seam in `homestead_health`),
  so the underscore hid a name callers already depended on, not a control
  anything enforced. What was never true, and stays true, is a reader that
  can **return short or fall back to plaintext**: `read_entries()` refuses
  by name (`IntegritySealError`) rather than serving a sealed log's content
  without the key or the extra, and a corrupt line raises instead of
  silently ending early. `_lines()` still returns everything unfiltered,
  and `.path` is still public — "no public reader" was never the property
  worth guarding; "no public reader that lies about completeness" is.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import warnings
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from . import paths

try:                                    # advisory file locking is Unix-only
    import fcntl                        # noqa: F401
    _HAVE_FCNTL = True
except ImportError:                     # pragma: no cover - Windows
    _HAVE_FCNTL = False

__all__ = [
    "VisibleLog", "IntegrityLog", "Event", "line_hash",
    "IntegrityKeyError", "init_key", "read_key", "default_key_path",
    "default_marker_path", "KEY_BYTES", "BOUNDARY_ACT",
    "IntegritySealError", "SEAL_BOUNDARY_ACT", "default_sealed_marker_path",
    "describe_verification",
]

GENESIS = "genesis"

#: The key file: 32 random bytes, hex-encoded (64 characters), at a fixed
#: location — `paths.anchors_dir()/integrity.key` — never per-log, because one
#: household has one key to lose (Open item 8: no escrow). See
#: `docs/DECISION-integrity-key-management.md`.
KEY_FILENAME = "integrity.key"
KEY_BYTES = 32

#: The tag on the one line that marks where an `IntegrityLog` turned keyed.
#: Lines before it verify unkeyed (the pre-existing chain, untouched); this
#: line and every line after it verify with HMAC. Written once, the first time
#: `append()` runs while a key is present — never by `init-key` itself, which
#: only makes the key and does not touch any log.
#:
#: **A keyed log therefore holds one row no caller wrote.** Anything that
#: counts or iterates a ledger's lines — `keep/sync.py`'s "ledgered once"
#: check is the live example — must skip `entry.get("act") == BOUNDARY_ACT`,
#: which is why this name is exported rather than being a private literal.
BOUNDARY_ACT = "keyed"

#: Which logs have turned keyed, recorded beside the key rather than inside
#: the log an attacker is rewriting. See `_record_boundary` for what this closes
#: and, precisely, what it does not.
MARKER_FILENAME = "integrity.keyed"

#: The tag on the one line that marks where an `IntegrityLog` turned
#: *sealed* (E6, Phase 4) — the exact parallel of `BOUNDARY_ACT` for keying.
#: Lines before it verify as they always did (plaintext, keyed or not);
#: this line and every line after are the AES-256-GCM ciphertext wrapper
#: format `keep/sealed.py` defines. Written once, by `IntegrityLog.seal()`
#: or lazily by the first `append()` on an instance with `sealed=True` —
#: never by `init-key`, which only makes the key. A sealed log is keyed
#: first: this row itself, like the `BOUNDARY_ACT` row before it, is a
#: plaintext keyed line, so a reader without the *sealing* extra can still
#: find where sealing began.
SEAL_BOUNDARY_ACT = "sealed"

#: Which logs have turned sealed, recorded beside the key — the parallel of
#: `MARKER_FILENAME` for keying. `IntegrityLog(sealed=None)` (the default)
#: reads this to decide whether a log it was not told about is sealed.
SEALED_MARKER_FILENAME = "integrity.sealed"


class IntegrityKeyError(Exception):
    """Refuse by name (I-11): a key is required and absent, a key file is
    unreadable as a key, or an existing key would be overwritten. Never
    confused with `verify()` returning `False` — that is tamper detection;
    this is "the key needed to even ask the question is missing or broken."
    """


class IntegritySealError(Exception):
    """Refuse by name (I-11), for sealing specifically: the `sealed` extra
    (`cryptography`) is not installed, or a sealed log's key is absent.
    Distinct from `IntegrityKeyError` because the two name different fixes
    — `pip install "homestead-affairs[sealed]"` versus `homestead integrity
    init-key` — and a caller catching one should not have to guess which
    applies. Never confused with `verify()` returning `False`: this is
    "cannot even ask the question," not a finding about the log. There is
    **no plaintext fallback** for any of these — a sealed log that cannot be
    unsealed is refused, never silently served as if it were not sealed.
    """


def default_key_path() -> Path:
    return paths.anchors_dir() / KEY_FILENAME


def _decode_key(raw: str, path: Path) -> bytes:
    raw = raw.strip()
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise IntegrityKeyError(
            f"the integrity key at {path} is not valid hex; refusing to use it"
        ) from exc
    if len(key) != KEY_BYTES:
        raise IntegrityKeyError(
            f"the integrity key at {path} is {len(key)} bytes, not {KEY_BYTES}; "
            "refusing to use it"
        )
    return key


def read_key(path: Path | None = None) -> bytes | None:
    """The key at `path` (default `default_key_path()`), or `None` if absent.

    A missing file is not an error — most logs are unkeyed and that is fine.
    A file that exists but is not 64 hex characters IS an error (refused by
    name), because using it anyway would silently produce a chain nothing else
    can ever verify.

    What counts as those 64 characters is `bytes.fromhex`'s answer, not a
    stricter one of our own: surrounding whitespace is stripped, uppercase is
    accepted, and so is whitespace *between* byte pairs — all three name the
    same 32 bytes, and an operator who restored the key by hand from a printed
    copy should not be refused over the case of a letter. Anything that does
    not name exactly 32 bytes is refused. Pinned by test.
    """
    path = path or default_key_path()
    if not path.exists():
        return None
    return _decode_key(path.read_text(encoding="utf-8"), path)


def init_key(path: Path | None = None) -> Path:
    """Create the integrity key: 32 random bytes, hex-encoded, written
    `O_EXCL` so a second call never overwrites the first (there is no escrow —
    Open item 8 — so overwriting would silently orphan whatever was keyed
    under the old one).

    Mode `0o600` on POSIX. Windows has no POSIX permission bits; `os.open`'s
    mode argument is accepted but mostly ignored there, so on Windows this
    relies on the file's ACL inheriting from its parent directory rather than
    on a mode bit — documented in `docs/DECISION-integrity-key-management.md`,
    not silently assumed.
    """
    path = path or default_key_path()
    paths.ensure(path.parent)
    key_hex = secrets.token_hex(KEY_BYTES)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags, 0o600)
    except FileExistsError as exc:
        raise IntegrityKeyError(
            f"something already exists at {path} — a key, or a symlink or "
            "other file standing where one goes; it is never overwritten and "
            "never followed. There is no escrow, so losing a key is the "
            "operator's to manage"
        ) from exc
    try:
        os.write(fd, key_hex.encode("ascii"))
    finally:
        os.close(fd)
    if os.name == "posix":
        os.chmod(path, 0o600)          # belt-and-suspenders against umask
    return path


def default_marker_path() -> Path:
    return paths.anchors_dir() / MARKER_FILENAME


def default_sealed_marker_path() -> Path:
    return paths.anchors_dir() / SEALED_MARKER_FILENAME


def _log_tag(path: Path) -> str:
    """A log's line in the marker: a digest of its resolved path, never the
    path itself. Fixed-width (no escaping question), and the marker discloses
    nothing about what the household keeps or where."""
    return hashlib.sha256(str(Path(path).resolve()).encode("utf-8")).hexdigest()


def _boundary_commitment(boundary_hash: str) -> str:
    """What the marker stores about the boundary row: a commitment to its
    keyed hash, **not** that hash.

    Storing the hash itself would hand a reader a valid head for this log at
    the moment it turned keyed — a bare-hex file publishing exactly the value
    an attacker needs to truncate every keyed line and write a matching
    anchor. Committing to it instead is checkable by anyone who can recompute
    the hash (which needs the key) and useless to anyone who cannot.
    """
    return hashlib.sha256(f"homestead-integrity-boundary:{boundary_hash}".encode()).hexdigest()


def _recorded_boundary(path: Path, *, marker_path: Path | None = None) -> str | None:
    """The commitment recorded when this log turned keyed, or `None` if this
    log has no marker line. `marker_path` defaults to the keyed marker
    (`default_marker_path()`); `IntegrityLog`'s sealed-boundary bookkeeping
    passes `default_sealed_marker_path()` through the same function rather
    than a second copy of it — the shape (a digest of the path, a commitment
    to a boundary row's keyed hash, one line per log) is identical for both.

    **What this closes.** Without it, a forger without the key does not need
    to forge an HMAC at all: they delete the `{"act": "keyed"}` row, re-chain
    the surviving lines with plain SHA-256 and write a bare-hex anchor. A
    verifier *holding the key* then sees a log that never turned keyed and
    reports it clean — the whole gain of keying, undone by a deletion. The
    marker is the second place the turning point is written, so the log alone
    can no longer deny it.

    **What it does not close.** The marker is a file on the same machine, so
    the same hand can delete it (`verify()` then falls back to "this log was
    never keyed" — the pre-E5 threat model for the prefix, honestly). Like the
    anchor it detects accident and a forger who does not know it is there; it
    does not make an on-machine adversary impossible, which F-5 says no
    application can. See `docs/DECISION-integrity-key-management.md` §4a.
    """
    marker = marker_path or default_marker_path()
    if not marker.exists():
        return None
    tag = _log_tag(path)
    for raw in marker.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw.isascii():
            continue        # `compare_digest` on str is ASCII-only; a line we
            #                 did not write is not a line about this log
        head, _, recorded = raw.partition(" ")
        if head and hmac.compare_digest(head, tag):
            return recorded or None
    return None


def _record_boundary(path: Path, boundary_hash: str, *, marker_path: Path | None = None) -> None:
    """Record that `path` turned keyed (or sealed — see `marker_path`) at
    this boundary row. Append-only and `0o600`, beside the key: one line per
    log, `<path digest> <commitment>`.
    """
    marker = marker_path or default_marker_path()
    if _recorded_boundary(path, marker_path=marker) is not None:
        return
    paths.ensure(marker.parent)
    fd = os.open(str(marker), os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    try:
        os.write(fd, f"{_log_tag(path)} {_boundary_commitment(boundary_hash)}\n".encode("ascii"))
    finally:
        os.close(fd)
    if os.name == "posix":
        os.chmod(marker, 0o600)


# One lock per process covers threads. Module-level rather than per-instance,
# because two SealedLog objects over the same path are the realistic case and
# a per-instance lock would not see the other one.
_APPEND_LOCK = threading.Lock()


class Event(str, Enum):
    """What the visible log may say happened. Closed, so argument one cannot
    become the free-text field the content leaks through (F-4)."""

    NOTE_ADDED = "note_added"
    NOTE_REMOVED = "note_removed"
    FACT_VERIFIED = "fact_verified"
    FACT_REJECTED = "fact_rejected"
    ITEM_RESOLVED = "item_resolved"
    ITEM_SNOOZED = "item_snoozed"
    RECORD_ADDED = "record_added"          # a record was entered by the operator
    RECORD_SYNCED = "record_synced"
    DRAFT_SAVED = "draft_saved"
    EXPORTED = "exported"
    LIVING_REPLACED = "living_replaced"    # a forgetting cell overwrote in place (H-8)


def _canonical(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def line_hash(entry: dict[str, Any], key: bytes | None = None) -> str:
    """The hash a following entry carries as its `prev`.

    `key=None` (the default, and the only form every existing caller uses):
    unkeyed and public — anyone who can read the file can compute it, and
    therefore forge a consistent chain. See the class docstring.

    `key=<32 bytes>`: the same canonical bytes, HMAC-SHA256'd instead of bare
    SHA256'd. Forging a consistent chain now requires the key, not just read
    access to the file. Nothing about the unkeyed branch changed — same
    bytes, same digest — so every pre-existing unkeyed log still verifies.
    """
    canonical = _canonical(entry).encode()
    if key is None:
        return hashlib.sha256(canonical).hexdigest()
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


def _boundary_index(lines: list[dict[str, Any]], *, act: str = BOUNDARY_ACT) -> int | None:
    """The index of the `{"act": act}` marker, or `None` if this chain has
    never turned that act. Defaults to `BOUNDARY_ACT` (keying); passing
    `act=SEAL_BOUNDARY_ACT` finds the sealing boundary the same way — the
    sealing search is unaffected by whether a keying boundary exists too,
    since a sealed log's boundary rows are always in `keyed, then sealed`
    order and each is found by its own `act` value independently."""
    for i, entry in enumerate(lines):
        if entry.get("act") == act:
            return i
    return None


def _hash_at(entry: dict[str, Any], idx: int, boundary: int | None, key: bytes | None) -> str:
    """`line_hash` for the entry at position `idx`, keyed or not depending on
    where it falls relative to the boundary — never on whether a key happens
    to be in hand right now. A keyed position without a key refuses by name
    (I-11): returning an unkeyed hash there would silently accept a chain a
    forger built without the key, which is exactly the gap keying exists to
    close.

    A sealed line (`keep/sealed.py`'s ciphertext wrapper, `entry["sealed"]
    == 1`) carries its own contribution to the chain as its `hash` field —
    computed at seal time, over the plaintext, before encryption — so this
    needs no key and no decryption to keep walking the chain (I-27's "chain
    still verifies by hash without decrypting"). Whether that `hash` field
    is *honest* is a stronger question `IntegrityLog.verify()`'s decrypting
    pass answers separately; this function only walks positions.
    """
    if entry.get("sealed") == 1:
        digest = entry.get("hash")
        if not isinstance(digest, str):
            raise ValueError(f"a sealed line at position {idx} has no hash field")
        return digest
    if boundary is not None and idx >= boundary:
        if key is None:
            raise IntegrityKeyError("this log is keyed; the key is absent")
        return line_hash(entry, key)
    return line_hash(entry)


def describe_verification(ok: bool, *, sealed: bool, decrypt: bool) -> str:
    """The three things `IntegrityLog.verify()`'s boolean can mean, spelled
    out — because a sealed log checked with `decrypt=False` proves *less*
    than an ordinary pass and must never be announced identically as "ok"
    (item 3 of the E6 bite: never report a sealed log clean by hashing
    ciphertext alone without saying so). `ok=False` is always "FAILED",
    sealed or not — a broken chain is a broken chain. Only a *passing*
    check on a sealed log, read without decrypting, gets the third answer.
    """
    if not ok:
        return "FAILED"
    if sealed and not decrypt:
        return "chain verified, contents not authenticated"
    return "ok"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ref(parts: Iterable[str]) -> str:
    """Join reference parts into the log's ``ref`` string.

    Each part is validated through `paths.component` — the same validator
    `export._segment` uses — so the two cannot disagree on what a component
    may contain. Before the fix for issue #23 these were two independently
    written checks (`_segment` allowed embedded ``\\n``, this rejected it),
    and the drift turned a rejection into a partial write on the export path.
    """
    parts = [str(p) for p in parts]
    if not parts:
        raise ValueError("a reference needs at least one part")
    for p in parts:
        paths.component(p, name="ref part")
    return "/".join(parts)


class VisibleLog:
    """Operator-readable. References only — never the content of anything."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (paths.logs_dir() / "visible.jsonl")

    def record(self, event: Event, *, ref: tuple[str, ...]) -> None:
        """Record that something happened, and to what.

        `event` must be an `Event`. There is deliberately no parameter for a
        body, a summary, a preview or a note — adding one re-creates F-4, and
        so does widening `event` back to a free string.
        """
        if not isinstance(event, Event):
            raise TypeError(
                f"event must be an Event, not {type(event).__name__} — a free "
                "string here is where note content leaked last time (F-4)"
            )
        paths.ensure(self.path.parent)
        entry = {"at": _now(), "event": event.value, "ref": _ref(ref)}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(entry) + "\n")

    def read(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(x) for x in lines[-limit:] if x.strip()]


class IntegrityLog:
    """Append-only and hash-chained, with an off-file head anchor.

    Read the module docstring for exactly what it catches and what it does not.
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        anchor_path: Path | None = None,
        key: bytes | None = None,
        keyed: bool | None = None,
        sealed: bool | None = None,
    ) -> None:
        """`keyed` controls whether this instance uses the HMAC key, in three
        states — pick one, don't guess from context:

        * `None` (default) — **auto**. Keyed iff `default_key_path()` exists
          and reads as a valid key; otherwise unkeyed. This is why a checkout
          that has never run `homestead integrity init-key` behaves exactly as
          before E5: no key file, no change.
        * `True` — **require** the key. Missing or invalid key file:
          `IntegrityKeyError` at construction, not a silent fall-back to
          unkeyed (I-11).
        * `False` — **force unkeyed**, even if a key file exists. For a caller
          that has a specific reason to read or write the pre-key segment of a
          log without needing the key on hand.

        `key`, if given, is the raw 32-byte key to use directly (skipping the
        file) — the same value `read_key()` would have returned. Mainly for
        tests that want a known key without touching `anchors_dir()`.
        Contradicts `keyed=False` (a key was handed over on purpose) and that
        combination is refused rather than silently resolved either way.

        `sealed` (E6, Phase 4) is the same three-state shape, layered on top
        of keying — sealing uses the same raw key (`keep/sealed.py`'s HKDF
        derives an independent AES subkey from it; there is no second
        secret to lose):

        * `None` (default) — **auto**. Sealed iff `default_sealed_marker_path()`
          records this log's sealing boundary **or** the log itself carries the
          `{"act": "sealed"}` row (`_has_sealed_boundary`) — either witness is
          enough, so deleting the marker file does not turn sealing off.
          Never refuses at construction
          even if the `sealed` extra or the key is missing — a caller that
          only wants `verify(decrypt=False)` (needs the key, via stdlib
          `hmac`, for the keyed scaffolding under any sealing; never the
          `cryptography` extra) must still be able to build this object;
          `append()`/`verify(decrypt=True)`/`read_entries()` check for
          themselves, lazily, only when they would actually touch
          ciphertext. A key-less log cannot be verified at all, sealed or
          not — that is unchanged from E5 and `decrypt` does not alter it.
        * `True` — **require** sealing. Refuses at construction
          (`IntegritySealError`, naming what is missing) if the key is
          absent or the `cryptography` extra is not installed — never a
          silent plaintext fallback (I-11).
        * `False` — **force unsealed**, even with a marker present. For a
          caller with a specific reason to read the pre-seal segment. It is a
          *read-side* escape hatch only: `append()` on a log that carries the
          sealed boundary row refuses by name rather than writing plaintext
          after it (a downgrade), whatever this flag says.

        Unsealing is not offered: nothing in this codebase turns a sealed
        log back to plaintext going forward. See
        `docs/DECISION-integrity-key-management.md`'s Sealing section.
        """
        self.path = path or (paths.logs_dir() / "integrity.jsonl")
        # The anchor defaults to a `.head` file beside the log — unchanged, so
        # every existing caller keeps its behaviour. A caller that wants the
        # head held off the log's own tree (the willow-mcp #280 separation)
        # passes `anchor_path`; `keep/export.py`'s `ledger()` is the one that
        # does, putting it under `paths.anchors_dir()`.
        self.anchor_path = anchor_path or self.path.with_suffix(".head")
        self.key = self._resolve_key(key, keyed)
        self.sealed = self._resolve_sealed(sealed)

    def _resolve_sealed(self, sealed: bool | None) -> bool:
        if sealed is False:
            return False
        if sealed is True:
            self._require_sealing_ready()
            return True
        # sealed is None: auto — see the constructor docstring for why this
        # branch never raises, unlike the other two.
        if _recorded_boundary(self.path, marker_path=default_sealed_marker_path()) is not None:
            return True
        # The marker is a file on the same machine, and deleting it must not
        # be a way to turn sealing off (the E6 audit planted exactly that: with
        # only the marker consulted, `rm anchors/integrity.sealed` made the very
        # next `append()` write plaintext after the sealed boundary, and
        # `verify()` still said ok). The log's own `{"act": "sealed"}` row is
        # the stronger witness — it is chained and keyed, so removing *it*
        # needs the key — so auto-detection reads it too and the two must both
        # be gone before a log stops looking sealed.
        return self._has_sealed_boundary()

    def _has_sealed_boundary(self) -> bool:
        """Whether this log's own lines carry the `{"act": "sealed"}` row.

        Defensive on purpose: a log whose tail is a half-written line from a
        crash must still *construct* (`verify()` is where that becomes a
        `False`), so an unparseable file answers "no boundary found here"
        rather than raising out of `__init__`."""
        try:
            return _boundary_index(self._lines(), act=SEAL_BOUNDARY_ACT) is not None
        except (json.JSONDecodeError, OSError):
            return False

    def _require_sealing_ready(self):
        """The key and the `cryptography` extra, both present, or refuse by
        name (`IntegritySealError`) naming whichever is missing — before any
        I/O. Returns the `sealed` module (imported here, lazily, and nowhere
        else at module scope in this file — I-27) so a caller does not need
        a second import statement."""
        if self.key is None:
            raise IntegritySealError(
                "sealing requires the integrity key, and none is available "
                "to this log — run `homestead integrity init-key` first, or "
                "pass key=... / keyed=True"
            )
        from . import sealed as _sealed_mod

        _sealed_mod.require_available()
        return _sealed_mod

    @staticmethod
    def _resolve_key(key: bytes | None, keyed: bool | None) -> bytes | None:
        if key is not None:
            if keyed is False:
                raise IntegrityKeyError(
                    "an explicit key was given together with keyed=False; "
                    "that is a contradiction, not a choice to resolve"
                )
            if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_BYTES:
                raise IntegrityKeyError(
                    f"an explicit key must be {KEY_BYTES} raw bytes"
                )
            return bytes(key)
        if keyed is False:
            return None
        if keyed is True:
            found = read_key()
            if found is None:
                raise IntegrityKeyError(
                    f"this log requires a key, and none is at "
                    f"{default_key_path()} — run `homestead integrity "
                    "init-key` first, or pass keyed=False if that is the "
                    "intent"
                )
            return found
        return read_key()          # keyed is None: auto — None if no key file

    @property
    def keyed(self) -> bool:
        return self.key is not None

    def _read_anchor(self) -> tuple[str, bool] | None:
        """The stored `(digest, is_keyed)`, or `None` if there is no anchor
        yet. A keyed anchor is written `hmac:<hex>` (item 6) so a reader — the
        CLI included — can say which kind it is without needing the key."""
        if not self.anchor_path.exists():
            return None
        raw = self.anchor_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        if raw.startswith("hmac:"):
            return raw[len("hmac:"):], True
        return raw, False

    def _write_anchor(self, head: str, *, keyed: bool = False) -> None:
        # Ensure the anchor's own parent — it may live in a different tree from
        # the log (anchors_dir()), which append() ensures separately for the log.
        paths.ensure(self.anchor_path.parent)
        text = f"hmac:{head}" if keyed else head
        self.anchor_path.write_text(text + "\n", encoding="utf-8")

    def _lines(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                out.append(json.loads(raw))
        return out

    def head(self) -> str:
        lines = self._lines()
        if not lines:
            return GENESIS
        boundary = _boundary_index(lines)
        return _hash_at(lines[-1], len(lines) - 1, boundary, self.key)

    def read_entries(self, *, decrypt: bool = True) -> Iterable[dict[str, Any]]:
        """Yield each entry this log actually recorded — boundary rows
        (`BOUNDARY_ACT`, `SEAL_BOUNDARY_ACT`) skipped, sealed lines
        decrypted when `decrypt` (the default).

        **The one public door for a log's content (E7).** `sync.
        _already_delivered`, `export`'s own re-reads, and (via a documented
        seam) `homestead_health`'s replacement lookup all went through a bare
        `json.loads` over the file before this had a public name — a sealed
        log's ciphertext wrapper breaks that silently (`entry.get("act")` on
        `{"sealed": 1, ...}` is always `None`; a sealed `living.jsonl`
        answered "never replaced" instead of refusing, `H6-sealed-reader`).
        Every such reader now names this method — I-16's chokepoint idea,
        applied here rather than the record store. `_entries()` is the same
        method under its old name, kept as a deprecated alias for one minor.

        **`decrypt` carries the refusal, the same split `verify()` makes:**

        * `decrypt=True` (default) — the log's actual content. The moment a
          sealed line is reached this requires the key and the
          `cryptography` extra, or `IntegritySealError` by name. A corrupt
          or tampered line raises from wherever `_lines()` or `sealed_mod.
          unseal_line` raises it — entries already yielded stay the intact
          prefix, but the generator never returns normally after, so
          `list(log.read_entries())` **raises, never returns a short list**.
        * `decrypt=False` — the *structural* question `verify(decrypt=
          False)` asks: what this log holds without touching `cryptography`.
          Identical to `decrypt=True` when no sealed lines exist. **For a
          log this instance considers sealed** (`self.sealed`), it refuses
          before yielding a single entry rather than serving the plaintext
          prefix and dropping the rest — a reader that can return short is
          the exact shape the narrowed `test_sealed_log_has_no_public_read_
          method` forbids. A caller who wants the pre-seal segment on
          purpose constructs `IntegrityLog(path, sealed=False)` instead (the
          documented read-side escape hatch) — a different, explicit ask.

        The only way to see fewer entries than the log holds is a refusal.
        """
        if self.sealed and not decrypt:
            raise IntegritySealError(
                "this log is sealed; decrypt=False cannot serve its content "
                "— there is no plaintext-only partial read of a sealed log "
                "(pass decrypt=True, or construct IntegrityLog(sealed=False) "
                "for the pre-seal segment specifically)"
            )
        sealed_mod = None
        for entry in self._lines():
            if entry.get("act") in (BOUNDARY_ACT, SEAL_BOUNDARY_ACT):
                continue
            if entry.get("sealed") == 1:
                if not decrypt:
                    continue        # only reachable via sealed=False on this
                    #                 instance — self.sealed is False there,
                    #                 so the guard above did not already fire
                if self.key is None:
                    raise IntegritySealError(
                        "this log is sealed; the key is absent — sealing "
                        f"requires the key at {default_key_path()}"
                    )
                if sealed_mod is None:
                    from . import sealed as sealed_mod       # lazy import, I-27
                entry = sealed_mod.unseal_line(entry, key=self.key)
            yield entry

    def _entries(self, *args: Any, **kwargs: Any) -> Iterable[dict[str, Any]]:
        """Deprecated alias for `read_entries()` (E7). Every in-package
        caller now spells the public name; this stays for one minor so
        nothing outside this checkout breaks on the rename without warning
        first. Identical yield, one `DeprecationWarning`, no other change —
        see `tests/test_invariants_logs.py::test_entries_alias_warns_once_
        and_yields_identically`.
        """
        warnings.warn(
            "IntegrityLog._entries() is a deprecated alias for "
            "read_entries() and will be removed in a future minor release",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.read_entries(*args, **kwargs)

    def _ensure_boundary(self, fh) -> None:
        """Write the `{"act": "keyed"}` boundary row, once — the first time
        this log is appended to while a key is present. `init-key` itself
        never touches a log; this is where a log actually turns keyed, lazily,
        on its own next write. Idempotent: a log that already has a boundary
        (this call or an earlier one) is left alone, so a mixed log's already
        recorded turning point never moves.
        """
        if _boundary_index(self._lines()) is not None:
            return
        marker = {"act": BOUNDARY_ACT, "at": _now(), "prev": self.head()}
        fh.write(_canonical(marker) + "\n")
        fh.flush()
        boundary_hash = line_hash(marker, self.key)
        self._write_anchor(boundary_hash, keyed=True)
        # The second place the turning point is written, so deleting this row
        # downgrades the log loudly instead of silently (`_recorded_boundary`).
        _record_boundary(self.path, boundary_hash)

    def _ensure_sealed_boundary(self, fh) -> None:
        """Write the `{"act": "sealed"}` boundary row, once — the exact
        parallel of `_ensure_boundary` for keying, called after it (a sealed
        log is keyed first: this row, and the plaintext prefix before it,
        verify by keyed HMAC, never by AES-GCM — a row that says "everything
        from here is ciphertext" cannot itself be the first ciphertext line,
        or a reader could not even find where sealing began). Idempotent.
        """
        if _boundary_index(self._lines(), act=SEAL_BOUNDARY_ACT) is not None:
            return
        marker = {"act": SEAL_BOUNDARY_ACT, "at": _now(), "prev": self.head()}
        fh.write(_canonical(marker) + "\n")
        fh.flush()
        boundary_hash = line_hash(marker, self.key)
        self._write_anchor(boundary_hash, keyed=True)
        _record_boundary(self.path, boundary_hash, marker_path=default_sealed_marker_path())

    def seal(self) -> None:
        """`homestead integrity seal`'s domain call: start sealing this log
        from here on. Requires the key and the `cryptography` extra —
        refused by name (`IntegritySealError`), before writing anything,
        never a partial seal. Ensures the keyed boundary first (sealing
        implies keying; there is no separate sealing secret), then the
        sealed boundary row, then marks this instance so `append()`
        encrypts from now on. Idempotent: a log that already carries the
        sealed boundary row is left alone. **Unsealing is not offered** —
        nothing in this codebase turns a sealed log back to plaintext.
        """
        self._require_sealing_ready()
        paths.ensure(self.path.parent)
        with _APPEND_LOCK:
            with self.path.open("a", encoding="utf-8") as fh:
                if _HAVE_FCNTL:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                try:
                    self._ensure_boundary(fh)
                    self._ensure_sealed_boundary(fh)
                finally:
                    if _HAVE_FCNTL:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        self.sealed = True

    def append(self, entry: dict[str, Any]) -> None:
        """Append one entry, reading the tail and writing under one lock.

        Read-then-write is not atomic, and the consequence is not a lost line
        but a **broken chain**: eight threads appending concurrently wrote all
        160 lines and left 72 duplicate `prev` links, so `verify()` returned
        False — an audit trail that indicts itself. That is
        `nestor/cascade.py:ledger_append`'s documented failure, reproduced here
        before this lock existed.

        Two locks, because there are two kinds of concurrent writer. The
        threading lock covers threads in this process. An advisory file lock
        covers separate processes — the app and an MCP entry point against the
        same log is not exotic — and is best-effort: where `fcntl` is absent the
        threading lock still holds, and a file lock is a lock, not a guarantee
        about other software.

        When `self.key` is set, the first call also writes the boundary row
        (see `_ensure_boundary`) before the entry itself, so every entry this
        call writes from here on is unambiguously on the keyed side. When
        `self.sealed` is set (E6), the same happens one layer further: the
        sealed boundary row is ensured, then the entry itself is encrypted
        (`keep/sealed.py:seal_line`) rather than written plaintext — never a
        silent plaintext fallback if sealing was asked for (I-11).
        """
        paths.ensure(self.path.parent)
        with _APPEND_LOCK:
            with self.path.open("a", encoding="utf-8") as fh:
                if _HAVE_FCNTL:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                try:
                    if self.key is not None:
                        self._ensure_boundary(fh)
                    sealed_mod = None
                    if self.sealed:
                        sealed_mod = self._require_sealing_ready()
                        self._ensure_sealed_boundary(fh)
                    elif self._has_sealed_boundary():
                        # A downgrade, refused by name rather than written.
                        # `IntegrityLog(path, sealed=False)` is a read-side
                        # escape hatch for the pre-seal segment, never a
                        # licence to put a plaintext line *after* the row that
                        # says everything from here is ciphertext — that line
                        # would chain and verify clean, and the content it
                        # leaked to disk would be unrecoverable from the file.
                        raise IntegritySealError(
                            f"{self.path} carries a sealed boundary; appending "
                            "a plaintext line after it would downgrade the log "
                            "— refused (construct without sealed=False, or seal "
                            "a different log)"
                        )
                    plain = dict(entry)
                    plain["at"] = _now()
                    plain["prev"] = self.head()   # re-read inside the lock,
                    #                                after any boundary rows
                    #                                this call just wrote
                    if sealed_mod is not None:
                        line = sealed_mod.seal_line(plain, key=self.key, prev=plain["prev"])
                        head_hash = line["hash"]
                    else:
                        line = plain
                        # The anchor is a separate file, so truncating the
                        # log without also editing this is caught by verify().
                        keyed_now = self.key is not None
                        head_hash = line_hash(plain, self.key) if keyed_now else line_hash(plain)
                    fh.write(_canonical(line) + "\n")
                    fh.flush()
                    self._write_anchor(head_hash, keyed=(self.key is not None))
                finally:
                    if _HAVE_FCNTL:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def verify(self, expected_head: str | None = None, *, decrypt: bool = True) -> bool:
        """Walk the chain and check it against the anchor.

        `expected_head`, if given, wins over the on-disk anchor — it is the only
        check that means anything against someone who can write to this machine,
        because they can edit the anchor too. Pass a head the operator recorded
        off the machine.

        **A downgrade is tamper, not "unkeyed".** A log the marker records as
        keyed (`_recorded_boundary`) must still carry that same boundary row:
        deleting it and re-chaining the survivors with plain SHA-256 is what a
        forger without the key would do, and it is answered with `False` — a
        finding — not with a clean unkeyed verification. "Cannot tell" stays
        reserved for `IntegrityKeyError`. The sealed boundary row (E6) is
        checked the identical way, against `default_sealed_marker_path()`,
        **and** a plaintext line sitting *after* that row is the same finding:
        it chains perfectly and nothing else in this walk would notice it, so
        it is checked for by name.

        **`decrypt` (E6, default `True`).** A sealed line's `hash` field
        (`keep/sealed.py`) lets the `prev`/`hash` chain be walked, and
        checked against the anchor, without touching ciphertext at all —
        that is what `decrypt=False` does, and it never needs the
        `cryptography` extra (only stdlib `hmac`, for the keyed boundary
        rows every sealed log carries — a log with no key at all still
        cannot be verified, `decrypt` or not; that is unchanged from E5).
        It proves the file's *structure* holds together (nothing
        truncated, nothing reordered by an attacker who also controls
        every `hash` field) and **nothing about whether the content is
        genuine**, because `hash` itself is not authenticated by
        anything decrypt=False touches. `decrypt=True` (the default) adds
        that: every sealed line is decrypted and its GCM tag and `hash`
        field checked (`keep/sealed.py:unseal_line`); a failure there is a
        finding (`False`), same as any other tamper — this method never
        reports a sealed log clean by hashing ciphertext alone unless the
        caller explicitly passed `decrypt=False` (see
        `describe_verification`, which puts that distinction into words).
        Missing key or missing extra, with a sealed line actually
        encountered and `decrypt=True`: `IntegritySealError`, "cannot tell,"
        never a silent `False`.

        Every comparison against a hash — the chain link and the final anchor
        or expected head — uses `hmac.compare_digest`, never `==`/`!=`
        (I-11's fail-closed spirit applied to timing, not just to defaults;
        see `tests/test_invariants_integrity_keyed.py`'s AST guard). A keyed
        segment encountered without the key raises `IntegrityKeyError` — that
        is "cannot tell," refused by name, never reported as `False` ("tamper
        found"), which is a different answer to a different question.
        """
        prev = GENESIS
        try:
            lines = self._lines()
        except json.JSONDecodeError:
            return False            # a partial final line from a crash mid-write
        boundary = _boundary_index(lines)
        recorded = _recorded_boundary(self.path)
        if recorded is not None:
            if boundary is None:
                return False        # the boundary row was deleted: a downgrade
            if self.key is not None and not hmac.compare_digest(
                _boundary_commitment(line_hash(lines[boundary], self.key)), recorded
            ):
                return False        # a different boundary row than the one recorded
        seal_boundary = _boundary_index(lines, act=SEAL_BOUNDARY_ACT)
        recorded_seal = _recorded_boundary(self.path, marker_path=default_sealed_marker_path())
        if recorded_seal is not None:
            if seal_boundary is None:
                return False        # the sealed boundary row was deleted: a downgrade
            if self.key is not None and not hmac.compare_digest(
                _boundary_commitment(line_hash(lines[seal_boundary], self.key)), recorded_seal
            ):
                return False        # a different boundary row than the one recorded

        sealed_mod = None
        for i, entry in enumerate(lines):
            prev_field = entry.get("prev")
            if not isinstance(prev_field, str) or not hmac.compare_digest(prev_field, prev):
                return False        # missing/wrong-typed prev is a mismatch, not a crash
            if seal_boundary is not None and i > seal_boundary and entry.get("sealed") != 1:
                # A plaintext line past the sealing boundary is a downgrade,
                # and it chains perfectly — nothing else in this walk would
                # notice it. Found by the E6 audit. `False` (a finding about
                # the log), never "cannot tell": this needs no key to see.
                return False
            if decrypt and entry.get("sealed") == 1:
                if self.key is None:
                    raise IntegritySealError(
                        "this log is sealed; the key is absent — sealing "
                        f"requires the key at {default_key_path()}"
                    )
                if sealed_mod is None:
                    from . import sealed as sealed_mod       # lazy import, I-27
                try:
                    # `unseal_line` itself checks the recovered plaintext's
                    # hash against the line's `hash` field with
                    # `compare_digest` — see `keep/sealed.py`; nothing here
                    # repeats that comparison.
                    sealed_mod.unseal_line(entry, key=self.key)
                except sealed_mod.SealTamperError:
                    return False    # ciphertext, AAD or hash field does not check out
            try:
                prev = _hash_at(entry, i, boundary, self.key)
            except ValueError:
                return False        # a sealed line missing its own hash field: corrupt, not "cannot tell"

        if expected_head is not None:
            return hmac.compare_digest(prev, expected_head)

        anchor = self._read_anchor()
        if anchor is None:
            return True
        anchor_hex, anchor_keyed = anchor
        if anchor_keyed and self.key is None:
            raise IntegrityKeyError(
                f"the anchor at {self.anchor_path} is keyed; the key is absent"
            )
        # truncated, or the final line was rewritten, if this does not match
        return hmac.compare_digest(prev, anchor_hex)
