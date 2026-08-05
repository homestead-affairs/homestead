"""Mutation harness for the `Purpose` corpus: does it actually bite?

`phase2_corpus_mutate.py` is the ancestor and it worked by **text substitution**
into a throwaway mock — each mutant was a `str.replace` against lines the corpus
author had written themselves. That is fine when you own the implementation you
are mutating. It is useless here: the blind half does not know what the real
`rungs.py` looks like, so no exact-string mutant would apply to it, and a mutant
that does not apply is a mutant that reports `KILLED` for free. Two of Phase 0's
scans had never fired, and this is the shape that lets that happen.

So this one mutates at the **API boundary** instead. Each mutant wraps the real
`homestead.keep.rungs` functions with one realistic defect and runs the corpus
against the result. It therefore works against *any* implementation of the
published contract, including the one this corpus was written blind against.

    # against the repo you are standing in
    PYTHONPATH=.:docs/audits python docs/audits/purpose_corpus_mutate.py

    # against any other checkout
    PYTHONPATH=/path/to/tree:docs/audits \\
        python docs/audits/purpose_corpus_mutate.py /path/to/tree

**A mutant that survives is a hole in the corpus, not a bug in the harness.**
The two controls that say the harness itself is honest are run first: the
unmutated tree must pass (or nothing below means anything) and `allow
everything` must die (or the runner is not running the tests).

The file is both the runner and the pytest plugin — invoked as `__main__` it
loops over the mutants; loaded as `-p purpose_corpus_mutate` it reads
`HOMESTEAD_MUTANT` from the environment and applies that one before collection,
which is early enough that the corpus's `from ... import may_render` picks up
the mutated binding.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

# ── the mutants ──────────────────────────────────────────────────────────────
# Each takes the module and returns nothing; it rebinds what it wants to break.
# Written against the published contract only, so they apply to any conforming
# implementation.

MUTANTS: dict[str, str] = {}


def mutant(name: str):
    def register(fn):
        MUTANTS[name] = fn.__name__
        globals()[fn.__name__] = fn
        return fn
    return register


# ── the enum's own guarantees ────────────────────────────────────────────────

@mutant("a purpose is free text again — any non-blank string declares")
def _m_free_text(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        if isinstance(purpose, str) and not isinstance(purpose, m.Purpose):
            purpose = m.Purpose.DRAFTING if purpose.strip() else None
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("the str-enum hole: the bare value of a member is accepted")
def _m_bare_value(m):
    orig = m.may_render
    values = {p.value: p for p in m.Purpose}

    def may_render(rung, surface, *, purpose=None):
        if type(purpose) is str and purpose in values:
            purpose = values[purpose]
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("membership by `in` rather than by type — a set of members finds a str")
def _m_membership_in(m):
    orig = m.may_render
    valid = set(m.Purpose)          # `"drafting" in valid` is True: same hash

    def may_render(rung, surface, *, purpose=None):
        if purpose is not None and purpose in valid:
            purpose = m.Purpose(purpose)
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("the enum refuses everything, members included")
def _m_refuse_all(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        if purpose is not None:
            raise m.UndeclaredPurpose(f"{purpose!r} is not a Purpose")
        return orig(rung, surface, purpose=None)
    m.may_render = may_render


@mutant("no purpose lifts anything — the argument is inert everywhere")
def _m_never_lifts(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        orig(rung, surface, purpose=purpose)        # keep the type check
        return orig(rung, surface, purpose=None)
    m.may_render = may_render


@mutant("`purpose=None` is an error rather than 'nobody declared one'")
def _m_none_is_an_error(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        if purpose is None:
            raise m.UndeclaredPurpose("a purpose is required")
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("a bad purpose denies quietly instead of refusing loudly")
def _m_quiet_denial(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        try:
            return orig(rung, surface, purpose=purpose)
        except m.UndeclaredPurpose:
            return False
    m.may_render = may_render


@mutant("a bad purpose raises a bare TypeError with no type of its own")
def _m_bare_typeerror(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        try:
            return orig(rung, surface, purpose=purpose)
        except m.UndeclaredPurpose as exc:
            raise TypeError(str(exc)) from None
    m.may_render = may_render


@mutant("the refusal says nothing about what would have been acceptable")
def _m_mute_refusal(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        try:
            return orig(rung, surface, purpose=purpose)
        except m.UndeclaredPurpose:
            raise m.UndeclaredPurpose("invalid argument") from None
    m.may_render = may_render


@mutant("the purpose is only checked after an unreadable rung has denied")
def _m_rung_first(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        readable = isinstance(rung, m.Rung) or (
            type(rung) is str and rung in {r.value for r in m.Rung}
        )
        if not readable:
            orig(rung, surface, purpose=None)       # surface still raises
            return False
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("one member is magic — EXPORT unlocks everything")
def _m_magic_member(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        if purpose is m.Purpose.EXPORT:
            return True
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("one member is inert — REDISCLOSURE declares nothing")
def _m_dead_member(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        if purpose is m.Purpose.REDISCLOSURE:
            purpose = None
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("a purpose is per-session: the last one declared stays in force")
def _m_per_session(m):
    orig = m.may_render
    remembered: list = []

    def may_render(rung, surface, *, purpose=None):
        if isinstance(purpose, m.Purpose):
            remembered.append(purpose)
        elif purpose is None and remembered:
            purpose = remembered[-1]
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("a stale cache keyed on (rung, surface) forgets the purpose — BUG-7")
def _m_stale_cache(m):
    orig = m.may_render
    seen: dict = {}

    def may_render(rung, surface, *, purpose=None):
        answer = orig(rung, surface, purpose=purpose)
        key = (rung, surface)
        if key in seen:
            return seen[key]
        seen[key] = answer
        return answer
    m.may_render = may_render


# ── the ceiling table, which the ruling says does not move ───────────────────

@mutant("I-35: the list pane serves an L4 payload once a purpose is declared")
def _m_list_pane_lifts(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        answer = orig(rung, surface, purpose=purpose)
        if (surface is m.Surface.S1_LIST and rung is m.Rung.L4
                and isinstance(purpose, m.Purpose)):
            return True
        return answer
    m.may_render = may_render


@mutant("I-13: L4 reaches the model prompt once a purpose is declared")
def _m_prompt_lifts(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        answer = orig(rung, surface, purpose=purpose)
        if (surface is m.Surface.S2_PROMPT and rung is m.Rung.L4
                and isinstance(purpose, m.Purpose)):
            return True
        return answer
    m.may_render = may_render


@mutant("I-13: L5 escapes onto egress for one member")
def _m_l5_escapes(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        answer = orig(rung, surface, purpose=purpose)
        if (surface is m.Surface.S4_EGRESS and rung is m.Rung.L5
                and purpose is m.Purpose.REDISCLOSURE):
            return True
        return answer
    m.may_render = may_render


@mutant("the detail pane stops being inert: a purpose takes L4 away")
def _m_detail_not_inert(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        answer = orig(rung, surface, purpose=purpose)
        if (surface is m.Surface.S1_DETAIL and rung is m.Rung.L4
                and isinstance(purpose, m.Purpose)):
            return False
        return answer
    m.may_render = may_render


@mutant("the agent surface loses its lift — L4 is unservable on S3")
def _m_s3_no_lift(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        if surface is m.Surface.S3_AGENT:
            orig(rung, surface, purpose=purpose)
            return orig(rung, surface, purpose=None)
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("monotonicity: L3 is refused on egress where L4 is served")
def _m_non_monotone(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        answer = orig(rung, surface, purpose=purpose)
        if (surface is m.Surface.S4_EGRESS and rung is m.Rung.L3
                and isinstance(purpose, m.Purpose)):
            return False
        return answer
    m.may_render = may_render


# ── the controls, and the classics the converted corpus must still kill ──────

@mutant("CONTROL · allow everything")
def _m_allow_all(m):
    m.may_render = lambda rung, surface, *, purpose=None: True


@mutant("deny everything")
def _m_deny_all(m):
    m.may_render = lambda rung, surface, *, purpose=None: False


@mutant("may_render returns None to mean 'derived'")
def _m_returns_none(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        return True if orig(rung, surface, purpose=purpose) else None
    m.may_render = may_render


@mutant("may_render grows an override")
def _m_force_param(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None, force=False):
        return True if force else orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("purpose becomes positional")
def _m_positional(m):
    orig = m.may_render

    def may_render(rung, surface, purpose=None):
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


@mutant("I-12: compose takes the min")
def _m_compose_min(m):
    order = {r: i for i, r in enumerate(m.Rung)}

    def compose(*rungs):
        if not rungs:
            return m.Rung.L5
        if not all(isinstance(r, m.Rung) for r in rungs):
            return m.Rung.L5
        return min(rungs, key=order.get)
    m.compose = compose


@mutant("I-11: composing nothing is L1")
def _m_compose_empty_l1(m):
    orig = m.compose
    m.compose = lambda *rungs: m.Rung.L1 if not rungs else orig(*rungs)


@mutant("I-11: an unclassified field defaults to L1")
def _m_classify_default(m):
    orig = m.classify_schema

    def classify_schema(schema):
        try:
            return orig(schema)
        except Exception:
            return {k: m.Rung.L1 for k in schema}
    m.classify_schema = classify_schema


@mutant("I-14: an integer rung is coerced to a rung")
def _m_int_rung(m):
    orig = m.may_render

    def may_render(rung, surface, *, purpose=None):
        if type(rung) is int and 1 <= rung <= 5:
            rung = m.Rung(f"L{rung}")
        return orig(rung, surface, purpose=purpose)
    m.may_render = may_render


# ── the pytest-plugin half ───────────────────────────────────────────────────

def pytest_configure(config):                   # noqa: ARG001 — pytest hook
    name = os.environ.get("HOMESTEAD_MUTANT")
    if not name:
        return
    import homestead.keep.rungs as rungs_mod
    import homestead.keep.surfaces as surfaces_mod

    rungs_mod.Surface = surfaces_mod.Surface     # convenience for the mutants
    globals()[MUTANTS[name]](rungs_mod)


# ── the runner half ──────────────────────────────────────────────────────────

TESTS = ["tests/test_surfaces_corpus.py", "tests/test_purpose_corpus.py"]


def run(base: pathlib.Path, mutant_name: str | None) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(base), str(pathlib.Path(__file__).resolve().parent)]
    )
    if mutant_name:
        env["HOMESTEAD_MUTANT"] = mutant_name
    else:
        env.pop("HOMESTEAD_MUTANT", None)
    args = [sys.executable, "-m", "pytest", *TESTS, "-q", "--no-header",
            "--tb=no", "-p", "no:cacheprovider", "-x"]
    if mutant_name:
        args += ["-p", "purpose_corpus_mutate"]
    proc = subprocess.run(args, cwd=base, capture_output=True, text=True, env=env)
    out = (proc.stdout or proc.stderr).strip().splitlines()
    return proc.returncode, out[-1] if out else "(no output)"


def main() -> int:
    base = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()

    code, summary = run(base, None)
    print(f"{'BASELINE  green' if code == 0 else 'BASELINE  RED':<18} {summary}")
    if code != 0:
        print("\nthe unmutated tree does not pass, so nothing below means "
              "anything. Fix that first.")
        return 2

    survivors = []
    for name in MUTANTS:
        code, summary = run(base, name)
        print(f"{'KILLED  ' if code else 'SURVIVED'}  {name}\n            {summary}")
        if code == 0:
            survivors.append(name)

    print()
    print("mutants:", len(MUTANTS), "· survivors:", survivors or "none")
    if "CONTROL · allow everything" in survivors:
        print("the control survived — the harness is not running the tests")
        return 2
    return 1 if survivors else 0


if __name__ == "__main__":
    raise SystemExit(main())
