"""E6 — Phase 4 sealing (`keep/sealed.py`), behind the optional `sealed`
extra. Wave 6 of `docs/PLAN-affairs-face.md` (decision 6, open item 8):
"keyed HMAC chain first (no dependency), then Phase 4 sealing behind extra
`sealed` (`cryptography`; pure-Python AEAD is not an option)."

Every claim below is the bite's own: `cryptography` is imported lazily,
inside functions, never at module load (I-27) — importing `keep.sealed`
with it blocked still succeeds, and only sealing or unsealing a line fails,
by name, naming the extra; `IntegrityLog(sealed=True)` refuses without the
key or the extra, never a plaintext fallback; a marked-sealed log missing
its key refuses the same way; a round trip (append -> entries -> verify)
holds; a flipped ciphertext byte, and a line moved to another chain
position, both fail `verify()`'s default (decrypting) pass while the
chain-only pass is shown to be fooled by exactly the residual the DECISION
doc names ("chain verified, contents not authenticated"); a truncated
sealed tail fails against the anchor; the sealed boundary row is written
once and skipped by `read_entries()`; unsealed and keyed-only logs are
byte-identical to before this bite; 10,000 sealed lines carry 10,000
distinct nonces; `sync._already_delivered` and `export.ledger()` both work
against a sealed log; the CLI never prints key material or a sealed line's
plaintext, on success or refusal; `--smoke` imports `keep.sealed` even
without the extra.
"""
from __future__ import annotations

import ast
import importlib
import json
import os
import re
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SEALED_SRC = ROOT / "homestead" / "keep" / "sealed.py"
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def keep(home):
    from homestead.keep import logs

    return logs


def _canonical(entry: dict) -> str:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"))


def _write_lines(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(_canonical(r) for r in records) + "\n", encoding="utf-8")


def _block_cryptography(monkeypatch) -> None:
    """Simulate the `sealed` extra's absence, reliably, no matter what an
    earlier test in this process already imported. `sys.modules
    ["cryptography"] = None` alone only blocks a *first-ever* `import
    cryptography...`: once a submodule (`cryptography.exceptions`, say) is
    already cached from a real seal/verify earlier in this process,
    `from cryptography.exceptions import X` finds it directly and never
    re-checks the parent — so every cached `cryptography*` entry has to go
    first, or this monkeypatch quietly stops proving anything."""
    for name in [n for n in list(sys.modules) if n == "cryptography" or n.startswith("cryptography.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, "cryptography", None)


# ── I-27: lazy import — the module loads without cryptography ──────────────

def test_sealed_module_imports_with_cryptography_blocked(monkeypatch):
    """A checkout without the `sealed` extra still imports `keep.sealed` —
    the whole point of a lazy import (I-27), shown by simulating the extra's
    absence regardless of what is actually installed here."""
    _block_cryptography(monkeypatch)
    sys.modules.pop("homestead.keep.sealed", None)
    mod = importlib.import_module("homestead.keep.sealed")
    assert mod.seal_line is not None


def test_i27_sealed_py_never_imports_cryptography_at_module_scope():
    """Static, over the source — the same shape as `test_invariants_fleet.
    py`'s `_toplevel_psycopg`: a top-level `import cryptography` would run
    clean in CI and only fail on a machine without the `sealed` extra."""

    def toplevel(tree) -> bool:
        for node in tree.body:
            if isinstance(node, ast.Import) and any(
                a.name.split(".")[0] == "cryptography" for a in node.names
            ):
                return True
            if (
                isinstance(node, ast.ImportFrom) and node.level == 0
                and (node.module or "").split(".")[0] == "cryptography"
            ):
                return True
        return False

    src = SEALED_SRC.read_text(encoding="utf-8")
    assert not toplevel(ast.parse(src)), "cryptography must be lazy, not top-level (I-27)"
    assert toplevel(ast.parse("import cryptography\n" + src)), (
        "the guard above has never fired until this plant shows it can"
    )


def test_i27_sealed_extra_declared_dependencies_unchanged():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dependencies = ["holidays>=0.102,<1.0"]' in text
    assert 'sealed = ["cryptography>=42,<47"]' in text


# ── refuse by name: the extra, the key, and both together ──────────────────

def test_sealed_true_refuses_by_name_without_the_key(keep, home):
    with pytest.raises(keep.IntegritySealError, match="key"):
        keep.IntegrityLog(sealed=True)


def test_sealed_true_refuses_by_name_without_the_extra(keep, home, monkeypatch):
    keep.init_key()
    _block_cryptography(monkeypatch)
    with pytest.raises(keep.IntegritySealError, match="sealed"):
        keep.IntegrityLog(sealed=True)


def test_marker_says_sealed_but_the_key_is_gone_refuses_by_name(keep, home):
    """Auto-detection (`sealed=None`) itself must not raise, but every
    sealed log is keyed first — the mandatory `{"act": "keyed"}` boundary
    row needs the raw key regardless of `decrypt` — so with the key gone
    entirely there is no verification left to do, chain-only or not; that
    is unchanged from E5 and `decrypt` does not create an exception to it."""
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "a"})
    keep.default_key_path().unlink()

    reopened = keep.IntegrityLog()
    assert reopened.sealed is True          # construction never refuses
    with pytest.raises(keep.IntegritySealError, match="key"):
        reopened.append({"kind": "b"})
    # The one key serves both keying and sealing, so losing it also breaks
    # the ordinary keyed-boundary check `verify()` reaches first — either
    # exception is "cannot tell," never a silent `False` or a plaintext read.
    with pytest.raises((keep.IntegrityKeyError, keep.IntegritySealError), match="key"):
        reopened.verify()
    with pytest.raises((keep.IntegrityKeyError, keep.IntegritySealError), match="key"):
        reopened.verify(decrypt=False)


