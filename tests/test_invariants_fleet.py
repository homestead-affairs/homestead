"""Wave 4 · E4-postgres-fleet — `keep/store.PostgresAdapter` and
`keep/fleet_cli.py`.

Promotes `tests/test_invariants_pending.py`'s I-39 (provisional) out of that
file, unmarked, and adds the rest of this bite's audit checklist — all
without a live Postgres, which is what keeps this file in the default
`invariants` matrix (no `fleet` extra installed there).
`tests/test_fleet_postgres.py` (`@pytest.mark.fleet`) is the end-to-end
counterpart, against a real database.

Two tests below construct a real `PostgresAdapter`, which needs `psycopg`
importable (not a live server, just the driver), so they
`importorskip("psycopg")` and skip on a machine without the `fleet` extra.
"""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "homestead"
FLEET_SRC = PKG / "keep" / "fleet_cli.py"
STORE_SRC = PKG / "keep" / "store.py"

_BANNED_CALLS = {"listen", "serve_forever", "create_server", "ThreadingHTTPServer"}


def _offenders(tree) -> list[str]:
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name in _BANNED_CALLS:
                hits.append(name)
    return hits


def _toplevel_psycopg(tree) -> bool:
    for node in tree.body:
        if isinstance(node, ast.Import) and any(
            a.name.split(".")[0] == "psycopg" for a in node.names
        ):
            return True
        if (
            isinstance(node, ast.ImportFrom) and node.level == 0
            and (node.module or "").split(".")[0] == "psycopg"
        ):
            return True
    return False


# ── promoted from tests/test_invariants_pending.py (I-39, provisional) ──────

def test_i39_the_fleet_ingest_never_listens_and_lazy_imports_psycopg():
    """The failure this guards against: I-30's "nothing here listens" holding
    for every module except the one built to talk to a shared Postgres, and
    I-27's scan reading only `pyproject.toml`'s `dependencies` — so a
    module-level `import psycopg` would run clean in CI and only fail on a
    machine without the `fleet` extra. Static, over the source."""
    fleet_tree = ast.parse(FLEET_SRC.read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "main" for node in fleet_tree.body
    ), "fleet_cli must declare main() — homestead-fleet ingest's entry point"
    assert not _offenders(fleet_tree), "the fleet ingest must never listen (I-30)"
    assert not _toplevel_psycopg(fleet_tree), "psycopg must be lazy, not top-level (I-27)"

    store_tree = ast.parse(STORE_SRC.read_text(encoding="utf-8"))
    pg_class = next(
        (n for n in ast.walk(store_tree)
         if isinstance(n, ast.ClassDef) and n.name == "PostgresAdapter"),
        None,
    )
    assert pg_class is not None, "store.py must declare PostgresAdapter"
    assert not _offenders(pg_class), "PostgresAdapter must never listen (I-30)"
    assert not _toplevel_psycopg(store_tree), "psycopg must be lazy in store.py too (I-27)"


def test_i39_planted_violations_are_caught():
    """A scan that has never fired has not been shown to check anything: a
    planted `serve_forever()` call and a planted top-level `import psycopg`
    in a parsed copy of `fleet_cli.py`'s text must both be caught by the same
    walks the test above performs."""
    src = FLEET_SRC.read_text(encoding="utf-8")
    planted_call = ast.parse(src + "\ndef _oops():\n    serve_forever()\n")
    assert _BANNED_CALLS & set(_offenders(planted_call))

    planted_import = ast.parse("import psycopg\n" + src)
    assert _toplevel_psycopg(planted_import)


# ── lazy import: the module imports fine with psycopg blocked ───────────────

def test_store_and_fleet_cli_import_with_psycopg_blocked(monkeypatch):
    """`sys.modules["psycopg"] = None` makes any `import psycopg` raise
    `ImportError` immediately. Both modules must still import cleanly."""
    monkeypatch.setitem(sys.modules, "psycopg", None)
    for name in ("homestead.keep.store", "homestead.keep.fleet_cli"):
        sys.modules.pop(name, None)
        assert importlib.import_module(name) is not None


