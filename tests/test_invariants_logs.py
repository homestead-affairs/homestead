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

import ast
import json
import re
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "homestead"


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


def test_record_added_is_a_closed_member_with_no_body_parameter(keep):
    """Health currently borrows `RECORD_SYNCED` for "a record was entered by the
    operator" — a name that means something else (sync is Phase 4+, and will
    need `RECORD_SYNCED` for its own, real, meaning). `RECORD_ADDED` gives
    that motion its own name, on the same closed enum, with the same
    reference-only shape — no new parameter on `VisibleLog.record` for it."""
    log = keep.VisibleLog()
    log.record(keep.Event.RECORD_ADDED, ref=("custody", "atom", "ATM-002"))
    (entry,) = log.read()
    assert entry["event"] == "record_added"
    assert entry["ref"] == "custody/atom/ATM-002"
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
    """Narrowed 2026-09-11 (E7, proposed by the H6 audit): the property this
    test protects was never "no public reader" — `_entries()` was already a
    public-in-practice reader every in-package caller depended on under a
    leading underscore, and `read_entries()` (this bite) gives it the name
    honestly. What must still never exist is a reader spelled with one of
    these bare names, because none of them carries anywhere to put a
    refusal in its own signature — `read()`/`render()`/`tail()`/`show()`/a
    bare `entries()` all promise "here is the log," full stop, with no way
    to say "except I can't tell you that part." `read_entries` is allowed
    because its keyword argument is exactly that place; `_lines()` staying
    unfiltered and undecrypted, and `.path` staying public, are the same
    naming-convention residual as before this bite — see the module
    docstring's own account of what changed here and what did not."""
    log = keep.IntegrityLog()
    for forbidden in ("read", "render", "tail", "entries", "all", "show",
                      # E7 audit: the spellings the next hand reaches for
                      # once `read_entries` exists and it wants something
                      # shorter. Same objection to each — none of them has
                      # anywhere to put "except I could not tell you that
                      # part", so none of them can exist at all.
                      "iter_entries", "records", "rows", "lines", "dump"):
        assert not hasattr(log, forbidden), (
            f"IntegrityLog.{forbidden}() would hand the audit trail to whoever "
            "opens the app — which is the reader F-6 is protecting against"
        )
    assert hasattr(log, "read_entries"), (
        "read_entries() is the one door this bite names publicly — its "
        "keyword argument is where a sealed log's refusal lives, which is "
        "the property this guard actually cares about"
    )


#: Every public name on `IntegrityLog`, and why it is allowed to be public.
#: A list of forbidden spellings only catches the spellings someone thought
#: of; this catches the one they did not. Adding a public member means
#: adding it here *and* answering, in `tests/test_invariants_sealed.py`'s
#: table (`test_no_public_reader_answers_a_sealed_log_short`), what it does
#: to a sealed log without the key, without the extra, truncated and
#: corrupt.
PUBLIC_INTEGRITY_LOG_SURFACE = {
    "append":        "writes; refuses a downgrade by name",
    "seal":          "writes the boundary; refuses without key or extra",
    "verify":        "a finding (bool) or a refusal — never content",
    "head":          "one hash, never content",
    "read_entries":  "content — the one door, refusal in the signature",
    "path":          "a path (the module docstring's acknowledged residual)",
    "anchor_path":   "a path",
    "key":           "the raw key, for a caller that already holds it",
    "keyed":         "bool",
    "sealed":        "bool",
}


def test_integrity_logs_public_surface_is_closed(keep):
    """The non-vacuity guard for the one above (E7 audit). A forbidden-name
    list can only ever fail to find a name nobody listed — it would have
    passed unchanged if this bite had added `IntegrityLog.dump_all()`. So
    the whole public surface is enumerated instead, and a new public member
    fails here until someone writes down what it answers on a sealed log."""
    public = {n for n in dir(keep.IntegrityLog) if not n.startswith("_")}
    public |= {n for n in vars(keep.IntegrityLog()) if not n.startswith("_")}
    assert public == set(PUBLIC_INTEGRITY_LOG_SURFACE), (
        "IntegrityLog's public surface moved: added "
        f"{sorted(public - set(PUBLIC_INTEGRITY_LOG_SURFACE))}, removed "
        f"{sorted(set(PUBLIC_INTEGRITY_LOG_SURFACE) - public)}. Adding one "
        "means adding it here, and to the sealed-log table in "
        "tests/test_invariants_sealed.py that says what it answers when the "
        "key, the extra, or the tail of the file is missing"
    )