def test_verify_decrypt_false_needs_the_key_but_never_the_extra(keep, home, monkeypatch):
    """The real value of `decrypt=False`: a household that still has its
    key but has not installed `homestead-affairs[sealed]` can confirm the
    log's structure with stdlib `hmac` alone. `decrypt=True` (the default)
    refuses by name, naming the extra, the moment it reaches a sealed line;
    `decrypt=False` never touches `cryptography` and succeeds."""
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "a"})
    log.append({"kind": "b"})
    assert log.verify() is True

    _block_cryptography(monkeypatch)
    reopened = keep.IntegrityLog()          # construction itself needs no extra
    with pytest.raises(keep.IntegritySealError, match="sealed"):
        reopened.verify()
    assert reopened.verify(decrypt=False) is True


# ── round trip, the boundary row, and byte-identical formats elsewhere ─────

def test_round_trip_append_entries_verify(keep, home):
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"kind": "plain-keyed", "ref": "p1"})
    log.seal()
    log.append({"kind": "secret", "ref": "s1"})
    log.append({"kind": "secret", "ref": "s2"})

    entries = list(log.read_entries())
    assert [e["ref"] for e in entries] == ["p1", "s1", "s2"]
    assert all(e.get("act") not in (keep.BOUNDARY_ACT, keep.SEAL_BOUNDARY_ACT) for e in entries)
    assert log.verify() is True
    assert log.verify(decrypt=False) is True

    ciphertext_lines = [
        json.loads(x) for x in log.path.read_text().splitlines() if '"sealed":1' in x
    ]
    assert len(ciphertext_lines) == 2
    for line in ciphertext_lines:
        assert set(line) == {"sealed", "nonce", "ct", "prev", "hash"}
        assert "s1" not in json.dumps(line) and "s2" not in json.dumps(line)


def test_seal_writes_exactly_one_boundary_row_and_one_marker_line(keep, home):
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "a"})
    lines = [json.loads(x) for x in log.path.read_text().splitlines()]
    boundaries = [e for e in lines if e.get("act") == keep.SEAL_BOUNDARY_ACT]
    assert len(boundaries) == 1

    marker = keep.default_sealed_marker_path()
    assert marker == home / "anchors" / "integrity.sealed"
    assert len(marker.read_text().splitlines()) == 1

    log.append({"kind": "b"})           # idempotent: seal() again changes nothing
    log.seal()
    lines2 = [json.loads(x) for x in log.path.read_text().splitlines()]
    assert len([e for e in lines2 if e.get("act") == keep.SEAL_BOUNDARY_ACT]) == 1
    assert len(marker.read_text().splitlines()) == 1


def test_unsealed_and_keyed_only_logs_are_unchanged_by_this_bite(keep, home):
    """Pins the exact field sets — a caller that never seals must see
    byte-identical behaviour to before E6."""
    log = keep.IntegrityLog(home / "u" / "integrity.jsonl", keyed=False)
    log.append({"kind": "x"})
    line = json.loads(log.path.read_text().splitlines()[0])
    assert set(line) == {"kind", "at", "prev"}
    assert log.sealed is False

    keep.init_key()
    klog = keep.IntegrityLog(home / "k" / "integrity.jsonl")
    klog.append({"kind": "y"})
    klines = [json.loads(x) for x in klog.path.read_text().splitlines()]
    assert klines[0]["act"] == keep.BOUNDARY_ACT and klines[0]["prev"] == "genesis"
    assert set(klines[1]) == {"kind", "at", "prev"}
    assert klog.sealed is False
    assert klog.verify() is True
    assert not keep.default_sealed_marker_path().exists()


# ── tamper: a flipped byte, a moved line, a truncated tail ─────────────────

def test_a_flipped_ciphertext_byte_fails_verify(keep, home):
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "a"})
    log.append({"kind": "b"})
    assert log.verify() is True

    records = [json.loads(x) for x in log.path.read_text().splitlines()]
    ct = bytearray.fromhex(records[-1]["ct"])
    ct[0] ^= 0xFF
    records[-1]["ct"] = ct.hex()
    _write_lines(log.path, records)
    assert log.verify() is False


