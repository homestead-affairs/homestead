"""Wave 4 · E4-sync-core — `keep/sync.py` and `keep/household.py`.

Promotes `tests/test_invariants_pending.py`'s I-37/I-38/I-40 (provisional)
out of that file, unmarked, and adds the rest of the audit checklist: the
full `SyncScope` refusal table, the scope-ceiling drop (not derive), the
S4/`Purpose.SYNC` gate call, which `_CEILING` cell governs an `L4` row under
a sync, envelope stability and tamper refusal, and the delivery contract.

Decision 5 (`docs/PLAN-affairs-face.md`), `docs/DECISION-sync-envelope-and-
consent.md` (~~proposed here, `verified_by:` blank~~ ratified by the
E4-sync-core audit, 2026-09-11, with its amendments recorded there) and
`docs/DECISION-purpose-sync.md` (ratified) are what this file checks against.
The final section is the audit's own, one test per amendment.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent / "homestead"
SYNC_SRC = PKG / "keep" / "sync.py"
HOUSEHOLD_SRC = PKG / "keep" / "household.py"


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def kit(home):
    from homestead.keep import household, logs, sync
    from homestead.keep.rungs import Classified, Purpose, Rung, Surface
    from homestead.keep.store import Sidecar

    def put(matter, item_type, item_id, rung, value, derived=None):
        Sidecar().put(matter, item_type, item_id, Classified(rung, value, derived))

    def scope(matters=("custody",), item_types=None, ceiling=Rung.L3, tables=("sidecar",)):
        return sync.SyncScope(matters=matters, item_types=item_types, ceiling=ceiling, tables=tables)

    return dict(
        household=household, logs=logs, sync=sync, Rung=Rung, Surface=Surface,
        Purpose=Purpose, Sidecar=Sidecar, put=put, scope=scope,
    )


def _lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _keys(obj):
    """Every mapping key anywhere inside a decoded JSON value — a top-level-
    only check misses a value leaked under `rows`."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _keys(v)


# ── promoted from tests/test_invariants_pending.py ───────────────────────────
# (I-37/I-38/I-40, provisional; ratified alongside this module by the audit)

def test_i37_a_sync_is_an_operator_authored_act(home, kit):
    """A refused confirm ledgers nothing and drops nothing (F-3's shape)."""
    sync, logs, put, scope = kit["sync"], kit["logs"], kit["put"], kit["scope"]
    from homestead.keep.egress import EgressRefused

    put("custody", "deadline", "primary.hearing", kit["Rung"].L1, "2026-10-06")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope())

    drop = home / "drop"
    with pytest.raises(EgressRefused):
        sync.deliver(envelope, confirm=None, drop_dir=drop)

    assert _lines(logs.IntegrityLog().path) == []
    assert logs.VisibleLog().read() == []
    assert not (drop.exists() and any(drop.iterdir()))


def test_i38_an_envelope_is_ledgered_once_with_references_only(home, kit):
    """One integrity entry, referenced by act, and one visible line — neither
    carrying the served value (F-4's shape, on the sync path)."""
    sync, logs, put, scope = kit["sync"], kit["logs"], kit["put"], kit["scope"]

    SECRET_DATE = "2026-10-06"
    put("custody", "deadline", "primary.hearing", kit["Rung"].L1, SECRET_DATE)
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope())
    sync.deliver(envelope, confirm=lambda wire: True, drop_dir=home / "drop")

    entries = _lines(logs.IntegrityLog().path)
    assert len(entries) == 1
    (entry,) = entries
    assert entry["act"] == "record_synced"
    for field in ("household", "envelope", "purpose", "scope", "rows", "destination"):
        assert field in entry
    keys = set(_keys(entry))
    for banned in ("value", "payload", "derived"):
        assert banned not in keys
    raw = json.dumps(entry)
    assert SECRET_DATE not in raw
    assert entry["household"] == envelope.household
    assert entry["envelope"] == envelope.envelope_id

    (visible,) = logs.VisibleLog().read()
    assert visible["event"] == logs.Event.RECORD_SYNCED.value
    assert visible["ref"] == f"{envelope.household}/{envelope.envelope_id}"
    assert SECRET_DATE not in json.dumps(visible)


def test_i40_an_unnamed_scope_syncs_nothing(home, kit):
    """The positive control matters as much as the two refusals: neither may
    be a `TypeError` (that is a changed signature, not a declined scope)."""
    scope, Rung = kit["scope"], kit["Rung"]

    assert scope() is not None
    with pytest.raises(Exception) as e1:
        scope(matters=())
    with pytest.raises(Exception) as e2:
        scope(ceiling=Rung.L5)
    assert not isinstance(e1.value, TypeError)
    assert not isinstance(e2.value, TypeError)


