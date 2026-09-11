"""The invariants later phases must satisfy — written now, failing on purpose.

Every one is `xfail(strict=True)`, which means two things at once:

  * the suite stays green while the phase is unbuilt, so CI is honest; and
  * the moment an implementation makes one of these pass, **the suite fails**
    and forces the test to be promoted out of this file.

So this is not a wish list. It is a set of claims that cannot be quietly
satisfied and cannot be quietly forgotten. Each one names the failure it exists
to prevent, in an app that has already produced that failure once.
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import json
from pathlib import Path

import pytest

# Every module a pending test reaches for, and the phase that builds it.
UNBUILT = {
    # homestead.keep.dates was Phase 1 and is built. Its three tests moved to
    # tests/test_invariants_dates.py, unmarked — which is what this file is
    # for: test_pending_liveness failed the moment the module existed and would
    # not go green again until they were promoted out.
    #
    # homestead.keep.surfaces was Phase 2 and is built. Its three tests, plus
    # the I-11 test that was mis-attributed to `registry`, moved to
    # tests/test_invariants_surfaces.py, unmarked. Same mechanism, second
    # occasion.
    #
    # **The mis-attribution was not a typo and is worth leaving written down.**
    # `test_i11_unclassified_field_is_a_build_failure` imported
    # `classify_schema` from `homestead.keep.rungs`, which has existed since
    # Phase 0, and was marked `@pending("homestead.keep.registry", ...)`
    # because `rungs` could not be named here: a module in this dict is
    # asserted *not to exist*, and `rungs` did. So a Phase 2 addition to an
    # already-built module had no honest home, and it borrowed a Phase 3 one.
    #
    # That is a real limit of R-6 rather than a slip. This guard is
    # **module-granular** — `importlib.util.find_spec` answers for a module, not
    # for a symbol inside it — so a pending test whose real dependency is a
    # *function* that does not exist yet cannot be tracked by it at all. Two
    # consequences, both live: the reason string can be wrong in a way nothing
    # detects, and such a test goes XPASS-strict when its symbol lands, which is
    # a failure but not one that names the module. Phase 3 adds `registry`
    # and functions to modules that already exist; if it needs symbol-granular
    # pending marks, this dict is the thing to widen.
    #
    # homestead.keep.record was Phase 3 here and is built early, as bite 1 of
    # docs/PLAN-first-runnable.md ("the store — records survive a restart"). The
    # plan re-scoped the record layer forward: it is the seam everything else
    # renders over, so it comes before the registry rather than beside it. Its
    # I-36 test — the canonical handle has no write method — moved to
    # tests/test_invariants_record.py, unmarked, the third occasion of this same
    # promotion (dates, surfaces, then record). test_pending_liveness failed the
    # moment the module existed and would not go green again until it was moved.
    #
    # homestead.keep.registry was Phase 3 and is built. Its I-23 test — the
    # registry is the only enumeration — moved to
    # tests/test_invariants_registry.py, unmarked, another occasion of this same
    # promotion (dates, surfaces, record, then registry).
    #
    # homestead.keep.egress was built after the runnable-path batch: I-17, no
    # network egress by default, refused unless a per-call act is shown exactly
    # what will be sent. Its test moved to tests/test_invariants_egress.py,
    # unmarked.
    # homestead.keep.patterns was the last one: I-18, the citation extractor's
    # closed reporter set, so an address cannot wear a citation's shape (F-3).
    # Its test moved to tests/test_invariants_patterns.py, unmarked. With it,
    # UNBUILT is empty — every invariant this file ever held has been built and
    # its test promoted out. The dict stays (empty) and so does the machinery,
    # because the next phase's first pending test is one line, and the history
    # above is the record of how the ones before it landed.
    #
    # homestead.app.window was built as bite 4 of docs/PLAN-first-runnable.md
    # (the two S1 surfaces). Its I-21 test — a fresh window rests on the cover —
    # moved to tests/test_invariants_window.py, unmarked.
    #
    # homestead.app.cover (the I-31 re-identification counts) was then built:
    # the cover may show a count only where the number reveals nothing about
    # which matter it came from. Its I-31 test moved to
    # tests/test_invariants_cover.py, unmarked — the fourth occasion of this
    # promotion (dates, surfaces, record, then cover). test_pending_liveness
    # failed the moment the module existed and would not go green again until it
    # was moved and struck from this dict.
    #
    # 2026-09-11 — E1-pending (docs/PLAN-affairs-face.md,
    # "so-lets-plan-it-sparkling-shell") reseeds this dict for the sync/fleet
    # wave, four modules at once rather than one:
    #
    #   * `homestead.keep.sync` and `homestead.keep.household` — Wave 4
    #     (E4-sync-core). I-37 (sync is an operator-authored act — a refused
    #     confirm ledgers nothing), I-38 (an envelope is ledgered once, with
    #     references only) key on `sync`.
    #   * `homestead.keep.fleet_cli` — Wave 4 (E4-postgres-fleet). I-39 (the
    #     fleet ingest never listens and lazy-imports psycopg) keys on it.
    #   * `homestead.keep.sync` again for I-40 (an unnamed scope syncs
    #     nothing) — `SyncScope` is declared there per the plan's Decision 5.
    #   * `homestead.app.reveal` — a later UI wave (I-32/I-33), carried over
    #     from Phase 2's own list ("Deliberately not included": *"the I-32
    #     reveal timer (pending test only)"*) and PHASE2-SURFACES.md's open
    #     items 2 ("May the rung indicator say something is sealed?") and its
    #     "No `L4` timeout" gap. Both tests are written against a **provisional**
    #     API (`reveal.open`/`reveal.expire`) — see their docstrings.
    #
    # These invariant numbers are themselves provisional (I-37…I-40; the plan's
    # Decision 10) until an audit ratifies them alongside the code that builds
    # each module — the reason string on every one of these five tests says so.
    "homestead.keep.sync": "Wave 4 (E4-sync-core)",
    "homestead.keep.household": "Wave 4 (E4-sync-core)",
    "homestead.keep.fleet_cli": "Wave 4 (E4-postgres-fleet)",
    "homestead.app.reveal": "a later UI wave (I-32/I-33)",
}


def pending(module: str, why: str):
    """xfail with a reason naming *this* test's module and phase.

    A shared reason string made four different states indistinguishable —
    unbuilt phase, uninstalled package, partial implementation, and a **typo in
    an imported symbol**. The audit demonstrated the last one: a registry
    satisfying I-23 exactly, with the pending test importing `all_matter_types`
    instead of `all_matters`, left the suite green at 13 xfailed. Naming the
    module per test, plus `test_pending_liveness` below, closes that.
    """
    phase = UNBUILT.get(module, "unknown phase")
    return pytest.mark.xfail(strict=True, reason=f"{module} unbuilt ({phase}) — {why}")


def test_pending_liveness():
    """The guard the shared reason string could not provide.

    Asserts exactly which modules are still unbuilt. When a phase lands, this
    fails *first* and by name — so a pending test cannot keep xfailing for a
    reason nobody checked, and cannot be silently dropped because someone
    mistyped a symbol.
    """
    built = sorted(m for m in UNBUILT if importlib.util.find_spec(m) is not None)
    assert not built, (
        f"these modules now exist: {built}. Their pending tests must be "
        "promoted out of this file, and this list updated — do not leave them "
        "xfailing."
    )


# ── Phase 3 · the registry ───────────────────────────────────────────────────

# I-23 (`homestead.keep.registry`) was promoted to
# tests/test_invariants_registry.py when the registry was built.

# I-36 (`homestead.keep.record`) was promoted to tests/test_invariants_record.py
# when the store was built as bite 1 of docs/PLAN-first-runnable.md.


# ── Phase 4 · surfaces ───────────────────────────────────────────────────────

# I-21 (`homestead.app.window`) was promoted to tests/test_invariants_window.py
# when the two S1 surfaces were built as bite 4 of docs/PLAN-first-runnable.md.


# I-31 (`homestead.app.cover`) was promoted to tests/test_invariants_cover.py
# when the cover's re-identification counts were built.


# I-17 (`homestead.keep.egress`) was promoted to tests/test_invariants_egress.py
# when network egress was built after the runnable-path batch.


# I-18 (`homestead.keep.patterns`) was promoted to
# tests/test_invariants_patterns.py — the last pending invariant to land, leaving
# UNBUILT empty. Every claim this file once made red is now built and green.


# ── Wave 4/5 · sync, the fleet, and a reveal that expires ───────────────────
#
# Seeded 2026-09-11, E1-pending (docs/PLAN-affairs-face.md). Every module named
# below imports inside the test body, per the mechanism this file documents —
# so each of these fails today (`ModuleNotFoundError`, or here and there a
# missing name on a module that already exists for another reason), is caught
# by `xfail(strict=True)`, and goes XPASS-strict — a build failure, on purpose
# — the day the real module makes it pass. That is the promotion signal; the
# assertions below are what should still be true once it fires.


def _lines(path):
    """Every JSON line at `path`, or `[]` if it does not exist yet — the shape
    `test_invariants_export.py` reads `IntegrityLog` with, reused here because
    `IntegrityLog` deliberately has no public `read()` (see `keep/logs.py`)."""
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


@pending(
    "homestead.keep.sync",
    "I-37 (provisional): sync is an operator-authored act, never background — "
    "a refused confirm ledgers nothing",
)
def test_i37_a_sync_is_an_operator_authored_act(tmp_path, monkeypatch):
    """The failure this guards against: a sync that fires without an operator
    confirming exactly what will leave — F-3's shape, egress that acts *for*
    someone rather than *at their direction*. `keep.egress.send` already
    refuses with no `confirm`; Decision 5 says the sync act inherits that same
    refusal rather than re-deciding it, so `sync.deliver(envelope, confirm=None)`
    must raise the identical `EgressRefused` — and because a refused act is not
    an act, it must not touch either log: no `IntegrityLog` entry, no
    `VisibleLog` line.

    Provisional I-37 (the plan's Decision 10, ratified by audit alongside the
    code). Promotes to tests/test_invariants_sync.py when Wave 4's
    E4-sync-core builds `homestead.keep.sync`.
    """
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    from homestead.keep import logs, sync
    from homestead.keep.egress import EgressRefused
    from homestead.keep.rungs import Classified, Rung
    from homestead.keep.store import Sidecar

    Sidecar().put("custody", "deadline", "primary.hearing", Classified(Rung.L1, "2026-10-06"))
    scope = sync.SyncScope(matters=("custody",), item_types=None, ceiling=Rung.L3, tables=("sidecar",))
    envelope = sync.compose({"sidecar": Sidecar()}, scope)

    with pytest.raises(EgressRefused):
        sync.deliver(envelope, confirm=None)

    assert _lines(logs.IntegrityLog().path) == [], "a refused sync writes no integrity entry"
    assert logs.VisibleLog().read() == [], "a refused sync writes no visible line"


@pending(
    "homestead.keep.sync",
    "I-38 (provisional): an envelope is ledgered once, with references only",
)
def test_i38_an_envelope_is_ledgered_once_with_references_only(tmp_path, monkeypatch):
    """The failure this guards against: F-4's shape landing on the sync path — a
    served value (here, a court date an adversary should not get for free out of
    an audit trail) copied into the very `IntegrityLog` entry that exists to
    *prove the act happened*, not to hold a second copy of the record. One
    delivery must write exactly one integrity entry, naming the act by
    reference (`act`, `household`, `envelope`, `purpose`, `scope`, `rows`,
    `destination`) and carrying none of `value`/`payload`/`derived`, nor any
    substring of a served value; and exactly one `VisibleLog` line
    (`RECORD_SYNCED`) whose `ref` is `(household, envelope_id)` — a reference an
    operator can look up, never the content.

    Provisional I-38. Promotes to tests/test_invariants_sync.py alongside I-37.
    """
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    from homestead.keep import logs, sync
    from homestead.keep.rungs import Classified, Rung
    from homestead.keep.store import Sidecar

    SECRET_DATE = "2026-10-06"
    Sidecar().put("custody", "deadline", "primary.hearing", Classified(Rung.L1, SECRET_DATE))
    scope = sync.SyncScope(matters=("custody",), item_types=None, ceiling=Rung.L3, tables=("sidecar",))
    envelope = sync.compose({"sidecar": Sidecar()}, scope)

    sync.deliver(envelope, confirm=lambda wire: True, drop_dir=tmp_path / "drop")

    entries = _lines(logs.IntegrityLog().path)
    assert len(entries) == 1, "exactly one integrity entry per delivered envelope"
    (entry,) = entries
    assert entry["act"] == "record_synced"
    for field in ("household", "envelope", "purpose", "scope", "rows", "destination"):
        assert field in entry, f"missing {field!r} — the entry must name the act by reference"
    for banned in ("value", "payload", "derived"):
        assert banned not in entry, f"the ledger carries references, never content ({banned!r})"
    raw = json.dumps(entry)
    assert SECRET_DATE not in raw, "no served value may appear in the ledger (I-15)"
    assert entry["household"] == envelope.household
    assert entry["envelope"] == envelope.envelope_id

    (visible,) = logs.VisibleLog().read()
    assert visible["event"] == logs.Event.RECORD_SYNCED.value
    assert visible["ref"] == f"{envelope.household}/{envelope.envelope_id}"
    assert SECRET_DATE not in json.dumps(visible)


@pending(
    "homestead.keep.fleet_cli",
    "I-39 (provisional): the fleet ingest never listens and lazy-imports psycopg",
)
def test_i39_the_fleet_ingest_never_listens_and_lazy_imports_psycopg():
    """The failure this guards against: I-30's "nothing here listens" holding
    for every module except the one built to talk to a shared Postgres — an
    ingest command is exactly the code someone reaches for `socketserver` in,
    and I-27's import scan reads only `pyproject.toml`'s `dependencies`, so a
    module-level `import psycopg` would run clean in CI and only fail on a
    machine without the `fleet` extra installed. Two static checks, over the
    actual source (an AST scan, not a runtime import of `psycopg`-touching
    code): `homestead/keep/fleet_cli.py` contains none of the I-30 banned call
    names (`tests/test_invariants_shape.py`'s list); and neither it nor the
    `PostgresAdapter` region of `homestead/keep/store.py` imports `psycopg` at
    module level — it may only be reached inside a function body.

    Provisional I-39. Promotes to tests/test_invariants_fleet.py when Wave 4's
    E4-postgres-fleet builds `homestead.keep.fleet_cli` and `store.PostgresAdapter`.
    """
    banned = {"listen", "serve_forever", "create_server", "ThreadingHTTPServer"}

    def offenders(tree) -> list[str]:
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in banned:
                    hits.append(name)
        return hits

    def toplevel_psycopg(tree) -> bool:
        for node in tree.body:
            if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "psycopg" for a in node.names):
                return True
            if isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "").split(".")[0] == "psycopg":
                return True
        return False

    fleet_cli = importlib.import_module("homestead.keep.fleet_cli")
    fleet_tree = ast.parse(Path(inspect.getfile(fleet_cli)).read_text(encoding="utf-8"))
    assert not offenders(fleet_tree), "the fleet ingest must never listen (I-30)"
    assert not toplevel_psycopg(fleet_tree), "psycopg must be lazy, not a top-level import (I-27)"

    from homestead.keep import store

    store_tree = ast.parse(Path(inspect.getfile(store)).read_text(encoding="utf-8"))
    pg_class = next(
        (n for n in ast.walk(store_tree) if isinstance(n, ast.ClassDef) and n.name == "PostgresAdapter"),
        None,
    )
    assert pg_class is not None, "store.py must declare PostgresAdapter"
    assert not offenders(pg_class), "PostgresAdapter must never listen (I-30)"
    assert not toplevel_psycopg(store_tree), "psycopg must be lazy in store.py too (I-27)"


@pending(
    "homestead.keep.sync",
    "I-40 (provisional): an unnamed scope syncs nothing",
)
def test_i40_an_unnamed_scope_syncs_nothing(tmp_path, monkeypatch):
    """The failure this guards against: `--matters all` — a scope that syncs
    whatever exists rather than what the operator named, which turns a new
    matter added next month into something that leaves the machine the next
    time sync runs, with no act authorizing *that* matter. A `SyncScope` with
    no matters, and one whose `ceiling` is `L5` (an explicit invitation to the
    one rung `serve()` never crosses), must both refuse at construction — not
    compose an envelope with nothing or everything in it.

    Provisional I-40. Promotes to tests/test_invariants_sync.py alongside
    I-37/I-38.
    """
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    from homestead.keep import sync
    from homestead.keep.rungs import Rung

    with pytest.raises(Exception):
        sync.SyncScope(matters=(), item_types=None, ceiling=Rung.L3, tables=("sidecar",))
    with pytest.raises(Exception):
        sync.SyncScope(matters=("custody",), item_types=None, ceiling=Rung.L5, tables=("sidecar",))


@pending(
    "homestead.app.reveal",
    "I-32 (provisional): a reveal expires back to derived",
)
def test_i32_a_reveal_expires_back_to_derived():
    """The failure this guards against: PHASE2-SURFACES.md names it directly —
    "No `L4` timeout. I-32 — a reveal expires back to derived — needs a running
    surface. `S1_DETAIL` here says *may*, not *for how long*." An `L4` opened on
    the detail pane and left on screen (a shared machine, F-1's reader) must
    stop showing the payload after its window closes and fall back to the
    derived instruction — the same `DERIVE` a surface gets when no reveal was
    ever granted, not a lower rung and not a crash.

    **The API below is provisional** — `homestead.app.reveal` does not exist,
    and `open()`/`expire()` are a guess against the surface's own language,
    kept only so the test compiles. The strict xfail does not lock in that
    shape; it proves one claim cannot be quietly satisfied — *an opened `L4`
    reveal reads back as derived once it has expired* — no matter what the
    real API turns out to be. Promotion should rewrite this test to whatever
    `reveal` module lands, keeping that one assertion.

    Promotes to tests/test_invariants_reveal.py in a later UI wave.
    """
    from homestead.app import reveal
    from homestead.keep.rungs import Classified, Rung

    item = Classified(Rung.L4, "he was drunk at pickup", derived="a parenting-time note")
    handle = reveal.open(item)
    assert handle.value == item.payload, "freshly opened, a reveal shows the payload"

    reveal.expire(handle)

    assert handle.value == item.derived, "expired, it falls back to the derived form"
    assert handle.value != item.payload, "never the payload once expired"


@pending(
    "homestead.app.reveal",
    "I-33 (provisional): one rung indicator per pane",
)
def test_i33_one_rung_indicator_per_pane():
    """The failure this guards against: decision 2's own question — "may the
    rung indicator say that something is sealed?" — answered either way by a
    *design* that shows one indicator per field instead of one per pane, which
    turns "showing derived · `L4` present" into a per-row badge an operator can
    count, and counting badges is exactly the re-identification channel I-31
    exists to close on the cover. A pane with a mix of rungs must summarize to
    a single indicator, not one per field.

    **The API below is provisional** — `homestead.app.reveal` does not exist,
    and `pane_indicators()` is a guess kept only so the test compiles; see the
    same note on `test_i32_a_reveal_expires_back_to_derived` above. The strict
    xfail proves one claim — *a pane's rung indicator is singular* — survives
    whatever the real API turns out to be.

    Promotes to tests/test_invariants_reveal.py in a later UI wave.
    """
    from homestead.app import reveal
    from homestead.keep.rungs import Classified, Rung

    items = [
        Classified(Rung.L1, "2026-10-06", derived="a hearing date"),
        Classified(Rung.L2, "case no. 12", derived="a case reference"),
        Classified(Rung.L4, "he was drunk at pickup", derived="a parenting-time note"),
    ]
    indicators = reveal.pane_indicators(items)
    assert len(indicators) == 1, (
        "one indicator per pane, not one per field (I-33) — a list of per-field "
        "badges is the shape this test exists to forbid"
    )
    assert "L4" in indicators[0], "the pane's single indicator names its highest rung"