def test_a_sealed_line_moved_to_another_position_fails_only_when_decrypted(keep, home):
    """The residual `describe_verification` puts into words: relabelling the
    visible `prev`/anchor fields (no key needed) fools the chain-only pass,
    and only decrypting — which authenticates `prev` as AAD — catches that
    the line was sealed under a *different* `prev` than the one it now sits
    behind. This is what "a sealed line cannot be moved" means."""
    pytest.importorskip("cryptography")
    keep.init_key()
    raw_key = keep.read_key()
    log_a = keep.IntegrityLog(home / "a" / "integrity.jsonl", key=raw_key, sealed=True)
    log_b = keep.IntegrityLog(home / "b" / "integrity.jsonl", key=raw_key, sealed=True)
    log_a.append({"kind": "x"})
    log_a.append({"kind": "victim"})
    log_b.append({"kind": "z"})

    victim = json.loads(log_a.path.read_text().splitlines()[-1])
    assert victim.get("sealed") == 1

    b_lines = log_b.path.read_text().splitlines()
    running_prev = json.loads(b_lines[-1])["prev"]

    forged = dict(victim)
    forged["prev"] = running_prev          # retarget the visible link only
    b_lines[-1] = _canonical(forged)
    log_b.path.write_text("\n".join(b_lines) + "\n", encoding="utf-8")
    log_b.anchor_path.write_text(f"hmac:{forged['hash']}\n", encoding="utf-8")

    assert log_b.verify(decrypt=False) is True, (
        "chain-only verification is fooled by a relabelled prev + a matching anchor"
    )
    assert log_b.verify() is False, (
        "decrypting exposes the AAD mismatch: this ciphertext was sealed "
        "under a different prev than the one it now claims"
    )


def test_a_truncated_sealed_tail_fails_against_the_anchor(keep, home):
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "a"})
    log.append({"kind": "b"})
    log.append({"kind": "c"})
    assert log.verify() is True

    lines = log.path.read_text().splitlines()
    log.path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    assert log.verify() is False
    assert log.verify(decrypt=False) is False


def test_a_sealed_line_missing_its_hash_field_fails_rather_than_crashes(keep, home):
    """`decrypt=False` walks a sealed line by its `hash` field alone
    (`_hash_at`); a line an attacker stripped that field from is corruption,
    not "cannot tell" — `verify()` returns `False`, never an unhandled
    `ValueError` out of a CLI command."""
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "a"})
    records = [json.loads(x) for x in log.path.read_text().splitlines()]
    del records[-1]["hash"]
    _write_lines(log.path, records)
    assert log.verify(decrypt=False) is False


# ── the nonce, 10,000 lines over ────────────────────────────────────────────

def test_10000_sealed_lines_carry_10000_distinct_nonces(keep, home):
    pytest.importorskip("cryptography")
    from homestead.keep import sealed

    keep.init_key()
    raw_key = keep.read_key()
    nonces = set()
    prev = "genesis"
    for i in range(10_000):
        line = sealed.seal_line({"kind": "n", "i": i, "prev": prev}, key=raw_key, prev=prev)
        nonces.add(line["nonce"])
        prev = line["hash"]
    assert len(nonces) == 10_000


# ── readers: sync and export go through read_entries(), not a bare json.loads ──

def test_sync_already_delivered_finds_a_prior_delivery_on_a_sealed_log(keep, home):
    pytest.importorskip("cryptography")
    from homestead.keep import sync

    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({
        "act": keep.Event.RECORD_SYNCED.value, "household": "hh-0123456789abcdef",
        "envelope": "env-abc123", "purpose": "sync", "scope": {"matters": ["custody"]},
        "rows": 1, "destination": "d",
    })
    assert sync._already_delivered(log, "env-abc123") is True
    assert sync._already_delivered(log, "env-does-not-exist") is False


def test_export_ledger_works_sealed(keep, home):
    pytest.importorskip("cryptography")
    from homestead.keep import export

    keep.init_key()
    export.ledger().seal()
    log = export.ledger()
    assert log.sealed is True
    log.append({"act": "exported", "ref": "custody/deadline/primary"})
    assert log.verify() is True
    refs = [e["ref"] for e in log.read_entries() if e.get("act") == "exported"]
    assert refs == ["custody/deadline/primary"]


# ── E7: read_entries() — the public reader that never returns short ────────
#
# `_entries()` had every one of these properties already; this bite gave it
# a public name (`read_entries`) and, in the same stroke, closed the one gap
# a public name could not be allowed to inherit: `decrypt=False` used to
# walk past a sealed line with a bare `continue`, so it quietly returned the
# plaintext prefix and dropped the rest — a short answer offered as if it
# were the whole log. These tests are `test_sealed_log_has_no_public_read_
# method`'s narrowed property, made concrete against the real reader.

def test_read_entries_on_a_sealed_log_yields_every_row_with_key_and_extra(keep, home):
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"kind": "plain", "ref": "p1"})
    log.seal()
    log.append({"kind": "secret", "ref": "s1"})
    log.append({"kind": "secret", "ref": "s2"})

    refs = [e["ref"] for e in log.read_entries()]
    assert refs == ["p1", "s1", "s2"]


