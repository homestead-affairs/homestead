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

_DIGEST_WORDS = ("hash", "digest", "prev", "head", "anchor", "hmac", "mac",
                 "tag", "recorded")


def _digest_named(node: ast.AST) -> bool:
    spellings = [n.id if isinstance(n, ast.Name) else n.attr
                 for n in ast.walk(node)
                 if isinstance(n, (ast.Name, ast.Attribute))]
    return any(word in s.lower() for s in spellings for word in _DIGEST_WORDS)


def _bare_digest_equalities(tree: ast.AST) -> list[int]:
    """Every `==`/`!=` on a digest-shaped operand, **anywhere in the module**
    — not only inside `verify()`.

    Scoping this to a function literally named `verify` was the first shape,
    and it checked less than it claimed: `verify()` delegates every hash it
    computes to `_hash_at`, `line_hash` and `_recorded_boundary`, so a bare
    `==` moved one call deep would have passed the guard while making exactly
    the change the guard exists to forbid. The operand-name filter is what
    keeps the wider walk honest rather than blanket: `entry.get("act") ==
    BOUNDARY_ACT` compares a sentinel, not a digest, and must not fire.
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            continue
        if _digest_named(node.left) or any(_digest_named(c) for c in node.comparators):
            out.append(node.lineno)
    return sorted(out)


def test_ast_guard_plant_a_bare_equality_and_watch_it_fire():
    fixture = "def verify(prev, anchor):\n    if prev == anchor:\n        return True\n    return False\n"
    assert _bare_digest_equalities(ast.parse(fixture)) == [2]


def test_ast_guard_fires_for_a_helper_verify_calls_not_only_for_verify_itself():
    """The guard's reach is the point: `verify()` is three lines of walking
    and every digest it compares is produced by a helper."""
    fixture = (
        "def verify(self):\n    return _hash_at(e) and _recorded(p)\n\n"
        "def _hash_at(entry, prev_hash, anchor_hex):\n"
        "    return prev_hash != anchor_hex\n"
    )
    assert _bare_digest_equalities(ast.parse(fixture)) == [5]


def test_ast_guard_does_not_fire_on_a_sentinel_comparison():
    """A blanket "no `==` in logs.py" would forbid `entry.get("act") ==
    BOUNDARY_ACT`, which is how the boundary row is found at all."""
    fixture = 'def _boundary_index(lines):\n    return [e for e in lines if e.get("act") == BOUNDARY_ACT]\n'
    assert _bare_digest_equalities(ast.parse(fixture)) == []


def test_logs_py_has_no_bare_digest_equality_and_verify_uses_compare_digest():
    src = (ROOT / "homestead" / "keep" / "logs.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    hits = _bare_digest_equalities(tree)
    assert hits == [], f"bare == /!= on a digest in logs.py at line(s) {hits}"

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
              "datetime", "enum", "pathlib", "typing", "__future__",
              "warnings"}   # E7: `_entries()`'s deprecated-alias warning
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


# ── downgrade: a keyed log offered as one that was never keyed ──────────────
#
# The audit's first attack, and the one the key exists to answer. Three
# rungs of it, each pinned separately, because they end differently:
#   1. key deleted, log intact          → refuse by name (cannot tell)
#   2. boundary row deleted, re-chained → False (a finding: the marker
#      beside the key still records that this log turned keyed)
#   3. key *and* marker deleted, log truncated to the pre-boundary prefix
#      → clean, and that is the honest residual, pinned so it cannot move
#      without someone noticing.

def _strip_boundary_and_rechain_unkeyed(keep, log) -> str:
    """Exactly what a forger without the key can do: drop the `{"act":
    "keyed"}` row, re-link every survivor with plain SHA-256, return the head
    they would write into the anchor."""
    lines = [json.loads(x) for x in log.path.read_text().splitlines()]
    prev = "genesis"
    out = []
    for entry in [e for e in lines if e.get("act") != keep.BOUNDARY_ACT]:
        entry = dict(entry, prev=prev)
        prev = keep.line_hash(entry)
        out.append(json.dumps(entry, sort_keys=True, separators=(",", ":")))
    log.path.write_text("\n".join(out) + "\n")
    log.anchor_path.write_text(prev + "\n")
    return prev


def _keyed_log_with_an_unkeyed_prefix(keep):
    log = keep.IntegrityLog()
    log.append({"kind": "unkeyed-1"})
    log.append({"kind": "unkeyed-2"})
    keep.init_key()
    keyed = keep.IntegrityLog()
    keyed.append({"kind": "keyed-1"})
    return keyed


def test_a_keyed_log_whose_key_file_is_gone_refuses_under_auto(keep, home):
    """Attack 1, first rung. Under `keyed=None` the constructor finds no key
    and the log looks unkeyed to it — so the temptation is to verify the
    unkeyed prefix and stop at the boundary row with a clean `True` over a
    partial log. It must refuse by name instead: the boundary row says "keyed
    from here", and a verifier that cannot read past it has not checked the
    log, whatever the prefix says."""
    _keyed_log_with_an_unkeyed_prefix(keep)
    keep.default_key_path().unlink()

    auto = keep.IntegrityLog()
    assert auto.keyed is False                      # auto found no key file
    with pytest.raises(keep.IntegrityKeyError, match="keyed"):
        auto.verify()


def test_deleting_the_boundary_row_is_a_downgrade_not_a_clean_unkeyed_log(keep, home):
    """Attack 1, second rung — the hole the key alone does not close. A forger
    without the key does not have to forge an HMAC: they delete the one row
    that says the log turned keyed, re-chain the survivors with the public
    SHA-256 they can compute, and write a bare-hex anchor. A verifier holding
    the key would then see a log that was never keyed and call it clean,
    undoing the whole gain by a deletion. The turning point is recorded beside
    the key as well, so the log alone can no longer deny it."""
    keyed = _keyed_log_with_an_unkeyed_prefix(keep)
    _strip_boundary_and_rechain_unkeyed(keep, keyed)

    assert keep.IntegrityLog().verify() is False, "a stripped boundary must be a finding"
    assert keep.IntegrityLog(keyed=False).verify() is False, (
        "and it is a finding about the log, not about which key is in hand"
    )


def test_truncating_to_before_the_boundary_is_caught_while_the_marker_stands(keep, home):
    """The same downgrade by truncation rather than by re-chaining: keep only
    the pre-key lines, whose chain and anchor an attacker can recompute in
    full. Caught for as long as the marker survives."""
    keyed = _keyed_log_with_an_unkeyed_prefix(keep)
    keep.default_key_path().unlink()
    lines = [x for x in keyed.path.read_text().splitlines()
             if json.loads(x).get("act") != keep.BOUNDARY_ACT][:2]
    keyed.path.write_text("\n".join(lines) + "\n")
    keyed.anchor_path.write_text(keep.line_hash(json.loads(lines[-1])) + "\n")

    assert keep.IntegrityLog().verify() is False


def test_the_residual_key_and_marker_gone_and_truncated_verifies_clean(keep, home):
    """**The residual, stated as a test rather than as a hope.** An attacker
    who deletes the key, deletes the marker beside it and truncates the log to
    its pre-boundary prefix leaves a log that is indistinguishable from one
    that was never keyed — because that is exactly what it now is. No file on
    this machine can close that (F-5), and the pre-E5 threat model for an
    unkeyed prefix is unchanged by keying. Pinned so that a later bite which
    thinks it has closed it has to change this test on purpose.
    See `docs/DECISION-integrity-key-management.md` §4a."""
    keyed = _keyed_log_with_an_unkeyed_prefix(keep)
    keep.default_key_path().unlink()
    keep.default_marker_path().unlink()
    lines = [x for x in keyed.path.read_text().splitlines()
             if json.loads(x).get("act") != keep.BOUNDARY_ACT][:2]
    keyed.path.write_text("\n".join(lines) + "\n")
    keyed.anchor_path.write_text(keep.line_hash(json.loads(lines[-1])) + "\n")

    assert keep.IntegrityLog().verify() is True


def test_a_re_keyed_log_does_not_launder_a_downgrade(keep, home):
    """Downgrade, then let the household's own next `append()` write a fresh
    boundary row: without the recorded hash the log would verify clean again,
    the alarm erased by ordinary use. The marker records *which* boundary row,
    not merely that there was one."""
    keyed = _keyed_log_with_an_unkeyed_prefix(keep)
    _strip_boundary_and_rechain_unkeyed(keep, keyed)
    keep.IntegrityLog().append({"kind": "after-the-downgrade"})

    assert keep.IntegrityLog().verify() is False


def test_a_legacy_log_untouched_since_init_key_still_verifies_clean(keep, home):
    """The false positive the blunt version of this rule would cause, pinned
    as the behaviour it must not have: "a key file exists and this anchor is
    bare hex" is the *normal* state of every pre-key log until its own next
    append, and refusing there would break exactly the legacy logs the bite
    promises not to touch."""
    log = keep.IntegrityLog()
    log.append({"kind": "unkeyed-1"})
    keep.init_key()

    assert keep.default_marker_path().exists() is False
    assert keep.IntegrityLog().verify() is True
    assert keep.IntegrityLog().anchor_path.read_text().startswith("hmac:") is False


def test_the_marker_is_0600_and_names_no_path(keep, home):
    keyed = _keyed_log_with_an_unkeyed_prefix(keep)
    marker = keep.default_marker_path()
    raw = marker.read_text(encoding="utf-8")
    assert len(raw.splitlines()) == 1
    assert str(keyed.path) not in raw and keyed.path.name not in raw
    assert re.fullmatch(r"[0-9a-f]{64} [0-9a-f]{64}", raw.strip())
    if os.name == "posix":
        assert (marker.stat().st_mode & 0o777) == 0o600


def test_the_marker_is_not_an_anchor_an_attacker_can_copy(keep, home):
    """The marker must not hand a reader a valid head. Recording the boundary
    row's keyed hash verbatim would publish, in a bare-hex file, exactly the
    value needed to truncate every keyed line and write a matching anchor —
    a downgrade guard that opens a truncation oracle is a bad trade. It
    records a commitment to that hash instead: checkable by anyone who can
    recompute it (which needs the key), useless to anyone who cannot."""
    keyed = _keyed_log_with_an_unkeyed_prefix(keep)
    key = keep.read_key()
    boundary = next(json.loads(x) for x in keyed.path.read_text().splitlines()
                    if json.loads(x).get("act") == keep.BOUNDARY_ACT)
    recorded = keep.default_marker_path().read_text().split()[1]
    assert recorded != keep.line_hash(boundary, key)

    # and the attack the verbatim form would have enabled, run for real:
    # truncate to the boundary row and paste the marker's value as the anchor.
    lines = keyed.path.read_text().splitlines()
    upto = lines[:[json.loads(x).get("act") for x in lines].index(keep.BOUNDARY_ACT) + 1]
    keyed.path.write_text("\n".join(upto) + "\n")
    keyed.anchor_path.write_text(f"hmac:{recorded}\n")
    assert keep.IntegrityLog().verify() is False


# ── boundary-row forgery: the shapes an attacker would try ─────────────────

def test_a_fresh_log_under_a_key_writes_the_boundary_row_first(keep, home):
    """"No unkeyed lines, so no boundary needed" is the tempting shortcut, and
    it is wrong: without a row at index 0 there is nothing in the chain saying
    this log was ever keyed, and `verify()` would have no boundary to check
    the marker against. A keyed log always has one, at index 0 when there is
    no prefix."""
    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"kind": "a"})
    lines = [json.loads(x) for x in log.path.read_text().splitlines()]
    assert lines[0] == {"act": "keyed", "at": lines[0]["at"], "prev": "genesis"}
    assert lines[1]["kind"] == "a"
    assert log.verify() is True


def test_a_second_boundary_row_appended_later_fails(keep, home):
    """The attacker's own `{"act": "keyed"}` row, appended at the end with the
    anchor's published hash as its `prev` — the one keyed digest they can read
    without the key. The chain accepts the link; the anchor they cannot
    recompute is what refuses."""
    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"kind": "a"})
    published_head = log.anchor_path.read_text().strip()[len("hmac:"):]
    forged = {"act": "keyed", "at": "2026-01-01T00:00:00+00:00", "prev": published_head}
    with log.path.open("a") as fh:
        fh.write(json.dumps(forged, sort_keys=True, separators=(",", ":")) + "\n")

    assert keep.IntegrityLog().verify() is False


def test_a_boundary_row_planted_earlier_in_the_prefix_fails(keep, home):
    """Moving the turning point backwards would re-read already-written
    unkeyed lines as keyed ones. `_boundary_index` takes the first marker, so
    the planted one wins — and everything after it then fails, because those
    lines were chained with SHA-256 and are now read as HMAC."""
    keyed = _keyed_log_with_an_unkeyed_prefix(keep)
    lines = keyed.path.read_text().splitlines()
    planted = json.dumps({"act": "keyed", "at": "2026-01-01T00:00:00+00:00",
                          "prev": json.loads(lines[0])["prev"]},
                         sort_keys=True, separators=(",", ":"))
    keyed.path.write_text("\n".join([planted] + lines) + "\n")

    assert keep.IntegrityLog().verify() is False


def test_a_keyed_log_holds_one_row_no_caller_wrote(keep, home):
    """`keep/sync.py` establishes "ledgered once" (I-38) by reading the
    ledger's lines, and a keyed ledger has one more line than the caller
    appended. `BOUNDARY_ACT` is exported so that consumer can skip it; this
    pins both halves of that contract."""
    keep.init_key()
    log = keep.IntegrityLog()
    log.append({"act": "record_synced", "envelope": "e1"})
    lines = [json.loads(x) for x in log.path.read_text().splitlines()]
    assert len(lines) == 2
    mine = [e for e in lines if e.get("act") != keep.BOUNDARY_ACT]
    assert len(mine) == 1 and mine[0]["envelope"] == "e1"


# ── key-file hygiene ────────────────────────────────────────────────────────

@pytest.mark.parametrize("label,text,accepted", [
    ("63 hex — odd length", "a" * 63, False),
    ("65 hex — odd length", "a" * 65, False),
    ("66 hex — 33 bytes", "a" * 66, False),
    ("empty file", "", False),
    ("uppercase", "AB" * 32, True),
    ("trailing newline", "ab" * 32 + "\n", True),
    ("surrounding whitespace", "  " + "ab" * 32 + "  \n", True),
    ("a space between byte pairs", "ab" * 16 + " " + "ab" * 16, True),
])
def test_key_file_hygiene_what_reads_as_a_key_and_what_refuses(keep, home, label, text, accepted):
    """Pinned in both directions. The three accepted forms all name the same
    32 bytes — an operator restoring the key by hand from a printed copy is
    not refused over the case of a letter — and everything that does not name
    exactly 32 bytes refuses by name rather than keying a chain nothing can
    verify afterwards."""
    path = keep.default_key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if accepted:
        assert keep.read_key() == bytes.fromhex("ab" * 32)
    else:
        with pytest.raises(keep.IntegrityKeyError):
            keep.read_key()


def test_init_key_refuses_a_symlink_standing_at_the_key_path(keep, home):
    """`O_EXCL` does not follow a symlink — including a dangling one, which is
    how a writer would try to have the key land somewhere they can read it.
    The refusal names the path, and the target is never created."""
    if os.name != "posix":
        pytest.skip("symlinks are the POSIX shape of this attack")
    path = keep.default_key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    elsewhere = home / "readable-by-anyone.txt"
    os.symlink(str(elsewhere), str(path))

    with pytest.raises(keep.IntegrityKeyError, match="already exists"):
        keep.init_key()
    assert not elsewhere.exists()


def test_init_key_creates_anchors_dir_and_the_key_is_the_thing_that_is_0600(keep, home):
    """`anchors_dir()` may not exist yet. It is created by `paths.ensure`,
    which is `mkdir` under the umask — an ordinary 0755 directory, because the
    anchor it holds is meant to be copyable off the machine. The *key* is what
    carries 0600, and it carries it whatever the umask says."""
    anchors = home / "anchors"
    assert not anchors.exists()
    old = os.umask(0)
    try:
        path = keep.init_key()
    finally:
        os.umask(old)
    assert path.parent == anchors and anchors.is_dir()
    if os.name == "posix":
        assert (path.stat().st_mode & 0o777) == 0o600


# ── I-22, keyed ────────────────────────────────────────────────────────────

def test_i22_concurrent_keyed_appends_do_not_break_the_chain(keep, home):
    """I-22 at the thread count `tests/test_invariants_logs.py` uses, with a
    key: eight threads, twenty appends each. Keying adds a second write inside
    the lock (the boundary row, and the marker beside the key), and "written
    once" has to survive the race that the unkeyed lock was added for."""
    keep.init_key()
    log = keep.IntegrityLog()

    def worker(n):
        for i in range(20):
            log.append({"kind": "verification", "ref": f"t{n}-{i}"})

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = [json.loads(x) for x in log.path.read_text().splitlines() if x.strip()]
    prevs = [e["prev"] for e in lines]
    assert [e for e in lines if e.get("act") == keep.BOUNDARY_ACT].__len__() == 1
    assert len(lines) == 161, f"lost lines: {len(lines)}"
    assert len(prevs) == len(set(prevs)), f"{len(prevs) - len(set(prevs))} duplicate prev links"
    assert len(keep.default_marker_path().read_text().splitlines()) == 1
    assert log.verify() is True