def test_constructing_the_adapter_refuses_by_name_naming_the_extra(monkeypatch):
    """With `psycopg` blocked, constructing `PostgresAdapter` refuses with
    `MissingFleetExtra`, naming the extra — never a bare
    `ModuleNotFoundError` a caller has to guess the fix for. `fleet_cli.
    _connect` is the one place *it* reaches for `psycopg`, and refuses the
    same way."""
    monkeypatch.setitem(sys.modules, "psycopg", None)
    sys.modules.pop("homestead.keep.store", None)
    sys.modules.pop("homestead.keep.fleet_cli", None)
    store = importlib.import_module("homestead.keep.store")
    fleet_cli = importlib.import_module("homestead.keep.fleet_cli")

    with pytest.raises(store.MissingFleetExtra) as e1:
        store.PostgresAdapter("postgresql://x/y", household="hh-0123456789abcdef")
    assert "fleet" in str(e1.value)

    with pytest.raises(fleet_cli.MissingFleetExtra) as e2:
        fleet_cli._connect("postgresql://x/y")
    assert "fleet" in str(e2.value)


# ── table-name validation, before any SQL interpolation ─────────────────────

def test_table_validation_plants():
    """`"sidecar; DROP TABLE envelopes"` and `"sidecar "` (a trailing space —
    a real, different identifier) are both refused by `InvalidTable` before a
    cursor is ever opened."""
    pytest.importorskip("psycopg")
    from homestead.keep import store

    adapter = store.PostgresAdapter("postgresql://x/y", household="hh-0123456789abcdef")
    for bad in ("sidecar; DROP TABLE envelopes", "sidecar ", "canonical\n", "junk"):
        with pytest.raises(store.InvalidTable) as e:
            adapter.read(bad, ("custody", "note", "n1"))
        assert repr(bad) in str(e.value)


# ── the SQL text of insert()/write() ─────────────────────────────────────────

class _RecordingCursor:
    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _RecordingConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_insert_and_write_sql_shape(monkeypatch):
    """`insert` is `ON CONFLICT DO NOTHING`, `write` is `ON CONFLICT ... DO
    UPDATE` — the append-only/upsert split canonical/sidecar rely on — and
    every value is a `%s` placeholder, never interpolated into the text."""
    pytest.importorskip("psycopg")
    from homestead.keep import store

    adapter = store.PostgresAdapter("postgresql://x/y", household="hh-0123456789abcdef")
    ref = ("custody", "note", "n1")

    insert_cursor = _RecordingCursor()
    monkeypatch.setattr(adapter, "_connect", lambda: _RecordingConn(insert_cursor))
    count = adapter.insert(store.SIDECAR, ref, "blob", envelope="e1", synced_at="2026-01-01T00:00:00Z")
    assert count == insert_cursor.rowcount
    (sql, params) = insert_cursor.executed[0]
    assert "ON CONFLICT" in sql and "DO NOTHING" in sql and "DO UPDATE" not in sql
    assert "blob" not in sql and "%s" in sql
    assert params == ("hh-0123456789abcdef", "custody", "note", "n1", "blob", "e1", "2026-01-01T00:00:00Z")

    write_cursor = _RecordingCursor()
    monkeypatch.setattr(adapter, "_connect", lambda: _RecordingConn(write_cursor))
    adapter.write(store.CANONICAL, ref, "blob2", envelope="e2", synced_at="2026-01-01T00:00:00Z")
    (sql2, _params2) = write_cursor.executed[0]
    assert "ON CONFLICT" in sql2 and "DO UPDATE" in sql2
    assert "blob2" not in sql2 and "%s" in sql2


# ── fleet_cli.ingest(): the five refusals, no live Postgres needed ─────────

class _FakeCursor:
    def __init__(self, existing_envelopes=frozenset(), existing_canonical=frozenset()):
        self.calls: list[tuple[str, tuple]] = []
        self.rowcount = 0
        self._existing_envelopes = set(existing_envelopes)
        self._existing_canonical = set(existing_canonical)
        self._fetch = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        text = sql.strip()
        if text.startswith("SELECT 1 FROM envelopes"):
            self._fetch = (1,) if tuple(params) in self._existing_envelopes else None
        elif text.startswith("INSERT INTO canonical") and "DO NOTHING" in sql:
            key = tuple(params[:4])
            if key in self._existing_canonical:
                self.rowcount = 0
            else:
                self.rowcount = 1
                self._existing_canonical.add(key)
        elif text.startswith("INSERT INTO sidecar"):
            self.rowcount = 1
        # CREATE TABLE / INSERT INTO envelopes / INSERT INTO anchors: no-ops

    def fetchone(self):
        return self._fetch


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _row(**over):
    row = {
        "table": "sidecar", "matter": "custody", "item_type": "note", "item_id": "n1",
        "rung": "L1", "disposition": "render", "value": "public value", "derived": None,
    }
    row.update(over)
    return row


