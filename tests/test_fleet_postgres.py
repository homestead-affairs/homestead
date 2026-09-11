"""E4-postgres-fleet's end-to-end leg — a real Postgres, the whole pipeline.

`tests/test_invariants_fleet.py` proves the shape without a database at all
(fake cursors, `psycopg` blocked). This file composes a real `Envelope` from
a temp household store with `keep.sync`, delivers it to a file drop exactly
as an operator would, and ingests that file into a real Postgres — the DDL
actually creates usable tables, `ON CONFLICT` behaves as claimed against a
real engine, and a second ingest really does see what the first one wrote.

Marked `fleet` and skipped, not failed, when `HOMESTEAD_FLEET_TEST_DSN` is
unset (every machine except the CI `fleet` job and a local run against a
Postgres the builder started by hand) — keeping the default `invariants`
matrix psycopg-free (I-27).
"""
from __future__ import annotations

import os

import pytest

DSN = os.environ.get("HOMESTEAD_FLEET_TEST_DSN")

pytestmark = [
    pytest.mark.fleet,
    pytest.mark.skipif(
        not DSN, reason="HOMESTEAD_FLEET_TEST_DSN is not set — needs a live Postgres"
    ),
]


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    return tmp_path


def _put_sidecar(matter, item_type, item_id, rung, value, derived=None):
    from homestead.keep.rungs import Classified
    from homestead.keep.store import Sidecar

    Sidecar().put(matter, item_type, item_id, Classified(rung, value, derived))


def _put_canonical(matter, item_type, item_id, rung, value, derived=None):
    """The canonical table has no `put` on the household side (I-6) — tests
    that need a canonical row write straight to the adapter, the same
    technique `tests/test_invariants_sync.py` uses."""
    from homestead.keep import store as _store
    from homestead.keep.rungs import Classified

    item = Classified(rung, value, derived)
    _store._default_adapter().write(
        _store.CANONICAL, (matter, item_type, item_id), _store._serialize(item)
    )


def _compose(matters=("custody",), ceiling=None, tables=("sidecar", "canonical")):
    from homestead.keep import sync
    from homestead.keep.rungs import Rung
    from homestead.keep.store import CANONICAL, SIDECAR, Canonical, Sidecar

    ceiling = ceiling or Rung.L3
    scope = sync.SyncScope(matters=matters, item_types=None, ceiling=ceiling, tables=tables)
    readers = {SIDECAR: Sidecar(), CANONICAL: Canonical()}
    return sync.compose(readers, scope)


def _deliver_and_reread(home, envelope):
    """Deliver to a file drop, exactly as an operator would, then read that
    same file back — the bytes `homestead-fleet ingest` would actually see,
    not the in-memory `Envelope` object."""
    from homestead.keep import sync

    drop = home / "drop"
    sync.deliver(envelope, confirm=lambda w: True, drop_dir=drop)
    body = (drop / f"{envelope.envelope_id}.json").read_bytes()
    return sync.Envelope.from_bytes(body)


def _query_one(dsn, sql, params):
    import psycopg

    conn = psycopg.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()


def test_ddl_is_idempotent():
    """`ensure_schema()` runs at the top of every ingest — a second call
    against a database it already shaped must not raise."""
    import psycopg

    from homestead.keep import fleet_cli

    conn = psycopg.connect(DSN)
    try:
        fleet_cli.ensure_schema(conn)
        fleet_cli.ensure_schema(conn)
    finally:
        conn.close()


