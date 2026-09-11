"""`docs/PLAN-affairs-face.md` — every struck bite names a PR *and* a release.

X7-drift-engine, Wave 7's plan-tracking requirement: the plan's engine bites,
copied into this repo, with each landed one struck through and named for the
PR and release that shipped it. The property worth a test is not "the right
bites are struck" — this repo cannot verify that mechanically without
re-deriving the whole git-log reading the document itself did — it is
narrower and checkable: **a struck bite whose annotation names no PR and no
release is a claim nobody could audit**, the doc-prose equivalent of a scan
that asserts a result with no evidence attached.

Two things the audit leg changed, both about what counts as evidence:

* **A PR number alone is not the claim the document makes.** Every strike in
  this file says "landed *and shipped*", and those are two facts with two
  different failure modes: a merged PR that never made a release, and a
  release named from memory. Both halves are required, and each has its own
  plant below.
* **The evidence window is the bullet, not 400 characters.** The first
  version looked a fixed distance past the closing `~~`, which meant a
  neighbouring bullet's PR number could satisfy a strike that named none of
  its own — precisely the accounting error the check exists to catch. The
  window is now the list item the strike sits in: from its `- ` to the next
  one. Paragraph-scoped evidence, the same rule the health leg's audit
  settled on, for the same reason.

Struck text is excluded from its own evidence. A bite whose *original* plan
text said "release 0.3.0" must not be allowed to satisfy "which release
shipped it" with the number the plan predicted — that is the claim under
test, not the proof of it — so each item is read through
`_strikethrough.live()` first, exactly as the doc guards in
`test_docs_drift.py` read prose.
"""
from __future__ import annotations

import re
from pathlib import Path

from _strikethrough import live

PLAN_FACE = Path(__file__).resolve().parent.parent / "docs" / "PLAN-affairs-face.md"

_STRUCK_SPAN = re.compile(r"~~.*?~~", re.DOTALL)
_PR_NUMBER = re.compile(r"#\d+")
_RELEASE = re.compile(r"\b\d+\.\d+\.\d+\b")


def _list_items(text: str) -> list[str]:
    """The document's top-level bullets, one string each — the evidence
    window. A bullet runs from its own `- ` at the start of a line to the
    next such line (continuation lines are indented, so they stay with their
    own bullet) or to the end of the section."""
    items: list[str] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("- "):
            if current is not None:
                items.append("\n".join(current))
            current = [line]
        elif current is not None:
            if line.startswith(("#", "|")) or (line and not line.startswith((" ", "\t"))):
                items.append("\n".join(current))
                current = None
            else:
                current.append(line)
    if current is not None:
        items.append("\n".join(current))
    return items


def _struck_items_missing_evidence(text: str) -> dict[str, list[str]]:
    """`{the struck bite, abbreviated: [what its own bullet never names]}`.

    Evidence is read from the bullet with its struck spans removed, so the
    plan's own prediction of a release number cannot stand in for the
    release that actually shipped it."""
    missing: dict[str, list[str]] = {}
    for item in _list_items(text):
        struck = _STRUCK_SPAN.search(item)
        if not struck:
            continue
        evidence = live(item)
        absent = []
        if not _PR_NUMBER.search(evidence):
            absent.append("a PR number")
        if not _RELEASE.search(evidence):
            absent.append("a release")
        if absent:
            missing[struck.group(0)[:80]] = absent
    return missing


def test_every_struck_bite_names_a_pr_number_and_a_release():
    text = PLAN_FACE.read_text("utf-8")
    assert _STRUCK_SPAN.search(text), (
        "no struck-through bite found at all — either nothing has landed "
        "(the engine is well past its first release) or the strike syntax "
        "drifted from ~~...~~"
    )
    missing = _struck_items_missing_evidence(text)
    assert not missing, (
        f"these struck bites do not name, outside the strike and inside "
        f"their own bullet, what landed them: {missing}"
    )


def test_the_evidence_guard_fires_on_a_planted_strike_with_no_pr(tmp_path):
    """Plant, half one: a strike whose bullet names a release and no PR."""
    planted = (
        "- ~~**E9-fake-bite** does a thing no test covers.~~ **Landed in "
        "release 0.9.0.**\n"
    )
    assert _struck_items_missing_evidence(planted) == {
        "~~**E9-fake-bite** does a thing no test covers.~~": ["a PR number"]
    }


def test_the_evidence_guard_fires_on_a_planted_strike_with_no_release(tmp_path):
    """Plant, half two: a strike whose bullet names a PR and no release —
    the half the first version of this guard did not ask for, so a bite
    merged but never shipped would have read as landed."""
    planted = (
        "- ~~**E9-fake-bite** does a thing no test covers.~~ **Landed: PR "
        "[#99](https://github.com/homestead-affairs/homestead/pull/99).**\n"
    )
    assert _struck_items_missing_evidence(planted) == {
        "~~**E9-fake-bite** does a thing no test covers.~~": ["a release"]
    }


def test_the_evidence_guard_reads_neither_the_strike_nor_the_next_bullet():
    """The two negative controls that make the window mean something.

    First: a bullet carrying both halves outside its strike passes. Second:
    a bullet whose *own* text is struck through with a PR and a release
    inside the strike does not — the plan predicted `release 0.3.0` in
    several of these bites, and letting a prediction prove itself is the
    accounting error this document exists to avoid. Third: the neighbouring
    bullet's evidence does not carry over, which the old fixed-width
    lookahead allowed.
    """
    good = (
        "- ~~**E9-fake-bite** does a thing.~~ **Landed: PR "
        "[#99](https://github.com/homestead-affairs/homestead/pull/99), "
        "release 0.9.0.**\n"
    )
    assert _struck_items_missing_evidence(good) == {}

    self_proving = "- ~~**E9-fake-bite**: release 0.3.0, see PR #99.~~ Landed.\n"
    assert _struck_items_missing_evidence(self_proving) == {
        "~~**E9-fake-bite**: release 0.3.0, see PR #99.~~": ["a PR number", "a release"]
    }

    neighbour = (
        "- ~~**E9-fake-bite** does a thing.~~ Landed.\n"
        "- **E10-other-bite** — **Landed: PR [#99](x), release 0.9.0.**\n"
    )
    assert _struck_items_missing_evidence(neighbour) == {
        "~~**E9-fake-bite** does a thing.~~": ["a PR number", "a release"]
    }


def test_every_module_bite_is_listed_and_says_where_it_is_tracked():
    """The other half of "struck through, never deleted", applied to bites
    this repo cannot see: a module bite left *out* of this document is
    indistinguishable from one that does not exist. Each is listed unstruck
    and attributed to the checkout that can answer for it, so a reader with
    that checkout open knows which `git log` to read."""
    text = PLAN_FACE.read_text("utf-8")
    for repo in ("homestead-law", "homestead-ledger", "homestead-health"):
        assert f"tracked in `{repo}`" in text, (
            f"no bite list is attributed to {repo}; a module bite with no "
            "repository named is a bite nobody can check"
        )
    for bite in ("W0-LAW", "L2b-instances", "G4-overlay", "H6-sealed-reader",
                 "L8-grant", "G8-business-books"):
        assert f"`{bite}`" in text, (
            f"{bite} is named in the affairs build-out plan and missing from "
            "this document — omission is the one mark this file may not make"
        )