def _envelope(rows=(), **over):
    from homestead.keep import sync as sync_mod

    identity = {
        "schema": sync_mod.SCHEMA, "household": "hh-0123456789abcdef",
        "composed_at": "2026-01-01T00:00:00+00:00", "head": "genesis",
        "scope": {"matters": ["custody"], "item_types": None, "ceiling": "L3", "tables": ["sidecar"]},
        "rows": list(rows), "count": len(rows),
    }
    identity.update(over)
    envelope_id = sync_mod._envelope_id(identity)
    return sync_mod.Envelope(
        schema=identity["schema"], household=identity["household"],
        composed_at=identity["composed_at"], head=identity["head"],
        scope=identity["scope"], rows=tuple(identity["rows"]),
        count=identity["count"], envelope_id=envelope_id,
    )


SECRET = "SECRET-VALUE-9f3ab1"


@pytest.mark.parametrize(
    "row_over, env_over, ingest_kw, expect",
    [
        pytest.param({}, {"schema": "homestead.sync/99"}, {}, "homestead.sync/99", id="bad-schema"),
        pytest.param(
            {}, {"household": "hh-aaaaaaaaaaaaaaaa"},
            {"household": "hh-bbbbbbbbbbbbbbbb"}, None, id="household-mismatch",
        ),
        pytest.param({"rung": "L5"}, {}, {}, "n1", id="l5-rung"),
        pytest.param({"rung": "not-a-rung"}, {}, {}, "n1", id="unreadable-rung"),
        pytest.param({"disposition": "derive"}, {}, {}, "derive", id="derive-row"),
    ],
)
def test_ingest_refuses_each_bad_input_by_name(row_over, env_over, ingest_kw, expect):
    """A bad schema, a mismatched household, an `L5` or unreadable rung, and
    a non-`render` row are each refused by name — a reference (schema
    string, row id, rung, disposition), never the row's own value."""
    from homestead.keep import fleet_cli

    env = _envelope(rows=(_row(value=SECRET, **row_over),), **env_over)
    with pytest.raises(fleet_cli.IngestRefused) as e:
        fleet_cli.ingest(env, "postgresql://x/y", **ingest_kw)
    if expect:
        assert expect in str(e.value)
    assert SECRET not in str(e.value)


def test_ingest_refuses_a_reingest_before_writing_any_row(monkeypatch):
    from homestead.keep import fleet_cli

    env = _envelope(rows=(_row(value=SECRET),))
    cursor = _FakeCursor(existing_envelopes={(env.household, env.envelope_id)})
    conn = _FakeConn(cursor)
    monkeypatch.setattr(fleet_cli, "_connect", lambda dsn: conn)

    with pytest.raises(fleet_cli.IngestRefused) as e:
        fleet_cli.ingest(env, "postgresql://x/y")
    assert env.envelope_id in str(e.value) and SECRET not in str(e.value)
    assert not any(c[0].strip().startswith("INSERT INTO sidecar") for c in cursor.calls), (
        "no row is written once the re-ingest check fires"
    )
    assert conn.rolled_back and conn.closed


def test_ingest_sidecar_upserts_and_canonical_is_insert_only(monkeypatch):
    """The written/skipped counts by reference: a fresh sidecar row and a
    fresh canonical row both count as written; a canonical row whose key
    already exists counts as skipped, never overwritten."""
    from homestead.keep import fleet_cli

    rows = (
        _row(item_id="n1", table="sidecar", value="a"),
        _row(item_id="n2", table="canonical", value="b"),
    )
    env = _envelope(rows=rows)
    conn = _FakeConn(_FakeCursor())
    monkeypatch.setattr(fleet_cli, "_connect", lambda dsn: conn)

    result = fleet_cli.ingest(env, "postgresql://x/y")
    assert result.written == 2 and result.skipped == 0
    assert conn.committed and not conn.rolled_back and conn.closed

    env2 = _envelope(rows=rows, composed_at="2026-02-01T00:00:00+00:00")
    cursor2 = _FakeCursor(existing_canonical={(env2.household, "custody", "note", "n2")})
    conn2 = _FakeConn(cursor2)
    monkeypatch.setattr(fleet_cli, "_connect", lambda dsn: conn2)

    result2 = fleet_cli.ingest(env2, "postgresql://x/y")
    assert result2.written == 1, "the sidecar row"
    assert result2.skipped == 1, "the canonical row, already there, is skipped not overwritten"