# ── the rest of the SyncScope refusal table ──────────────────────────────────

@pytest.mark.parametrize(
    "kwargs, expect_type",
    [
        pytest.param(dict(matters=(), ceiling="L3", tables=("sidecar",)), "value", id="empty-matters"),
        pytest.param(dict(matters=("custody",), ceiling="L3", tables=()), "value", id="empty-tables"),
        pytest.param(dict(matters=("custody",), ceiling="L5", tables=("sidecar",)), "value", id="l5-ceiling"),
        pytest.param(dict(matters=("custody",), ceiling="L3", tables=("sidecar", "junk")), "value", id="unknown-table"),
        pytest.param(dict(matters=["custody"], ceiling="L3", tables=("sidecar",)), "type", id="matters-not-a-tuple"),
        pytest.param(dict(matters=("custody",), ceiling="L3", tables=["sidecar"]), "type", id="tables-not-a-tuple"),
        pytest.param(dict(matters=("custody",), item_types=["deadline"], ceiling="L3", tables=("sidecar",)), "type", id="item-types-not-a-tuple-or-none"),
        pytest.param(dict(matters=("custody",), ceiling=None, tables=("sidecar",)), "type", id="ceiling-not-a-rung"),
    ],
)
def test_the_full_syncscope_refusal_table(home, kit, kwargs, expect_type):
    """Every way `SyncScope` refuses: `UnnamedScope` (a `ValueError`) for a
    scope naming too little, `TypeError` for the wrong kind of value."""
    sync, Rung = kit["sync"], kit["Rung"]
    kwargs = {"item_types": None, **kwargs}
    if isinstance(kwargs["ceiling"], str):
        kwargs["ceiling"] = getattr(Rung, kwargs["ceiling"])

    exc = TypeError if expect_type == "type" else sync.UnnamedScope
    with pytest.raises(exc):
        sync.SyncScope(**kwargs)


# ── compose(): drops DENY and above-ceiling rows, dropped not derived ───────

def test_compose_drops_l5_and_above_ceiling_rows_entirely(home, kit):
    """A denied datum and one above the scope's own ceiling are both
    **absent** — not `deny`-marked, not derived, not a `None`-valued row.
    `S4_EGRESS` with a declared purpose never returns `derive` at all (its
    ceiling with one is `L4`), so a surviving row's disposition is `render`."""
    sync, put, scope, Rung = kit["sync"], kit["put"], kit["scope"], kit["Rung"]

    put("custody", "note", "n1", Rung.L1, "public note")
    put("custody", "note", "n2", Rung.L2, "household note")
    put("custody", "note", "n3", Rung.L3, "attributed note", "an attributed note")
    put("custody", "note", "n4", Rung.L4, "SECRET-L4-VALUE", "a protected note")
    put("custody", "note", "n5", Rung.L5, "SECRET-L5-VALUE")

    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope(ceiling=Rung.L2))

    assert {row["item_id"] for row in envelope.rows} == {"n1", "n2"}
    for row in envelope.rows:
        assert row["disposition"] == "render"
        assert row["value"] is not None

    raw = json.dumps(envelope.rows)
    assert "SECRET-L4-VALUE" not in raw
    assert "SECRET-L5-VALUE" not in raw
    assert not any(row["disposition"] in ("deny", "derive") for row in envelope.rows)


def test_an_l4_row_under_an_l4_ceiling_is_rendered(home, kit):
    """Pins the governing cell: `_CEILING[S4_EGRESS] == (L2, L4)`. A declared
    purpose lifts to `L4`, so a `SyncScope(ceiling=L4)` renders an `L4` datum
    in full — neither derived nor dropped. If a future ratification lowered
    the with-purpose cell below `L4`, this test would flip to asserting the
    row is dropped instead."""
    sync, put, scope, Rung = kit["sync"], kit["put"], kit["scope"], kit["Rung"]
    from homestead.keep.rungs import _CEILING, Surface

    assert _CEILING[Surface.S4_EGRESS] == (Rung.L2, Rung.L4), "recheck this test's premise"

    put("custody", "child", "kid1", Rung.L4, "Jane Doe", "a child on the custody matter")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope(ceiling=Rung.L4))

    assert len(envelope.rows) == 1
    (row,) = envelope.rows
    assert row["rung"] == "L4" and row["disposition"] == "render" and row["value"] == "Jane Doe"


