"""A synthetic custody matter, for seeing the surfaces work end to end (bite 4).

**Synthetic data only** — the plan holds real data until the ledger is wired, and
this writes to a throwaway store, never a real household root. It seeds one
custody matter into the sidecar and composes the list and a detail through the
gate, so the store → `serve` → surface pipeline can be run and read without a
display: `python -m homestead.app --demo`.

The values are invented; the rungs are the custody pack's, so what renders where
is the real crossing, not a mock. `courthouse`/`hearing_date` (L1) and `ssn` (L5)
carry no derived form; the L3/L4 fields carry one, because that is the human
re-identification judgement `Classified` requires and a pack does not author.
"""
from __future__ import annotations

from homestead.app.window import Ref, Window
from homestead.keep.record import Sidecar
from homestead.keep.rungs import Classified, Disposition
from homestead.packs import custody

MATTER = custody.MATTER  # "custody"

#: field → (payload, derived form or None). Invented content; real rungs.
_DEMO: dict[str, tuple[str, str | None]] = {
    "courthouse": ("Dept 4, Superior Court of California, County of Marin", None),
    "hearing_date": ("2026-09-15 08:30 · Dept 4", None),
    "case_number": ("FL-2026-00123", "A case number is on file"),
    "docket": ("Entry 14 — response filed 2026-08-01", "A docket entry is on file"),
    "opposing_party": ("Jordan Rivera", "The other parent is named"),
    "parenting_time": (
        "Tue/Thu 3-7pm, alternating weekends — minor A.R.",
        "A recurring parenting-time obligation on Tue/Thu",
    ),
    "child_name": ("A. Rivera, age 8", "A minor child is named in this matter"),
    "diagnosis": ("ADHD (per IEP, 2026-03)", "A medical category is on file for a person"),
    "notes": (
        "Late to pickup twice this month; smelled of alcohol on the 3rd.",
        "An operator note is on file",
    ),
    "ssn": ("123-45-6789", None),
}


def seed(store: Sidecar) -> None:
    """Write the synthetic matter into the store, replacing any prior demo. Each
    field becomes one record keyed `(custody, <field>, primary)`, classified at
    the pack's rung."""
    for field, (payload, derived) in _DEMO.items():
        rung = custody.FIELDS[field]
        store.put(MATTER, field, "primary", Classified(rung, payload, derived), overwrite=True)


def open_matter(store: Sidecar) -> Window:
    """Load the matter from the store into a Window's list pane."""
    window = Window()
    window.open_list(store.records(MATTER))
    return window


def _ref(field: str) -> Ref:
    return (MATTER, field, "primary")


def compose_demo(store: Sidecar) -> str:
    """Seed, list, and open two items — a headless proof of the whole pipeline,
    returning the text a view would draw so it can be read without a display.

    It shows the list (L1-L3 payloads, L4 as its derived form, no L5), then opens
    the `child_name` detail — where the L4 payload the list withheld now renders —
    and finally opens the sealed `ssn`, which the detail still denies."""
    seed(store)
    window = open_matter(store)

    lines = [f"{MATTER} — list (S1_LIST):"]
    for row in window.rows:
        lines.append(f"  [{row.rung.value}] {row.text}")

    served = window.open_detail(_ref("child_name"))
    shown = served.value if served.disposition is Disposition.RENDER else "(withheld)"
    lines.append(f"detail child_name (S1_DETAIL): [{served.rung.value}] {shown}")

    sealed = window.open_detail(_ref("ssn"))
    lines.append(
        f"detail ssn (S1_DETAIL): {sealed.disposition.value} (value={sealed.value!r})"
    )
    return "\n".join(lines)
