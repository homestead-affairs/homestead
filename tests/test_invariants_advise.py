"""The advisory content check (I-18, and the three conditions).

`classify_schema` checks a rung was *declared*, not that it was declared *well*.
`advise` is the half it cannot do: a pattern check over a field's content against
its declared rung, which flags *declared L1, content shaped like an SSN*. It is
the guard the `notes = L4` decision was left leaning on.

The negatives are the load-bearing tests. F-3 was a citation regex that matched
`1420 Maple 87501` and missed `347 F.3d 1120`; a matcher whose patterns fire on
the ordinary content of an `L1` field would push every field up and drown the
real signal, so each pattern is held to the benign strings it must not fire on as
hard as to the PII it must.
"""
from __future__ import annotations

from homestead.keep.advise import CATEGORIES, Advisory, advise
from homestead.keep.rungs import Rung


# ── I-18 · the patterns catch their category (no false negative on the real thing) ──

POSITIVES = {
    "ssn": "school form needs SSN 123-45-6789 before Friday",
    "credit_card": "retainer paid on card 4111 1111 1111 1111",
    "dob": "child DOB: 2018-03-04, enrolled since",
    "bank": "support deposits to routing 021000021 account 123456789",
    "phone": "reach the other parent at 415-555-1234 after 6",
    "email": "correspondence went to jordan.rivera@example.com twice",
    "ein": "the business EIN 12-3456789 is on the filing",
}


def test_every_category_has_a_positive_and_it_matches():
    """Each known category matches its canonical PII at a low declared rung —
    the false-negative-on-the-real-thing check. And the fixture covers the whole
    known set, so a category added without a positive fails here."""
    assert set(POSITIVES) == set(CATEGORIES)
    for category, text in POSITIVES.items():
        cats = {a.category for a in advise(Rung.L1, text)}
        assert category in cats, f"{category} did not fire on {text!r}"


# ── I-18 · the patterns do NOT fire on ordinary L1 content (the F-3 discipline) ──

NEGATIVES = [
    "1420 Maple 87501",                         # F-3's address
    "88 Ridgeline 90210",                       # F-3's address
    "347 F.3d 1120",                            # a legal citation, not PII
    "Hearing Aug 15, 2026 at 8:30am, Dept 3",   # a hearing date — no DOB context
    "2026-09-15 08:30 · Dept 4",                # a hearing datetime
    "Entry 14 — response filed 2026-08-01",     # a docket entry
    "Case FL-2026-00123, Superior Court",       # a case number
    "mailing ZIP is 87501-1234",                # a ZIP+4, not an SSN
    "Tue/Thu 3-7pm, alternating weekends",      # a parenting schedule
    "took that into account when scheduling 3 visits",  # 'account' in prose
    "the minor is 8 years old",                 # an age, not a DOB
    "Dept 4, Superior Court of California",     # a courthouse
]


def test_no_pattern_fires_on_ordinary_content():
    """Every benign string produces no advisory even at the lowest rung, where
    every category is eligible to fire. A hearing date is not a birth date, a
    ZIP+4 is not an SSN, an address is not a phone number."""
    for text in NEGATIVES:
        result = advise(Rung.L1, text)
        assert result == (), f"{text!r} wrongly flagged {[a.category for a in result]}"


# ── condition 1 · only ever argues up, never down ────────────────────────────

def test_it_only_argues_up():
    """A concern is reported only when the content implies a rung *higher* than
    declared. Declared at or above the implied rung, there is nothing to say —
    and there is no path that reports a concern implying a lower rung."""
    # an SSN (implies L5) in a field declared L1 flags; declared L5 does not.
    assert advise(Rung.L1, POSITIVES["ssn"])
    assert advise(Rung.L5, POSITIVES["ssn"]) == ()
    # for every positive, at every declared rung, no advisory ever implies <= declared
    for text in POSITIVES.values():
        for declared in Rung:
            for a in advise(declared, text):
                assert a.implies is not declared
                # implies is strictly higher: composing them yields implies
                from homestead.keep.rungs import compose
                assert compose(a.implies, declared) is a.implies


