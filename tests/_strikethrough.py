"""What a document still *asserts*, for the grep guards that scan prose.

House style keeps history struck through rather than deleting it, so a stale
sentence quoted inside `~~...~~` is not a live claim and must not trip a
drift guard. Two guards need that reading — `test_invariants_registry.py`
("only custody is registered") and `test_invariants_release.py` (the PyPI
publisher's owner) — and two copies of it would drift apart, which is the
same failure those guards exist to catch. One helper, imported by both.

`live()` does two things, and the second one is the one that was missing:

* drops every `~~...~~` span, `re.DOTALL` because a struck span wraps lines;
* collapses runs of whitespace to single spaces, because the prose it scans
  is hard-wrapped. The first version of the registry guard matched raw text,
  so its phrase "only custody is registered" could never match the README
  sentence it was written for — the README wrapped it as "Only custody is\\n
  registered". The guard passed on the very file it was meant to police.
"""
from __future__ import annotations

import re

_STRUCK = re.compile(r"~~.*?~~", re.DOTALL)
_WHITESPACE = re.compile(r"\s+")


def live(text: str) -> str:
    """The still-asserted text: struck spans removed, whitespace flattened."""
    return _WHITESPACE.sub(" ", _STRUCK.sub("", text)).strip()
