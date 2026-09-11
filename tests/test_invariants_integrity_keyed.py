"""E5 — an optional HMAC key closes the gap `logs.py`'s own docstring names:
"An on-machine anchor detects accident, not an adversary — there is no
location on this machine the writer cannot reach," because an unkeyed
`line_hash` is a public SHA-256 anyone who can edit the log can also
recompute. Wave 5 of `docs/PLAN-affairs-face.md` (decision 6, open item 8):
"keyed HMAC chain first (no dependency), then Phase 4 sealing... no escrow."

Every claim below is the plan's own bullet: a key at
`anchors_dir()/integrity.key`, 32 random bytes hex-encoded, `O_EXCL`, mode
0600 on POSIX, made by `homestead integrity init-key`, never overwritten;
`IntegrityLog(key=..., keyed=...)` with `None`/`True`/`False`; the keyed line
hash is `hmac.new(key, <the unkeyed bytes>, sha256)`; unkeyed legacy logs
still verify unchanged; a keyed log verified without the key refuses by name,
never "corrupt"; a mixed log records a `{"act": "keyed"}` boundary row, and a
forged line at the boundary fails; `verify()` uses `hmac.compare_digest`
everywhere, planted; the forged-chain-plus-anchor attack now fails keyed and
still succeeds unkeyed — the gain, stated as a test; the CLI never prints key
material; the anchor is `hmac:<hex>` for a keyed log; no new dependency
(I-27); `--smoke` still imports; `export.ledger()` works keyed and unkeyed.
"""
from __future__ import annotations

import ast
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def keep(home):
    from homestead.keep import logs

    return logs


def _canonical(entry: dict) -> bytes:
    return json.dumps(entry, sort_keys=True, separators=(",", ":")).encode()


# ── the key file ────────────────────────────────────────────────────────────

def test_init_key_writes_64_hex_chars_at_the_documented_path(keep, home):
    path = keep.init_key()
    assert path == home / "anchors" / "integrity.key"
    raw = path.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"[0-9a-f]{64}", raw), raw
    assert bytes.fromhex(raw)
    key = keep.read_key()
    assert key == bytes.fromhex(raw) and len(key) == 32


def test_a_second_init_key_refuses_by_name_and_never_overwrites(keep, home):
    path = keep.init_key()
    original = path.read_bytes()
    with pytest.raises(keep.IntegrityKeyError, match="already exists"):
        keep.init_key()
    assert path.read_bytes() == original


def test_init_key_is_0600_on_posix(keep, home):
    if os.name != "posix":
        pytest.skip("mode bits are POSIX-only; see the DECISION doc's Windows section")
    path = keep.init_key()
    assert (path.stat().st_mode & 0o777) == 0o600


def test_init_key_o_excl_race_exactly_one_writer_wins(keep, home):
    """Two calls racing for the same path: O_EXCL means the loser gets
    `FileExistsError` (wrapped `IntegrityKeyError`), not a torn/doubled
    write, and the file that lands is a single valid 64-hex key."""
    path = keep.default_key_path()
    results = []

    def attempt():
        try:
            keep.init_key(path)
            results.append("won")
        except keep.IntegrityKeyError:
            results.append("lost")

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["lost", "won"]
    assert re.fullmatch(r"[0-9a-f]{64}", path.read_text(encoding="utf-8").strip())


def test_a_key_file_with_wrong_length_or_bad_hex_is_refused_by_name(keep, home):
    path = keep.default_key_path()
    path.parent.mkdir(parents=True)
    path.write_text("ab" * 16 + "\n")              # 16 bytes, not 32
    with pytest.raises(keep.IntegrityKeyError, match="not 32|32 bytes"):
        keep.read_key()
    path.write_text("this is not hex at all\n")
    with pytest.raises(keep.IntegrityKeyError, match="hex"):
        keep.read_key()


# ── the three-state `keyed` knob, and the keyed line hash ──────────────────

def test_auto_is_unkeyed_with_no_key_file_keyed_once_one_exists(keep, home):
    assert keep.read_key() is None
    log = keep.IntegrityLog()
    assert log.keyed is False
    log.append({"kind": "a"})
    assert log.verify() is True

    keep.init_key()
    assert keep.IntegrityLog().keyed is True


def test_keyed_true_requires_the_key_keyed_false_forces_unkeyed(keep, home):
    with pytest.raises(keep.IntegrityKeyError, match="init-key|key"):
        keep.IntegrityLog(keyed=True)
    keep.init_key()
    assert keep.IntegrityLog(keyed=True).keyed is True
    assert keep.IntegrityLog(keyed=False).keyed is False