def test_read_entries_on_a_sealed_log_without_the_key_refuses_by_name(keep, home):
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "secret", "ref": "s1"})

    (home / "anchors" / "integrity.key").unlink()
    reopened = keep.IntegrityLog()          # construction itself needs no key
    with pytest.raises(keep.IntegritySealError, match="key"):
        list(reopened.read_entries())


def test_read_entries_on_a_sealed_log_without_the_extra_refuses_by_name(keep, home, monkeypatch):
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "secret", "ref": "s1"})

    _block_cryptography(monkeypatch)
    reopened = keep.IntegrityLog()          # construction itself needs no extra
    with pytest.raises(keep.IntegritySealError, match="sealed"):
        list(reopened.read_entries())


def test_read_entries_on_a_truncated_sealed_tail_raises_never_returns_short(keep, home):
    """The pin: `list(log.read_entries())` raises, and does not return a
    short list. Entries before the corrupted line are yielded first (a
    generator, so the intact prefix is real work already done) — but the
    caller iterating it (here, `list()`) never gets a completed result back
    to mistake for the whole log; the exception is what it gets instead."""
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"kind": "plain", "ref": "p1"})
    log.seal()
    log.append({"kind": "secret", "ref": "s1"})
    log.append({"kind": "secret", "ref": "s2"})

    lines = [json.loads(x) for x in log.path.read_text(encoding="utf-8").splitlines()]
    tail = lines[-1]
    assert tail.get("sealed") == 1
    tail["ct"] = ("0" if tail["ct"][0] != "0" else "1") + tail["ct"][1:]   # flip a ciphertext byte
    _write_lines(log.path, lines)

    from homestead.keep.sealed import SealTamperError

    reopened = keep.IntegrityLog()
    got = []
    with pytest.raises(SealTamperError):
        for entry in reopened.read_entries():
            got.append(entry)
    assert [e["ref"] for e in got] == ["p1", "s1"]     # exactly the intact prefix

    with pytest.raises(SealTamperError):
        list(keep.IntegrityLog().read_entries())       # never returns, on retry either


def test_read_entries_decrypt_false_on_a_sealed_log_refuses_before_yielding(keep, home):
    """The gap this bite closes. Before E7, `decrypt=False` walked past a
    sealed line with a bare `continue` and returned the plaintext prefix —
    a short, honest-looking answer that was in fact missing every sealed
    row. `read_entries(decrypt=False)` on a log this instance considers
    sealed now refuses immediately, before a single entry is yielded, so a
    caller cannot iterate partway and stop believing it saw everything."""
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"kind": "plain", "ref": "p1"})
    log.seal()
    log.append({"kind": "secret", "ref": "s1"})

    gen = log.read_entries(decrypt=False)
    with pytest.raises(keep.IntegritySealError, match="decrypt"):
        next(gen)                          # not even the plaintext prefix comes out


def test_read_entries_decrypt_false_on_an_unsealed_or_keyed_only_log_is_unchanged(keep, home):
    """No sealed lines exist, so there is nothing for `decrypt` to differ
    over — `decrypt=False` behaves exactly like the default."""
    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"kind": "keyed-only", "ref": "k1"})
    log.append({"kind": "keyed-only", "ref": "k2"})

    assert [e["ref"] for e in log.read_entries(decrypt=False)] == \
        [e["ref"] for e in log.read_entries(decrypt=True)] == ["k1", "k2"]


def test_entries_alias_warns_once_and_yields_identically(keep, home):
    """`_entries()` stays for one minor, unchanged in behaviour, so nothing
    outside this checkout breaks on the rename without warning first."""
    log = keep.IntegrityLog()
    log.append({"kind": "a", "ref": "r1"})
    log.append({"kind": "b", "ref": "r2"})

    with pytest.warns(DeprecationWarning, match="read_entries"):
        via_alias = list(log._entries())
    via_public = list(log.read_entries())
    assert via_alias == via_public


# ── the CLI: `seal`, and never a key or a sealed line's plaintext ──────────

def _run_cli(*args, env):
    return subprocess.run([sys.executable, "-m", "homestead.app", *args],
                           capture_output=True, text=True, env=env)


def _cli_env(home: Path) -> dict:
    return dict(os.environ, HOMESTEAD_HOME=str(home))


