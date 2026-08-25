"""The one path resolver. Everything a household owns hangs off `home()`.

**This is the only module in the package permitted to resolve a home
directory**, and `Path.home()` is the only spelling it may use. Both rules are
enforced by AST scan in `tests/test_invariants_paths.py`, and both exist because
the failures happened:

* **I-19.** law-gazelle's own resolver defaulted correctly — and its documented
  launcher (`dev.sh:17`) overrode it to `$HOME/Desktop/Nest`, putting case
  databases, drafts, letters and a manifest indexing the whole matter into the
  least private directory on a shared machine. The resolver was right and the
  launcher was the leak, so nothing here may be overridden to a fixed location.
  `HOMESTEAD_HOME` exists for tests and for an operator who deliberately moves
  the root; it is not a hook for a convenience default.

* **I-20.** `Path(os.path.expanduser("~")) / ".willow" / "apps" / APP_ID`
  extracts as bare `~` in the store's vault-leak linter and disappears from the
  report, while the identical path written `Path.home() / ...` is correctly
  flagged. Two spellings, same semantics, opposite verdicts. We use the one the
  tooling can see.
"""
from __future__ import annotations

import os
import unicodedata
from pathlib import Path

__all__ = ["home", "app_data", "logs_dir", "record_dir", "sidecar_dir",
           "matter_dir", "drafts_dir", "exports_dir", "anchors_dir", "ensure",
           "component"]

_ROOT_ENV = "HOMESTEAD_HOME"
_ROOT_NAME = ".homestead"


def home() -> Path:
    """The household root. `$HOMESTEAD_HOME`, else `<home>/.homestead`."""
    override = os.environ.get(_ROOT_ENV)
    if override:
        return Path(override)
    return Path.home() / _ROOT_NAME


def app_data() -> Path:
    return home()


def logs_dir() -> Path:
    return home() / "logs"


def record_dir() -> Path:
    """The canonical record. Read-only to this application (I-6, I-36)."""
    return home() / "record"


def sidecar_dir() -> Path:
    """Where the app writes (I-6). The canonical record is read-only, so the
    application's own records — everything it authors or stores — go here, in a
    parallel tree keyed the same way. Separate from `record_dir()` on purpose:
    a write path that led into the canonical record is exactly the type-level
    hole I-6 closes."""
    return home() / "sidecar"


def matter_dir(matter: str) -> Path:
    return record_dir() / matter


def drafts_dir() -> Path:
    return home() / "drafts"


def exports_dir() -> Path:
    """Where an export writes the artifact — the record leaving (bite 5, S4).

    Its own tree, separate from the record, the sidecar and the logs. An export
    is the operator taking their record out; the content lands here and nowhere
    near a log, which carries references only (I-15). Kept distinct from the
    anchor tree on purpose: wiping the export area must not reach the head that
    vouches for the ledger."""
    return home() / "exports"


def anchors_dir() -> Path:
    """Where an `IntegrityLog` head anchor is held, off the log's own tree.

    The willow-mcp #280 separation: the head that vouches for the chain is not
    stored next to the chain, so truncating the logs — or wiping the export
    tree — does not clear the witness in the same stroke. This is **not** a
    location the app cannot reach (F-5: a shared OS account has no such place);
    it is the head kept independent of the storage it vouches for. The real
    closure against an adversary stays `verify(expected_head=…)` with a head the
    operator recorded off the machine — see docs/DECISION-export-and-the-anchor.md."""
    return home() / "anchors"


def component(value: str, *, name: str = "component") -> str:
    """One reference component — the single validator both `export._segment`
    and `logs._ref` route through, so the two can never drift on what a
    reference part may contain.

    The drift is what issue #23 was: `export._segment` rejected `/`, `\\`,
    `.`/`..`, `\\x00`, and surrounding whitespace, but not embedded newlines;
    `logs._ref` rejected `/`, `\\`, and `\\n`, but not `..`, `\\x00`, or other
    control characters. A component such as ``"subj-01\\nFORGED"`` passed
    `_segment`, reached the artifact write and the `IntegrityLog.append`, and
    only then failed at `_ref` when `VisibleLog.record` ran — a partial write
    the caller saw as a clean refusal, and a `VisibleLog` that never learned
    the act happened.

    The strict spelling refuses:

    * separators (``/``, ``\\``) — a component is a single path segment;
    * ``.`` and ``..`` — the traversals `ensure()` also refuses;
    * ``\\x00`` — a null byte, subset of the control-char rule below but
      called out because it is the classic path-truncation trick;
    * surrounding whitespace — kept from the earlier `_segment` for the same
      reason: a reference is exactly what it names;
    * any character in Unicode categories starting with ``C`` (Cc control, Cf
      format, Cs surrogate, Cn unassigned), and the two line-break separators
      ``Zl`` / ``Zp`` — this is the total closure the issue names, catching
      newline, tab, zero-width space (Cf, invisible to ``str.isspace()``), and
      Unicode line separator (Zl, another `isspace()` miss on some platforms)
      in one rule rather than a growing blocklist. Regular space (``Zs``) is
      allowed for the reason below.

    Regular interior spaces are allowed: a matter or item id can be
    ``"custody-1"`` or ``"Doe v Roe"``. The rule refuses what is invisible or
    control, not what happens to render.

    Raises `ValueError` on refusal. Callers that own a contract exception
    (`export.ExportRefused`) catch and re-raise; callers that don't (`logs`)
    let the `ValueError` surface.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string, not {value!r}")
    if value.strip() != value:
        raise ValueError(
            f"{name}={value!r} has surrounding whitespace; a reference "
            "component is exactly what it names"
        )
    if value in (".", ".."):
        raise ValueError(
            f"{name}={value!r} is a path traversal — a reference component "
            "may not name its own directory or its parent"
        )
    if "/" in value or "\\" in value:
        raise ValueError(
            f"{name}={value!r} contains a path separator — a reference "
            "component is a single segment, not a path"
        )
    for ch in value:
        cat = unicodedata.category(ch)
        if cat.startswith("C") or cat in {"Zl", "Zp"}:
            raise ValueError(
                f"{name}={value!r} contains a control, format, or line-break "
                f"character ({ch!r}, Unicode category {cat}); a reference "
                "component must be printable so the two logs cannot disagree "
                "on what it holds"
            )
    return value


def ensure(path: Path | str) -> Path:
    """Create a directory under the root. Refuses anything outside it.

    **Resolves before checking.** `Path.parents` is lexical — it does not
    normalize `..` — so the first version of this guard accepted
    `home()/".."/".."/"x"` and `mkdir` created a directory at the filesystem
    root. Absolute-outside was correctly refused the whole time; the hole was
    normalization, not a missing check.

    `resolve()` also follows symlinks, which is the other half: a symlink
    planted under the root would otherwise redirect writes outside it.
    """
    root = home().resolve()
    candidate = Path(path)
    target = candidate if candidate.is_absolute() else root / candidate
    target = target.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"refusing to create {target} outside {root}")
    target.mkdir(parents=True, exist_ok=True)
    return target
