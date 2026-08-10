"""The adapter seam — I-6, I-7, I-9, I-11, held against every backing.

The payoff of `keep/store.py`: the record invariants are the contract, and both
the file adapter and the SQLite adapter satisfy them. Every test here runs
against **both**, parametrized on the adapter — so a claim that passes is a claim
the contract holds regardless of what stores the blob, which is exactly what lets
a Postgres adapter (the shared fleet engine) inherit the lot by implementing four
methods.
"""
from __future__ import annotations

import json
import threading

import pytest

from homestead.keep.rungs import Classified, Rung
from homestead.keep.store import (
    CANONICAL,
    SIDECAR,
    Canonical,
    FileAdapter,
    InvalidKey,
    RecordExists,
    Replaced,
    SQLiteAdapter,
    Sidecar,
    key,
)


@pytest.fixture(params=[FileAdapter, SQLiteAdapter], ids=["file", "sqlite"])
def adapter(request, tmp_path, monkeypatch):
    """A fresh adapter of each kind, rooted at an isolated /.homestead."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    return request.param()


def _fresh(adapter):
    """A second adapter of the same kind on the same root — to read back across
    store instances (persistence)."""
    return type(adapter)()


# ── the rung travels, and survives a new store instance ──────────────────────

def test_the_rung_travels_and_persists(adapter):
    Sidecar(adapter).put("custody", "case_number", "primary",
                         Classified(Rung.L3, "FL-1", derived="a case is on file"))
    back = Sidecar(_fresh(adapter)).get("custody", "case_number", "primary")
    assert back.rung is Rung.L3
    assert back.payload == "FL-1"
    assert back.derived == "a case is on file"


# ── I-7 · one key ────────────────────────────────────────────────────────────

def test_i7_key_validation():
    assert key("custody", "deadline", "h") == ("custody", "deadline", "h")
    for bad in ("", "   ", "..", "a/b", "a\\b", ".", "x\x00y"):
        with pytest.raises(InvalidKey):
            key(bad, "deadline", "id")
        with pytest.raises(InvalidKey):
            key("custody", "deadline", bad)


# ── I-9 · writes never silently overwrite (on either backing) ────────────────

def test_i9_a_write_refuses_to_clobber(adapter):
    store = Sidecar(adapter)
    assert store.put("custody", "note", "n", Classified(Rung.L2, "first")) is None
    with pytest.raises(RecordExists):
        store.put("custody", "note", "n", Classified(Rung.L2, "second"))
    assert store.get("custody", "note", "n").payload == "first"


def test_i9_an_overwrite_reports_what_it_replaced(adapter):
    store = Sidecar(adapter)
    store.put("custody", "note", "n", Classified(Rung.L2, "first"))
    replaced = store.put("custody", "note", "n", Classified(Rung.L2, "second"), overwrite=True)
    assert isinstance(replaced, Replaced)
    assert replaced.previous.payload == "first"
    assert store.get("custody", "note", "n").payload == "second"


def test_i9_concurrent_writes_do_not_clobber(adapter):
    """O_EXCL on the file adapter, the primary key on the SQLite one — both make
    the refusal atomic. Of N racers on one key, exactly one wins."""
    store = Sidecar(adapter)
    n = 8
    barrier = threading.Barrier(n)
    outcomes: list[str] = []
    guard = threading.Lock()

    def racer(i: int) -> None:
        barrier.wait()
        try:
            store.put("custody", "note", "n", Classified(Rung.L2, f"w{i}"))
            with guard:
                outcomes.append("won")
        except RecordExists:
            with guard:
                outcomes.append("refused")

    threads = [threading.Thread(target=racer, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("won") == 1, outcomes
    assert outcomes.count("refused") == n - 1


# ── I-11 at the storage boundary — fail closed to L5, on either backing ──────

def test_a_corrupt_blob_reads_l5(adapter):
    adapter.write(SIDECAR, key("custody", "deadline", "x"), "{not json at all")
    assert Sidecar(adapter).get("custody", "deadline", "x").rung is Rung.L5


def test_a_missing_or_unreadable_rung_reads_l5(adapter):
    for bad in (None, "L9", "unknown", 3, True):
        adapter.write(SIDECAR, key("custody", "deadline", "x"),
                      json.dumps({"rung": bad, "payload": "a name"}))
        assert Sidecar(adapter).get("custody", "deadline", "x").rung is Rung.L5, bad


def test_a_derived_form_lost_reads_l5(adapter):
    adapter.write(SIDECAR, key("custody", "deadline", "x"),
                  json.dumps({"rung": "L3", "payload": "a name"}))
    assert Sidecar(adapter).get("custody", "deadline", "x").rung is Rung.L5


# ── I-6 · the canonical handle is read-only by type ──────────────────────────

def test_i6_canonical_has_no_write_methods():
    for forbidden in ("put", "write", "update", "delete", "purge", "remove", "drop", "insert"):
        assert not hasattr(Canonical, forbidden), f"Canonical.{forbidden} exists"


def test_canonical_reads_what_was_placed(adapter):
    adapter.write(CANONICAL, key("custody", "filing", "petition"),
                  json.dumps({"rung": "L4", "payload": "a diagnosis", "derived": "a filing exists"}))
    got = Canonical(adapter).get("custody", "filing", "petition")
    assert got.rung is Rung.L4 and got.payload == "a diagnosis"
    adapter.write(CANONICAL, key("custody", "filing", "petition"),
                  json.dumps({"rung": "L9", "payload": "a diagnosis"}))
    assert Canonical(adapter).get("custody", "filing", "petition").rung is Rung.L5


# ── enumeration, deadlines, advice — over either backing ─────────────────────

def test_records_enumerates_a_matter(adapter):
    store = Sidecar(adapter)
    store.put("custody", "courthouse", "main", Classified(Rung.L1, "Dept 4"))
    store.put("custody", "case_number", "primary", Classified(Rung.L3, "FL-1", derived="d"))
    store.put("bankruptcy", "docket", "d1", Classified(Rung.L1, "public"))
    got = dict(store.records("custody"))
    assert set(got) == {("custody", "courthouse", "main"), ("custody", "case_number", "primary")}


def test_records_reads_a_corrupt_row_as_l5(adapter):
    store = Sidecar(adapter)
    store.put("custody", "case_number", "primary", Classified(Rung.L3, "FL-1", derived="d"))
    adapter.write(SIDECAR, key("custody", "notes", "n1"), "corrupt")
    got = dict(store.records("custody"))
    assert got[("custody", "notes", "n1")].rung is Rung.L5
    assert got[("custody", "case_number", "primary")].rung is Rung.L3


def test_deadlines_parse_gate_and_gap(adapter):
    store = Sidecar(adapter)
    store.put("custody", "deadline", "resp", Classified(Rung.L1, "2026-08-05", "a response"))
    store.put("custody", "deadline", "eval", Classified(Rung.L4, "2026-08-12", "an eval is due"))
    store.put("custody", "deadline", "sealed", Classified(Rung.L5, "2026-08-11"))
    store.put("custody", "deadline", "broken", Classified(Rung.L1, "sometime", "a bad date"))

    dues = {d.ref[2]: d for d in store.deadlines("custody")}
    assert "sealed" not in dues                      # L5 dropped
    assert dues["resp"].iso == "2026-08-05"          # L1 parsed
    assert dues["eval"].shown == "an eval is due"    # L4 shows derived, not the date
    assert dues["broken"].gap is True and dues["broken"].iso is None   # unparseable → gap (I-8)


def test_advise_flags_a_misdeclared_record(adapter):
    store = Sidecar(adapter)
    store.put("custody", "notes", "n1",
              Classified(Rung.L4, "SSN 123-45-6789 for the form", derived="a note"))
    assert any(a.category == "ssn" for a in store.advise("custody", "notes", "n1"))
