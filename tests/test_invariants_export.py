"""Bite 5 — the export act writes the ledger, and neither log carries content.

`docs/PLAN-first-runnable.md` bite 5, *done when*:

  * an export writes one `IntegrityLog` entry naming the purpose declared;
  * `verify(expected_head)` catches a hand-edited entry;
  * the visible log shows the act with no record content in it.

And the constraints the audit hardened around it:

  * the export path is gated through `serve(…, S4_EGRESS, purpose=…)`, so an
    unpurposed export is refused and an `L5` datum is refused *before* anything
    is ledgered — a refused export is not an export;
  * a note body never reaches either log (I-15, F-4): the logs carry references,
    the artifact carries the content, and the two do not swap roles;
  * the head anchor lives outside the tree the log is in and outside the tree the
    export writes to — the willow-mcp #280 separation (`DECISION-export-and-the-
    anchor.md`), with the off-machine head returned in the receipt as the one
    real closure.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def kit(home):
    from homestead.keep import export, logs, paths, rungs

    return export, logs, paths, rungs


# A distinctive private body — the F-4 shape. If this string ever appears in a
# log the note has leaked the way law-gazelle's add_note leaked it.
BODY = "he was drunk at pickup on 2026-08-01 — SSN 123-45-6789"


def _l4_item(rungs):
    return rungs.Classified(rungs.Rung.L4, BODY, derived="a parenting-time note")


def _read(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


# ── done-when 1 — one integrity entry, naming the purpose ─────────────────────

def test_an_export_writes_exactly_one_integrity_entry_naming_the_purpose(kit):
    export, logs, paths, rungs = kit
    receipt = export.export_record(
        _l4_item(rungs), "custody", "atom", "ATM-001",
        purpose=rungs.Purpose.EXPORT,
    )
    entries = _read(export.ledger().path)
    assert len(entries) == 1, "exactly one entry per export"
    (entry,) = entries
    assert entry["act"] == logs.Event.EXPORTED.value
    assert entry["purpose"] == rungs.Purpose.EXPORT.value
    assert entry["matter"] == "custody"
    assert entry["item_id"] == "ATM-001"
    assert receipt.purpose is rungs.Purpose.EXPORT


def test_the_integrity_entry_is_a_reference_never_content(kit):
    export, logs, paths, rungs = kit
    export.export_record(
        _l4_item(rungs), "custody", "atom", "ATM-001",
        purpose=rungs.Purpose.EXPORT,
    )
    raw = export.ledger().path.read_text(encoding="utf-8")
    assert BODY not in raw, "the payload must never enter the ledger (I-15)"
    assert "a parenting-time note" not in raw, "nor the derived form"


# ── done-when 2 — verify(expected_head) catches a hand-edit ───────────────────

def test_verify_with_the_receipt_head_catches_a_hand_edited_entry(kit):
    export, logs, paths, rungs = kit
    receipt = export.export_record(
        _l4_item(rungs), "custody", "atom", "ATM-001",
        purpose=rungs.Purpose.EXPORT,
    )
    ledger = export.ledger()
    assert ledger.verify(expected_head=receipt.head) is True

    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    doctored = json.loads(lines[-1])
    doctored["purpose"] = rungs.Purpose.SUBJECT_ACCESS.value   # rewrite the reason
    ledger.path.write_text(json.dumps(doctored, sort_keys=True) + "\n", encoding="utf-8")

    assert ledger.verify(expected_head=receipt.head) is False, (
        "the off-machine head from the receipt is what catches an edited ledger"
    )


# ── done-when 3 — the visible log shows the act, no content ───────────────────

def test_the_visible_log_shows_the_act_with_no_content(kit):
    export, logs, paths, rungs = kit
    export.export_record(
        _l4_item(rungs), "custody", "atom", "ATM-001",
        purpose=rungs.Purpose.EXPORT,
    )
    (entry,) = logs.VisibleLog().read()
    assert entry["event"] == logs.Event.EXPORTED.value
    assert entry["ref"] == "custody/atom/ATM-001"
    assert BODY not in json.dumps(entry)
    assert "a parenting-time note" not in json.dumps(entry)


# ── the body reaches the artifact, and neither log (I-15) ─────────────────────

def test_the_content_leaves_in_the_artifact_and_in_neither_log(kit):
    export, logs, paths, rungs = kit
    receipt = export.export_record(
        _l4_item(rungs), "custody", "atom", "ATM-001",
        purpose=rungs.Purpose.EXPORT,
    )
    # the export is the record leaving: the content is in the artifact
    assert receipt.artifact is not None
    assert BODY in receipt.artifact.read_text(encoding="utf-8")
    # and it is in neither log
    assert BODY not in export.ledger().path.read_text(encoding="utf-8")
    assert BODY not in logs.VisibleLog().path.read_text(encoding="utf-8")


# ── the export path is gated ──────────────────────────────────────────────────

def test_an_unpurposed_export_is_refused_and_not_ledgered(kit):
    export, logs, paths, rungs = kit
    with pytest.raises(export.ExportRefused):
        export.export_record(
            _l4_item(rungs), "custody", "atom", "ATM-001", purpose=None,
        )
    assert not export.ledger().path.exists(), "a refused export writes no ledger"
    assert not logs.VisibleLog().path.exists()


def test_a_malformed_purpose_raises_from_the_gate(kit):
    export, logs, paths, rungs = kit
    with pytest.raises(rungs.UndeclaredPurpose):
        export.export_record(
            _l4_item(rungs), "custody", "atom", "ATM-001", purpose="export",
        )
    assert not export.ledger().path.exists()


def test_an_l5_datum_may_not_be_exported_and_is_not_ledgered(kit):
    export, logs, paths, rungs = kit
    sealed = rungs.Classified(rungs.Rung.L5, "sealed order text")
    with pytest.raises(export.ExportRefused):
        export.export_record(
            sealed, "custody", "atom", "SEAL-1", purpose=rungs.Purpose.EXPORT,
        )
    assert not export.ledger().path.exists(), "L5 denies before anything is ledgered"
    assert not logs.VisibleLog().path.exists()


def test_export_takes_a_classified_not_a_bare_value(kit):
    export, logs, paths, rungs = kit
    with pytest.raises(TypeError):
        export.export_record(
            "just a string", "custody", "atom", "X", purpose=rungs.Purpose.EXPORT,
        )


# ── issue #23 · a bad reference component is refused before anything is written

# The regression the two-independent-validators bug produced: `export._segment`
# allowed embedded control characters (\n, \t, \x00, zero-width space) that
# `logs._ref` rejected, so a bad `item_id` passed the front-load check, reached
# `_write_artifact` and `IntegrityLog.append`, and only *then* raised at
# `VisibleLog.record` — a bare `ValueError` shaped like a clean refusal, over an
# artifact on disk and an integrity entry the operator's log never learned about.
# Fix: one shared `paths.component` validator, called from both `_segment` and
# `_ref`. The four tests below hold that closure honest.

_BAD_REF_CHARS = pytest.mark.parametrize(
    "bad",
    [
        "subj-01\nFORGED",       # newline — the exact case from the issue
        "subj-01\rFORGED",       # carriage return
        "subj-01\tFORGED",       # tab
        "subj-01\x00FORGED",     # null byte
        "subj-01​FORGED",   # zero-width space — Cf, str.isspace() misses it
        "subj-01 FORGED",   # Unicode line separator — Zl, another isspace miss
    ],
    ids=["newline", "carriage-return", "tab", "null", "zero-width-space",
         "unicode-line-sep"],
)


@_BAD_REF_CHARS
def test_a_bad_component_refuses_cleanly_and_writes_nothing(kit, bad):
    """Issue #23: a control/format character in a reference component must
    refuse *before* the artifact and the integrity entry land. If it doesn't,
    the operator sees a raised exception over a committed act — a leak that
    looks like a refusal."""
    export, logs, paths, rungs = kit

    with pytest.raises(export.ExportRefused):
        export.export_record(
            _l4_item(rungs), "immunizations", "history", bad,
            purpose=rungs.Purpose.EXPORT,
        )

    # No artifact, no integrity entry, no visible entry — nothing at all.
    assert not paths.exports_dir().exists() or not any(paths.exports_dir().rglob("*.json"))
    assert not export.ledger().path.exists(), (
        "the integrity ledger must not carry an entry for a refused export"
    )
    assert not logs.VisibleLog().path.exists(), (
        "the visible log must not carry an entry for a refused export"
    )


@_BAD_REF_CHARS
def test_the_two_validators_agree_on_bad_components(bad):
    """`export._segment` and `logs._ref` must refuse the same set of components.
    Before the shared `paths.component` validator they didn't, and the drift
    was issue #23. Kept as a regression: parametrized over the exact characters
    that split the two old checks."""
    from homestead.keep import export, logs, paths

    with pytest.raises(ValueError):
        paths.component(bad, name="test")
    with pytest.raises(export.ExportRefused):
        export._segment("test", bad)
    with pytest.raises(ValueError):
        logs._ref(("matter", "type", bad))


def test_a_segment_refusal_is_export_refused_not_bare_valueerror(kit):
    """The issue named this half too: the old `_segment` raised its own
    `ExportRefused` for whitespace / separators / traversal, but the *log*
    validator raised bare `ValueError` — so a caller catching the contract
    exception could still be surprised. Now every refusal on the export path
    surfaces as `ExportRefused`, whether it comes from `_segment` up front or
    from `logs._ref` on a path that predates the shared validator."""
    export, logs, paths, rungs = kit

    with pytest.raises(export.ExportRefused):
        export.export_record(
            _l4_item(rungs), "immunizations", "history", "subj-01\nFORGED",
            purpose=rungs.Purpose.EXPORT,
        )


def test_component_accepts_ordinary_identifiers():
    """The rule refuses what is invisible or control, not what happens to
    render — a regular interior space stays legal so a matter can be
    ``"Doe v Roe"`` or an id ``"custody-1"``."""
    from homestead.keep import paths

    for good in ("ATM-001", "custody-1", "Doe v Roe", "subj_01", "étude"):
        assert paths.component(good, name="ok") == good


def test_component_refuses_empty_and_dots_and_separators():
    """The pre-existing `_segment` rejections, now enforced by the shared
    validator — parametrized here so a future rewrite doesn't quietly loosen
    one of them."""
    from homestead.keep import paths
    import pytest as _pt

    for bad in ("", "   ", " x", "x ", ".", "..", "a/b", "a\\b"):
        with _pt.raises(ValueError):
            paths.component(bad, name="bad")


# ── the head anchor lives off the log's own tree (willow-mcp #280) ────────────

def test_the_anchor_lives_outside_the_log_tree_and_the_export_tree(kit):
    export, logs, paths, rungs = kit
    ledger = export.ledger()
    assert paths.logs_dir() in ledger.path.parents, "the chain is in logs_dir()"
    assert paths.anchors_dir() in ledger.anchor_path.parents, (
        "the anchor is held in anchors_dir(), not beside the log"
    )
    assert paths.logs_dir() not in ledger.anchor_path.parents
    assert paths.exports_dir() not in ledger.anchor_path.parents


def test_wiping_the_log_dir_does_not_take_the_anchor(kit):
    """The #280 separation, exercised. Truncate the log; the anchor survives in
    its own tree, so verify() catches the truncation instead of clearing with
    it."""
    export, logs, paths, rungs = kit
    for i in range(3):
        export.export_record(
            _l4_item(rungs), "custody", "atom", f"ATM-{i}",
            purpose=rungs.Purpose.EXPORT,
        )
    ledger = export.ledger()
    assert ledger.verify() is True
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    ledger.path.write_text("\n".join(lines[:1]) + "\n", encoding="utf-8")   # truncate to one line
    assert ledger.verify() is False, (
        "the anchor is in a separate tree, so truncation is caught, not hidden"
    )