def test_explicit_key_bytes_bypasses_the_file_a_wrong_key_just_fails(keep, home):
    raw_key = b"\x01" * 32
    log = keep.IntegrityLog(key=raw_key)
    assert log.keyed is True
    log.append({"kind": "a"})
    assert log.verify() is True
    other = keep.IntegrityLog(log.path, anchor_path=log.anchor_path, key=b"\x02" * 32)
    assert other.verify() is False           # wrong key: a mismatch, not a raise
    with pytest.raises(keep.IntegrityKeyError):
        keep.IntegrityLog(key=b"\x00" * 32, keyed=False)   # contradiction


def test_keyed_line_hash_is_hmac_sha256_of_the_same_bytes(keep, home):
    entry = {"kind": "verification", "ref": "a", "prev": "genesis", "at": "t"}
    key = b"\x07" * 32
    assert keep.line_hash(entry, key) == hmac.new(key, _canonical(entry), hashlib.sha256).hexdigest()
    assert keep.line_hash(entry) == hashlib.sha256(_canonical(entry)).hexdigest()
    assert keep.line_hash(entry) != keep.line_hash(entry, key)


# ── legacy unkeyed logs still verify, unchanged ─────────────────────────────

def test_unkeyed_legacy_log_verifies_under_keyed_false_and_under_auto(keep, home):
    log = keep.IntegrityLog()
    log.append({"kind": "a"})
    log.append({"kind": "b"})
    assert keep.IntegrityLog(keyed=False).verify() is True
    assert keep.IntegrityLog().verify() is True    # auto, no key file


def test_unkeyed_log_on_disk_line_format_is_byte_identical_to_before(keep, home):
    """The sibling sync bite reads `head()`/appends through this class with no
    idea keying exists. An unkeyed line's shape may not change."""
    log = keep.IntegrityLog()
    log.append({"kind": "verification", "ref": "x"})
    line = json.loads(log.path.read_text().splitlines()[0])
    assert set(line) == {"kind", "ref", "at", "prev"}
    assert line["prev"] == "genesis" and "act" not in line


# ── a keyed log/anchor without the key refuses by name, never "corrupt" ────

def test_keyed_log_and_anchor_verified_without_the_key_refuse_by_name(keep, home):
    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"kind": "a"})
    assert log.anchor_path.read_text().startswith("hmac:")
    without_key = keep.IntegrityLog(keyed=False)
    with pytest.raises(keep.IntegrityKeyError, match="keyed"):
        without_key.verify()


# ── the anchor file format ──────────────────────────────────────────────────

def test_anchor_format_bare_hex_unkeyed_hmac_prefixed_keyed(keep, home):
    unkeyed = keep.IntegrityLog()
    unkeyed.append({"kind": "a"})
    raw = unkeyed.anchor_path.read_text().strip()
    assert re.fullmatch(r"[0-9a-f]{64}", raw), raw

    keep.init_key()
    keyed = keep.IntegrityLog(home / "keyed.jsonl")
    keyed.append({"kind": "a"})
    raw2 = keyed.anchor_path.read_text().strip()
    assert raw2.startswith("hmac:")
    assert re.fullmatch(r"[0-9a-f]{64}", raw2[len("hmac:"):])


# ── the boundary row, and mixed logs ────────────────────────────────────────

def test_init_key_does_not_touch_any_log(keep, home):
    log = keep.IntegrityLog()
    log.append({"kind": "a"})
    before = log.path.read_text()
    keep.init_key()
    assert log.path.read_text() == before


def test_first_keyed_append_writes_one_boundary_row_not_one_per_append(keep, home):
    log = keep.IntegrityLog()
    log.append({"kind": "unkeyed-1"})
    log.append({"kind": "unkeyed-2"})
    keep.init_key()
    keyed_log = keep.IntegrityLog()      # auto — key file now exists
    keyed_log.append({"kind": "keyed-1"})
    keyed_log.append({"kind": "keyed-2"})

    lines = [json.loads(x) for x in log.path.read_text().splitlines()]
    assert len(lines) == 5
    boundaries = [i for i, e in enumerate(lines) if e.get("act") == "keyed"]
    assert boundaries == [2]
    assert lines[3]["kind"] == "keyed-1" and lines[4]["kind"] == "keyed-2"
    assert keyed_log.verify() is True


def test_lines_before_the_boundary_verify_unkeyed_after_verify_keyed(keep, home):
    log = keep.IntegrityLog()
    log.append({"kind": "unkeyed-1"})
    keep.init_key()
    key = keep.read_key()
    keep.IntegrityLog().append({"kind": "keyed-1"})

    lines = [json.loads(x) for x in log.path.read_text().splitlines()]
    assert lines[1]["prev"] == keep.line_hash(lines[0])           # into the marker: unkeyed
    assert lines[2]["prev"] == keep.line_hash(lines[1], key)      # out of the marker: keyed