def test_the_public_surface_guard_is_not_vacuous(keep, monkeypatch):
    """The plant for the guard above: a public member that nobody wrote
    down. Set on the class, not an instance, because that is how one would
    actually arrive — a new `def` in `logs.py`."""
    monkeypatch.setattr(keep.IntegrityLog, "dump", lambda self: "everything",
                        raising=False)
    public = {n for n in dir(keep.IntegrityLog) if not n.startswith("_")}
    assert public - set(PUBLIC_INTEGRITY_LOG_SURFACE) == {"dump"}


def _ast_calls_named(tree: ast.AST, name: str) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Attribute) and node.func.attr == name)
            or (isinstance(node.func, ast.Name) and node.func.id == name)
        )
    ]


def _entries_calls_outside_its_own_definition(package_root: Path) -> list[str]:
    """Every call to `_entries(` under `package_root`, except the alias's
    own body (`return self.read_entries(...)` inside `def _entries`, which
    calls `read_entries`, never `_entries`, so it never matches anyway —
    there is nothing to except in practice, which is the point: after this
    bite, zero in-package call sites should still spell the deprecated
    name)."""
    hits = []
    for path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in _ast_calls_named(tree, "_entries"):
            # `.as_posix()`, not `str()`: the engine's CI matrix includes
            # Windows, where `str()` renders `keep\offender.py` and any
            # comparison against a posix literal below fails only there.
            rel = path.relative_to(package_root.parent).as_posix()
            hits.append(f"{rel}:{call.lineno}")
    return hits


def test_no_in_package_caller_still_spells_the_deprecated_entries_alias():
    """A scan that has never fired has not been shown to check anything —
    so this plants the violation it exists to catch (below) as well as
    running clean against the tree. `sync._already_delivered` was the one
    real caller (E6); this bite moved it to `read_entries()`, and nothing
    else in `homestead/` may reach for the deprecated name going forward."""
    hits = _entries_calls_outside_its_own_definition(PACKAGE)
    assert hits == [], (
        "these call sites still spell the deprecated IntegrityLog._entries() "
        f"alias instead of read_entries(): {hits}"
    )


def test_entries_alias_scan_fires_on_a_planted_violation(tmp_path):
    """The scan above has never fired against the real tree (it is clean),
    which proves nothing about whether it *can* fire — so a fake package is
    built here with exactly the violation it exists to catch."""
    fake_pkg = tmp_path / "fake_homestead"
    (fake_pkg / "keep").mkdir(parents=True)
    (fake_pkg / "__init__.py").write_text("", encoding="utf-8")
    (fake_pkg / "keep" / "__init__.py").write_text("", encoding="utf-8")
    (fake_pkg / "keep" / "offender.py").write_text(
        "def f(log):\n"
        "    for entry in log._entries():\n"
        "        pass\n",
        encoding="utf-8",
    )
    hits = _entries_calls_outside_its_own_definition(fake_pkg)
    assert hits == ["fake_homestead/keep/offender.py:2"]


def test_sealed_log_verify_does_not_return_content(keep):
    log = keep.IntegrityLog()
    log.append({"kind": "verification", "ref": "custody/atom/ATM-001"})
    assert log.verify() in (True, False)


def test_both_logs_live_under_the_root(keep, tmp_path):
    assert tmp_path in keep.IntegrityLog().path.parents
    assert tmp_path in keep.VisibleLog().path.parents


# ── E7 audit: the deprecated `_entries()` alias, and its removal ───────────

#: The release that removes `IntegrityLog._entries()`. E7 cuts 0.12.0 and the
#: alias lives "one minor"; a removal nobody wrote a date on is a removal
#: that never happens, so the version is here, in the method's own docstring,
#: and in `docs/DECISION-integrity-key-management.md` §9 — and the test below
#: starts failing the moment the changelog says it has arrived.
ENTRIES_ALIAS_REMOVED_IN = (0, 13, 0)


def _latest_released_version(text: str | None = None) -> tuple[int, int, int]:
    """The top `## [X.Y.Z]` heading in CHANGELOG.md — release-please writes
    it from the tag, and unlike `importlib.metadata.version()` it is the same
    number in a worktree, a shallow CI checkout and an editable install
    (which report a `.devN+g<sha>` guess derived from whatever tags the
    checkout happens to carry).

    `text` is for the plant below. This read the shipped changelog and
    nothing else until X7-drift's meta-scan named it: it decides *which half*
    of the deprecation-window assertion runs, and it had never once been
    shown to read a changelog correctly.
    """
    if text is None:
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^## \[(\d+)\.(\d+)\.(\d+)\]", text, re.M)
    assert m, "CHANGELOG.md has no released-version heading to read"
    return tuple(int(g) for g in m.groups())


