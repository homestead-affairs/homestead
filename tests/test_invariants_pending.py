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
    # 2026-09-11 — E1-pending, bite 7 of the affairs build-out plan
    # ("so-lets-plan-it-sparkling-shell"), reseeds this dict for the sync/fleet
    # wave, four modules at once rather than one. **That plan is not in this
    # repo yet**: it lands as `docs/PLAN-affairs-face.md` in its own Wave 7
    # bite, so until then the citations below are to the plan by name, and
    # every claim they carry is restated here rather than pointed at.
    #
    #   * `homestead.keep.sync` and `homestead.keep.household` — Wave 4
    #     (E4-sync-core). I-37 (sync is an operator-authored act — a refused
    #     confirm ledgers nothing), I-38 (an envelope is ledgered once, with
    #     references only) key on `sync`.
    #   * `homestead.keep.fleet_cli` — Wave 4 (E4-postgres-fleet). I-39 (the
    #     fleet ingest never listens and lazy-imports psycopg) keys on it.
    #   * `homestead.keep.sync` again for I-40 (an unnamed scope syncs
    #     nothing) — `SyncScope` is declared there per the plan's Decision 5.
    #   * `homestead.app.reveal` — a later UI wave (I-32/I-33). The affairs
    #     plan's "Deliberately not included" list keeps it there for now (*"the
    #     I-32 reveal timer (pending test only)"*), so the claims are Phase 2's
    #     and only the deferral is this plan's: docs/PHASE2-SURFACES.md, "What
    #     this does **not** cover" ("No `L4` timeout … `S1_DETAIL` here says
    #     *may*, not *for how long*") and product decision 2, whose original
    #     text is the question "May the rung indicator say that something is
    #     sealed?". Decision 2 is **ratified** — the indicator may not say `L5
    #     present` — and "needs Phase 4" because there is no renderer; I-33
    #     below tests the singular-indicator half only, not the ratified L5
    #     half, which belongs to the bite that builds the pane. Both tests are
    #     written against a **provisional** API (`reveal.open`/`reveal.expire`)
    #     — see their docstrings.
    #
    # These invariant numbers are themselves provisional (I-37…I-40; the plan's
    # Decision 10) until an audit ratifies them alongside the code that builds
    # each module — the reason string on every one of these five tests says so.
    #
    # 2026-09-11 — E4-sync-core built `homestead.keep.sync` and
    # `homestead.keep.household`. Their three tests (I-37, I-38, I-40) moved to
    # tests/test_invariants_sync.py, unmarked — the fifth occasion of this same
    # promotion (dates, surfaces, record, cover, now sync/household).
    # `test_pending_liveness` failed the moment the two modules existed and
    # would not go green again until they were moved and struck from this
    # dict. `homestead.keep.fleet_cli` (I-39, `E4-postgres-fleet`) and
    # `homestead.app.reveal` (I-32/I-33, a later UI wave) are still unbuilt.
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
# UNBUILT empty. Every claim this file once made red was then built and green —
# which held until 2026-09-11, when the section below reseeded the dict.


# ── Wave 4/5 · sync, the fleet, and a reveal that expires ───────────────────
#
# Seeded 2026-09-11, E1-pending (the affairs build-out plan; see the note in
# UNBUILT above for where it lives). Every module named below is reached inside
# the test body, per the mechanism this file documents — four by import, and
# `fleet_cli` by `find_spec` alone, because the violation *that* test guards
# against is a top-level import that would kill it before it could assert. So
# each of these fails today (`ModuleNotFoundError`, a missing spec, or here and
# there a missing name on a module that already exists for another reason), is
# caught by `xfail(strict=True)`, and goes XPASS-strict — a build failure, on
# purpose — the day the real module makes it pass. That is the promotion signal;
# the assertions below are what should still be true once it fires.
#
# I-37 (`homestead.keep.sync` — sync is an operator-authored act, a refused
# confirm ledgers nothing) and I-38 (an envelope is ledgered once, references
# only) and I-40 (an unnamed scope syncs nothing) were promoted to
# tests/test_invariants_sync.py, unmarked, when E4-sync-core built
# `homestead.keep.sync` and `homestead.keep.household` — the fifth occasion of
# this same promotion mechanism (dates, surfaces, record, cover, now sync).
# That file also carries the rest of the audit checklist for those two
# modules: the full `SyncScope` refusal table, the scope-ceiling drop (not
# derive), which `_CEILING` cell governs a synced `L4` row, envelope
# stability and tamper refusal, and the delivery contract's duplicate and
# destination handling.


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
    machine without the `fleet` extra installed. So the checks are static, over
    the actual source (an AST scan, not a runtime import of `psycopg`-touching
    code): `homestead/keep/fleet_cli.py` declares `main` — the console script's
    entry point, so an empty file does not satisfy this test — and contains none
    of the I-30 banned call names (`tests/test_invariants_shape.py`'s list); and
    neither it nor the `PostgresAdapter` region of `homestead/keep/store.py`
    imports `psycopg` at module level — it may only be reached inside a function
    body.

    **Nothing here is imported, and that is the point.** The first version of
    this test called `importlib.import_module("homestead.keep.fleet_cli")` to
    find the file, which meant that the one violation it exists to catch — a
    top-level `import psycopg` — killed the test with `ModuleNotFoundError`
    before a single assertion ran, on every machine without the `fleet` extra,
    which is the default `test` job. The suite stayed red, so nothing shipped;
    but it was red in a way that reads as "the extra is not installed", and the
    obvious next move is a `skipif` that switches the guard off precisely where
    it is needed. Reproduced against a simulated `keep/fleet_cli.py` during the
    E1-pending audit. `find_spec().origin` locates the source without executing
    it, so the scan answers for the file rather than for this machine's
    packages. The same for `store.py`, which the suite happens to import
    anyway — one mechanism, no exception to remember.

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

    def source(module: str) -> ast.Module:
        """The module's own text, located without importing it."""
        spec = importlib.util.find_spec(module)
        assert spec is not None and spec.origin, f"{module} must exist, as a file"
        return ast.parse(Path(spec.origin).read_text(encoding="utf-8"))

    fleet_tree = source("homestead.keep.fleet_cli")
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "main" for node in fleet_tree.body
    ), "fleet_cli must declare main() — `homestead-fleet ingest`'s entry point"
    assert not offenders(fleet_tree), "the fleet ingest must never listen (I-30)"
    assert not toplevel_psycopg(fleet_tree), "psycopg must be lazy, not a top-level import (I-27)"

    store_tree = source("homestead.keep.store")
    pg_class = next(
        (n for n in ast.walk(store_tree) if isinstance(n, ast.ClassDef) and n.name == "PostgresAdapter"),
        None,
    )
    assert pg_class is not None, "store.py must declare PostgresAdapter"
    assert not offenders(pg_class), "PostgresAdapter must never listen (I-30)"
    assert not toplevel_psycopg(store_tree), "psycopg must be lazy in store.py too (I-27)"


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