def test_no_event_member_collides_with_the_boundary_sentinel(keep, home):
    """`export.py` writes `{"act": Event.EXPORTED.value, ...}` — the same
    field the boundary marker uses. No real entry may ever collide with it."""
    assert keep.BOUNDARY_ACT == "keyed"
    assert all(member.value != keep.BOUNDARY_ACT for member in keep.Event)


def test_a_forged_line_inserted_right_at_the_boundary_fails(keep, home):
    """The boundary is where a forger without the key would most plausibly
    try to slip a line in, hoping the reader is still checking unkeyed."""
    log = keep.IntegrityLog()
    log.append({"kind": "unkeyed-1"})
    keep.init_key()
    keyed_log = keep.IntegrityLog()
    keyed_log.append({"kind": "keyed-1"})
    keyed_log.append({"kind": "keyed-2"})

    lines = log.path.read_text().splitlines()
    forged = dict(json.loads(lines[1]))
    forged["forged"] = True
    # An attacker without the key can only recompute the *unkeyed* chain from
    # here on — exactly what they could do before this bite existed.
    prev = keep.line_hash(forged)
    new_rest = []
    for raw in lines[2:]:
        e = dict(json.loads(raw))
        e["prev"] = prev
        prev = keep.line_hash(e)
        new_rest.append(e)
    doctored = [json.dumps(forged, sort_keys=True, separators=(",", ":"))]
    doctored += [json.dumps(e, sort_keys=True, separators=(",", ":")) for e in new_rest]
    log.path.write_text("\n".join([lines[0]] + doctored) + "\n")
    keep.IntegrityLog().anchor_path.write_text(f"hmac:{prev}\n")

    assert keep.IntegrityLog().verify() is False


# ── the closed gain: forged chain + anchor fails keyed, succeeds unkeyed ───

def _attacker_rewrite_line_3_unkeyed(raw_lines: list[str]) -> tuple[list[str], str]:
    """Rewrite entry index 2 and recompute every following chain hash and the
    final anchor exactly as an attacker WITHOUT the key would — plain
    SHA-256 throughout, since that is all filesystem access can compute."""
    entries = [json.loads(x) for x in raw_lines]
    entries[2] = dict(entries[2], ref="FORGED-BY-ATTACKER")
    prev = entries[2]["prev"]
    for i in range(2, len(entries)):
        entries[i] = dict(entries[i], prev=prev)
        canonical = json.dumps(entries[i], sort_keys=True, separators=(",", ":")).encode()
        prev = hashlib.sha256(canonical).hexdigest()
    out = [json.dumps(e, sort_keys=True, separators=(",", ":")) for e in entries]
    return out, prev


def test_forged_chain_and_anchor_fails_with_a_key_but_still_succeeds_without_one(keep, home):
    keep.init_key()
    keyed_log = keep.IntegrityLog()
    for i in range(5):
        keyed_log.append({"kind": "verification", "ref": f"e{i}"})
    doctored, forged_anchor = _attacker_rewrite_line_3_unkeyed(keyed_log.path.read_text().splitlines())
    keyed_log.path.write_text("\n".join(doctored) + "\n")
    keyed_log.anchor_path.write_text(forged_anchor + "\n")   # attacker has no key: a plain hex anchor
    assert keep.IntegrityLog().verify() is False, (
        "a key-holding verifier must reject a forgery an attacker without the key built"
    )

    unkeyed_dir = home / "unkeyed"
    unkeyed_dir.mkdir()
    unkeyed_log = keep.IntegrityLog(unkeyed_dir / "integrity.jsonl", keyed=False)
    for i in range(5):
        unkeyed_log.append({"kind": "verification", "ref": f"e{i}"})
    doctored2, forged_anchor2 = _attacker_rewrite_line_3_unkeyed(unkeyed_log.path.read_text().splitlines())
    unkeyed_log.path.write_text("\n".join(doctored2) + "\n")
    unkeyed_log.anchor_path.write_text(forged_anchor2 + "\n")
    assert keep.IntegrityLog(unkeyed_dir / "integrity.jsonl", keyed=False).verify() is True, (
        "the same attack against an unkeyed log is the documented, still-open "
        "threat model — this bite does not silently change it"
    )


# ── verify() uses hmac.compare_digest everywhere: an AST guard, planted ────

def _bare_digest_equalities(tree: ast.AST) -> list[int]:
    """Every `==`/`!=` inside a function named `verify` — its whole job is
    comparing values a forger is trying to match, so it uses
    `hmac.compare_digest`, never a bare operator, for any of them."""
    return [
        inner.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "verify"
        for inner in ast.walk(node)
        if isinstance(inner, ast.Compare)
        and any(isinstance(op, (ast.Eq, ast.NotEq)) for op in inner.ops)
    ]


def test_ast_guard_plant_a_bare_equality_and_watch_it_fire():
    fixture = "def verify(prev, anchor):\n    if prev == anchor:\n        return True\n    return False\n"
    assert _bare_digest_equalities(ast.parse(fixture)) == [2]


