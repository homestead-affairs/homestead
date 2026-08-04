"""I-22, I-15 — two logs, and neither of them is a confession timeline.

F-6 named the tension: a supervising attorney, LSC Part 1636 and any breach
clock all require an audit trail; an abuser sharing the machine reads it with
one keypress. The resolution is two logs with different powers.

F-4 is why the visible one carries references and never content: law-gazelle's
`add_note` copied the first 80 characters of every private note into the
activity log, and the last 8 activity rows went into every model prompt.
Note → log → prompt, and the log was one keystroke from the screen.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture()
def keep(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    from homestead.keep import logs

    return logs


# ── the visible log ──────────────────────────────────────────────────────────

def test_i15_visible_log_stores_a_reference_never_content(keep):
    log = keep.VisibleLog()
    log.record("note_added", ref=("custody", "atom", "ATM-001"))
    (entry,) = log.read()
    assert entry["ref"] == "custody/atom/ATM-001"
    assert "body" not in entry and "text" not in entry


def test_i15_visible_log_refuses_free_text(keep):
    log = keep.VisibleLog()
    with pytest.raises(TypeError):
        log.record("note_added", ref=("custody", "atom", "A"), body="he threatened")


# ── the sealed log ───────────────────────────────────────────────────────────

def test_sealed_log_is_hash_chained(keep):
    log = keep.SealedLog()
    log.append({"kind": "verification", "ref": "custody/atom/ATM-001"})
    log.append({"kind": "export", "ref": "custody/draft/D-1"})
    lines = [json.loads(x) for x in log.path.read_text().splitlines()]
    assert lines[0]["prev"] == "genesis"
    assert lines[1]["prev"] == keep.line_hash(lines[0])
    assert log.verify() is True


def test_sealed_log_detects_tampering(keep):
    log = keep.SealedLog()
    log.append({"kind": "verification", "ref": "a"})
    log.append({"kind": "verification", "ref": "b"})
    raw = log.path.read_text().splitlines()
    doctored = json.loads(raw[0])
    doctored["ref"] = "c"
    log.path.write_text("\n".join([json.dumps(doctored, sort_keys=True), raw[1]]) + "\n")
    assert log.verify() is False


def test_i22_sealed_log_has_no_render_path(keep):
    """The app appends to it and never shows it. That is the whole point."""
    log = keep.SealedLog()
    for forbidden in ("read", "render", "tail", "entries", "all", "show"):
        assert not hasattr(log, forbidden), (
            f"SealedLog.{forbidden}() would hand the audit trail to whoever "
            "opens the app — which is the reader F-6 is protecting against"
        )


def test_sealed_log_verify_does_not_return_content(keep):
    log = keep.SealedLog()
    log.append({"kind": "verification", "ref": "custody/atom/ATM-001"})
    assert log.verify() in (True, False)


def test_both_logs_live_under_the_root(keep, tmp_path):
    assert tmp_path in keep.SealedLog().path.parents
    assert tmp_path in keep.VisibleLog().path.parents