def test_seal_and_verify_cli_never_print_key_material_or_a_sealed_lines_plaintext(home):
    pytest.importorskip("cryptography")
    env = _cli_env(home)
    from homestead.keep import export

    assert _run_cli("integrity", "init-key", env=env).returncode == 0

    secret = "TOTALLY-SECRET-MEDICAL-CONTENT"
    export.ledger().append({"kind": secret})

    sealed = _run_cli("integrity", "seal", env=env)
    assert sealed.returncode == 0, sealed.stderr
    assert not HEX64.search(sealed.stdout) and not HEX64.search(sealed.stderr)

    export.ledger().append({"kind": secret})   # now a sealed line carrying it

    ok = _run_cli("integrity", "verify", env=env)
    assert ok.returncode == 0 and "sealed" in ok.stdout
    assert secret not in ok.stdout and secret not in ok.stderr
    assert not HEX64.search(ok.stdout) and not HEX64.search(ok.stderr)

    (home / "anchors" / "integrity.key").unlink()
    refused = _run_cli("integrity", "verify", env=env)
    assert refused.returncode == 3 and "refused" in refused.stderr
    assert secret not in refused.stdout and secret not in refused.stderr
    assert not HEX64.search(refused.stdout) and not HEX64.search(refused.stderr)


def test_seal_cli_usage_and_refusal_exit_codes(home):
    env = _cli_env(home)
    assert _run_cli("integrity", "seal", "extra", "args", env=env).returncode == 2
    # no key yet: seal refuses by name (3), never silently writing plaintext on
    r = _run_cli("integrity", "seal", env=env)
    assert r.returncode == 3 and "refused" in r.stderr


# ── --smoke imports keep.sealed even without the extra ─────────────────────

def test_smoke_imports_sealed_module_even_without_cryptography(home):
    """A fresh interpreter, not this test process: `homestead.keep` may
    already hold a live `sealed` attribute from an earlier test in this
    file, and `from package import submodule` is free to reuse that
    attribute without re-touching `sys.modules` — checking `sys.modules`
    in-process would then pass or fail on an import-cache accident, not on
    what `--smoke` actually names. A subprocess has no such history."""
    script = (
        "import sys\n"
        "sys.modules['cryptography'] = None\n"
        "from homestead.app.__main__ import main\n"
        "rc = main(['--smoke'])\n"
        "assert rc == 0, rc\n"
        "assert 'homestead.keep.sealed' in sys.modules, sorted(sys.modules)\n"
        "print('sealed-import-check-ok')\n"
    )
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                        env=_cli_env(home))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "sealed-import-check-ok" in r.stdout


# ── the downgrade: a plaintext line after the sealed boundary (E6 audit) ────
#
# The three tests below were planted by the E6 audit and all three failed
# before the fix beside them: sealing could be turned off by asking for it
# (`sealed=False`), by deleting one sidecar file, or by an attacker simply
# writing a well-chained plaintext line onto the end. Each left the content
# it appended in the clear on disk and left `verify()` saying "ok".

def test_sealed_false_cannot_append_plaintext_after_the_sealed_boundary(keep, home):
    """`sealed=False` is a read-side escape hatch for the pre-seal segment,
    never a licence to write plaintext after the row that says everything
    from here is ciphertext. Before the fix this appended, the secret hit
    the disk in the clear, and `verify()` returned `True`."""
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "s1"})

    down = keep.IntegrityLog(sealed=False)
    assert down.sealed is False
    with pytest.raises(keep.IntegritySealError, match="downgrade"):
        down.append({"kind": "PLAINTEXT-AFTER-SEAL"})
    assert "PLAINTEXT-AFTER-SEAL" not in log.path.read_text(encoding="utf-8")
    assert keep.IntegrityLog().verify() is True


def test_deleting_the_sealed_marker_does_not_downgrade_the_log(keep, home):
    """`anchors/integrity.sealed` is a file on the same machine, so the same
    hand can delete it. The log's own `{"act": "sealed"}` row is chained and
    keyed — removing *that* needs the key — so auto-detection reads both and
    one deletion no longer turns sealing off. Before the fix, `rm` on the
    marker made the very next `append()` write plaintext."""
    pytest.importorskip("cryptography")
    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "s1"})

    keep.default_sealed_marker_path().unlink()
    reopened = keep.IntegrityLog()
    assert reopened.sealed is True, "the log's own boundary row still says sealed"
    reopened.append({"kind": "STILL-SECRET"})
    assert "STILL-SECRET" not in log.path.read_text(encoding="utf-8")
    assert keep.IntegrityLog().verify() is True


def test_verify_rejects_a_plaintext_line_after_the_sealed_boundary(keep, home):
    """The same downgrade written straight onto the file by someone holding
    the key — correctly chained, matching anchor, and therefore invisible to
    every other check `verify()` makes. It is a finding (`False`), not
    "cannot tell", because spotting it needs no key at all."""
    pytest.importorskip("cryptography")
    keep.init_key()
    raw_key = keep.read_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"kind": "s1"})
    assert log.verify() is True

    records = [json.loads(x) for x in log.path.read_text(encoding="utf-8").splitlines()]
    forged = {"kind": "PLAINTEXT-AFTER-SEAL", "at": "2026-09-11T00:00:00+00:00",
              "prev": records[-1]["hash"]}
    records.append(forged)
    _write_lines(log.path, records)
    log.anchor_path.write_text(
        f"hmac:{keep.line_hash(forged, raw_key)}\n", encoding="utf-8")

    assert keep.IntegrityLog().verify() is False
    assert keep.IntegrityLog().verify(decrypt=False) is False