def test_verify_in_logs_py_has_no_bare_digest_equality_and_uses_compare_digest():
    src = (ROOT / "homestead" / "keep" / "logs.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    hits = _bare_digest_equalities(tree)
    assert hits == [], f"bare == /!= on a digest in verify() at line(s) {hits}"

    verify_fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "verify")
    calls = [n.func.attr for n in ast.walk(verify_fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert calls.count("compare_digest") >= 3, (
        "verify() should route the prev-chain check, the expected_head check "
        "and the anchor check through hmac.compare_digest"
    )


# ── the CLI never prints key material ───────────────────────────────────────

def _run_cli(*args, env):
    return subprocess.run([sys.executable, "-m", "homestead.app", *args],
                           capture_output=True, text=True, env=env)


def _cli_env(home: Path) -> dict:
    return dict(os.environ, HOMESTEAD_HOME=str(home))


def test_init_key_cli_prints_a_path_never_a_key_and_refuses_a_second_call(home):
    env = _cli_env(home)
    r = _run_cli("integrity", "init-key", env=env)
    assert r.returncode == 0, r.stderr
    assert not HEX64.search(r.stdout) and not HEX64.search(r.stderr)
    assert "integrity.key" in r.stdout

    r2 = _run_cli("integrity", "init-key", env=env)
    assert r2.returncode != 0
    assert not HEX64.search(r2.stdout) and not HEX64.search(r2.stderr)
    assert "already exists" in r2.stderr or "refused" in r2.stderr


def test_verify_cli_reports_unkeyed_then_keyed_never_printing_key_material(home):
    env = _cli_env(home)
    from homestead.keep import export
    export.ledger().append({"kind": "verification", "ref": "a"})

    r = _run_cli("integrity", "verify", env=env)
    assert r.returncode == 0 and "unkeyed" in r.stdout and "ok" in r.stdout
    assert not HEX64.search(r.stdout) and not HEX64.search(r.stderr)

    _run_cli("integrity", "init-key", env=env)
    export.ledger().append({"kind": "verification", "ref": "b"})
    r2 = _run_cli("integrity", "verify", env=env)
    assert r2.returncode == 0 and "keyed" in r2.stdout
    assert not HEX64.search(r2.stdout) and not HEX64.search(r2.stderr)


def test_verify_cli_with_a_custom_path(home):
    from homestead.keep import logs
    custom = home / "somewhere" / "custom.jsonl"
    logs.IntegrityLog(custom).append({"kind": "a"})
    r = _run_cli("integrity", "verify", "--path", str(custom), env=_cli_env(home))
    assert r.returncode == 0 and "unkeyed" in r.stdout and "ok" in r.stdout


# ── I-27: no new dependency; --smoke still imports ─────────────────────────

def test_i27_no_new_dependency_and_only_stdlib_backs_the_key_machinery():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    declared_block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", pyproject, re.MULTILINE | re.DOTALL)
    assert declared_block
    assert declared_block.group(1).strip().strip(",").strip() == '"holidays>=0.102,<1.0"'

    stdlib = {"hashlib", "hmac", "json", "os", "secrets", "threading", "fcntl",
              "datetime", "enum", "pathlib", "typing", "__future__"}
    tree = ast.parse((ROOT / "homestead" / "keep" / "logs.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib or top == "homestead", top


def test_smoke_still_imports(home):
    r = subprocess.run([sys.executable, "-m", "homestead.app", "--smoke"],
                        capture_output=True, text=True, env=_cli_env(home))
    assert r.returncode == 0 and "smoke ok" in r.stdout


# ── export.ledger() works keyed and unkeyed ─────────────────────────────────

def test_export_ledger_works_unkeyed_and_keyed(keep, home):
    from homestead.keep import export
    unkeyed = export.ledger()
    assert unkeyed.keyed is False
    unkeyed.append({"kind": "verification", "ref": "a"})
    assert unkeyed.verify() is True

    keep.init_key()
    keyed = export.ledger()
    assert keyed.keyed is True
    keyed.append({"kind": "verification", "ref": "b"})
    assert keyed.verify() is True
    lines = [json.loads(x) for x in keyed.path.read_text().splitlines()]
    assert any(e.get("act") == "keyed" for e in lines)
    assert keyed.anchor_path.read_text().startswith("hmac:")


def test_export_record_end_to_end_keyed(keep, home):
    keep.init_key()
    from homestead.keep import export, rungs
    item = rungs.Classified(rungs.Rung.L4, "content", derived="a note")
    receipt = export.export_record(
        item, "custody", "atom", "ATM-001", purpose=rungs.Purpose.EXPORT,
    )
    assert export.ledger().verify() is True
    assert receipt.head == export.ledger().head()