def test_compose_serves_on_s4_egress_with_purpose_sync(home, kit, monkeypatch):
    """`compose()` scores every candidate on `Surface.S4_EGRESS` with
    `Purpose.SYNC` — checked by recording the call."""
    sync, put, scope = kit["sync"], kit["put"], kit["scope"]
    Surface, Purpose = kit["Surface"], kit["Purpose"]

    put("custody", "note", "n1", kit["Rung"].L1, "hi")
    calls = []
    real_serve = sync.serve

    def spy(item, surface, *, purpose=None):
        calls.append((surface, purpose))
        return real_serve(item, surface, purpose=purpose)

    monkeypatch.setattr(sync, "serve", spy)
    sync.compose({"sidecar": kit["Sidecar"]()}, scope())

    assert calls
    assert all(s is Surface.S4_EGRESS and p is Purpose.SYNC for s, p in calls)


def test_compose_respects_item_types_and_matters(home, kit):
    """A `SyncScope` narrows to exactly the matters and item types named."""
    sync, put, scope, Rung = kit["sync"], kit["put"], kit["scope"], kit["Rung"]

    put("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    put("custody", "note", "n1", Rung.L1, "a note")
    put("bankruptcy", "deadline", "d2", Rung.L1, "2026-11-01")

    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope(item_types=("deadline",)))
    assert {(r["matter"], r["item_type"], r["item_id"]) for r in envelope.rows} == {
        ("custody", "deadline", "d1")
    }


# ── the envelope itself ──────────────────────────────────────────────────────

