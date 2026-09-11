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
once and skipped by `_entries()`; unsealed and keyed-only logs are
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

    entries = list(log._entries())
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


# ── readers: sync and export go through _entries(), not a bare json.loads ──

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
    refs = [e["ref"] for e in log._entries() if e.get("act") == "exported"]
    assert refs == ["custody/deadline/primary"]


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
    `_already_delivered` routes through `_entries()`, so the missing extra
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
