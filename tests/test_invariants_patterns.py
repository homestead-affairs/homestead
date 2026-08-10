"""I-18 — extraction patterns are anchored and tested against PII negatives.

F-3: the citation regex matched `1420 Maple 87501` and missed `347 F.3d 1120`,
and the path that consumed citations POSTed what it matched — a home address left
the machine dressed as case law. The negatives are the load-bearing tests here:
an extraction pattern's false positive is not a miss, it is an exfiltration, so
each pattern is held to the address, phone, SSN and date shapes it must *not*
pull as hard as to the citations it must.
"""
from __future__ import annotations

from homestead.keep.patterns import CITATION


# ── the pinned F-3 case ──────────────────────────────────────────────────────

def test_i18_extraction_patterns_reject_pii():
    """Promoted from test_invariants_pending.py, verbatim: the exact citation
    that was missed matches, and the exact addresses that got through do not."""
    assert CITATION.findall("347 F.3d 1120")
    assert not CITATION.findall("1420 Maple 87501")
    assert not CITATION.findall("88 Ridgeline 90210")


# ── the reporter is a closed set, so real citations match ─────────────────────

CITATIONS = [
    "347 F.3d 1120",            # the one F-3 missed
    "410 U.S. 113",             # Roe v. Wade
    "550 U.S. 544",             # Twombly
    "163 U. S. 537",            # spaced reporter — same reporter
    "123 F. Supp. 2d 456",      # multi-token reporter with a series
    "5 Cal. 4th 1",             # a state reporter with a series
    "98 N.E.2d 34",
    "789 P.2d 12",
    "42 F. App'x 5",
]


def test_every_reporter_shape_is_matched():
    """A citation for each reporter shape the closed set covers — the
    false-negative-on-the-real-thing check that F-3 also failed."""
    for cite in CITATIONS:
        assert CITATION.findall(cite), f"missed a real citation: {cite!r}"


def test_a_citation_is_extracted_from_surrounding_prose():
    """Extraction, not just whole-string match: the citation is pulled out of a
    sentence, and its three parts come back."""
    matches = CITATION.findall("see 347 F.3d 1120 (9th Cir. 2003) for the standard")
    assert matches == [("347", "F.3d", "1120")]


# ── the negatives — nothing PII-shaped is pulled (the F-3 discipline) ─────────

NOT_CITATIONS = [
    "1420 Maple 87501",             # F-3's address
    "88 Ridgeline 90210",           # F-3's address
    "742 Evergreen Terrace 90210",  # a two-word street
    "123 Main St 45601",            # an address
    "1600 Pennsylvania 20500",      # an address
    "5 Elm 87501",                  # short street name
    "347 555 1120",                 # a phone-shaped triple — the middle is digits
    "123 45 6789",                  # an SSN-shaped triple
    "2026 08 10",                   # a date-shaped triple
    "12 Angry 1957",                # a number, a capitalized word, a number
    "3 Blind 2020",                 # the F-3 shape exactly — no reporter, no match
]


def test_no_pii_or_address_is_matched_as_a_citation():
    """The heart of I-18. Every one of these is `number word number` — the shape
    the loose regex matched — and none is a citation, because the middle token is
    not a reporter. A false positive here is PII on the wire."""
    for text in NOT_CITATIONS:
        assert not CITATION.findall(text), f"matched a non-citation: {text!r}"


def test_an_address_in_prose_is_not_pulled():
    """The live hazard, in the shape it actually arrives: an address sitting in a
    note must not be extracted and handed to whatever consumes citations."""
    assert not CITATION.findall("the exchange happens at 1420 Maple 87501 on Fridays")


def test_the_reporter_must_be_a_member_not_any_word():
    """The F-3 fix stated directly: swapping the reporter for a plausible
    capitalized word — even one shaped like an abbreviation — does not match. The
    set is closed; membership is the whole check."""
    assert not CITATION.findall("347 Maple 1120")
    assert not CITATION.findall("347 Xyz. 1120")     # looks like an abbreviation, isn't one
    assert not CITATION.findall("347 Ave. 1120")     # a real abbreviation, not a reporter