def test_envelope_id_is_stable_and_changes_with_a_row(home, kit, monkeypatch):
    """The same store composed twice at the same instant produces the same
    id; a changed store changes it. `_now_iso` is frozen — `composed_at`
    genuinely differing across wall-clock time is not the property tested."""
    sync, put, scope, Rung = kit["sync"], kit["put"], kit["scope"], kit["Rung"]
    Sidecar = kit["Sidecar"]

    monkeypatch.setattr(sync, "_now_iso", lambda: "2026-01-01T00:00:00+00:00")
    put("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    s = scope()

    first = sync.compose({"sidecar": Sidecar()}, s)
    second = sync.compose({"sidecar": Sidecar()}, s)
    assert first.envelope_id == second.envelope_id

    put("custody", "deadline", "d2", Rung.L1, "2026-11-01")
    third = sync.compose({"sidecar": Sidecar()}, s)
    assert third.envelope_id != first.envelope_id


def test_envelope_from_bytes_refuses_a_tampered_byte(home, kit):
    sync, put, scope, Rung = kit["sync"], kit["put"], kit["scope"], kit["Rung"]

    put("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope())

    body = envelope.to_bytes()
    assert sync.Envelope.from_bytes(body) == envelope

    tampered = bytearray(body)
    tampered[-4] ^= 0xFF
    with pytest.raises(sync.TamperedEnvelope):
        sync.Envelope.from_bytes(bytes(tampered))
    with pytest.raises(sync.TamperedEnvelope):
        sync.Envelope.from_bytes(body[:-2])


# ── deliver(): destinations, duplication, and what the confirm sees ─────────

def test_url_and_drop_dir_both_or_neither_is_refused(home, kit):
    sync, put, scope, Rung = kit["sync"], kit["put"], kit["scope"], kit["Rung"]

    put("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope())

    with pytest.raises(ValueError):
        sync.deliver(envelope, confirm=lambda w: True)
    with pytest.raises(ValueError):
        sync.deliver(envelope, confirm=lambda w: True, url="https://example.invalid/x", drop_dir=home / "drop")


def test_a_refused_confirm_leaves_both_logs_byte_identical(home, kit):
    """Byte-for-byte, not just "no new lines" — checked around a prior
    *successful* delivery so a refusal has something it could append to."""
    sync, logs, put, scope = kit["sync"], kit["logs"], kit["put"], kit["scope"]
    Rung, Sidecar = kit["Rung"], kit["Sidecar"]

    put("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    s = scope()
    sync.deliver(sync.compose({"sidecar": Sidecar()}, s), confirm=lambda w: True, drop_dir=home / "drop")

    integrity_before = logs.IntegrityLog().path.read_bytes()
    visible_before = logs.VisibleLog().path.read_bytes()

    put("custody", "deadline", "d2", Rung.L1, "2026-11-01")
    second = sync.compose({"sidecar": Sidecar()}, s)
    from homestead.keep.egress import EgressRefused

    with pytest.raises(EgressRefused):
        sync.deliver(second, confirm=lambda w: False, drop_dir=home / "drop")

    assert logs.IntegrityLog().path.read_bytes() == integrity_before
    assert logs.VisibleLog().path.read_bytes() == visible_before


def test_the_file_drop_is_o_excl(home, kit):
    """A second delivery of the same envelope, and a file already at the
    target name with the ledger wiped, are both refused (I-9's shape)."""
    sync, put, scope, Rung = kit["sync"], kit["put"], kit["scope"], kit["Rung"]

    put("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope())

    drop = home / "drop"
    sync.deliver(envelope, confirm=lambda w: True, drop_dir=drop)
    with pytest.raises(sync.AlreadyDelivered):
        sync.deliver(envelope, confirm=lambda w: True, drop_dir=drop)

    kit["logs"].IntegrityLog().path.unlink()   # the ledger check alone no longer applies
    assert (drop / f"{envelope.envelope_id}.json").exists()
    with pytest.raises(sync.AlreadyDelivered):   # the O_EXCL write is the structural backstop
        sync.deliver(envelope, confirm=lambda w: True, drop_dir=drop)


def test_the_file_wire_names_the_destination_and_size_never_a_row(home, kit):
    sync, put, scope, Rung = kit["sync"], kit["put"], kit["scope"], kit["Rung"]

    SECRET = "2026-10-06-A-VERY-SPECIFIC-DATE"
    put("custody", "deadline", "d1", Rung.L1, SECRET)
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope())

    seen = []
    sync.deliver(envelope, confirm=lambda w: seen.append(w) or True, drop_dir=home / "drop")

    (wire,) = seen
    assert wire.method == "FILE"
    assert str(home / "drop" / f"{envelope.envelope_id}.json") == wire.url
    assert SECRET not in wire.body and SECRET not in wire.url
    assert "bytes" in wire.body


def test_url_leg_uses_egress_send_with_its_own_confirm(home, kit, monkeypatch):
    """The URL leg is exactly `egress.send` — same refusal, same per-call
    confirm — proven by a declined confirm refusing with no network reached,
    and (transport injected, same technique `test_invariants_egress.py`
    uses) an approved one ledgering the URL as the destination."""
    sync, logs, put, scope = kit["sync"], kit["logs"], kit["put"], kit["scope"]

    SECRET = "2026-10-06"
    put("custody", "deadline", "d1", kit["Rung"].L1, SECRET)
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope())

    from homestead.keep.egress import EgressRefused

    with pytest.raises(EgressRefused):
        sync.deliver(envelope, confirm=lambda w: False, url="https://example.invalid/intake")
    assert _lines(logs.IntegrityLog().path) == []

    calls = []
    monkeypatch.setattr(sync.egress, "_default_transport", lambda wire: calls.append(wire) or "ok")

    sync.deliver(envelope, confirm=lambda w: True, url="https://example.invalid/intake")
    assert calls and calls[0].url == "https://example.invalid/intake"

    (entry,) = _lines(logs.IntegrityLog().path)
    assert entry["destination"] == "https://example.invalid/intake"
    assert SECRET not in json.dumps(entry)


def test_every_new_refusal_message_names_no_record_value(home, kit):
    sync, put, scope, Rung = kit["sync"], kit["put"], kit["scope"], kit["Rung"]

    SECRET = "SECRET-VALUE-9f3ab1"
    put("custody", "note", "n1", Rung.L3, SECRET, "a note")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope())
    assert SECRET in json.dumps(envelope.rows), "sanity: the value really is in the envelope"

    messages: list[str] = []
    from homestead.keep.egress import EgressRefused

    with pytest.raises(EgressRefused) as e1:
        sync.deliver(envelope, confirm=None, drop_dir=home / "drop")
    messages.append(str(e1.value))

    with pytest.raises(sync.UnnamedScope) as e2:
        scope(matters=())
    messages.append(str(e2.value))

    with pytest.raises(sync.TamperedEnvelope) as e3:
        sync.Envelope.from_bytes(b"not json at all, and definitely not " + SECRET.encode())
    messages.append(str(e3.value))

    sync.deliver(envelope, confirm=lambda w: True, drop_dir=home / "drop")
    with pytest.raises(sync.AlreadyDelivered) as e4:
        sync.deliver(envelope, confirm=lambda w: True, drop_dir=home / "drop")
    messages.append(str(e4.value))

    for msg in messages:
        assert SECRET not in msg


# ── the chokepoint holds in this file too (I-16) ────────────────────────────

def _payload_reaches(tree: ast.AST) -> list[int]:
    return [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "payload"
    ]


def test_sync_and_household_reach_no_payload():
    """Already covered by the whole-package scan in
    `test_invariants_chokepoint.py` (neither file is in its `ALLOWED` set) —
    named here too, plus a planted-violation fire test (a scan that has
    never fired has not been shown to check anything)."""
    for src in (SYNC_SRC, HOUSEHOLD_SRC):
        assert not _payload_reaches(ast.parse(src.read_text(encoding="utf-8")))

    planted = SYNC_SRC.read_text(encoding="utf-8") + "\ndef _leak(item):\n    return item.payload\n"
    assert _payload_reaches(ast.parse(planted))


def test_sync_row_shape_is_served_value_plus_derived_only(home, kit):
    """Every row is `table`/`matter`/`item_type`/`item_id`/`rung`/
    `disposition`/`value` (from `Served`) plus `derived` (the one field read
    directly off `Classified`) — nothing else."""
    sync, put, scope = kit["sync"], kit["put"], kit["scope"]

    put("custody", "note", "n1", kit["Rung"].L1, "hi")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, scope())
    (row,) = envelope.rows
    assert set(row) == {"table", "matter", "item_type", "item_id", "rung", "disposition", "value", "derived"}


# ── I-17 / I-30 / I-27, this bite's own slice ────────────────────────────────

_NET = {"socket", "ssl", "urllib", "http", "requests", "httpx", "aiohttp",
        "websockets", "urllib3", "socketserver", "ftplib", "telnetlib",
        "smtplib", "xmlrpc"}


def _toplevel_imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_i17_i30_sync_dials_nothing_and_listens_nothing():
    """This bite's own slice of the whole-package scans in
    `test_invariants_shape.py`: no network import, no listen/serve call."""
    banned_calls = {"listen", "serve_forever", "create_server", "ThreadingHTTPServer"}
    for src in (SYNC_SRC, HOUSEHOLD_SRC):
        tree = ast.parse(src.read_text(encoding="utf-8"))
        assert not (_NET & _toplevel_imports(tree))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                assert name not in banned_calls


def test_i27_no_new_dependency_was_declared():
    """E4-sync-core adds no dependency — the declared list is unchanged."""
    root = Path(__file__).resolve().parent.parent
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dependencies = ["holidays>=0.102,<1.0"]' in text


def test_smoke_imports_sync_and_household():
    """`--smoke` proves packaging survived for these two modules — asserted
    against the source since this file does not run the CLI."""
    src = (PKG / "app" / "__main__.py").read_text(encoding="utf-8")
    assert "sync" in src and "household" in src


# ── household.py ─────────────────────────────────────────────────────────────

def test_household_id_is_stable_and_shaped_hh_16_hex(home, kit):
    household = kit["household"]
    first = household.household_id()
    assert first == household.household_id()
    assert first.startswith("hh-") and len(first) == len("hh-") + 16
    int(first[3:], 16)   # the suffix is hex — raises otherwise


def test_household_id_create_can_lose_the_race(home, kit):
    """A second creator reads the winner's id back rather than overwriting
    it — simulated by pre-seeding the file as a winner would have left it."""
    household = kit["household"]
    from homestead.keep import paths

    paths.ensure(paths.home())
    (paths.home() / "household.id").write_text("hh-0123456789abcdef\n", encoding="utf-8")
    assert household.household_id() == "hh-0123456789abcdef"


def test_household_id_refuses_a_malformed_file_by_name(home, kit):
    household = kit["household"]
    from homestead.keep import paths

    paths.ensure(paths.home())
    (paths.home() / "household.id").write_text("not-an-id\n", encoding="utf-8")
    with pytest.raises(household.MalformedHouseholdId):
        household.household_id()


# ── E4-sync-core audit, 2026-09-11 ───────────────────────────────────────────
# Each test below reproduces something the built module did before the audit.

def _adapters():
    from homestead.keep.store import FileAdapter, SQLiteAdapter

    return FileAdapter(), SQLiteAdapter()


@pytest.mark.parametrize("table", ["sidecar", "canonical"])
def test_every_rung_by_every_ceiling_cell_on_both_tables(home, kit, table):
    """The whole (rung × ceiling) grid, on both tables — the audit's item 1.

    `S4_EGRESS` under a declared purpose has ceiling `L4`, so it renders
    every rung it does not deny and **never** returns `derive`: the scope's
    own ceiling is the only thing that stops an `L1`-minded operator sending
    `L4` in full. So each cell asserts exactly which rungs survive, that a
    survivor is `render` with its real value, and that `L5` is absent at
    every ceiling including the highest one a scope may name.
    """
    sync, Rung = kit["sync"], kit["Rung"]
    from homestead.keep.rungs import Classified
    from homestead.keep.store import CANONICAL, Canonical, SIDECAR, Sidecar, _serialize
    from homestead.keep import store as _store

    order = [Rung.L1, Rung.L2, Rung.L3, Rung.L4, Rung.L5]
    for rung in order:
        item = Classified(rung, f"VALUE-{rung.value}",
                          "a stand-in" if rung in (Rung.L3, Rung.L4) else None)
        if table == "sidecar":
            Sidecar().put("custody", "note", rung.value, item)
        else:
            _store._default_adapter().write(
                CANONICAL, ("custody", "note", rung.value), _serialize(item)
            )

    readers = {SIDECAR: Sidecar(), CANONICAL: Canonical()}
    for i, ceiling in enumerate([Rung.L1, Rung.L2, Rung.L3, Rung.L4]):
        envelope = sync.compose(
            readers,
            sync.SyncScope(matters=("custody",), item_types=None, ceiling=ceiling,
                           tables=(table,)),
        )
        expected = {r.value for r in order[: i + 1]}
        assert {row["item_id"] for row in envelope.rows} == expected, (
            f"{table} at ceiling {ceiling.value}"
        )
        assert "L5" not in {row["item_id"] for row in envelope.rows}
        for row in envelope.rows:
            assert row["disposition"] == "render"
            assert row["value"] == f"VALUE-{row['rung']}"
            assert row["table"] == table


def test_the_envelope_id_is_the_same_through_either_store_backing(home, kit):
    """The failure this guards against: an id addressed by iteration order
    rather than content. `FileAdapter` sorts `<item_id>.json` filenames and
    `SQLiteAdapter` sorts `item_id` columns, and they disagree wherever an id
    holds a `.` or a `-` — so one store composed through two backings gave
    two ids for identical rows, and `AlreadyDelivered` could not tell the
    second was the first."""
    sync, Rung = kit["sync"], kit["Rung"]
    from homestead.keep.rungs import Classified
    from homestead.keep.store import Sidecar

    ids = ["b", "a", "a-1", "a.1", "Z", "10"]
    file_adapter, sqlite_adapter = _adapters()
    for adapter in (file_adapter, sqlite_adapter):
        for item_id in ids:
            Sidecar(adapter).put("custody", "note", item_id, Classified(Rung.L1, f"v-{item_id}"))

    scope = kit["scope"]()
    composed = [sync.compose({"sidecar": Sidecar(a)}, scope)
                for a in (file_adapter, sqlite_adapter)]
    assert composed[0].rows == composed[1].rows
    assert [r["item_id"] for r in composed[0].rows] == sorted(ids)
    assert composed[0].envelope_id == composed[1].envelope_id


def test_from_bytes_refuses_a_forged_envelope_that_hashes_correctly(home, kit):
    """A matching id proves nothing was edited after composition; it proves
    nothing about whether the bytes were ever an envelope. Each forgery below
    carries a **correct** sha256 of its own contents and was accepted before
    the audit — the `rows`-as-an-object one silently becoming a one-tuple of a
    dict key."""
    import hashlib

    sync, Rung = kit["sync"], kit["Rung"]
    kit["put"]("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, kit["scope"]())

    def forge(**over):
        ident = envelope._identity_fields()
        ident.update(over)
        raw = json.dumps(ident, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        out = dict(ident, envelope_id=hashlib.sha256(raw.encode()).hexdigest())
        return json.dumps(out, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode()

    assert sync.Envelope.from_bytes(forge()) == envelope, "the positive control"
    for why, over in [
        ("a count that disagrees with len(rows)", dict(count=99)),
        ("another schema version", dict(schema="homestead.sync/99")),
        ("no schema at all", dict(schema=None)),
        ("rows as an object rather than an array", dict(rows={"table": "sidecar"})),
    ]:
        with pytest.raises(sync.TamperedEnvelope):
            sync.Envelope.from_bytes(forge(**over))
        assert why


def test_only_true_confirms_a_delivery_on_either_leg(home, kit, monkeypatch):
    """Truthiness is not consent. `lambda w: input("send? [y/N] ")` returns
    `"n"` — truthy — and sent the envelope before the audit. Both legs now
    take `True` and nothing else, and the confirm is called exactly **once**
    per delivery: on the URL leg by `egress.send`, which `deliver` does not
    pre-confirm behind."""
    sync, Rung = kit["sync"], kit["Rung"]
    from homestead.keep.egress import EgressRefused
    from homestead.keep.store import Sidecar

    monkeypatch.setattr(sync.egress, "_default_transport", lambda wire: "ok")
    drop = home / "drop"

    def fresh(tag):
        kit["put"]("custody", "note", tag, Rung.L1, "x")
        return sync.compose({"sidecar": Sidecar()}, kit["scope"]())

    for i, (why, answer) in enumerate([
        ("the string a [y/N] prompt returns for 'no'", "n"),
        ("any other truthy non-bool", 1),
        ("a truthy container", ["yes"]),
    ]):
        for leg in ("file", "url"):
            with pytest.raises(EgressRefused):
                sync.deliver(
                    fresh(f"{i}{leg}"), confirm=lambda w: answer,
                    **({"drop_dir": drop} if leg == "file" else {"url": "https://x.invalid/i"}),
                )
            assert why

    for leg in ("file", "url"):
        seen = []
        sync.deliver(
            fresh(f"ok{leg}"), confirm=lambda w: seen.append(w) or True,
            **({"drop_dir": drop} if leg == "file" else {"url": "https://x.invalid/i"}),
        )
        assert len(seen) == 1, f"{leg}: the confirm is shown once, not twice"
    assert seen[0].method == "POST", "the URL leg's one confirm is egress.send's own"


def test_a_relative_drop_dir_is_refused_and_a_drop_outside_home_stays_refused(home, kit):
    """The failure this guards against: `paths.ensure` resolves a relative
    path against `paths.home()` and `open()` resolves it against the cwd, so
    a relative `drop_dir` created `<home>/relout` and then wrote — or failed
    to write — into `<cwd>/relout`. The ledger's `destination` is the record
    of where an envelope went, and only an absolute path is that in every
    cwd. A drop *outside* `paths.home()` is refused by `paths.ensure`'s own
    containment rule, which this bite inherits rather than widens."""
    sync, Rung = kit["sync"], kit["Rung"]
    kit["put"]("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, kit["scope"]())

    with pytest.raises(ValueError, match="absolute"):
        sync.deliver(envelope, confirm=lambda w: True, drop_dir=Path("relout"))
    assert not (home / "relout").exists()

    with pytest.raises(ValueError, match="outside"):
        sync.deliver(envelope, confirm=lambda w: True, drop_dir=home.parent / "elsewhere")

    receipt = sync.deliver(envelope, confirm=lambda w: True, drop_dir=sync.default_drop_dir())
    from homestead.keep import paths

    assert Path(receipt.destination).is_absolute()
    assert receipt.destination.startswith(str(paths.exports_dir() / "sync"))
    assert _lines(kit["logs"].IntegrityLog().path)[-1]["destination"] == receipt.destination


def test_a_refused_confirm_does_not_even_create_the_directory(home, kit):
    """A refused act leaves nothing behind — the directory included. The
    drop was `mkdir`-ed before the confirm was shown before the audit."""
    sync, Rung = kit["sync"], kit["Rung"]
    from homestead.keep.egress import EgressRefused

    kit["put"]("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, kit["scope"]())

    never = home / "never"
    for confirm in (None, lambda w: False):
        with pytest.raises(EgressRefused):
            sync.deliver(envelope, confirm=confirm, drop_dir=never)
        assert not never.exists()


def test_a_symlink_at_the_target_is_refused_not_followed(home, kit):
    """`O_EXCL` fails on an existing symlink, so a symlink planted at
    `<envelope_id>.json` cannot redirect a drop over a file elsewhere."""
    import os

    sync, Rung = kit["sync"], kit["Rung"]
    kit["put"]("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, kit["scope"]())

    drop = home / "drop"
    drop.mkdir()
    victim = home / "victim.txt"
    victim.write_text("ORIGINAL", encoding="utf-8")
    os.symlink(victim, drop / f"{envelope.envelope_id}.json")

    with pytest.raises(sync.AlreadyDelivered):
        sync.deliver(envelope, confirm=lambda w: True, drop_dir=drop)
    assert victim.read_text(encoding="utf-8") == "ORIGINAL"


def test_the_write_order_is_destination_then_integrity_then_visible(home, kit, monkeypatch):
    """Pins the order, and with it the crash window ruled on in
    `docs/DECISION-sync-envelope-and-consent.md` § "The crash window": a
    crash after the destination and before the `IntegrityLog` leaves an
    envelope delivered and **unledgered**, never ledgered and unsent. That
    direction is the one an audit trail can live with, and the file leg's
    `O_EXCL` closes it structurally on a retry."""
    sync, logs, Rung = kit["sync"], kit["logs"], kit["Rung"]

    kit["put"]("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, kit["scope"]())
    drop = home / "drop"
    target = drop / f"{envelope.envelope_id}.json"

    class Boom(RuntimeError):
        pass

    class NoLedger(logs.IntegrityLog):
        def append(self, entry):
            raise Boom("crashed between the drop and the ledger")

    with pytest.raises(Boom):
        sync.deliver(envelope, confirm=lambda w: True, drop_dir=drop, integrity=NoLedger())
    assert target.exists(), "the destination is written first"
    assert _lines(logs.IntegrityLog().path) == []
    assert logs.VisibleLog().read() == []

    # ... and a retry of that same envelope is refused by O_EXCL, not re-sent.
    with pytest.raises(sync.AlreadyDelivered):
        sync.deliver(envelope, confirm=lambda w: True, drop_dir=drop)


def test_an_unreadable_ledger_line_refuses_by_name(home, kit):
    """A ledger this cannot read cannot be shown not to hold this envelope
    already, so the act does not happen — refused by name (I-11), never a
    bare `JSONDecodeError` out of `deliver`, and never a second delivery."""
    sync, logs, Rung = kit["sync"], kit["logs"], kit["Rung"]
    from homestead.keep.egress import EgressRefused

    kit["put"]("custody", "deadline", "d1", Rung.L1, "2026-10-06")
    envelope = sync.compose({"sidecar": kit["Sidecar"]()}, kit["scope"]())
    sync.deliver(envelope, confirm=lambda w: True, drop_dir=home / "drop")

    # Composed *before* the corruption: `compose()` reads the head through
    # `IntegrityLog.head()`, whose own behaviour on a half-written final line
    # is `keep/logs.py`'s to define, not this module's.
    kit["put"]("custody", "note", "n9", Rung.L1, "x")
    second = sync.compose({"sidecar": kit["Sidecar"]()}, kit["scope"]())

    path = logs.IntegrityLog().path
    path.write_text(path.read_text(encoding="utf-8") + '{"act": "record_syn',
                    encoding="utf-8")

    with pytest.raises(EgressRefused) as caught:
        sync.deliver(second, confirm=lambda w: True, drop_dir=home / "drop")
    assert "line" in str(caught.value)
    assert not (home / "drop" / f"{second.envelope_id}.json").exists()


def test_a_unicode_value_and_its_escaped_spelling_do_not_collide(home, kit):
    """`ensure_ascii=False` is pinned one way: a value holding `é` and a
    value holding the six characters `\\u00e9` are different records and must
    hash differently, or an envelope could be swapped for another."""
    sync = kit["sync"]

    assert sync._canonical_bytes({"x": "héllo"}) == b'{"x":"h\xc3\xa9llo"}'
    assert sync._envelope_id({"x": "héllo"}) != sync._envelope_id({"x": "h\\u00e9llo"})


@pytest.mark.parametrize(
    "content, ok",
    [
        ("hh-0123456789abcdef\n", True),
        ("hh-0123456789abcdef", True),
        ("hh-0123456789ABCDEF\n", False),
        ("hh-0123456789abcde\n", False),
        ("hh-0123456789abcdef0\n", False),
        ("hh-0123456789abcdef\nhh-ffffffffffffffff\n", False),
        ("", False),
    ],
)
def test_the_household_id_file_shape_table(home, kit, content, ok):
    """Uppercase hex, fifteen, seventeen, a second id on a second line and an
    empty file are all refused by name; a trailing newline or none is read.
    A regenerated id would fork a household whose fleet rows are already
    keyed by the first, which is why none of these regenerate."""
    household = kit["household"]
    from homestead.keep import paths

    paths.ensure(paths.home())
    (paths.home() / "household.id").write_text(content, encoding="utf-8")
    if ok:
        assert household.household_id() == "hh-0123456789abcdef"
    else:
        with pytest.raises(household.MalformedHouseholdId):
            household.household_id()
