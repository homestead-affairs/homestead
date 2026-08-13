"""`homestead.keep.nestor_seam` — the one place this face touches Nestor.

Nestor is an OPTIONAL EXTRA (`pyproject.toml`'s `[project.optional-
dependencies] entity`), pinned to the tag `v0.2.0`, never a required
dependency. Two properties carry that, each a test:

* **The seam is a no-op without the extra.** Nothing in `nestor_seam.py`
  imports `nestor` at module load — an AST scan, the same trick
  `test_invariants_egress.py` uses for `urllib` — so a checkout that never
  installs `[entity]` still imports this module and runs the rest of the
  suite. Every test in this file that *does* exercise Nestor's own machinery
  skips (not fails) when `nestor` is not importable, so a cold checkout
  without the extra keeps `pytest -q` bare and green (I-28).

* **Nothing crosses before `bind()`.** `resolver_for()` and `verify_ledger()`
  both refuse — `SeamNotBoundError` — before a ledger path is pinned, which is
  the leak PRECONDITION 1 in the module docstring names: an unbound Nestor
  ledger writes household entity resolutions to `data/ledger.jsonl` relative
  to the working directory, outside anything this face's own rules reach.
  Both refusal tests run unconditionally (they never reach an `import
  nestor`), so they hold even on a checkout without the extra installed.

And the forbidden-act test the guardrails ask for: `verify_ledger()` refuses
(`False`) a hash chain that was edited after the fact — the same shape
`homestead.keep.logs`'s own `IntegrityLog.verify()` is held to.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from homestead.keep import nestor_seam
from homestead.keep.nestor_seam import SeamNotBoundError

PKG = Path(__file__).resolve().parent.parent / "homestead"
SEAM = PKG / "keep" / "nestor_seam.py"


class _FakeStore:
    """The minimum `nestor.storage.Storage` surface `EntityResolver` touches
    when there is nothing sealed yet: `memory_init` (constructor) and
    `memory_candidates` (an empty domain, reached by `.resolve()`'s fallback
    to `memory.lookup`). Real persistence is this face's own build item —
    this seam only requires that *a* conforming store be passed in
    (PRECONDITION 2: never a process-wide global)."""

    def __init__(self) -> None:
        self.memory_init_calls = 0

    def memory_init(self) -> None:
        self.memory_init_calls += 1

    def memory_candidates(self, source_lang: str, target_lang: str) -> list:
        return []


@pytest.fixture(autouse=True)
def _reset_seam_state():
    """`nestor_seam` holds module-level `_bound`/`_ledger_path`, so one test's
    `bind()` must not leak into the next. Also resets Nestor's own
    process-wide ledger-verification cache when Nestor is installed, so a
    tampered-chain test in one case cannot be masked by another test's
    already-verified cache entry for a *different* tmp path — unlikely to
    collide by path, but the cache is process-wide state and this is the
    cheap way to not depend on that."""
    nestor_seam._bound = False
    nestor_seam._ledger_path = None
    try:
        import nestor.cascade as cascade
    except ImportError:
        cascade = None
    if cascade is not None:
        cascade._LEDGER_OVERRIDE = None
        cascade.reset_ledger_session()
    yield
    nestor_seam._bound = False
    nestor_seam._ledger_path = None
    if cascade is not None:
        cascade._LEDGER_OVERRIDE = None
        cascade.reset_ledger_session()


# ── the seam is a no-op without the extra ────────────────────────────────────

def test_nestor_seam_imports_no_nestor_at_module_load():
    """`import homestead.keep.nestor_seam` must succeed on a checkout that
    never installed `[entity]`. `bind`/`resolver_for`/`verify_ledger` each
    import `nestor` locally, inside the function — never at module scope."""
    tree = ast.parse(SEAM.read_text(encoding="utf-8"))
    top_level: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level.add(node.module.split(".")[0])
    assert "nestor" not in top_level, (
        "nestor_seam.py imports `nestor` at module load — this makes the "
        "optional extra ambient: a checkout without [entity] would fail to "
        "import this module, and every other test in the suite with it."
    )


def test_nestor_seam_never_calls_seal_or_add_alias():
    """Covenant: this seam proposes nothing and seals nothing on its own
    initiative. `EntityResolver.seal`/`.add_alias` are human-initiated writes
    (they take a `verifier=`); `resolver_for` only *returns* a resolver, it
    never calls either method itself. An AST scan rather than a runtime check,
    on the same reasoning `test_invariants_chokepoint.py` gives for scanning
    over trusting a helper: this is a property the source must not have, not
    a behavior to sample at test time."""
    tree = ast.parse(SEAM.read_text(encoding="utf-8"))
    banned = {"seal", "add_alias"}
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in banned
    ]
    assert not offenders, (
        f"nestor_seam.py calls a human-gated seal method itself, at line(s) "
        f"{offenders} — sealing must stay a caller's explicit act with a "
        f"named verifier, never something this seam does on its own."
    )


# ── nothing crosses before bind() — unconditional, no nestor import reached ──

def test_resolver_for_refuses_before_bind():
    with pytest.raises(SeamNotBoundError):
        nestor_seam.resolver_for("party", _FakeStore())


def test_verify_ledger_refuses_before_bind():
    with pytest.raises(SeamNotBoundError):
        nestor_seam.verify_ledger()


# ── bound behavior — skips (not fails) without the `entity` extra ───────────
#
# `importorskip` is called *inside* each test below, not at module scope.
# `test_invariants_release.py` calls it at module scope, which is fine there —
# that whole file is about a workflow file PyYAML is needed to read. Here it
# would be wrong: a module-level `importorskip` failing aborts collection of
# the *entire file*, taking the four unconditional tests above down with it —
# exactly the "no nestor at load" and "refuses before bind" proofs that must
# hold on a checkout *without* the extra. `test_theme.py`'s per-test
# `importorskip("tkinter")` is the precedent this follows instead.


def test_bind_pins_the_ledger_under_household_root_keep(tmp_path):
    """The path contract: `<household_root>/keep/ledger.jsonl`, computed from
    `homestead.keep.paths`-shaped input — never a literal, never Nestor's own
    `nestor.homestead_paths` (PRECONDITION 1: one resolver on this side)."""
    pytest.importorskip("nestor", reason="the `entity` extra is not installed")
    ledger = nestor_seam.bind(tmp_path)
    assert ledger == tmp_path / "keep" / "ledger.jsonl"

    from nestor.cascade import _ledger_path as resolved

    assert resolved() == ledger


def test_bind_defaults_to_homestead_keep_paths_home(monkeypatch, tmp_path):
    """With no argument, `bind()` calls the one module permitted to resolve a
    home directory (I-19/I-20) rather than inventing its own default."""
    pytest.importorskip("nestor", reason="the `entity` extra is not installed")
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    ledger = nestor_seam.bind()
    assert ledger == tmp_path / "keep" / "ledger.jsonl"


def test_resolver_for_after_bind_returns_a_scoped_entity_resolver(tmp_path):
    pytest.importorskip("nestor", reason="the `entity` extra is not installed")
    nestor_seam.bind(tmp_path)
    store = _FakeStore()
    resolver = nestor_seam.resolver_for("party", store)

    from nestor.entity import EntityResolver

    assert isinstance(resolver, EntityResolver)
    assert resolver.domain == "party"
    assert resolver.store is store
    assert store.memory_init_calls == 1


def test_resolver_for_never_installs_a_global_store(tmp_path):
    """PRECONDITION 2: the store travels only as the explicit argument.
    `nestor.storage.get_store()` with no explicit store must still raise —
    proof that `resolver_for` never called `nestor.storage.set_store()`."""
    pytest.importorskip("nestor", reason="the `entity` extra is not installed")
    nestor_seam.bind(tmp_path)
    nestor_seam.resolver_for("party", _FakeStore())

    from nestor.storage import get_store

    with pytest.raises(RuntimeError):
        get_store()


def test_verify_ledger_true_for_an_unwritten_chain(tmp_path):
    """No ledger yet is not a broken one — matches
    `homestead.keep.logs.IntegrityLog.verify()`'s convention for absence."""
    pytest.importorskip("nestor", reason="the `entity` extra is not installed")
    nestor_seam.bind(tmp_path)
    assert nestor_seam.verify_ledger() is True


