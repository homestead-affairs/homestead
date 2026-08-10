"""I-6, I-7, I-9, I-36 — the record, and I-11 at the storage boundary.

Bite 1 of `docs/PLAN-first-runnable.md`: *the store — records survive a
restart.* The engine (rungs, surfaces, dates, logs, paths) was built, tested,
and connected to nothing; this is the first thing that persists a `Classified`
and gives it back. Every test here is a check the plan named, written before the
code that satisfies it.

The seam these hold is the one the build plan calls out in I-6: **the canonical
record is read-only, enforced by type, and writes go to a sidecar.** So there
are two handles — a `Canonical` that can only read, and a `Sidecar` the app
writes to — and one key derivation shared by both, because BUG-11 was two call
sites deriving the same key differently.

The rung is the load-bearing part. A store that returns a payload without its
rung has silently declassified it, and `compose` is `max` precisely so that
aggregation can never lower one — a storage layer that drops the rung on the
way to disk is the same declassification by a slower road.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from homestead.keep import paths
from homestead.keep.record import Canonical, InvalidKey, Replaced, Sidecar, key
from homestead.keep.rungs import Classified, Rung


# ── promoted from test_invariants_pending.py ─────────────────────────────────

def test_i36_nothing_deletes_canonical_data():
    """I-6/I-36, enforced by type rather than by convention. The canonical
    handle has *no* write method — not delete, not update, not even write — so
    the app cannot destroy evidence on a schedule (F-5), by inertia, or by
    mistake. Auto-purging a live matter is what this forecloses."""
    for forbidden in ("delete", "purge", "remove", "drop", "write", "update"):
        assert not hasattr(Canonical, forbidden), (
            f"Canonical.{forbidden} exists. I-6 says the canonical handle is "
            "read-only by type; a write path on it is the convention this "
            "invariant refuses to trust."
        )


# ── I-7 · one key derivation, and it cannot escape its tree ──────────────────

def test_i7_read_and_write_derive_the_key_the_same_way():
    """BUG-11: a literal matter name in one call site and a derived one in
    another meant a record was filed where it could not be found. The key is
    computed in exactly one place, from `(matter, item_type, item_id)`, and both
    the sidecar and the canonical handle prepend their own tree root to it."""
    rel = key("custody", "deadline", "hearing-2026-08-15")
    assert rel == Path("custody") / "deadline" / "hearing-2026-08-15.json"


def test_i7_a_key_component_cannot_smuggle_a_path(monkeypatch, tmp_path):
    """A key is not a place to put a path. A component with a separator or a
    `..` would let a write land outside its matter's tree — the same class of
    escape `ensure()` refuses for directories."""
    for bad in ("..", "a/b", "a\\b", ".", "", "   ", "x\x00y"):
        with pytest.raises(InvalidKey):
            key(bad, "deadline", "id")
        with pytest.raises(InvalidKey):
            key("custody", bad, "id")
        with pytest.raises(InvalidKey):
            key("custody", "deadline", bad)


# ── bite 1 · records survive a restart, and the rung travels with them ───────

def test_the_rung_travels_with_the_datum(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    item = Classified(
        rung=Rung.L3,
        payload="Custody hearing, Judge Alvarez, 9:00am",
        derived="A hearing is scheduled in this matter",
    )
    store.put("custody", "deadline", "hearing", item)

    back = store.get("custody", "deadline", "hearing")
    assert back.rung is Rung.L3
    assert back.payload == item.payload
    assert back.derived == item.derived


def test_a_record_survives_the_process_exiting(tmp_path):
    """The plan's check, taken literally: written by one process, read by
    another. Nothing here holds state in memory, and this proves it — a store
    that only round-trips within one interpreter has persisted nothing."""
    writer = textwrap.dedent(
        """
        from homestead.keep.record import Sidecar
        from homestead.keep.rungs import Classified, Rung
        Sidecar().put("custody", "note", "n1",
            Classified(Rung.L3, "a name and a place", "a note exists"))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", writer],
        env={"HOMESTEAD_HOME": str(tmp_path), "PATH": ""},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    import os
    os.environ["HOMESTEAD_HOME"] = str(tmp_path)
    try:
        back = Sidecar().get("custody", "note", "n1")
    finally:
        del os.environ["HOMESTEAD_HOME"]
    assert back.rung is Rung.L3
    assert back.payload == "a name and a place"


# ── I-11 at the storage boundary — absence fails closed to L5, not L1 ─────────

def _write_raw(tmp_path: Path, raw: dict) -> None:
    """Hand-write a sidecar file, bypassing the store, to simulate a row that
    was corrupted, hand-edited, or written by an older schema."""
    target = paths.sidecar_dir() / key("custody", "deadline", "x")
    paths.ensure(target.parent)
    target.write_text(json.dumps(raw))


