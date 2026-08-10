"""The advisory content check — *declared `L1`, content shaped like an SSN*.

`classify_schema` checks that a field declared a rung, not that it declared one
*well*: it accepts `L1` for a sealed case number without a murmur. This is the
half it cannot do — a pattern check over a field's **content** against its
**declared** rung, which is exactly the class of error that gap admits. It is the
guard the `notes = L4` decision was left leaning on (docs/audits/
bites-1-3-remediation.md #5): a note declared `L4` that turns out to hold an SSN
is content shaped for `L5`, and this is what says so.

It is built to three conditions, and each is a property a test holds, not a
promise a docstring makes:

1. **It may only argue a rung *up*, never down.** `advise` reports a category
   only when the rung its content implies is *higher* than the declared one.
   There is no path that returns a concern implying a lower rung — `compose` is
   `max` for the same reason, and a tool that could argue a datum *down* is a
   declassifier, of which there is deliberately none.

2. **Advisory, never a gate.** `advise` returns concerns and raises nothing; it
   blocks no write and refuses no save. A regex that blocked a save would have
   quietly relocated a human judgement into a pattern list. Nothing in this
   package calls it in a blocking path.

3. **Its silence is not a clean bill.** An empty result means *no pattern here
   matched* — never *this content is safe*. There is no `is_clean`, no `ok`, no
   boolean verdict to render, precisely because a false negative is the dangerous
   direction and absence must fail toward suspicion (I-11's posture). The
   patterns catch what they catch; the world holds PII shapes they do not.

**The patterns are anchored and tested against negatives (I-18).** F-3 was a
citation regex that matched `1420 Maple 87501` and missed `347 F.3d 1120`. Every
pattern here ships with the benign strings it must *not* fire on — an address, a
ZIP+4, a hearing date, a docket entry, a citation — alongside the PII it must.
Because a false positive here only ever *raises* a rung (the safe direction), the
patterns lean toward catching; the negatives exist so they do not fire on the
ordinary content of an `L1` field and drown the real signal.

**It never echoes what it matched.** An `Advisory` carries the category, the rung
its shape implies, and the rung declared — a reference to a concern, never the
matched text (I-15). An advisory that quoted the SSN it found would be the leak it
exists to prevent.

**It reaches no `.payload`.** It takes the content as a plain string, so it is
neither the gate nor the store and the chokepoint holds — whoever legitimately
holds a record's content (the store) passes it in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .rungs import Rung, compose

__all__ = ["Advisory", "advise", "CATEGORIES"]


@dataclass(frozen=True)
class Advisory:
    """One concern: content shaped like `category`, whose shape implies `implies`,
    in a field declared `declared` (and `implies` is strictly higher — that is
    the only reason this exists). Carries no excerpt of the match: a reference to
    a concern, not the datum (I-15)."""

    category: str
    implies: Rung
    declared: Rung

    def message(self) -> str:
        return (
            f"content is shaped like {self.category} (implies {self.implies.value}), "
            f"but the field is declared {self.declared.value} — consider raising it. "
            "This is advisory: a shape is not a classification, and no match is "
            "not proof of none."
        )


#: category → (anchored pattern, the rung its content implies). The rungs are the
#: model's: an SSN is L5; a card, a bank number, a date of birth are L4; a phone,
#: an email, an EIN resolve to a person or entity at L3. Dates and bank numbers
#: are matched only in an explicit context (`DOB:`, `routing`), because a bare
#: date is a hearing date (L1) far more often than a birth date, and flagging
#: every date would push the L1 fields up and drown the signal.
_PATTERNS: dict[str, tuple[re.Pattern[str], Rung]] = {
    # ddd-dd-dddd (or space) — distinct from a phone (3-3-4) and a ZIP+4 (5-4).
    "ssn": (re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b"), Rung.L5),
    # four groups of four — a card number written the way people write it.
    "credit_card": (re.compile(r"\b(?:\d{4}[-\s]){3}\d{4}\b"), Rung.L4),
    # a date, but only where something says it is a birth date.
    "dob": (
        re.compile(
            r"\b(?:dob|d\.o\.b\.?|date of birth|birth\s?date|born(?:\s+on)?)\b"
            r"[\s:]*(?:\d{1,4}[-/]\d{1,2}[-/]\d{1,4}|[A-Za-z]+\.?\s+\d{1,2},?\s+\d{4})",
            re.IGNORECASE,
        ),
        Rung.L4,
    ),
    # a routing/account number, but only where labelled as one.
    "bank": (
        re.compile(r"\b(?:routing|aba|account|acct)\b[\s#:.]*\d{6,17}\b", re.IGNORECASE),
        Rung.L4,
    ),
    # (ddd) ddd-dddd or ddd-ddd-dddd — 3-3-4, not the 3-2-4 of an SSN.
    "phone": (
        re.compile(r"(?<!\d)(?:\(\d{3}\)\s?|\d{3}[-.\s])\d{3}[-.\s]\d{4}(?!\d)"),
        Rung.L3,
    ),
    "email": (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), Rung.L3),
    # dd-ddddddd — an EIN, distinct from an SSN's 3-2-4.
    "ein": (re.compile(r"\b\d{2}-\d{7}\b"), Rung.L3),
}

#: The categories this matcher knows. Named so a caller can say *which* shapes
#: were checked — and, by their absence from the world, cannot: the list is the
#: honest bound on what silence means.
CATEGORIES: tuple[str, ...] = tuple(_PATTERNS)


def _exceeds(implies: Rung, declared: Rung) -> bool:
    """`implies` is strictly higher than `declared`. Uses `compose` (the `max`)
    rather than a private order table, so this cannot disagree with the gate
    about which rung is higher."""
    return compose(implies, declared) is implies and implies is not declared


def advise(declared: Rung, content: object) -> tuple[Advisory, ...]:
    """Concerns where `content` is shaped like a category whose rung exceeds
    `declared`. Advisory only: it raises nothing and blocks nothing.

    Only ever argues *up*: a category whose implied rung is at or below `declared`
    is not reported, because the declared rung already covers it and this tool
    does not exist to argue a datum down. An empty result is *no pattern matched*,
    which is **not** a clean bill — the patterns know what they know.

    `content` is coerced to text so a non-string payload is still scanned rather
    than silently skipped; `declared` must be a `Rung`.
    """
    if not isinstance(declared, Rung):
        raise TypeError(
            f"advise() needs the declared Rung, not {type(declared).__name__} — "
            "it checks content against a classification the caller already has"
        )
    text = content if isinstance(content, str) else str(content)
    out: list[Advisory] = []
    for category, (pattern, implies) in _PATTERNS.items():
        if _exceeds(implies, declared) and pattern.search(text):
            out.append(Advisory(category=category, implies=implies, declared=declared))
    return tuple(out)
