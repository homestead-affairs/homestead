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
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "homestead"
FLEET_SRC = PKG / "keep" / "fleet_cli.py"
STORE_SRC = PKG / "keep" / "store.py"

#: `tests/test_invariants_shape.py`'s package-wide list, plus the three it
#: deliberately leaves out. `bind` is not banned package-wide because tkinter
#: spells event binding `widget.bind(...)` and the guard would be switched off
#: within a week; neither of *these two* files has a widget in it, so here it
#: is banned and `socket.bind` is caught. `start_server`/`start_unix_server`
#: are asyncio's spelling, which the package-wide list never needed.
_BANNED_CALLS = {
    "listen", "serve_forever", "create_server", "ThreadingHTTPServer",
    "bind", "start_server", "start_unix_server",
}

#: Modules that exist to listen, banned at *any* depth in these two files —
#: not just at module level, because the point of `fleet_cli.py` is that it
#: dials out inside a function, and a `import http.server` inside one would
#: pass a top-level-only scan. `urllib` is not here: `_redact_dsn` imports
#: `urllib.parse` inside a function on purpose, and splitting a URL is not
#: listening.
_BANNED_IMPORTS = {"socket", "socketserver", "http", "asyncio", "ssl"}


def _offenders(tree) -> list[str]:
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name in _BANNED_CALLS:
                hits.append(name)
        elif isinstance(node, ast.Import):
            hits += [a.name for a in node.names
                     if a.name.split(".")[0] in _BANNED_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            root = (node.module or "").split(".")[0]
            if root in _BANNED_IMPORTS:
                hits.append(node.module or "")
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


@pytest.mark.parametrize(
    "plant",
    [
        pytest.param("def _oops():\n    serve_forever()\n", id="serve_forever"),
        pytest.param("def _oops(s):\n    s.listen(5)\n", id="listen"),
        pytest.param("def _oops(s):\n    s.bind(('0.0.0.0', 8080))\n", id="socket.bind"),
        pytest.param("def _oops():\n    import socket\n", id="import-socket-in-a-function"),
        pytest.param("import http.server\n", id="http.server"),
        pytest.param("def _oops():\n    import http.server\n", id="http.server-in-a-function"),
        pytest.param("from http.server import HTTPServer\n", id="from-http.server"),
        pytest.param(
            "async def _oops():\n    await asyncio.start_server(h, '0.0.0.0', 1)\n",
            id="asyncio.start_server",
        ),
        pytest.param("import asyncio\n", id="import-asyncio"),
        pytest.param("import socketserver\n", id="import-socketserver"),
    ],
)
def test_i39_planted_listeners_are_caught(plant):
    """A scan that has never fired has not been shown to check anything. Each
    of these, appended to a parsed copy of `fleet_cli.py`'s own text, must be
    caught by the same walk `test_i39_...` performs on the real file — and
    the real file must be clean of all of them, which the test above asserts.

    The list is the audit's own (E4-postgres-fleet, 2026-09-11): before it,
    `_BANNED_CALLS` was the package-wide four, so `socket.bind`,
    `asyncio.start_server` and an `import http.server` inside a function all
    passed a guard whose whole purpose is that this file never grows a
    listener."""
    src = FLEET_SRC.read_text(encoding="utf-8")
    assert _offenders(ast.parse(src + "\n" + plant)), (
        "the I-39 scan must catch this plant"
    )


def test_i39_planted_toplevel_psycopg_is_caught():
    """The other half: a top-level `import psycopg` — which would run clean
    in CI (I-27's scan reads only `dependencies`) and fail only on a machine
    without the `fleet` extra."""
    src = FLEET_SRC.read_text(encoding="utf-8")
    assert _toplevel_psycopg(ast.parse("import psycopg\n" + src))
    assert not _toplevel_psycopg(ast.parse(src))


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

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_insert_and_write_sql_shape(monkeypatch):
    """`insert` is `ON CONFLICT DO NOTHING`, `write` is `ON CONFLICT ... DO
    UPDATE` — the append-only/upsert split canonical/sidecar rely on — and
    every value is a `%s` placeholder, never interpolated into the text.

    `value` is canonicalized to JSON text before it becomes a parameter
    (E7b, 2026-09-11): a mapping here, to prove this is not just a string
    that happens to round-trip, and a `None` for `write`, to prove a JSON
    `null` becomes the four-byte text `null` rather than a SQL `NULL`."""
    pytest.importorskip("psycopg")
    from homestead.keep import store

    adapter = store.PostgresAdapter("postgresql://x/y", household="hh-0123456789abcdef")
    ref = ("custody", "note", "n1")
    value = {"counterpart": "c", "from": "chk", "to": "visa"}
    text = store.canonical_value_text(value)

    insert_cursor = _RecordingCursor()
    monkeypatch.setattr(adapter, "_connect", lambda: _RecordingConn(insert_cursor))
    count = adapter.insert(store.SIDECAR, ref, value, envelope="e1", synced_at="2026-01-01T00:00:00Z")
    assert count == insert_cursor.rowcount
    (sql, params) = insert_cursor.executed[0]
    assert "ON CONFLICT" in sql and "DO NOTHING" in sql and "DO UPDATE" not in sql
    assert text not in sql and "%s" in sql
    assert params == (
        "hh-0123456789abcdef", "custody", "note", "n1", text,
        store.VALUE_FORMAT_JSON, "e1", "2026-01-01T00:00:00Z",
    )

    write_cursor = _RecordingCursor()
    monkeypatch.setattr(adapter, "_connect", lambda: _RecordingConn(write_cursor))
    adapter.write(store.CANONICAL, ref, None, envelope="e2", synced_at="2026-01-01T00:00:00Z")
    (sql2, params2) = write_cursor.executed[0]
    assert "ON CONFLICT" in sql2 and "DO UPDATE" in sql2
    assert "%s" in sql2
    assert params2[4] == "null", "a JSON null stores as the text 'null', never a SQL NULL"
    assert params2[5] == store.VALUE_FORMAT_JSON
    assert "value_format=excluded.value_format" in sql2, (
        "an upsert over a pre-E7b row must move its value_format too, or the "
        "row would claim to be raw text while holding canonical JSON"
    )


def test_postgres_adapter_write_canonicalizes_a_mapping_and_decode_value_reverses_it(monkeypatch):
    """The adapter round trip through a fake adapter: `write` stores
    canonical text plus the `value_format` that says so, and
    `fleet_cli.decode_value` reads the same mapping back out of the pair
    (E7b, 2026-09-11)."""
    pytest.importorskip("psycopg")
    from homestead.keep import fleet_cli, store

    adapter = store.PostgresAdapter("postgresql://x/y", household="hh-0123456789abcdef")
    cursor = _RecordingCursor()
    monkeypatch.setattr(adapter, "_connect", lambda: _RecordingConn(cursor))
    value = {"counterpart": "c", "from": "chk", "to": "visa"}
    adapter.write(
        store.SIDECAR, ("transfers", "pair", "p1"), value,
        envelope="e1", synced_at="2026-01-01T00:00:00Z",
    )
    (_sql, params) = cursor.executed[0]
    stored_text, stored_format = params[4], params[5]
    assert stored_text == store.canonical_value_text(value)
    decoded = fleet_cli.decode_value(stored_text, value_format=stored_format)
    assert decoded == fleet_cli.Decoded(value, legacy=False)


def test_a_pre_e7b_row_is_read_as_the_raw_text_it_is_never_guessed_at():
    """**The E7b audit's finding (2026-09-11).** Before this bite,
    `PostgresAdapter.insert`/`.write` took an already-serialized blob and
    passed it straight into the statement, so every fleet row written until
    now holds the served string *verbatim* — `2026-10-06`, not
    `"2026-10-06"`. The bite's note said no migration was needed because
    "every stored value was already a JSON string literal"; it was not.
    `json.loads` on such a row either raises or, worse, quietly succeeds
    with the wrong type: a ledger amount `1450.00` reads back as the float
    `1450.0`, a household's money re-typed by a reader that thought it was
    decoding. So `decode_value` is *told*, from the row's own
    `value_format`, and a `raw` row comes back tagged `legacy=True`."""
    from homestead.keep import fleet_cli
    from homestead.keep.store import VALUE_FORMAT_RAW

    for legacy_text in ("2026-10-06", "1450.00", "123", "true", "null", "a note"):
        got = fleet_cli.decode_value(legacy_text, value_format=VALUE_FORMAT_RAW)
        assert got == fleet_cli.Decoded(legacy_text, legacy=True), (
            "a pre-E7b row is the string it is — never re-typed by json.loads"
        )

    # And the same texts through the guessing reader this replaces: two of
    # them raise and four come back as the wrong Python type, which is why
    # a try/except fallback was not enough on its own.
    assert json.loads("1450.00") == 1450.0 and isinstance(json.loads("1450.00"), float)
    assert json.loads("123") == 123 and json.loads("true") is True

    # A `json` row is parsed, and a `json` row whose text will not parse is
    # reported as legacy rather than raised on (I-11) — the column and the
    # text disagreeing is an answer, not a traceback.
    assert fleet_cli.decode_value('{"a":1}', value_format="json") == fleet_cli.Decoded(
        {"a": 1}, legacy=False
    )
    assert fleet_cli.decode_value("2026-10-06", value_format="json") == fleet_cli.Decoded(
        "2026-10-06", legacy=True
    )


def test_ensure_schema_adds_the_value_format_column_to_a_table_already_there():
    """The migration, such as it is: `CREATE TABLE IF NOT EXISTS` cannot add
    a column to a table that already exists, so an `ALTER TABLE … ADD COLUMN
    IF NOT EXISTS … DEFAULT 'raw'` runs beside it. Existing rows — the
    pre-E7b ones — gain the column already saying `raw`, which is true of
    them by construction (E7b audit, 2026-09-11)."""
    from homestead.keep import fleet_cli
    from homestead.keep.store import CANONICAL, SIDECAR, VALUE_FORMAT_RAW

    cursor = _RecordingCursor()
    fleet_cli.ensure_schema(_RecordingConn(cursor))
    statements = [sql for sql, _params in cursor.executed]
    for table in (CANONICAL, SIDECAR):
        assert any(
            s.startswith(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS value_format")
            and f"DEFAULT '{VALUE_FORMAT_RAW}'" in s
            for s in statements
        ), f"{table} must gain value_format even when the table predates it"
        assert any(
            s.startswith(f"CREATE TABLE IF NOT EXISTS {table}") and "value_format" in s
            for s in statements
        ), f"a fresh {table} must be created with the column too"


def test_canonical_value_text_is_stable_sorted_and_keeps_unicode():
    """The canonical form is stable: sorted keys, no spaces, non-ASCII
    preserved literally rather than `\\uXXXX`-escaped — the same shape
    `keep/sync.py`'s `_canonical_bytes` freezes an envelope with."""
    from homestead.keep import store

    text = store.canonical_value_text({"b": 1, "a": "café", "z": None})
    assert text == '{"a":"café","b":1,"z":null}'


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
        lambda env, dsn, household=None, allow_stale=False: (_ for _ in ()).throw(
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

    def fake_ingest(env, dsn, household=None, allow_stale=False):
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


# ── the audit's own additions (E4-postgres-fleet audit, 2026-09-11) ─────────

@pytest.mark.parametrize(
    "dsn, must_show, must_not_show",
    [
        pytest.param(
            "postgresql://alice:hunter2@db.example.invalid:5432/fleet",
            ["db.example.invalid", "5432", "fleet"], ["hunter2", "alice"],
            id="url-form",
        ),
        pytest.param(
            "host=db.example.invalid port=5432 dbname=fleet user=alice password=hunter2",
            ["db.example.invalid", "fleet"], ["hunter2", "alice"],
            id="keyword-value-form",
        ),
        pytest.param(
            "postgresql://alice:hunter2@h/d?sslmode=require&passfile=/etc/pgpass",
            ["h"], ["hunter2", "passfile", "pgpass"],
            id="url-with-a-credential-in-the-query",
        ),
        pytest.param(
            "host=h sslpassword=hunter2 passfile=/etc/pgpass dbname=d",
            ["h", "d"], ["hunter2", "passfile", "pgpass"],
            id="keyword-value-other-credential-keywords",
        ),
        pytest.param("'unbalanced", [], ["unbalanced"], id="unparseable"),
    ],
)
def test_redact_dsn_shows_the_destination_and_no_credential(dsn, must_show, must_not_show):
    """libpq takes two DSN forms, and the confirm prints whichever the
    operator typed. The keyword/value form is not a URL: `urlsplit` hands it
    back whole, so the first version of `_redact_dsn` printed
    `password=hunter2` to stdout (found by this audit). The allow-list means
    a keyword it has never heard of is dropped rather than shown."""
    from homestead.keep import fleet_cli

    out = fleet_cli._redact_dsn(dsn)
    for want in must_show:
        assert want in out, f"the operator must still see the destination: {want}"
    for never in must_not_show:
        assert never not in out, f"{never!r} must never be printed"


def test_the_confirm_never_prints_a_keyword_value_password(monkeypatch, capsys, tmp_path):
    """The same thing end to end, through `main()`'s own confirm — the leak
    was in what the prompt printed, not in a helper nobody called."""
    from homestead.keep import fleet_cli

    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    env = _envelope(rows=(_row(value=SECRET),))
    path = tmp_path / "env.json"
    path.write_bytes(env.to_bytes())

    rc = fleet_cli.main([
        "ingest", str(path),
        "--dsn", "host=db.example.invalid port=5432 dbname=fleet user=alice password=hunter2",
    ])
    assert rc == 1
    out = capsys.readouterr()
    assert "db.example.invalid" in out.out
    assert "hunter2" not in out.out + out.err
    assert SECRET not in out.out + out.err


@pytest.mark.parametrize(
    "row_over, drop, id_hint",
    [
        pytest.param({"item_id": "n\x001"}, None, "item_id", id="nul-in-item-id"),
        pytest.param({}, "matter", "matter", id="row-missing-matter"),
        pytest.param({}, "item_type", "item_type", id="row-missing-item-type"),
        pytest.param({}, "value", "value", id="row-missing-value"),
        pytest.param({"matter": "  "}, None, "matter", id="whitespace-matter"),
        pytest.param({"matter": "../etc"}, None, "matter", id="separator-in-matter"),
    ],
)
def test_ingest_refuses_an_unstorable_row_by_name_never_by_traceback(row_over, drop, id_hint):
    """Every field that reaches a statement is checked before one is built.

    The failure this guards against: an envelope hashes correctly over
    whatever it carries (`Envelope.from_bytes` proves only that the bytes
    were not edited after composition), so a row can be missing `matter`
    entirely or carry a NUL byte inside an identifier Postgres refuses
    outright. Before this audit those came out of `ingest()` as a bare
    `KeyError` or a `psycopg.DataError` stack — not a refusal by name
    (I-11), and on the `DataError` path only after a connection had been
    opened."""
    from homestead.keep import fleet_cli

    row = _row(value=SECRET)
    row.update(row_over)
    if drop:
        row.pop(drop)
    env = _envelope(rows=(row,))
    with pytest.raises(fleet_cli.IngestRefused) as e:
        fleet_cli.ingest(env, "postgresql://x/y")
    assert id_hint in str(e.value)
    assert SECRET not in str(e.value), "a refusal names the field, never the value (I-15)"


def test_ingest_refuses_a_row_with_a_value_json_cannot_serialize(monkeypatch):
    """A `bytes` value cannot even be hashed into an `envelope_id` (E7b,
    2026-09-11) — `json.dumps` refuses it — so this builds the `Envelope`
    object directly rather than through the `_envelope()` helper above: the
    shape a hand-built or buggy composer could produce, since `Envelope`'s
    own constructor does not validate its rows. `Envelope.from_bytes()`
    could never hand `ingest()` this row (a byte string has no JSON form to
    have round-tripped through), so this is belt and braces against a
    caller other than that one."""
    from homestead.keep import fleet_cli
    from homestead.keep import sync as sync_mod

    row = _row(value=b"not json-serialisable")
    env = sync_mod.Envelope(
        schema=sync_mod.SCHEMA, household="hh-0123456789abcdef",
        composed_at="2026-01-01T00:00:00+00:00", head="genesis",
        scope={"matters": ["custody"], "item_types": None,
               "ceiling": "L3", "tables": ["sidecar"]},
        rows=(row,), count=1, envelope_id="not-checked-by-ingest",
    )
    with pytest.raises(fleet_cli.IngestRefused) as e:
        fleet_cli.ingest(env, "postgresql://x/y")
    assert "value" in str(e.value)


# ── E7b: `value` is any JSON shape `serve()` can return, not just `str` ─────

@pytest.mark.parametrize(
    "value",
    [
        {"counterpart": "c", "from": "chk", "to": "visa"},
        ["a", "b", 3],
        True,
        False,
        0,
        -17,
        None,
        "a\x00b",
    ],
    ids=["mapping", "list", "true", "false", "zero", "negative-int", "null",
         "nul-inside-a-string"],
)
def test_validate_rows_accepts_every_json_shape_serve_can_return(monkeypatch, value):
    """`serve()` returns exactly one of `str`, a mapping, a list, a `bool`,
    an `int`, or `None` for `value`; before this bite only a plain `str`
    passed `_validate_rows`, so a ledger `transfers` pair — an L2 mapping —
    was refused before the dial (the G5-sync audit's finding, 2026-09-11).

    A string containing a NUL byte is included too: it used to be refused
    as a byte Postgres cannot hold, and no longer needs to be —
    `canonical_value_text` escapes it to `\\u0000` before it ever reaches a
    statement, so no literal NUL byte is ever stored."""
    from homestead.keep import fleet_cli

    conn = _FakeConn(_FakeCursor())
    monkeypatch.setattr(fleet_cli, "_connect", lambda dsn: conn)
    result = fleet_cli.ingest(
        _envelope(rows=(_row(rung="L2", value=value),)), "postgresql://x/y"
    )
    assert result.written == 1 and conn.committed


def test_a_nul_byte_in_a_value_is_escaped_and_round_trips(monkeypatch):
    """The rule the old `"\\x00" in value` refusal is replaced by, pinned
    both ways: the *stored text* holds no literal NUL byte (Postgres `TEXT`
    rejects one) and the value still reads back as the string it was. A
    removal not replaced by a positive check is just a removal."""
    from homestead.keep import fleet_cli, store

    cursor = _FakeCursor()
    monkeypatch.setattr(fleet_cli, "_connect", lambda dsn: _FakeConn(cursor))
    fleet_cli.ingest(_envelope(rows=(_row(value="a\x00b"),)), "postgresql://x/y")

    (stored,) = [
        params[4] for sql, params in cursor.calls
        if sql.strip().startswith("INSERT INTO sidecar") and params
    ]
    assert "\x00" not in stored and stored == '"a\\u0000b"'
    assert fleet_cli.decode_value(
        stored, value_format=store.VALUE_FORMAT_JSON
    ) == fleet_cli.Decoded("a\x00b", legacy=False)


@pytest.mark.parametrize(
    "disposition",
    ["derive", "deny", "wharrgarbl"],
    ids=["derive", "deny", "not-a-disposition"],
)
def test_a_non_render_row_is_refused_outright_even_with_no_value(disposition):
    """**Fail closed on the disposition, whatever the `value` is (E7b
    audit, 2026-09-11).** E7b first relaxed this to "a non-`render` row is
    fine as long as it carries no value", reading a `DERIVE` row with
    `value: null` as a shape the fleet should expect. It is not: `compose()`
    drops every `DENY` and above-ceiling row before freezing, and `serve()`
    on `S4_EGRESS` with a declared purpose renders L1–L4 and denies L5 — it
    never returns `DERIVE` at all (`keep/rungs.py`'s `_CEILING`). A
    non-`render` row is therefore forged or hand-built, and the relaxed rule
    wrote it as the text `null` — on the insert-only canonical table, taking
    that key for good so the household's real row could never land."""
    from homestead.keep import fleet_cli

    env = _envelope(rows=(_row(disposition=disposition, value=None),))
    with pytest.raises(fleet_cli.IngestRefused) as e:
        fleet_cli.ingest(env, "postgresql://x/y")
    assert disposition in str(e.value) and "render" in str(e.value)


def test_compose_emits_only_render_rows_so_the_outright_refusal_costs_nothing(tmp_path, monkeypatch):
    """The other half of the rule above, read off `compose()` rather than
    asserted about it: every row a real envelope carries is `render`, so
    refusing every non-`render` row turns nothing legitimate away."""
    from homestead.keep import sync as sync_mod
    from homestead.keep.rungs import Classified, Rung
    from homestead.keep.store import Sidecar, SQLiteAdapter

    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    sidecar = Sidecar(SQLiteAdapter(tmp_path / "s.db"))
    sidecar.put("custody", "note", "n1", Classified(Rung.L1, "a date"))
    sidecar.put("custody", "note", "n2", Classified(Rung.L4, "a long note", "an instruction"))
    sidecar.put("custody", "note", "n3", Classified(Rung.L5, "withheld"))

    envelope = sync_mod.compose(
        {"sidecar": sidecar},
        sync_mod.SyncScope(matters=("custody",), item_types=None,
                           ceiling=Rung.L4, tables=("sidecar",)),
    )
    assert envelope.rows, "the fixture must actually compose something"
    assert {row["disposition"] for row in envelope.rows} == {"render"}
    assert "n3" not in {row["item_id"] for row in envelope.rows}, "L5 is dropped, not derived"


@pytest.mark.parametrize(
    "value, hint",
    [
        pytest.param(1.10, "float", id="float"),
        pytest.param(float("nan"), "float", id="nan"),
        pytest.param(float("inf"), "float", id="infinity"),
        pytest.param(b"bytes", "serialize", id="bytes"),
        pytest.param({"a", "b"}, "serialize", id="set"),
        pytest.param("x" * (64 * 1024 + 1), "bytes", id="over-the-cap"),
    ],
)
def test_ingest_refuses_a_hostile_value_by_name_never_by_traceback(value, hint):
    """**Each of these was accepted, or came out as a traceback, until the
    E7b audit (2026-09-11).**

    A `float` is refused by name: money is a two-decimal *string*
    (`homestead_ledger.money.amount_text`), no module puts a float in a
    record, and a float does not round-trip as one text — `1.10` and `1.1`
    are one number and two texts, so one record would sync as two rows.
    `NaN`/`Infinity` are floats too, which Python's `json` writes as text no
    other JSON reader can parse; `allow_nan=False` in
    `canonical_value_text` is the backstop under the same rule. And nothing
    capped the size at all: `sync.compose()` puts no bound on a served
    value, so a 1 MB row framed, crossed and ingested."""
    from homestead.keep import fleet_cli
    from homestead.keep import sync as sync_mod

    # Built directly: a `bytes` or a `set` has no JSON form, so `_envelope()`
    # cannot hash an identity over one.
    env = sync_mod.Envelope(
        schema=sync_mod.SCHEMA, household="hh-0123456789abcdef",
        composed_at="2026-01-01T00:00:00+00:00", head="genesis",
        scope={"matters": ["custody"], "item_types": None,
               "ceiling": "L3", "tables": ["sidecar"]},
        rows=(_row(value=value),), count=1, envelope_id="not-checked-by-ingest",
    )
    with pytest.raises(fleet_cli.IngestRefused) as e:
        fleet_cli.ingest(env, "postgresql://x/y")
    assert hint in str(e.value)


def test_ingest_refuses_a_nested_value_by_name_rather_than_a_recursion_error():
    """A value nested past `MAX_VALUE_DEPTH` is refused by name before any
    serializer sees it. The plant is deliberately shallow enough to
    serialize on every interpreter: on 3.10/3.11 a 2000-deep list raised
    `RecursionError` inside `json.dumps`, on 3.12 it does not (the C
    encoder's recursion is no longer counted), and CI showed the old plant
    reaching the dial there. The depth bound is the fleet's, not Python's."""
    from homestead.keep import fleet_cli
    from homestead.keep import sync as sync_mod

    planted: object = []
    for _ in range(fleet_cli.MAX_VALUE_DEPTH + 8):
        planted = [planted]
    env = sync_mod.Envelope(
        schema=sync_mod.SCHEMA, household="hh-0123456789abcdef",
        composed_at="2026-01-01T00:00:00+00:00", head="genesis",
        scope={"matters": ["custody"], "item_types": None,
               "ceiling": "L3", "tables": ["sidecar"]},
        rows=(_row(value=planted),), count=1, envelope_id="not-checked-by-ingest",
    )
    with pytest.raises(fleet_cli.IngestRefused) as e:
        fleet_cli.ingest(env, "postgresql://x/y")
    assert "nested deeper than" in str(e.value)
    assert "[" not in str(e.value)


def test_a_value_at_the_depth_cap_still_crosses():
    """The cap is a bound, not a fear of nesting: exactly `MAX_VALUE_DEPTH`
    levels validates (a real ledger row is two deep at most)."""
    from homestead.keep import fleet_cli
    from homestead.keep import sync as sync_mod

    planted: object = "leaf"
    for _ in range(fleet_cli.MAX_VALUE_DEPTH - 1):
        planted = [planted]
    env = sync_mod.Envelope(
        schema=sync_mod.SCHEMA, household="hh-0123456789abcdef",
        composed_at="2026-01-01T00:00:00+00:00", head="genesis",
        scope={"matters": ["custody"], "item_types": None,
               "ceiling": "L3", "tables": ["sidecar"]},
        rows=(_row(value=planted),), count=1, envelope_id="not-checked-by-ingest",
    )
    fleet_cli._validate_rows(env)


def test_canonical_value_text_is_the_encoder_the_envelope_is_frozen_with():
    """One canonical encoding, not two that can drift: a row's value,
    canonicalized, is a literal substring of the envelope bytes
    `sync._canonical_bytes` freezes — and canonicalizing what comes back out
    of those bytes gives the same text again (round-trip stability)."""
    from homestead.keep import fleet_cli, store
    from homestead.keep import sync as sync_mod

    values = [{"b": 1, "a": "café"}, ["x", 2], "a\x00b", None, True, 0]
    rows = tuple(
        _row(item_id=f"n{n}", value=v) for n, v in enumerate(values)
    )
    envelope = _envelope(rows=rows)
    frozen = envelope.to_bytes()
    assert sync_mod.Envelope.from_bytes(frozen).envelope_id == envelope.envelope_id

    for row in sync_mod.Envelope.from_bytes(frozen).rows:
        text = store.canonical_value_text(row["value"])
        assert text.encode("utf-8") in frozen, (
            "the fleet's stored text must be exactly the envelope's own bytes "
            "for that value, not a second encoding of it"
        )
        decoded = fleet_cli.decode_value(text, value_format=store.VALUE_FORMAT_JSON)
        assert store.canonical_value_text(decoded.value) == text


def test_a_ledger_transfer_pair_mapping_value_crosses(monkeypatch):
    """The G5-sync audit's finding, verbatim: the ledger's `transfers` pair
    is an L2 served value that is a mapping `{counterpart, from, to}`, and
    before this bite `_validate_rows` refused any row whose `value` was not
    a Python `str` — so a ledger envelope carrying a transfer pair was
    refused before the dial, never reaching Postgres at all."""
    import hashlib

    from homestead.keep import fleet_cli

    fingerprint = hashlib.sha256(b"transfer-out").hexdigest()
    counterpart = hashlib.sha256(b"transfer-in").hexdigest()
    row = {
        "table": "sidecar", "matter": "transfers", "item_type": "pair",
        "item_id": fingerprint, "rung": "L2", "disposition": "render",
        "value": {"counterpart": counterpart, "from": "chk", "to": "visa"},
        "derived": None,
    }
    conn = _FakeConn(_FakeCursor())
    monkeypatch.setattr(fleet_cli, "_connect", lambda dsn: conn)
    result = fleet_cli.ingest(_envelope(rows=(row,)), "postgresql://x/y")
    assert result.written == 1 and conn.committed


def test_ingest_refuses_a_row_that_is_not_an_object():
    from homestead.keep import fleet_cli

    env = _envelope(rows=("not-a-row",))
    with pytest.raises(fleet_cli.IngestRefused) as e:
        fleet_cli.ingest(env, "postgresql://x/y")
    assert "JSON object" in str(e.value)


def test_an_l4_render_row_is_accepted(monkeypatch):
    """S4 with a declared purpose renders up to `L4` (the sync ruling), so an
    `L4`/`render` row is the ordinary case, not an edge one — `L5` and
    `derive` are what refuse."""
    from homestead.keep import fleet_cli

    conn = _FakeConn(_FakeCursor())
    monkeypatch.setattr(fleet_cli, "_connect", lambda dsn: conn)
    result = fleet_cli.ingest(_envelope(rows=(_row(rung="L4"),)), "postgresql://x/y")
    assert result.written == 1 and conn.committed


def test_main_refuses_by_name_when_the_database_cannot_be_reached(tmp_path, capsys):
    """A mistyped `--dsn` ended the command in a `psycopg.OperationalError`
    traceback before this audit. The exception class is named, the
    destination is the redacted form, and the driver's own message — built
    from the conninfo — is deliberately not echoed."""
    pytest.importorskip("psycopg")
    from homestead.keep import fleet_cli

    env = _envelope(rows=(_row(value=SECRET),))
    path = tmp_path / "env.json"
    path.write_bytes(env.to_bytes())

    rc = fleet_cli.main([
        "ingest", str(path), "--yes",
        "--dsn", "postgresql://alice:hunter2@127.0.0.1:1/nothing-listens-here",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "refused:" in err and "nothing was ingested" in err
    assert "hunter2" not in err and SECRET not in err


@pytest.mark.parametrize(
    "composed_at, anchored_at, stale",
    [
        ("2026-05-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", False),
        ("2026-01-01T00:00:00+00:00", "2026-05-01T00:00:00+00:00", True),
        # Equal is not stale: `sync._now_iso()` has second resolution, and two
        # envelopes composed in the same second are ordinary.
        ("2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", False),
        # Fail closed: an ordering that cannot be established is not one.
        ("2026-01-01", "2026-01-01T00:00:00+00:00", True),
        ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00+00:00", True),
        (None, "2026-01-01T00:00:00+00:00", True),
    ],
)
def test_stale_is_decided_on_composed_at_and_fails_closed(composed_at, anchored_at, stale):
    """`head` is a hash chain head — it has no order, and two heads cannot be
    compared without walking a chain the fleet does not have. `composed_at`
    is ordered, and for `sync._now_iso()`'s one fixed-width UTC format byte
    order *is* time order, so it is compared as text rather than through
    `fromisoformat`, which I-1/I-2 ban package-wide."""
    from homestead.keep import fleet_cli

    assert fleet_cli._is_stale(composed_at, anchored_at) is stale


def test_ingest_carries_no_row_sql_of_its_own():
    """The two code paths are one. `ingest()` writes rows through
    `store.PostgresAdapter.insert/write` and holds them open with
    `adapter.transaction()`; it does not carry a second copy of their
    statements, which is what let the two drift on columns or on either `ON
    CONFLICT` clause with nothing checking that they agreed.

    Structural, over `ingest`'s own source: no string constant inside it may
    insert into a record table. The `envelopes`/`anchors` statements stay —
    they are this command's bookkeeping, not the record store's contract."""
    tree = ast.parse(FLEET_SRC.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "ingest")
    literals = [
        n.value.lower() for n in ast.walk(fn)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    for table in ("sidecar", "canonical"):
        assert not any(f"insert into {table}" in lit for lit in literals), (
            f"ingest() must not re-spell the {table} insert — "
            "PostgresAdapter owns that statement"
        )
    assert any("insert into envelopes" in lit for lit in literals)
    assert any("insert into anchors" in lit for lit in literals)


def test_the_transaction_context_does_not_nest_and_rolls_back(monkeypatch):
    """`transaction()` is the seam that made one code path possible, so its
    own contract is pinned: the statements inside commit nothing, a clean
    exit commits once, any exception rolls back, and it refuses to nest
    rather than quietly sharing one connection between two blocks."""
    pytest.importorskip("psycopg")
    from homestead.keep import store

    conn = _RecordingConn(_RecordingCursor())
    conn.rolled_back = False
    conn.committed = False
    conn.commit = lambda: setattr(conn, "committed", True)
    conn.rollback = lambda: setattr(conn, "rolled_back", True)
    adapter = store.PostgresAdapter(
        "postgresql://x/y", household="hh-0123456789abcdef", connect=lambda dsn: conn
    )

    with adapter.transaction():
        adapter.write(store.SIDECAR, ("custody", "note", "n1"), "b",
                      envelope="e1", synced_at="2026-01-01T00:00:00+00:00")
        assert not conn.committed, "a row inside the transaction commits nothing"
        with pytest.raises(RuntimeError):
            with adapter.transaction():
                pass
    assert conn.committed and not conn.rolled_back

    conn2 = _RecordingConn(_RecordingCursor())
    conn2.rolled_back = False
    conn2.committed = False
    conn2.commit = lambda: setattr(conn2, "committed", True)
    conn2.rollback = lambda: setattr(conn2, "rolled_back", True)
    adapter2 = store.PostgresAdapter(
        "postgresql://x/y", household="hh-0123456789abcdef", connect=lambda dsn: conn2
    )
    with pytest.raises(ValueError):
        with adapter2.transaction():
            raise ValueError("planted")
    assert conn2.rolled_back and not conn2.committed
