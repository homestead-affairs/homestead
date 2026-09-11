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
import uuid

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


# ── the audit's own additions (E4-postgres-fleet audit, 2026-09-11) ─────────

#: A fresh token per run. The tests below name their own households rather
#: than deriving one from `HOMESTEAD_HOME`, and a fixed name would make them
#: pass once against a clean database and fail on every re-run — a test that
#: only works the first time is a test that will be deleted.
_RUN = uuid.uuid4().hex[:12]


def _hh(name: str) -> str:
    return f"hh-{name}-{_RUN}"


def _envelope_for(household, rows, composed_at="2026-01-01T00:00:00+00:00", head="genesis"):
    """A hand-built envelope for a named household — the end-to-end tests
    above compose one from a real store, which is the right shape for the
    happy path but cannot produce a *hostile* row, an envelope for a second
    household, or two envelopes in a chosen order."""
    from homestead.keep import sync as sync_mod

    identity = {
        "schema": sync_mod.SCHEMA, "household": household,
        "composed_at": composed_at, "head": head,
        "scope": {"matters": ["custody"], "item_types": None,
                  "ceiling": "L3", "tables": ["sidecar"]},
        "rows": list(rows), "count": len(rows),
    }
    return sync_mod.Envelope(
        schema=identity["schema"], household=identity["household"],
        composed_at=identity["composed_at"], head=identity["head"],
        scope=identity["scope"], rows=tuple(identity["rows"]),
        count=identity["count"], envelope_id=sync_mod._envelope_id(identity),
    )


def _hostile_row(**over):
    row = {
        "table": "sidecar", "matter": "custody", "item_type": "note",
        "item_id": "n1", "rung": "L1", "disposition": "render",
        "value": "public value", "derived": None,
    }
    row.update(over)
    return row


INJECTION = "x'); DROP TABLE sidecar; --"


def test_an_injection_shaped_value_lands_as_a_literal_string(home):
    """Every value is a `%s` parameter, so a `matter` that reads as SQL is
    stored as the text it is. A `household` of ten thousand characters is
    stored whole — `TEXT`, not a guessed width."""
    from homestead.keep import fleet_cli

    hh = _hh("wide") + "a" * 10_000
    env = _envelope_for(hh, [_hostile_row(matter=INJECTION, item_id="inj")])
    assert fleet_cli.ingest(env, DSN).written == 1

    (stored,) = _query_one(
        DSN, "SELECT matter FROM sidecar WHERE household=%s AND item_id=%s", (hh, "inj")
    )
    assert stored == INJECTION, "the value is a parameter, never SQL text"

    (length,) = _query_one(
        DSN, "SELECT length(household) FROM sidecar WHERE household=%s AND item_id=%s",
        (hh, "inj"),
    )
    assert length == len(hh)

    # The tables the injection names are all still there.
    for table in ("sidecar", "canonical", "envelopes", "anchors"):
        assert _query_one(DSN, f"SELECT to_regclass('{table}') IS NOT NULL", ()) == (True,)


def test_nothing_from_a_failed_envelope_persists_and_a_rerun_succeeds():
    """Atomicity, against the real engine: a planted failure on the last
    row's `execute` must leave no row, no `envelopes` row and no `anchors`
    row — and the re-run must then succeed, with no half-ingested state
    standing in its way. (`ensure_schema()`'s DDL commits before the data
    transaction opens, so the tables survive the rollback; that is what the
    re-run needs.)"""
    from homestead.keep import fleet_cli

    hh = _hh("atomicity-audit")
    env = _envelope_for(hh, [_hostile_row(item_id=f"r{i}") for i in range(3)])
    real_connect = fleet_cli._connect

    class Planted(Exception):
        pass

    class _Cur:
        def __init__(self, inner, owner):
            self._inner, self._owner = inner, owner

        def __enter__(self):
            self._inner.__enter__()
            return self

        def __exit__(self, *exc):
            return self._inner.__exit__(*exc)

        def execute(self, sql, params=None):
            if sql.strip().startswith("INSERT INTO sidecar"):
                self._owner.n += 1
                if self._owner.n == 3:
                    raise Planted("the last row of the envelope")
            return self._inner.execute(sql, params)

        def fetchone(self):
            return self._inner.fetchone()

        @property
        def rowcount(self):
            return self._inner.rowcount

    class _Conn:
        def __init__(self, inner):
            self._inner, self.n = inner, 0

        def cursor(self):
            return _Cur(self._inner.cursor(), self)

        def commit(self):
            return self._inner.commit()

        def rollback(self):
            return self._inner.rollback()

        def close(self):
            return self._inner.close()

    fleet_cli._connect = lambda dsn: _Conn(real_connect(dsn))
    try:
        with pytest.raises(Planted):
            fleet_cli.ingest(env, DSN)
    finally:
        fleet_cli._connect = real_connect

    for table in ("sidecar", "envelopes", "anchors"):
        assert _query_one(
            DSN, f"SELECT count(*) FROM {table} WHERE household=%s", (hh,)
        ) == (0,), f"{table} kept something from an envelope that never committed"

    assert fleet_cli.ingest(env, DSN).written == 3, "the re-run is not blocked"
    assert _query_one(
        DSN, "SELECT count(*) FROM sidecar WHERE household=%s", (hh,)
    ) == (3,)


