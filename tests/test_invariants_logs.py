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
import threading

import pytest


@pytest.fixture()
def keep(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    from homestead.keep import logs

    return logs


# ── the visible log ──────────────────────────────────────────────────────────

def test_i15_visible_log_stores_a_reference_never_content(keep):
    log = keep.VisibleLog()
    log.record(keep.Event.NOTE_ADDED, ref=("custody", "atom", "ATM-001"))
    (entry,) = log.read()
    assert entry["ref"] == "custody/atom/ATM-001"
    assert entry["event"] == "note_added"
    assert "body" not in entry and "text" not in entry


def test_living_replaced_records_the_forgetting_lane_motion(keep):
    """Issue #24 — a consumer's forgetting lane (`homestead-health`'s living
    lane, H-8: overwrite in place, no recoverable prior) needs a closed
    `Event` member to surface its motion in the operator's activity feed.
    Bending an existing member (say `RECORD_SYNCED`, "a record was stored")
    to mean "a value was forgotten" is precisely the mislabelling the closed
    enum exists to prevent — R-7's own reason.

    The member behaves like every other one: reference-only, no content, and
    the closed-enum discipline still refuses free text in `event`."""
    log = keep.VisibleLog()
    log.record(keep.Event.LIVING_REPLACED, ref=("concerns", "cell", "C-1"))
    (entry,) = log.read()
    assert entry["event"] == "living_replaced"
    assert entry["ref"] == "concerns/cell/C-1"
    # The content-free rule still holds for the new member.
    assert "body" not in entry and "text" not in entry and "value" not in entry


def test_i15_visible_log_refuses_free_text_in_any_position(keep):
    """The first version asserted only that a kwarg *named* `body` raised —
    a test of Python's calling convention. The leak had simply moved to
    argument one, exactly as it did in law-gazelle's `log_activity(event_type,
    summary)`. `event` is now a closed enum."""
    log = keep.VisibleLog()
    with pytest.raises(TypeError):
        log.record("Note added: he was drunk again at pickup", ref=("custody", "atom", "A"))
    with pytest.raises(TypeError):
        log.record("note_added", ref=("custody", "atom", "A"))
    with pytest.raises(TypeError):
        log.record(keep.Event.NOTE_ADDED, ref=("custody", "atom", "A"), body="content")


# ── the sealed log ───────────────────────────────────────────────────────────

def test_sealed_log_is_hash_chained(keep):
    log = keep.IntegrityLog()
    log.append({"kind": "verification", "ref": "custody/atom/ATM-001"})
    log.append({"kind": "export", "ref": "custody/draft/D-1"})
    lines = [json.loads(x) for x in log.path.read_text().splitlines()]
    assert lines[0]["prev"] == "genesis"
    assert lines[1]["prev"] == keep.line_hash(lines[0])
    assert log.verify() is True


def test_i22_concurrent_appends_do_not_break_the_chain(keep):
    """Eight threads, twenty appends each. Before `append()` took a lock this
    wrote all 160 lines with 72 duplicate `prev` links and `verify()` False —
    an audit trail that indicts itself, which is `cascade.ledger_append`'s
    documented failure reproduced at the same thread count."""
    log = keep.IntegrityLog()

    def worker(n):
        for i in range(20):
            log.append({"kind": "verification", "ref": f"t{n}-{i}"})

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = [json.loads(x) for x in log.path.read_text().splitlines() if x.strip()]
    prevs = [e["prev"] for e in lines]
    assert len(lines) == 160, f"lost lines: {len(lines)}"
    assert len(prevs) == len(set(prevs)), f"{len(prevs) - len(set(prevs))} duplicate prev links"
    assert log.verify() is True


def test_anchor_catches_truncation(keep):
    """What the anchor is for. Without it, deleting the tail verified clean —
    the chain from genesis to any earlier point is still internally consistent,
    which is why a chain alone cannot detect a shorter chain."""
    log = keep.IntegrityLog()
    for i in range(4):
        log.append({"kind": "verification", "ref": f"e{i}"})
    lines = log.path.read_text().splitlines()
    log.path.write_text("\n".join(lines[:2]) + "\n")     # drop the last two
    assert log.verify() is False


def test_anchor_catches_a_rewritten_final_line(keep):
    """The chain vouches for every line except the last, which nothing follows.
    The anchor is what follows it."""
    log = keep.IntegrityLog()
    log.append({"kind": "verification", "ref": "a"})
    log.append({"kind": "verification", "ref": "b"})
    lines = log.path.read_text().splitlines()
    doctored = json.loads(lines[-1])
    doctored["ref"] = "c"
    log.path.write_text("\n".join(lines[:-1] + [json.dumps(doctored, sort_keys=True)]) + "\n")
    assert log.verify() is False


def test_anchor_does_not_stop_someone_who_edits_both(keep):
    """The honest limit, asserted so nobody assumes otherwise.

    An on-machine anchor detects accident, not an adversary — there is no
    location on this machine the writer cannot reach. Only a head the operator
    recorded off the machine closes it, and this test is the reason
    `verify(expected_head=...)` exists.
    """
    log = keep.IntegrityLog()
    log.append({"kind": "verification", "ref": "real"})
    true_head = log.head()

    log.path.unlink()
    log.anchor_path.unlink()
    forged = keep.IntegrityLog(log.path)
    forged.append({"kind": "verification", "ref": "forged"})

    assert forged.verify() is True, "a forged chain plus its own anchor is consistent"
    assert forged.verify(expected_head=true_head) is False, (
        "an off-machine head is the only thing that catches it"
    )


def test_verify_accepts_a_matching_expected_head(keep):
    log = keep.IntegrityLog()
    log.append({"kind": "verification", "ref": "a"})
    assert log.verify(expected_head=log.head()) is True
    assert log.verify(expected_head="not-the-head") is False


def test_sealed_log_detects_tampering(keep):
    log = keep.IntegrityLog()
    log.append({"kind": "verification", "ref": "a"})
    log.append({"kind": "verification", "ref": "b"})
    raw = log.path.read_text().splitlines()
    doctored = json.loads(raw[0])
    doctored["ref"] = "c"
    log.path.write_text("\n".join([json.dumps(doctored, sort_keys=True), raw[1]]) + "\n")
    assert log.verify() is False


def test_sealed_log_has_no_public_read_method(keep):
    """A naming convention, not a control — `_lines()` returns everything and
    `.path` is public. This shapes the app's own habits and stops nobody with
    filesystem access. See the module docstring; the threat model is the one
    open decision in docs/PHASE0-REMEDIATION.md."""
    log = keep.IntegrityLog()
    for forbidden in ("read", "render", "tail", "entries", "all", "show"):
        assert not hasattr(log, forbidden), (
            f"IntegrityLog.{forbidden}() would hand the audit trail to whoever "
            "opens the app — which is the reader F-6 is protecting against"
        )


def test_sealed_log_verify_does_not_return_content(keep):
    log = keep.IntegrityLog()
    log.append({"kind": "verification", "ref": "custody/atom/ATM-001"})
    assert log.verify() in (True, False)


def test_both_logs_live_under_the_root(keep, tmp_path):
    assert tmp_path in keep.IntegrityLog().path.parents
    assert tmp_path in keep.VisibleLog().path.parents
