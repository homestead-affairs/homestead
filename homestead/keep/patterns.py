"""Extraction patterns — anchored, and tested against what they must not match.

I-18: **any pattern that could match PII is anchored and tested against PII
negatives.** An extraction pattern reads structure out of free text — a citation
out of a draft — and whatever it pulls can be acted on: cited, looked up, and in
the predecessor, *sent*. So a pattern that matches the wrong thing does not merely
miss; it exfiltrates. Every pattern here ships with the benign strings it must
not fire on, and the citation one ships with the exact address that got through.

## F-3, which is why the citation pattern is a closed set

The predecessor's citation regex was, in effect, *a number, then a word, then a
number* — and `1420 Maple 87501` is a number, a word, and a number. It matched a
home address, and the path that consumed citations **POSTed what it matched**, so
an address left the machine dressed as case law. The same regex *missed*
`347 F.3d 1120`, because "F.3d" is not the plain capitalized word the loose
pattern expected. Loose in the direction that leaks, strict in the direction that
drops the real thing — the worst of both.

The fix is that the middle token is **not any word**. A legal citation is
`volume reporter page`, and the *reporter* is one of a closed set of published
abbreviations — `U.S.`, `F.3d`, `F. Supp. 2d`, `N.E.2d`, and their kin. `Maple`
is not a reporter; `Ridgeline` is not a reporter; a street name never will be. So
the pattern cannot match an address, not because a negative test forbids that one
address but because the shape it requires is one an address does not have. The
closed set is the same move the rung, surface and purpose models make: a
membership test, never a free string. F-3 was the free string in the one place it
could POST.

The reporter list is not exhaustive — U.S. case reporting is vast — and that is
the safe direction here: an unknown reporter means a citation is *missed*, not
that an address is *matched*. A missed citation is a link not made; a matched
address is PII on the wire. When the list needs a reporter it lacks, it is added
with the citation it should have caught, as a test.
"""
from __future__ import annotations

import re

__all__ = ["CITATION", "REPORTERS"]

#: The closed set of reporter abbreviations, as regex fragments. Internal spacing
#: is `\s*` because "F. Supp. 2d" and "F.Supp.2d" are the same reporter, and a
#: trailing series (`2d`, `3d`, `4th`) is optional where the reporter has one.
#: Each entry is *the reporter*, never a wildcard — that is the whole of the F-3
#: fix. Add a reporter by adding its fragment (and the citation that needs it, as
#: a test); an unknown reporter misses a cite, it never matches an address.
REPORTERS: tuple[str, ...] = (
    r"U\.\s*S\.",                                  # U.S.
    r"S\.\s*Ct\.",                                 # S. Ct.
    r"L\.\s*Ed\.(?:\s*2d)?",                       # L. Ed., L. Ed. 2d
    r"F\.\s*Supp\.(?:\s*(?:2d|3d))?",              # F. Supp., F. Supp. 2d/3d
    r"F\.\s*App'x",                                # F. App'x
    r"F\.R\.D\.",                                  # F.R.D.
    r"F\.(?:\s*(?:2d|3d|4th))?",                   # F., F.2d, F.3d, F.4th
    r"A\.(?:\s*(?:2d|3d))?",                       # A., A.2d, A.3d
    r"P\.(?:\s*(?:2d|3d))?",                       # P., P.2d, P.3d
    r"N\.\s*E\.(?:\s*(?:2d|3d))?",                 # N.E., N.E.2d, N.E.3d
    r"N\.\s*W\.(?:\s*2d)?",                        # N.W., N.W.2d
    r"S\.\s*E\.(?:\s*2d)?",                        # S.E., S.E.2d
    r"S\.\s*W\.(?:\s*(?:2d|3d))?",                 # S.W., S.W.2d, S.W.3d
    r"So\.(?:\s*(?:2d|3d))?",                      # So., So. 2d, So. 3d
    r"Cal\.(?:\s*App\.)?(?:\s*(?:2d|3d|4th|5th))?",  # Cal., Cal. App. 4th, ...
    r"N\.\s*Y\.(?:\s*(?:2d|3d))?",                 # N.Y., N.Y.2d, N.Y.3d
)

# Longest fragment first, so "F. Supp. 2d" is tried before "F." and a series
# reporter is not shadowed by its base. Backtracking would find it either way,
# but ordering makes the reporter group capture the whole reporter.
_REPORTER = "(?:" + "|".join(sorted(REPORTERS, key=len, reverse=True)) + ")"

#: `volume reporter page` — two anchored integers around a reporter from the
#: closed set. `findall` yields `(volume, reporter, page)`; a non-citation yields
#: nothing. This is the pattern F-3 got wrong in both directions, made strict on
#: the middle token so an address cannot wear it.
CITATION: re.Pattern[str] = re.compile(
    r"\b(?P<volume>\d+)\s+(?P<reporter>" + _REPORTER + r")\s+(?P<page>\d+)\b"
)