def test_verify_ledger_true_for_an_intact_chain_after_a_resolve(tmp_path):
    pytest.importorskip("nestor", reason="the `entity` extra is not installed")
    nestor_seam.bind(tmp_path)
    resolver = nestor_seam.resolver_for("party", _FakeStore())
    resolver.resolve("Jane Q. Doe")  # unmatched — still appends an entry_resolve line

    ledger_path = tmp_path / "keep" / "ledger.jsonl"
    assert ledger_path.exists(), "resolve() must append to the pinned ledger"
    assert nestor_seam.verify_ledger() is True


# ── the forbidden-act test: a tampered chain must be refused ─────────────────

def test_verify_ledger_refuses_a_tampered_chain(tmp_path):
    """A guard that cannot be shown to fail has not been shown to work: write
    two legitimate entries, edit the first in place, and confirm
    `verify_ledger()` reports `False` rather than the tamper going unnoticed.

    Two entries, not one: Nestor's own chain vouches for every line *except*
    the newest, which nothing follows (the module docstring's PRECONDITION 1,
    and `nestor.ledger.verify`'s own documented limit) — editing the only line
    in a one-entry chain breaks nothing, because nothing chains onto it yet.
    """
    pytest.importorskip("nestor", reason="the `entity` extra is not installed")
    nestor_seam.bind(tmp_path)
    resolver = nestor_seam.resolver_for("party", _FakeStore())
    resolver.resolve("Jane Q. Doe")
    resolver.resolve("John R. Roe")

    ledger_path = tmp_path / "keep" / "ledger.jsonl"
    assert nestor_seam.verify_ledger() is True, "sanity: the untampered chain is intact"

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "two resolves must write two entries"
    tampered = json.loads(lines[0])
    tampered["canonical"] = "SOMEONE ELSE ENTIRELY"
    lines[0] = json.dumps(tampered)
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # A fresh process would re-walk from scratch; this process cached the walk
    # as part of resolve()'s append, so the cache must be dropped to re-read
    # the tampered bytes rather than trusting last time's answer.
    from nestor.cascade import reset_ledger_session

    reset_ledger_session()

    assert nestor_seam.verify_ledger() is False, (
        "an edited ledger line must be caught, not verified clean — a guard "
        "that cannot fail is not a guard"
    )