def test_a_missing_rung_reads_l5_on_the_way_out(tmp_path, monkeypatch):
    """I-11's whole posture, applied at storage: a stored datum whose rung is
    gone is not `L1` and not an error the caller can default — it reads `L5` and
    is never served. The payload rides along but `L5` is served on no surface."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    _write_raw(tmp_path, {"payload": "a name", "derived": "something"})
    assert Sidecar().get("custody", "deadline", "x").rung is Rung.L5


def test_an_unreadable_rung_reads_l5(tmp_path, monkeypatch):
    """`"L9"`, an integer, a bool — every unreadable rung reads `L5`, the same
    way `_read_rung` refuses them at the gate. An integer rung in storage is
    I-14's cross-scale catastrophe arriving as data."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    for bad in ("L9", "unknown", 3, True, None):
        _write_raw(tmp_path, {"rung": bad, "payload": "a name", "derived": "d"})
        assert Sidecar().get("custody", "deadline", "x").rung is Rung.L5, bad


def test_a_derived_form_lost_in_storage_reads_l5(tmp_path, monkeypatch):
    """A stored `L3` whose derived form went missing cannot be rebuilt as a
    valid `Classified` (L3 is served as a stand-in on at least one surface, so
    it must carry one — BUG-5). Rather than raise or invent one, the read fails
    closed to `L5`: absence at the storage boundary is served as nothing."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    _write_raw(tmp_path, {"rung": "L3", "payload": "a name"})
    assert Sidecar().get("custody", "deadline", "x").rung is Rung.L5


# ── I-9 · writes never silently overwrite ────────────────────────────────────

def test_i9_a_write_refuses_to_clobber(tmp_path, monkeypatch):
    """BUG-8's answer: a second write to an occupied key does not quietly
    replace what was there. It refuses."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    first = Classified(Rung.L2, "first")
    assert store.put("custody", "note", "n", first) is None

    with pytest.raises(FileExistsError):
        store.put("custody", "note", "n", Classified(Rung.L2, "second"))
    # and the original is untouched
    assert store.get("custody", "note", "n").payload == "first"


def test_i9_an_overwrite_reports_what_it_replaced(tmp_path, monkeypatch):
    """The other half of I-9: when a replacement is asked for explicitly, it
    reports what it displaced rather than losing it silently."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    store.put("custody", "note", "n", Classified(Rung.L2, "first"))
    replaced = store.put(
        "custody", "note", "n", Classified(Rung.L2, "second"), overwrite=True
    )
    assert isinstance(replaced, Replaced)
    assert replaced.previous.payload == "first"
    assert store.get("custody", "note", "n").payload == "second"


# ── the canonical handle reads, and shares the one key ───────────────────────

def test_canonical_reads_what_the_operator_placed(tmp_path, monkeypatch):
    """The operator's own tools grow the canonical record; the app reads it.
    Written by hand into the record tree (never by the app), and read back
    through the same key derivation the sidecar uses."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    target = paths.record_dir() / key("custody", "filing", "petition")
    paths.ensure(target.parent)
    target.write_text(json.dumps({"rung": "L4", "payload": "a diagnosis", "derived": "a filing exists"}))

    got = Canonical().get("custody", "filing", "petition")
    assert got.rung is Rung.L4
    assert got.payload == "a diagnosis"


