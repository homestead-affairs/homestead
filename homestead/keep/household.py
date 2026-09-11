"""The household's own identifier — one per root, created once.

Decision 5 of the affairs build plan puts a fleet store behind sync: a
household's own record, copied to a place the household controls. That store
needs something to key rows by that is neither a person's name nor a
machine's hostname — an id for the *household*, stable across every sync
this root ever sends. This module is the one place that id is minted and
read.

**Created once, and the create can lose.** A second process (or a second
call racing the first) that reaches for the id before the file exists does
not overwrite whatever the first one wrote — it tries an exclusive create,
loses, and reads the winner's id back. The same shape I-9 gives every other
exclusive-create path here (`store.Sidecar.put`, `export._write_artifact`).

**A malformed file refuses by name (I-11).** `household.id` holding anything
that does not read as `hh-<16 hex>` — truncated by a crash mid-write,
hand-edited, or garbage — is refused rather than silently regenerated.
Regenerating one here would mint a *second* identity for a household whose
fleet rows are already keyed by the first, which is worse than refusing to
run.

**Shared per OS account (F-5; open item 6 of the affairs build plan).** This
file lives under `paths.home()` — one root per `$HOMESTEAD_HOME`, or one per
OS user when unset — not one root per person typing at the keyboard. Two
people sharing an account share one household id, exactly as they already
share one integrity chain and one export tree. Accepted here, not fixed, for
the same reason `keep/logs.py`'s own docstring makes the same call: a shared
OS account has no wall an application can build.
"""
from __future__ import annotations

import os
import re

from . import paths

__all__ = ["household_id", "MalformedHouseholdId"]

_FILENAME = "household.id"
_PATTERN = re.compile(r"^hh-[0-9a-f]{16}$")


class MalformedHouseholdId(ValueError):
    """`household.id` exists but does not read as `hh-<16 hex>`. Refused by
    name (I-11), never guessed and never silently regenerated — the failure
    mode a fresh id would buy back is worse than the one it would fix, since
    the fleet store already has rows keyed by whatever the original id was.
    """


def _generate() -> str:
    """`hh-` plus 16 lowercase hex characters — 8 bytes from the OS CSPRNG.
    Not derived from the machine or the account: F-5 already says this
    application cannot tell how many people share it, and this id names the
    record, not the hardware it happens to live on today."""
    return f"hh-{os.urandom(8).hex()}"


def household_id() -> str:
    """The household's id, read from `paths.home()/household.id`.

    Minted with an exclusive create on first use; every later call — in this
    process or another — reads the file back rather than minting again. See
    the module docstring for the create-can-lose race and the F-5 sharing
    this id inherits.
    """
    target = paths.home() / _FILENAME
    if not target.exists():
        paths.ensure(target.parent)
        candidate = _generate()
        try:
            with open(target, "x", encoding="utf-8") as fh:   # O_EXCL — the create can lose
                fh.write(candidate + "\n")
            return candidate
        except FileExistsError:
            pass   # lost the race — fall through and read the winner's id

    raw = target.read_text(encoding="utf-8").strip()
    if not _PATTERN.match(raw):
        raise MalformedHouseholdId(
            f"{target} does not read as hh-<16 hex> — refused rather than "
            "guessed or regenerated (I-11). A corrupted household id must "
            "not silently fork the household's identity in its own fleet "
            "store."
        )
    return raw