def test_a_crash_after_commit_leaves_the_envelope_in_and_a_rerun_refuses_by_name():
    """The other side of atomicity, pinned rather than fixed: if the process
    dies after the commit but before the CLI prints, the envelope *is* in.
    The re-run is then a re-ingest, refused by name — which is the right
    answer, and is why the refusal exists."""
    from homestead.keep import fleet_cli

    hh = _hh("crash-after-commit")
    env = _envelope_for(hh, [_hostile_row(item_id="r1")])
    assert fleet_cli.ingest(env, DSN).written == 1
    with pytest.raises(fleet_cli.IngestRefused) as e:
        fleet_cli.ingest(env, DSN)
    assert env.envelope_id in str(e.value) and "already ingested" in str(e.value)


def test_the_adapter_and_the_ingest_write_the_same_row():
    """Two code paths, one contract. `ingest()` now writes rows through
    `PostgresAdapter.insert/write`, so this is a regression test for the
    duplication it replaced: the same row, written each way into two
    households, must come back identical column for column, and the two
    `ON CONFLICT` clauses must behave as claimed (canonical insert-only,
    sidecar upsert)."""
    from homestead.keep import fleet_cli
    from homestead.keep.store import CANONICAL, SIDECAR, PostgresAdapter

    blob = '{"rung": "L1", "payload": "the same blob", "derived": null}'
    ha, hb = _hh("path-ingest"), _hh("path-adapter")
    env = _envelope_for(ha, [_hostile_row(item_id="cmp", value=blob)])
    fleet_cli.ingest(env, DSN)

    adapter = PostgresAdapter(DSN, household=hb)
    adapter.write(SIDECAR, ("custody", "note", "cmp"), blob,
                  envelope=env.envelope_id, synced_at="2026-01-01T00:00:00+00:00")

    cols = "matter, item_type, item_id, value, envelope"
    assert (
        _query_one(DSN, f"SELECT {cols} FROM sidecar WHERE household=%s AND item_id='cmp'", (ha,))
        == _query_one(DSN, f"SELECT {cols} FROM sidecar WHERE household=%s AND item_id='cmp'", (hb,))
    ), "the two paths must write the same row"

    ts = "2026-01-01T00:00:00+00:00"
    assert adapter.insert(CANONICAL, ("custody", "note", "c"), blob, envelope="e1", synced_at=ts) == 1
    assert adapter.insert(CANONICAL, ("custody", "note", "c"), "OTHER", envelope="e2", synced_at=ts) == 0
    assert _query_one(
        DSN, "SELECT value FROM canonical WHERE household=%s AND item_id='c'", (hb,)
    ) == (blob,), "canonical is insert-only — DO NOTHING, never overwritten"


def test_a_stale_envelope_is_refused_and_allow_stale_leaves_the_anchor():
    """A *different* envelope with an older `composed_at` than the anchored
    one would move the household's anchor backwards, so it is refused by
    name. `--allow-stale` ingests its rows and still leaves the anchor where
    it is: the anchor only ever moves forward."""
    from homestead.keep import fleet_cli

    hh = _hh("stale-audit")
    newer = _envelope_for(hh, [_hostile_row(item_id="new")],
                          composed_at="2026-05-01T00:00:00+00:00", head="HEAD-NEW")
    older = _envelope_for(hh, [_hostile_row(item_id="old")],
                          composed_at="2026-01-01T00:00:00+00:00", head="HEAD-OLD")

    assert fleet_cli.ingest(newer, DSN).anchor_moved is True
    with pytest.raises(fleet_cli.IngestRefused) as e:
        fleet_cli.ingest(older, DSN)
    assert "backwards" in str(e.value) and "--allow-stale" in str(e.value)
    assert _query_one(
        DSN, "SELECT count(*) FROM sidecar WHERE household=%s AND item_id='old'", (hh,)
    ) == (0,), "a refused stale envelope writes nothing"

    result = fleet_cli.ingest(older, DSN, allow_stale=True)
    assert result.written == 1 and result.anchor_moved is False
    assert _query_one(DSN, "SELECT head, envelope FROM anchors WHERE household=%s", (hh,)) == (
        "HEAD-NEW", newer.envelope_id,
    ), "the anchor never moves backwards, even with --allow-stale"


def test_two_households_in_one_database_never_see_each_others_rows():
    """Every statement is scoped to the household the adapter was
    constructed with, and the primary key carries it — the same key in two
    households is two rows, and a read of one never returns the other."""
    from homestead.keep import fleet_cli
    from homestead.keep.store import SIDECAR, PostgresAdapter

    h1, h2 = _hh("tenant-one"), _hh("tenant-two")
    fleet_cli.ingest(_envelope_for(h1, [_hostile_row(item_id="same", value="one")]), DSN)
    fleet_cli.ingest(_envelope_for(h2, [_hostile_row(item_id="same", value="two")]), DSN)

    assert PostgresAdapter(DSN, household=h1).read(SIDECAR, ("custody", "note", "same")) == "one"
    assert PostgresAdapter(DSN, household=h2).read(SIDECAR, ("custody", "note", "same")) == "two"
    assert PostgresAdapter(DSN, household=h1).read_matter(SIDECAR, "custody") == [
        (("custody", "note", "same"), "one")
    ]
    assert _query_one(
        DSN, "SELECT count(*) FROM sidecar WHERE item_id='same' AND household IN (%s,%s)", (h1, h2)
    ) == (2,)