def test_canonical_reads_fail_closed_too(tmp_path, monkeypatch):
    """The storage-boundary rule is a property of the read, not of the writer,
    so it holds for the canonical handle as well: an unreadable rung in the
    canonical record reads `L5`."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    target = paths.record_dir() / key("custody", "filing", "petition")
    paths.ensure(target.parent)
    target.write_text(json.dumps({"payload": "a diagnosis"}))
    assert Canonical().get("custody", "filing", "petition").rung is Rung.L5


# ── audit remediation ────────────────────────────────────────────────────────

def test_i9_concurrent_writes_do_not_silently_clobber(tmp_path, monkeypatch):
    """The audit's TOCTOU, closed. The first version checked `exists()` and then
    wrote, with a window between; two writers both saw an empty slot and both
    wrote, one clobbering the other and returning None as if it were a clean
    first write (166 of 200 racing rounds). Now the check and the create are one
    act under a lock, and the first write is an exclusive create — so of N
    racers on one key, exactly one wins and the rest are refused."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    import threading

    store = Sidecar()
    n = 8
    barrier = threading.Barrier(n)
    outcomes: list[tuple[str, object]] = []
    guard = threading.Lock()

    def racer(i: int) -> None:
        barrier.wait()  # release all threads at once, to actually contend
        try:
            result = store.put("custody", "note", "n", Classified(Rung.L2, f"writer-{i}"))
            with guard:
                outcomes.append(("won", result))
        except FileExistsError:
            with guard:
                outcomes.append(("refused", None))

    threads = [threading.Thread(target=racer, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    won = [o for o in outcomes if o[0] == "won"]
    refused = [o for o in outcomes if o[0] == "refused"]
    assert len(won) == 1, f"exactly one racer should win, got {len(won)}"
    assert won[0][1] is None, "the winning first write reports None, not a clobber"
    assert len(refused) == n - 1, "every other racer is refused, not silently dropped"


def test_a_corrupt_row_reads_l5_rather_than_crashing(tmp_path, monkeypatch):
    """I-11 at the storage boundary, past the rung: an undecodable file — empty,
    truncated, garbage, an older schema — is a corrupt row, and a corrupt row
    reads `L5`, not a `JSONDecodeError` that crashes the surface reading it. The
    audit found `json.loads` sat outside the fail-closed path; now it is inside
    it."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    target = paths.sidecar_dir() / key("custody", "deadline", "x")
    paths.ensure(target.parent)
    for junk in ("", "   ", "{not json", "\x00\x01\x02garbage", "not json at all"):
        target.write_text(junk)
        assert Sidecar().get("custody", "deadline", "x").rung is Rung.L5, repr(junk)


def test_overwriting_a_corrupt_row_replaces_it_rather_than_crashing(tmp_path, monkeypatch):
    """The other side of the same fix: `put(overwrite=True)` over a corrupt file
    reads the previous (fail-closed to L5) and replaces it, rather than crashing
    on the unreadable prior."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    target = paths.sidecar_dir() / key("custody", "note", "n")
    paths.ensure(target.parent)
    target.write_text("}{ not json")

    store = Sidecar()
    replaced = store.put("custody", "note", "n", Classified(Rung.L2, "clean"), overwrite=True)
    assert replaced is not None
    assert replaced.previous.rung is Rung.L5      # the corrupt prior read closed
    assert store.get("custody", "note", "n").payload == "clean"


def test_i6_only_the_store_reaches_the_canonical_tree():
    """I-6, closed at the app boundary. `Canonical` has no write method — but the
    audit showed `record_dir()` returns a plain writable `Path`, so app code
    could overwrite, unlink, or fabricate canonical data by reaching for the raw
    path, past the read-only handle. So only `paths.py` (which defines them) and
    `record.py` (whose `Canonical` reads them) may name `record_dir`/`matter_dir`:
    a surface cannot misuse a writable canonical path it cannot even name.

    This does not make the filesystem itself read-only — nothing in Python can —
    but it means no module in the package holds a path to write there, which is
    the enforceable half of 'the app has no write path to the record'."""
    import ast

    pkg = Path(__file__).resolve().parent.parent / "homestead"
    allowed = {pkg / "keep" / "paths.py", pkg / "keep" / "record.py"}
    offenders = []
    for mod in sorted(p for p in pkg.rglob("*.py") if "__pycache__" not in p.parts):
        if mod in allowed:
            continue
        for node in ast.walk(ast.parse(mod.read_text("utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr in {"record_dir", "matter_dir"}:
                offenders.append(f"{mod.relative_to(pkg.parent)}:{node.lineno} .{node.attr}")
            elif isinstance(node, ast.Name) and node.id in {"record_dir", "matter_dir"}:
                offenders.append(f"{mod.relative_to(pkg.parent)}:{node.lineno} {node.id}")
    assert not offenders, (
        "only the store may reach the canonical tree; a module names a canonical "
        f"path at {offenders}. The canonical record is read-only to the app "
        "(I-6), and a writable Path to it in any other module is that guarantee "
        "reduced to a convention."
    )


# ── enumeration — a matter's records, by reference (bite 4) ──────────────────

def test_records_enumerates_a_matter_with_refs(tmp_path, monkeypatch):
    """The list pane needs a matter's records, each with a handle to open it. The
    handle is the key — a reference, not content (I-15)."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    store.put("custody", "courthouse", "main", Classified(Rung.L1, "Dept 4"))
    store.put("custody", "case_number", "primary",
              Classified(Rung.L3, "FL-1", derived="a case is on file"))
    store.put("bankruptcy", "docket", "d1", Classified(Rung.L1, "public"))

    got = dict(store.records("custody"))
    assert set(got) == {("custody", "courthouse", "main"),
                        ("custody", "case_number", "primary")}
    assert got[("custody", "case_number", "primary")].payload == "FL-1"
    # a different matter's records are not enumerated
    assert all(ref[0] == "custody" for ref, _ in store.records("custody"))


def test_records_reads_a_corrupt_row_as_l5_without_breaking_enumeration(tmp_path, monkeypatch):
    """One unreadable file must not take the whole list down, and must not read
    as anything but L5 — the same fail-closed rule as `get`, applied per row."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    store = Sidecar()
    store.put("custody", "case_number", "primary",
              Classified(Rung.L3, "FL-1", derived="d"))
    corrupt = paths.sidecar_dir() / key("custody", "notes", "n1")
    paths.ensure(corrupt.parent)
    corrupt.write_text("garbage{")

    got = dict(store.records("custody"))
    assert got[("custody", "notes", "n1")].rung is Rung.L5
    assert got[("custody", "case_number", "primary")].rung is Rung.L3


def test_records_of_an_absent_matter_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    assert Sidecar().records("custody") == []


def test_records_refuses_a_traversal_matter(tmp_path, monkeypatch):
    """Enumeration joins the matter to the tree root, so the matter is validated
    as one safe segment first — a `..` cannot walk the walk out of its tree."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    with pytest.raises(InvalidKey):
        Sidecar().records("../escape")
