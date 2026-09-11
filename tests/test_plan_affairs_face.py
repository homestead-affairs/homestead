"""`docs/PLAN-affairs-face.md` — every struck bite names the PR that landed it.

X7-drift-engine, Wave 7's plan-tracking requirement: the plan's engine bites,
copied into this repo, with each landed one struck through and named for the
PR and release that shipped it. The property worth a test is not "the right
bites are struck" — this repo cannot verify that mechanically without
re-deriving the whole git-log reading the document itself did — it is
narrower and checkable: **a struck bite that names no PR number is a claim
nobody could audit**, the doc-prose equivalent of a scan that asserts a
result with no evidence attached. Planted the usual way.
"""
from __future__ import annotations

import re
from pathlib import Path

PLAN_FACE = Path(__file__).resolve().parent.parent / "docs" / "PLAN-affairs-face.md"

_STRUCK_SPAN = re.compile(r"~~.*?~~", re.DOTALL)
_PR_NUMBER = re.compile(r"#\d+")

#: How far past a struck span's closing `~~` the "landed" annotation is
#: allowed to sit. Generous on purpose — this document wraps its annotations
#: across several lines (`**Landed: PR\n  [#NN](...), release\n  0.X.0.**`)
#: — but bounded, so a PR number three paragraphs away for an unrelated bite
#: cannot satisfy a struck line that names none of its own.
_LOOKAHEAD = 400


def _struck_spans_missing_a_pr_number(text: str) -> list[str]:
    """Every struck span in `text` with no `#<digits>` in the text that
    immediately follows it — the shape a "landed" annotation with no PR
    number attached would take."""
    missing = []
    for match in _STRUCK_SPAN.finditer(text):
        window = text[match.end() : match.end() + _LOOKAHEAD]
        if not _PR_NUMBER.search(window):
            missing.append(match.group(0)[:80])
    return missing


def test_every_struck_bite_names_a_pr_number():
    text = PLAN_FACE.read_text("utf-8")
    assert _STRUCK_SPAN.search(text), (
        "no struck-through bite found at all — either nothing has landed "
        "(unlikely; the engine is at 0.11.0) or the strike syntax drifted "
        "from ~~...~~"
    )
    missing = _struck_spans_missing_a_pr_number(text)
    assert not missing, (
        f"these struck bites name no PR number within {_LOOKAHEAD} chars of "
        f"the strike: {missing}"
    )


def test_the_pr_number_guard_fires_on_a_planted_struck_bite_with_no_pr(tmp_path):
    """A scan that has never fired has not been shown to check anything."""
    unattributed = tmp_path / "planted_unattributed.md"
    unattributed.write_text(
        "- ~~**E9-fake-bite** does a thing no test covers.~~ Landed, done.\n",
        "utf-8",
    )
    assert _struck_spans_missing_a_pr_number(unattributed.read_text("utf-8"))

    attributed = tmp_path / "planted_attributed.md"
    attributed.write_text(
        "- ~~**E9-fake-bite** does a thing no test covers.~~ **Landed: PR "
        "[#99](https://github.com/homestead-affairs/homestead/pull/99).**\n",
        "utf-8",
    )
    assert not _struck_spans_missing_a_pr_number(attributed.read_text("utf-8"))