def test_the_changelog_version_reader_fires_on_a_planted_changelog():
    """A scan that has never fired has not been shown to check anything, and
    this one silently decides whether the assertion below is "the alias must
    still be here" or "the alias must be gone". Planted four ways: the
    ordinary heading; a heading below an `## [Unreleased]` section, which
    must NOT be read as the release; a two-digit minor, because `0.9.0` and
    `0.10.0` sort the wrong way as strings and this returns integers; and a
    changelog with no released heading at all, which must refuse rather than
    hand back a default that would quietly flip the branch.
    """
    assert _latest_released_version("## [0.12.0](https://x) (2026-09-11)\n") == (0, 12, 0)

    assert _latest_released_version(
        "# Changelog\n\n## [Unreleased]\n\n## [0.13.0](https://x) (2026-09-12)\n"
        "\n## [0.12.0](https://x) (2026-09-11)\n"
    ) == (0, 13, 0), "the topmost released heading is the release"

    assert _latest_released_version("## [0.10.0](https://x)\n") > (0, 9, 0), (
        "0.10.0 is after 0.9.0 — this returns integers, not a string that "
        "would sort them the other way round"
    )

    with pytest.raises(AssertionError):
        _latest_released_version("# Changelog\n\nNothing has been released yet.\n")


def test_the_entries_alias_is_gone_by_its_named_removal_version():
    """The reminder. `_entries()` is a `DeprecationWarning` alias kept for
    one minor; `DeprecationWarning` is silent by default, so nothing else in
    this repo or any module downstream will ever *notice* that the minor has
    passed. This fails on the first release at or past the named version
    while the alias is still there."""
    from homestead.keep.logs import IntegrityLog

    if _latest_released_version() < ENTRIES_ALIAS_REMOVED_IN:
        assert hasattr(IntegrityLog, "_entries"), (
            "the deprecation window has not closed yet — removing the alias "
            "early breaks homestead-health's ledger_seam, which reaches for "
            "it by name (H6-sealed-reader)"
        )
        return
    assert not hasattr(IntegrityLog, "_entries"), (
        f"IntegrityLog._entries() was to be removed in "
        f"{'.'.join(str(n) for n in ENTRIES_ALIAS_REMOVED_IN)} and the "
        "changelog says that release has shipped — delete the alias, drop "
        "`warnings` from the I-27 stdlib allowlist in "
        "tests/test_invariants_integrity_keyed.py if nothing else needs it, "
        "and strike the sentence in DECISION-integrity-key-management.md §9"
    )


def test_the_named_removal_version_is_written_down_where_a_reader_looks():
    """The version is in three places on purpose — the method's docstring,
    the DECISION doc, and the constant above — and this is what keeps them
    the same number."""
    want = ".".join(str(n) for n in ENTRIES_ALIAS_REMOVED_IN)
    from homestead.keep.logs import IntegrityLog

    assert want in (IntegrityLog._entries.__doc__ or ""), (
        f"_entries()'s docstring does not name {want} as its removal release"
    )
    decision = (ROOT / "docs" / "DECISION-integrity-key-management.md").read_text(
        encoding="utf-8")
    assert want in decision.split("## 9 ·", 1)[1], (
        f"DECISION §9 does not name {want} as the alias's removal release"
    )


def test_the_entries_alias_warns_when_it_is_called_not_when_it_is_iterated(keep):
    """`stacklevel=2` only names the caller's own line if the warning fires
    at *call* time. Written as a generator function (`yield from
    self.read_entries(...)`) the alias would warn at the first `next()`
    instead — somewhere else entirely, possibly inside a comprehension in a
    third module, and possibly never for a caller that builds the generator
    and drops it. This pins the shape: calling it warns, before anything is
    iterated."""
    import inspect
    import warnings as _w

    log = keep.IntegrityLog()
    log.append({"kind": "a", "ref": "r1"})

    assert not inspect.isgeneratorfunction(keep.IntegrityLog._entries), (
        "_entries() must not be a generator function — its DeprecationWarning "
        "would then fire on the first next(), not at the call stacklevel=2 "
        "names"
    )
    with _w.catch_warnings(record=True) as caught:
        _w.simplefilter("always")
        gen = log._entries()               # not iterated
    assert [w.category for w in caught] == [DeprecationWarning]
    assert caught[0].filename == __file__, (
        "stacklevel=2 should name the caller's file, not logs.py"
    )
    assert [e["ref"] for e in gen] == ["r1"]