# ── sync, without the extra: refuse by name, never "not delivered" ──────────

def test_sync_on_a_sealed_log_without_the_extra_refuses_by_name(keep, home, monkeypatch):
    """The answer that must never come back is `False` — "this envelope was
    not delivered" — for a log whose delivery row is simply unreadable here.
    `_already_delivered` routes through `read_entries()`, so the missing extra
    surfaces as `IntegritySealError` (I-11) and `deliver` cannot send a
    second copy on the strength of a read that never happened."""
    pytest.importorskip("cryptography")
    from homestead.keep import sync

    keep.init_key()
    log = keep.IntegrityLog()
    log.seal()
    log.append({"act": keep.Event.RECORD_SYNCED.value, "envelope": "env-abc123"})
    assert sync._already_delivered(log, "env-abc123") is True

    _block_cryptography(monkeypatch)
    reopened = keep.IntegrityLog()
    with pytest.raises(keep.IntegritySealError, match="sealed"):
        sync._already_delivered(reopened, "env-abc123")


# ── the sealed line's `hash` field is always an HMAC, never a plain digest ──

def test_seal_line_refuses_a_missing_or_short_key_rather_than_publishing_a_digest(keep, home):
    """A sealed line's `hash` rides beside the ciphertext in the clear. Keyed
    it is an HMAC and says nothing; unkeyed it is a public SHA-256 of the
    plaintext, and ledger rows are low-entropy enough (`{"act":
    "record_synced", ...}` shapes) that a dictionary attack recovers them —
    the encryption defeated without touching AES. So the key is required
    where the hash is computed, not only by `IntegrityLog` upstream."""
    pytest.importorskip("cryptography")
    from homestead.keep import sealed

    keep.init_key()
    raw_key = keep.read_key()
    entry = {"act": "record_synced", "envelope": "env-abc123", "prev": "genesis"}
    for bad in (None, b"", b"short", raw_key.hex()):
        with pytest.raises(keep.IntegritySealError, match="key"):
            sealed.seal_line(entry, key=bad, prev="genesis")
        with pytest.raises(keep.IntegritySealError, match="key"):
            sealed.unseal_line({"nonce": "00" * 12, "ct": "00" * 32,
                                "prev": "genesis", "hash": ""}, key=bad)

    line = sealed.seal_line(entry, key=raw_key, prev="genesis")
    assert line["hash"] == keep.line_hash(entry, raw_key)
    assert line["hash"] != keep.line_hash(entry), "an unkeyed digest is an oracle"
    assert len(bytes.fromhex(line["nonce"])) == sealed.NONCE_BYTES == 12


# ── CI actually runs both legs ──────────────────────────────────────────────

def test_ci_runs_one_leg_with_the_sealed_extra_and_one_without():
    """A skip leg that never runs proves nothing. `tests/
    test_invariants_sealed.py` is half `importorskip("cryptography")`, so a
    CI that installs the extra nowhere would be green on encryption that had
    never executed — and one that installed it everywhere would never
    exercise the refusal path. Both legs are asserted to exist, and the
    aggregate `test` gate is asserted to wait on the new one (a job branch
    protection does not require is a job that cannot fail a merge)."""
    yaml = pytest.importorskip("yaml")
    jobs = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())["jobs"]

    def installs(job) -> str:
        return " ".join(str(s.get("run", "")) for s in jobs[job].get("steps", []))

    with_extra = [j for j in jobs if "[sealed]" in installs(j)]
    assert with_extra, "no CI leg installs the sealed extra"
    assert "sealed" not in installs("invariants"), (
        "the cold `invariants` matrix is the without-the-extra leg (I-27)"
    )
    assert set(with_extra) <= set(jobs["test"]["needs"]), (
        "a leg the aggregate `test` gate does not need cannot block a merge"
    )


# ── E7 audit: the short-answer property, adversarially ─────────────────────
#
# The narrowed `test_sealed_log_has_no_public_read_method` claims something
# about *every* public reader, not just `read_entries()`. These make that
# claim concrete: each public reader is put in front of a sealed log in each
# of the four states a reader can meet one, and the answer is classified.
# Only three answers are allowed — raise, a hash (not content), or a `False`
# finding. A *complete-looking short list of content* is the defect, and it
# is what two of these found.


def _sealed_log(keep, *, plain: int = 1, secret: int = 2):
    """A sealed log with real rows either side of the boundary."""
    keep.init_key()
    log = keep.IntegrityLog()
    for i in range(plain):
        log.append({"kind": "plain", "ref": f"p{i + 1}"})
    log.seal()
    for i in range(secret):
        log.append({"kind": "secret", "ref": f"s{i + 1}"})
    return log


def _outcome(fn):
    """`("raised", ExcName)` or `("returned", value)` — the classifier the
    table below reads."""
    try:
        return "returned", fn()
    except Exception as exc:                       # noqa: BLE001 - classifying
        return "raised", type(exc).__name__


