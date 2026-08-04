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
from pathlib import Path

__all__ = ["home", "app_data", "logs_dir", "record_dir", "matter_dir", "drafts_dir"]

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


def matter_dir(matter: str) -> Path:
    return record_dir() / matter


def drafts_dir() -> Path:
    return home() / "drafts"


def ensure(path: Path) -> Path:
    """Create a directory under the root. Refuses anything outside it."""
    root = home()
    resolved = path if path.is_absolute() else root / path
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"refusing to create {resolved} outside {root}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