# ── the CLI's exit codes, and the grep that proves it says no key ──────────

def test_the_hex_grep_used_by_the_cli_tests_is_shown_to_fire():
    """The grep is the whole control in the tests above it; a grep that has
    never matched has not been shown to check anything."""
    assert HEX64.search("homestead: integrity key created: " + "ab" * 32)
    assert not HEX64.search("homestead: integrity key created at /home/x/anchors/integrity.key")


def test_verify_exit_codes_clean_failed_refused_and_unparseable(home):
    """Three answers, three codes: 0 clean, 1 the chain does not hold, 3
    refused by name (cannot tell), 2 a command line that does not parse. A
    cron job that reads "cannot tell" as "tampered" is the failure this
    separation exists to prevent."""
    env = _cli_env(home)
    from homestead.keep import export, logs

    export.ledger().append({"kind": "verification", "ref": "a"})
    assert _run_cli("integrity", "verify", env=env).returncode == 0

    _run_cli("integrity", "init-key", env=env)
    export.ledger().append({"kind": "verification", "ref": "b"})
    assert _run_cli("integrity", "verify", env=env).returncode == 0

    (home / "anchors" / "integrity.key").unlink()
    refused = _run_cli("integrity", "verify", env=env)
    assert refused.returncode == 3 and "refused" in refused.stderr
    assert not HEX64.search(refused.stdout) and not HEX64.search(refused.stderr)

    broken = home / "broken.jsonl"
    logs.IntegrityLog(broken).append({"kind": "a"})
    broken.write_text(json.dumps({"kind": "a", "at": "t", "prev": "not-genesis"}) + "\n")
    assert _run_cli("integrity", "verify", "--path", str(broken), env=env).returncode == 1

    assert _run_cli("integrity", "verify", "--nope", env=env).returncode == 2
    assert _run_cli("integrity", "init-key", "extra", env=env).returncode == 2


def test_verify_never_falls_through_to_the_default_ledger_on_a_typo(home):
    """`verify --pat /some/log` answering "ok" about a *different* log than
    the operator named is the worst thing this command can do; it refuses to
    parse instead (I-11 — refuse, never default)."""
    env = _cli_env(home)
    from homestead.keep import export
    export.ledger().append({"kind": "verification", "ref": "a"})
    r = _run_cli("integrity", "verify", "--pat", str(home / "nothing.jsonl"), env=env)
    assert r.returncode == 2 and "ok" not in r.stdout
