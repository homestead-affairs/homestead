"""Wave 4 · E4-sync-core — `keep/sync.py` and `keep/household.py`.

Promotes `tests/test_invariants_pending.py`'s I-37/I-38/I-40 (provisional)
out of that file, unmarked, and adds the rest of the audit checklist: the
full `SyncScope` refusal table, the scope-ceiling drop (not derive), the
S4/`Purpose.SYNC` gate call, which `_CEILING` cell governs an `L4` row under
a sync, envelope stability and tamper refusal, and the delivery contract.

Decision 5 (`docs/PLAN-affairs-face.md`), `docs/DECISION-sync-envelope-and-
consent.md` (proposed here, `verified_by:` blank), and
`docs/DECISION-purpose-sync.md` (ratified) are what this file checks against.
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
