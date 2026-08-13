"""nestor_seam.py — the ONLY place this face touches Nestor.

Landed at the `nestor` pin `v0.2.0` (see `pyproject.toml`'s `[project.optional-
dependencies] entity` extra). Written contract-first per the draft this module
replaces (`safe-app-store/docs/drafts/nestor_seam.py`): the seam and its
contract existed before any call site, so the boundary was built before there
was anything to drift across.

Nestor is Apache-2.0 with ``dependencies = []``. Nothing here obliges a
household to install a dependency tree.

**Nestor is an OPTIONAL EXTRA** (decided 2026-08-04), never a required
dependency. Every function here degrades to *feature absent* when Nestor is
not installed — nothing here raises on import, nothing here crashes a surface.
The household's own sealed log (build plan I-22, `homestead.keep.logs`) exists
regardless; Nestor's ledger is bound only when the extra is present and
`bind()` has run.

═══════════════════════════════════════════════════════════════════════════
TAKEN FROM NESTOR   (pin: v0.2.0, a tag — never a branch, fleet rule R14)
═══════════════════════════════════════════════════════════════════════════

  EntityResolver(store, domain=..., seal_threshold=...)   nestor.entity
      .resolve(surface) -> dict      read-only; fuzzy-match a surface form
                                     against sealed aliases
      .seal(surface, canonical, verifier=...)             human-initiated write
      .add_alias(surface, canonical, verifier=...)        human-initiated write

  Storage                                                 nestor.storage
      A Protocol. Nestor owns no persistence — "a concrete implementation is
      *injected* by the host." `resolver_for()` takes the store as a
      parameter rather than constructing one; a SQLite (or other) adapter
      conforming to the Protocol is this face's own build item, not this
      seam's.

  set_ledger_path(path)                                   nestor.cascade
      REQUIRED. See PRECONDITIONS. `bind()` calls this — it is the only
      function in this module that changes where Nestor's audit trail lives.

  ledger.verify(path, expected_head=...)                  nestor.ledger
      Verify the chain on read/boot. A broken chain is a refusal upstream of
      this call — `verify_ledger()` reports `False` for the caller to act on,
      the same convention `homestead.keep.logs.IntegrityLog.verify()` uses.

═══════════════════════════════════════════════════════════════════════════
NOT TAKEN   (deliberate — the omissions carry as much weight as the takings)
═══════════════════════════════════════════════════════════════════════════

  nestor.cascade translation pipeline   translate_text, translate_segment,
      graduate_segment. Translation is not this face's domain.

  nestor.matcher / nestor.semantic_matcher   reached only through
      EntityResolver. Never imported directly; that is how the surface widens.

  nestor.serve / nestor.ui / nestor.ui_page   an HTTP server. ``ui.py`` imports
      ``http.server`` and ``urllib.parse`` at module level, which would put a
      network import in the import-pure core and fail this repo's own
      `test_i30_i26_nothing_imports_the_network` (I-26/I-30) the moment the
      extra was installed and this seam imported it eagerly. It is not
      imported here, anywhere, ever.

  nestor.answer · curator · frank · glossary · langid · segment · reconcile
      · calibrate · portable · keyring · signing · memory · embedding_store
      · sqlite_store · engine · cli
      Not our business. Some are excellent. Not ours.

  THE ``cloud`` EXTRA  (``anthropic``)  — MUST NEVER BE INSTALLED ON THIS FACE.
      This face's premise is that nothing leaves the device. Installing this
      extra anywhere in the dependency chain contradicts the product.

  THE ``semantic`` EXTRA  (``fastembed``) — license discrepancy: its ``license``
      field says Apache while its PyPI classifier says ``Other/Proprietary``.
      Unresolved, so unused. Local embeddings, if this face ever wants them,
      are a separate decision.

═══════════════════════════════════════════════════════════════════════════
PRECONDITIONS   — all three MUST hold before any Nestor call in this process
═══════════════════════════════════════════════════════════════════════════

1.  THE LEDGER IS PINNED INSIDE `<household root>/keep/ledger.jsonl`.

    This is the one that is easy to miss and expensive to miss. Nestor's
    hash-chained ledger is **not part of the Storage protocol** — injecting the
    store does not cover it. Unbound, it resolves independently:

        _LEDGER_OVERRIDE  →  $NESTOR_LEDGER  →  "data/ledger.jsonl"

    So a default install writes to ``data/ledger.jsonl`` relative to the
    working directory: outside the household root, outside anything this
    face's own rules reach. `bind()` exists to close that window before any
    other Nestor call in this process — see `SeamNotBoundError`.

    The path is not invented here. It is the contract already agreed on both
    sides: `homestead.keep.paths.home()` and Nestor's own
    `nestor.homestead_paths.home()` resolve identically ($HOMESTEAD_HOME, else
    `<user-home>/.homestead`), and both name `keep/ledger.jsonl` under it as
    the pinned ledger. This seam calls **only** `homestead.keep.paths` for
    WHERE (I-19/I-20 — paths.py is the one module that resolves a home
    directory) and never `nestor.homestead_paths`, so there is one resolver on
    this side of the boundary, not two that could drift.

    And ``EntityResolver.resolve()`` appends on EVERY call (``entity.py``):

        {"kind": "entity_resolve",
         "surface_sha": sha256(surface)[:16],   # input, hashed
         "canonical":   <resolved value>,       # OUTPUT, IN CLEARTEXT
         "sealed": ..., "confidence": ...}

    The input is hashed; the resolved value is not. In a legal matter that is a
    line recording, in the clear, that some surface form resolves to a named
    party. Local, but recorded — and by default recorded somewhere this face's
    own rules do not reach, until `bind()` has run.

    Two notes on that hash, so nobody mistakes it for protection: it is SHA-256
    truncated to 16 hex characters (64 bits) and unsalted. Against low-entropy
    inputs such as personal names it is dictionary-reversible. ``surface_sha``
    is an audit identifier, not a privacy control.

    None of this is a defect in Nestor. The ledger is the audit trail; it is
    *meant* to live outside the store it audits, and that is correct design for
    Nestor. It simply means this face has a second wire to bind, not one.

2.  THE STORE IS PASSED EXPLICITLY, NEVER SET GLOBALLY.

    ``nestor.storage`` offers ``set_store()`` as a process-wide global. This
    seam does not call it. `resolver_for()` requires the caller's `store`
    explicitly, so two modules can never share a resolver's store by accident,
    and so the household's store cannot be picked up by code that was not
    handed it. Nestor's own contract: "an explicit argument always wins over
    the global."

3.  NESTOR IS PINNED TO A TAG.

    `v0.2.0`, never a branch on anything that ships (fleet rule R14). Never
    vendored: vendored source gets read and edited, a wheel in site-packages
    does not. See `pyproject.toml`'s `entity` extra.

═══════════════════════════════════════════════════════════════════════════
VOCABULARY
═══════════════════════════════════════════════════════════════════════════

Nestor's words stop here. This face speaks its own domain and the seam
translates, so the app is never renamed to match a dependency.

    Nestor              this face
    ─────────────       ─────────────────────────────────────────────
    seal                attest / verification   (cf. set_fact_verification)
    canonical           the resolved party, court, creditor, employer
    surface             the form as written in the record
    pair                a verification
    passage             — not used here

═══════════════════════════════════════════════════════════════════════════
FOR AGENTS AND FUTURE READERS
═══════════════════════════════════════════════════════════════════════════

Nestor is a PINNED DEPENDENCY consumed only through this file. Do not modify
it, do not propose changes to it, and do not move logic from this face into
it. If Nestor needs a change, that is an issue on Nestor's own repo.

The subject of work here is *how this face uses Nestor*, never Nestor itself.

Covenant: this seam never seals anything on its own initiative.
`EntityResolver.seal` / `.add_alias` are human-initiated writes upstream of
this module (a caller passes a `verifier=`); nothing here calls them, and
nothing here manufactures a `verifier`. A machine proposes; only a named human
seals.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import paths

__all__ = ["bind", "resolver_for", "verify_ledger", "SeamNotBoundError"]


class SeamNotBoundError(RuntimeError):
    """A Nestor call was attempted before `bind()` pinned the ledger.

    Raised rather than defaulted, because the default is the leak: an unbound
    ledger writes household entity resolutions to `data/ledger.jsonl` in the
    working directory. Fail closed — the same posture the promotion gate takes.
    """


_bound: bool = False
_ledger_path: Optional[Path] = None


def bind(household_root: Path | None = None) -> Path:
    """Pin Nestor's ledger inside the household root. Call once, before use.

    `household_root` defaults to `homestead.keep.paths.home()` — the one
    resolver this module is permitted to call (I-19/I-20) — and should only be
    passed explicitly by a test or an operator who deliberately moved the
    root, on the same terms `paths.py` itself documents for `HOMESTEAD_HOME`.

    Sets Nestor's ledger location to `<household_root>/keep/ledger.jsonl` —
    the path both this repo and `nestor.homestead_paths` agree on — via
    `nestor.cascade.set_ledger_path()`. Idempotent: calling it again with the
    same root re-asserts the same path (`set_ledger_path` is itself a no-op on
    an unchanged path); calling it with a different root re-binds to the new
    one. Returns the ledger path that is now pinned.

    Nestor is imported here, not at module load, so a checkout without the
    `entity` extra still imports this module cleanly — the seam is optional
    (I-27's promise extended to an optional extra: nothing ambient).
    """
    global _bound, _ledger_path

    from nestor.cascade import set_ledger_path

    root = Path(household_root) if household_root is not None else paths.home()
    ledger = root / "keep" / "ledger.jsonl"
    set_ledger_path(ledger)
    _ledger_path = ledger
    _bound = True
    return ledger


def resolver_for(domain: str, store: Any) -> Any:
    """An `EntityResolver` over an explicitly-injected household store.

    `domain` separates disjoint entity graphs within one store — "party",
    "court", "creditor", "employer" — so a custody matter's people and a
    bankruptcy matter's creditors never cross-talk.

    `store` is required and passed straight through to Nestor — this seam
    never calls `nestor.storage.set_store()` and never falls back to a global
    (PRECONDITION 2). Raises `SeamNotBoundError` if `bind()` has not run:
    constructing a resolver with an unpinned ledger is the leak this seam
    exists to prevent, so it is refused before Nestor is even imported.
    """
    if not _bound:
        raise SeamNotBoundError(
            "resolver_for() called before bind(). Call nestor_seam.bind() "
            "once at startup — an EntityResolver built on an unpinned ledger "
            "would write household entity resolutions to data/ledger.jsonl "
            "in the working directory, outside anything this face's own "
            "rules reach."
        )

    from nestor.entity import EntityResolver

    return EntityResolver(store, domain=domain)


def verify_ledger(expected_head: Optional[str] = None) -> bool:
    """Walk the hash chain and confirm every link. Run on read/boot.

    Returns `True` for an intact chain (or no ledger yet — Nestor's own
    `verify()` treats absence as trivially valid, matching
    `homestead.keep.logs.IntegrityLog.verify()`'s convention) and `False` for
    a broken one. The bool return, not an exception, is deliberate and matches
    this repo's own `IntegrityLog.verify()`: a broken chain is a refusal for
    the *caller* to act on — nothing in this module decides what "refusal"
    means for a given surface.

    Note Nestor's own stated limit: the walk vouches for every line except the
    last, which nothing follows — pass `expected_head` from somewhere the
    ledger's writer cannot reach (the operator, off this machine) if that tip
    needs covering too.

    Raises `SeamNotBoundError` if `bind()` has not run: there is no ledger
    path to verify until this seam has pinned one.
    """
    if not _bound:
        raise SeamNotBoundError(
            "verify_ledger() called before bind(). Call nestor_seam.bind() "
            "once at startup so there is a pinned ledger path to verify."
        )

    from nestor.ledger import verify

    ok, _detail = verify(str(_ledger_path), expected_head=expected_head)
    return ok