def test_ingest_end_to_end_writes_rows_sets_the_anchor_and_refuses_a_reingest(home):
    from homestead.keep import fleet_cli, household
    from homestead.keep.rungs import Rung

    _put_sidecar("custody", "deadline", "primary.hearing", Rung.L1, "2026-10-06")
    _put_canonical("custody", "note", "c1", Rung.L1, "canonical note one")

    envelope = _compose()
    assert envelope.count == 2
    read_back = _deliver_and_reread(home, envelope)

    result = fleet_cli.ingest(read_back, DSN, household=household.household_id())
    assert result.written == 2
    assert result.skipped == 0

    with pytest.raises(fleet_cli.IngestRefused):
        fleet_cli.ingest(read_back, DSN, household=household.household_id())

    (sidecar_value,) = _query_one(
        DSN,
        "SELECT value FROM sidecar WHERE household=%s AND matter=%s "
        "AND item_type=%s AND item_id=%s",
        (envelope.household, "custody", "deadline", "primary.hearing"),
    )
    assert "2026-10-06" in sidecar_value

    (canonical_value,) = _query_one(
        DSN,
        "SELECT value FROM canonical WHERE household=%s AND matter=%s "
        "AND item_type=%s AND item_id=%s",
        (envelope.household, "custody", "note", "c1"),
    )
    assert "canonical note one" in canonical_value

    anchor = _query_one(
        DSN, "SELECT head, envelope FROM anchors WHERE household=%s", (envelope.household,)
    )
    assert anchor == (envelope.head, envelope.envelope_id)

    ingested = _query_one(
        DSN,
        "SELECT row_count FROM envelopes WHERE household=%s AND envelope=%s",
        (envelope.household, envelope.envelope_id),
    )
    assert ingested == (2,)


def test_canonical_is_insert_only_sidecar_upserts(home):
    """A second envelope changing both a sidecar row and a canonical row:
    the sidecar row is replaced (upsert), the canonical row is not (insert
    only, skipped) — the fleet's own copy of I-6."""
    from homestead.keep import fleet_cli, household
    from homestead.keep.rungs import Rung

    _put_sidecar("custody", "deadline", "primary.hearing", Rung.L1, "2026-10-06")
    _put_canonical("custody", "note", "c1", Rung.L1, "original canonical value")

    first = _deliver_and_reread(home, _compose())
    hh = household.household_id()
    first_result = fleet_cli.ingest(first, DSN, household=hh)
    assert first_result.written == 2 and first_result.skipped == 0

    # Change both: an ordinary sidecar overwrite, and a "canonical" row
    # only possible by writing the adapter directly (_put_canonical) — the
    # point under test is the *fleet's* own insert-only behaviour, not
    # household-side read-only, which I-6 enforces elsewhere.
    from homestead.keep.rungs import Classified
    from homestead.keep.store import Sidecar

    Sidecar().put(
        "custody", "deadline", "primary.hearing", Classified(Rung.L1, "2026-11-01"),
        overwrite=True,
    )
    _put_canonical("custody", "note", "c1", Rung.L1, "a DIFFERENT canonical value")

    second = _deliver_and_reread(home, _compose())
    assert second.envelope_id != first.envelope_id, "changed content, a fresh envelope"

    second_result = fleet_cli.ingest(second, DSN, household=hh)
    assert second_result.written == 1, "the sidecar row"
    assert second_result.skipped == 1, "the canonical row, already there, is skipped"

    (sidecar_value,) = _query_one(
        DSN,
        "SELECT value FROM sidecar WHERE household=%s AND matter=%s "
        "AND item_type=%s AND item_id=%s",
        (hh, "custody", "deadline", "primary.hearing"),
    )
    assert "2026-11-01" in sidecar_value, "the sidecar row was replaced"

    (canonical_value,) = _query_one(
        DSN,
        "SELECT value FROM canonical WHERE household=%s AND matter=%s "
        "AND item_type=%s AND item_id=%s",
        (hh, "custody", "note", "c1"),
    )
    assert "original canonical value" in canonical_value
    assert "DIFFERENT" not in canonical_value, "the canonical row was never overwritten"

    anchor = _query_one(
        DSN, "SELECT head, envelope FROM anchors WHERE household=%s", (hh,)
    )
    assert anchor == (second.head, second.envelope_id), "the anchor tracks the latest ingest"