def _reader_table(keep, path):
    """Every public reader on `IntegrityLog`, by the name a caller spells."""
    return {
        "read_entries()":
            lambda: [e["ref"] for e in keep.IntegrityLog(path).read_entries()],
        "read_entries(decrypt=False)":
            lambda: [e["ref"] for e in keep.IntegrityLog(path).read_entries(decrypt=False)],
        "IntegrityLog(sealed=False).read_entries()":
            lambda: [e["ref"] for e in keep.IntegrityLog(path, sealed=False).read_entries()],
        "IntegrityLog(sealed=False).read_entries(decrypt=False)":
            lambda: [e["ref"] for e in
                     keep.IntegrityLog(path, sealed=False).read_entries(decrypt=False)],
        "_entries() alias":
            lambda: [e["ref"] for e in keep.IntegrityLog(path)._entries()],
        "verify()": lambda: keep.IntegrityLog(path).verify(),
        "verify(decrypt=False)": lambda: keep.IntegrityLog(path).verify(decrypt=False),
        "head()": lambda: keep.IntegrityLog(path).head(),
    }


def test_no_public_reader_answers_a_sealed_log_short(keep, home):
    """The table. Every public reader on `IntegrityLog`, against a sealed
    log in each of the four states it can be met in, must raise, hand back a
    hash, or report a `False` finding — never a short list of content that
    reads as the whole log.

    `head()` returning the last hash of a truncated file is fine: it is a
    hash, not content, and it is what an operator compares against the head
    they wrote down. `verify()` returning `False` is fine: that is the
    finding. What is not fine is `read_entries()` handing back two of three
    rows and returning normally, which is what a truncated tail used to get
    (fixed with `_require_whole`), and what `IntegrityLog(sealed=False).
    read_entries(decrypt=False)` used to get on any sealed log at all (fixed
    by asking the file, not the constructor argument). Both are planted
    individually below; this is the sweep that says nothing else does it
    either."""
    pytest.importorskip("cryptography")
    log = _sealed_log(keep)
    path = log.path
    full = ["p1", "s1", "s2"]
    assert [e["ref"] for e in log.read_entries()] == full      # the control

    def check(state: str):
        for label, call in _reader_table(keep, path).items():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                how, what = _outcome(call)
            if how == "raised":
                continue                          # a refusal is always fine
            if "entries" in label:
                assert what == full, (
                    f"{state}: {label} returned {what!r} — content short of "
                    f"{full!r}, offered as if it were the whole log"
                )
            else:
                assert isinstance(what, (bool, str)), (
                    f"{state}: {label} returned {what!r} — a reader that does "
                    "not hand back content handed back some"
                )

    check("intact")

    intact = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(intact[:-1]) + "\n", encoding="utf-8")
    check("truncated tail")

    path.write_text("\n".join(intact) + "\n{not json\n", encoding="utf-8")
    check("garbage line")

    path.write_text("\n".join(intact) + "\n", encoding="utf-8")
    (home / "anchors" / "integrity.key").unlink()
    check("key deleted")


def test_no_public_reader_answers_short_without_the_extra(keep, home, monkeypatch):
    """The same table, in the state the `sealed` extra is simply not
    installed — the leg the CI runs without `[sealed]`, and the one where a
    plaintext fallback would be cheapest to write by accident."""
    pytest.importorskip("cryptography")
    log = _sealed_log(keep)
    path = log.path
    _block_cryptography(monkeypatch)

    for label, call in {
        "read_entries()": lambda: list(keep.IntegrityLog(path).read_entries()),
        "read_entries(decrypt=False)":
            lambda: list(keep.IntegrityLog(path).read_entries(decrypt=False)),
        "IntegrityLog(sealed=False).read_entries()":
            lambda: list(keep.IntegrityLog(path, sealed=False).read_entries()),
        "IntegrityLog(sealed=False).read_entries(decrypt=False)":
            lambda: list(keep.IntegrityLog(path, sealed=False).read_entries(decrypt=False)),
    }.items():
        how, what = _outcome(call)
        assert how == "raised", (
            f"without the extra, {label} returned {what!r} instead of "
            "refusing — a plaintext fallback by another name"
        )


def test_sealed_false_does_not_buy_a_plaintext_prefix_of_a_sealed_log(keep, home):
    """The plant (E7 audit). `sealed=False` is documented as a *read-side*
    escape hatch, and before this fix it was exactly that: on a log whose
    file carries the sealed boundary row, `IntegrityLog(path, sealed=False).
    read_entries(decrypt=False)` returned the pre-seal plaintext rows and
    stopped, with nothing in the return value saying the rest existed. The
    guard the bite narrowed forbids precisely that answer — and it was one
    constructor argument away from every caller, key or no key.

    E6's audit made `append()` read the file's own boundary row rather than
    the constructor argument; this is the same ruling on the read side."""
    pytest.importorskip("cryptography")
    log = _sealed_log(keep)

    for kwargs in ({"sealed": False},
                   {"sealed": False, "keyed": False},
                   {"sealed": False, "key": None}):
        reopened = keep.IntegrityLog(log.path, **kwargs)
        assert reopened.sealed is False              # the argument is honoured
        with pytest.raises(keep.IntegritySealError, match="sealed=False"):
            list(reopened.read_entries(decrypt=False))

    # …and with the key in hand, `decrypt=True` still serves the whole log:
    # the escape hatch was never about hiding rows from a reader who can
    # decrypt them.
    assert [e["ref"] for e in
            keep.IntegrityLog(log.path, sealed=False).read_entries()] == ["p1", "s1", "s2"]