def test_there_is_no_function_that_argues_down():
    """The module exposes a matcher and a type, and nothing that lowers a rung or
    pronounces a datum safe — condition 3's structural half. `compose` (imported
    for the ordering) only ever takes a max."""
    import homestead.keep.advise as mod
    for banned in ("declassify", "lower", "clean", "is_clean", "is_safe", "ok", "safe"):
        assert not hasattr(mod, banned), f"advise exposes {banned!r}"


# ── condition 2 · advisory, never a gate ─────────────────────────────────────

def test_advise_raises_nothing_and_blocks_nothing():
    """Whatever it is handed — PII, junk, an empty string, a non-string — it
    returns a tuple and raises nothing. A matcher that raised would be a gate."""
    for content in ("", "   ", POSITIVES["ssn"], 1234567, None, ["a", "list"]):
        result = advise(Rung.L2, content)
        assert isinstance(result, tuple)
        assert all(isinstance(a, Advisory) for a in result)


def test_advise_is_called_in_no_blocking_path():
    """The store's put/serve path does not consult the matcher — an advisory that
    could stop a write is a gate. `Sidecar.advise` exists as a *read-only* check
    the operator runs, and put() never calls it."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent
           / "homestead" / "keep" / "record.py").read_text("utf-8")
    tree = ast.parse(src)
    put = next(n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "put")
    calls = {
        (node.func.attr if isinstance(node.func, ast.Attribute)
         else getattr(node.func, "id", ""))
        for node in ast.walk(put) if isinstance(node, ast.Call)
    }
    assert "advise" not in calls, "put() consults the advisory matcher — that is a gate"


# ── it never echoes what it matched (I-15) ───────────────────────────────────

def test_an_advisory_never_carries_the_matched_text():
    """An advisory quoting the SSN it found would be the leak it exists to
    prevent. It carries the category and the rungs, never the datum."""
    for a in advise(Rung.L1, "SSN 123-45-6789 and card 4111 1111 1111 1111"):
        blob = repr(a) + a.message()
        assert "123-45-6789" not in blob
        assert "4111" not in blob


# ── the notes-residual closure (audit finding #5) ────────────────────────────

def test_it_catches_an_l5_datum_hiding_in_an_l4_note():
    """The exact residual the `notes = L4` decision left open: a note declared L4
    holding an SSN is content shaped for L5, and this is what says so. And a bare
    hearing date declared L1 is *not* pushed up — the matcher does not fire on the
    ordinary content it must live alongside."""
    note = ("Late to pickup twice this month; smelled of alcohol on the 3rd. "
            "School form needs SSN 123-45-6789.")
    concerns = advise(Rung.L4, note)
    assert any(a.category == "ssn" and a.implies is Rung.L5 for a in concerns)

    # the L1 hearing date, which must not be dragged up by the same tool
    assert advise(Rung.L1, "2026-09-15 08:30 · Dept 4") == ()


# ── the store integration — read-only, non-blocking ──────────────────────────

def test_sidecar_advises_over_a_stored_record(tmp_path, monkeypatch):
    """The store holds a record's content, so it is where the matcher can be
    handed it without a surface reaching a payload. A mis-declared note flags; a
    correctly-classified courthouse is quiet."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    from homestead.keep.record import Sidecar
    from homestead.keep.rungs import Classified

    store = Sidecar()
    store.put("custody", "notes", "n1",
              Classified(Rung.L4, "SSN 123-45-6789 for the school form",
                         derived="an operator note is on file"))
    store.put("custody", "courthouse", "main",
              Classified(Rung.L1, "Dept 4, Superior Court of California"))

    flagged = store.advise("custody", "notes", "n1")
    assert any(a.category == "ssn" for a in flagged)
    assert store.advise("custody", "courthouse", "main") == ()