# ── main(): --yes skips only the confirm, never a refusal ───────────────────

def test_yes_skips_the_confirm_but_never_a_refusal(monkeypatch, capsys, tmp_path):
    from homestead.keep import fleet_cli

    monkeypatch.setattr("builtins.input", lambda prompt="": (_ for _ in ()).throw(
        AssertionError("input() must not be called with --yes")))
    monkeypatch.setattr(
        fleet_cli, "ingest",
        lambda env, dsn, household=None: (_ for _ in ()).throw(
            fleet_cli.IngestRefused("refused: planted")),
    )

    env = _envelope(rows=(_row(),))
    path = tmp_path / "ok.json"
    path.write_bytes(env.to_bytes())
    rc = fleet_cli.main(["ingest", str(path), "--dsn", "postgresql://x/y", "--yes"])
    assert rc == 1
    assert "refused" in capsys.readouterr().err


def test_without_yes_a_declined_confirm_never_calls_ingest(monkeypatch, capsys, tmp_path):
    from homestead.keep import fleet_cli

    called = []
    monkeypatch.setattr(fleet_cli, "ingest", lambda *a, **k: called.append(1))
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    env = _envelope(rows=(_row(value=SECRET),))
    path = tmp_path / "env.json"
    path.write_bytes(env.to_bytes())

    rc = fleet_cli.main(["ingest", str(path), "--dsn", "postgresql://x/y"])
    assert rc == 1
    assert not called, "a declined confirm never reaches ingest()"
    out = capsys.readouterr()
    assert SECRET not in out.out and SECRET not in out.err


def test_the_confirm_prints_the_host_never_the_password_or_a_row(monkeypatch, capsys, tmp_path):
    from homestead.keep import fleet_cli

    monkeypatch.setattr(fleet_cli, "ingest", lambda *a, **k: fleet_cli.IngestResult(written=1, skipped=0))
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    env = _envelope(rows=(_row(value=SECRET),))
    path = tmp_path / "env.json"
    path.write_bytes(env.to_bytes())

    rc = fleet_cli.main([
        "ingest", str(path), "--dsn", "postgresql://alice:hunter2@db.example.invalid:5432/fleet",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "db.example.invalid" in out
    assert "hunter2" not in out and "alice" not in out and SECRET not in out
    assert env.envelope_id in out and str(env.count) in out


def test_dsn_falls_back_to_the_env_var(monkeypatch, tmp_path):
    """`--dsn` is preferred; else `HOMESTEAD_FLEET_DSN`; else a refusal
    (exit 2), never a guess."""
    from homestead.keep import fleet_cli

    seen = {}

    def fake_ingest(env, dsn, household=None):
        seen["dsn"] = dsn
        return fleet_cli.IngestResult(0, 0)

    monkeypatch.setattr(fleet_cli, "ingest", fake_ingest)
    env = _envelope(rows=(_row(),))
    path = tmp_path / "env.json"
    path.write_bytes(env.to_bytes())

    monkeypatch.setenv("HOMESTEAD_FLEET_DSN", "postgresql://env-dsn/fleet")
    assert fleet_cli.main(["ingest", str(path), "--yes"]) == 0
    assert seen["dsn"] == "postgresql://env-dsn/fleet"

    monkeypatch.delenv("HOMESTEAD_FLEET_DSN", raising=False)
    assert fleet_cli.main(["ingest", str(path), "--yes"]) == 2


# ── I-27: no new required dependency; markers registered ───────────────────

def test_i27_fleet_is_an_optional_extra_not_a_dependency():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dependencies = ["holidays>=0.102,<1.0"]' in text, (
        "the fleet extra must not widen the required dependency list"
    )
    assert 'fleet = ["psycopg[binary]>=3.1,<4"]' in text
    assert '"fleet:' in text, "pytest -q must never warn about an unregistered marker"