def test_sealed_false_refuses_even_with_the_sealed_marker_deleted(keep, home):
    """Both witnesses, not one. Deleting `anchors/integrity.sealed` was E6's
    downgrade plant; `read_entries()` must not be the route that reopens it,
    so the refusal reads the log's own `{"act": "sealed"}` row too."""
    pytest.importorskip("cryptography")
    log = _sealed_log(keep)
    keep.default_sealed_marker_path().unlink()

    with pytest.raises(keep.IntegritySealError):
        list(keep.IntegrityLog(log.path, sealed=False).read_entries(decrypt=False))


def test_a_hand_built_sealed_line_with_no_witness_still_refuses(keep, home):
    """Neither marker nor boundary row, one sealed line: the last way a
    `decrypt=False` walk could silently skip content. It refuses instead."""
    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"kind": "plain", "ref": "p1"})
    lines = [json.loads(x) for x in log.path.read_text(encoding="utf-8").splitlines()]
    lines.append({"sealed": 1, "prev": "x", "hash": "y", "ct": "zz", "n": "nn"})
    _write_lines(log.path, lines)

    with pytest.raises(keep.IntegritySealError, match="sealed line"):
        list(keep.IntegrityLog(log.path).read_entries(decrypt=False))


def test_read_entries_refuses_a_truncated_log_instead_of_returning_short(keep, home):
    """The plant (E7 audit). Chopping the last line off a log leaves every
    survivor chaining and decrypting perfectly — the anchor is the only
    witness that there were more. Before this fix `read_entries()` walked the
    survivors and *returned*, so a caller got a complete-looking two-row
    answer about a three-row log: `H6-sealed-reader`'s "never replaced" with
    a different first step. It now refuses by name."""
    pytest.importorskip("cryptography")
    log = _sealed_log(keep)
    assert [e["ref"] for e in log.read_entries()] == ["p1", "s1", "s2"]

    lines = log.path.read_text(encoding="utf-8").splitlines()
    log.path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

    reopened = keep.IntegrityLog(log.path)
    with pytest.raises(keep.IntegrityIncompleteError, match="anchor"):
        list(reopened.read_entries())
    assert reopened.verify() is False           # the same file, as a finding
    assert isinstance(reopened.head(), str)     # a hash is not content


def test_truncation_refusal_holds_for_an_unsealed_log_too(keep, home):
    """Nothing about this is sealing-specific — an unsealed, unkeyed log is
    the cheapest thing in the repo to truncate, and `read_entries()` is now
    the reader health's seam calls on `living.jsonl`."""
    log = keep.IntegrityLog(keyed=False)
    log.append({"kind": "a", "ref": "r1"})
    log.append({"kind": "b", "ref": "r2"})
    lines = log.path.read_text(encoding="utf-8").splitlines()
    log.path.write_text(lines[0] + "\n", encoding="utf-8")

    with pytest.raises(keep.IntegrityIncompleteError):
        list(keep.IntegrityLog(log.path, keyed=False).read_entries())


def test_a_log_with_no_anchor_still_reads(keep, home):
    """No anchor, no claim about length — the same posture `verify()` takes
    (`anchor is None` -> `True`). The completeness check must not turn a log
    nobody ever anchored into an unreadable one."""
    log = keep.IntegrityLog(keyed=False)
    log.append({"kind": "a", "ref": "r1"})
    log.anchor_path.unlink()
    assert [e["ref"] for e in keep.IntegrityLog(log.path, keyed=False).read_entries()] == ["r1"]


def test_sync_on_a_truncated_ledger_refuses_rather_than_delivering_twice(keep, home):
    """What the truncation refusal is actually worth, at the one seam that
    reads this log to decide whether to act. `_already_delivered` answering
    `False` about a ledger whose `record_synced` row was chopped off is a
    second delivery of the same envelope — the exactly-once property sync
    exists to hold. Before the E7 audit's `_require_whole`, that is what it
    answered."""
    from homestead.keep import sync

    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"act": keep.Event.RECORD_SYNCED.value, "envelope": "env-abc123"})
    assert sync._already_delivered(log, "env-abc123") is True

    lines = log.path.read_text(encoding="utf-8").splitlines()
    log.path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

    with pytest.raises(keep.IntegrityIncompleteError):
        sync._already_delivered(keep.IntegrityLog(log.path), "env-abc123")
