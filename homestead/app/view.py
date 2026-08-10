"""The tkinter view that draws a `Window` (bite 4).

Thin by construction (I-29): it turns `Window` state into widgets and clicks into
`Window` calls, and holds no domain logic. It draws `Row.text` and
`Served.value` — what the gate handed back — and reaches no `.payload`; the
chokepoint (`test_invariants_chokepoint.py`) makes that a build failure and also
forbids reflection here, so this file only ever renders what it was served.

It rests on the **cover** (I-21): nothing is drawn until the operator asks. The
list shows a rung and a line per item; opening one shows the detail. Synthetic
data only (`demo.seed`), in a throwaway store, until the ledger is wired — so
running this never writes a real household's record.

`tkinter` is imported inside `run()` so the module stays importable on a headless
box (the suite reads this file; it does not open a display).
"""
from __future__ import annotations

import os
import tempfile

from homestead.app import advisories, demo
from homestead.app.window import Window
from homestead.keep.record import Sidecar
from homestead.keep.rungs import Disposition


def run() -> int:
    import tkinter as tk
    from tkinter import ttk

    # A throwaway root, so running the view never touches a real household store.
    os.environ.setdefault("HOMESTEAD_HOME", tempfile.mkdtemp(prefix="homestead-demo-"))
    store = Sidecar()
    demo.seed(store)
    window = Window()

    root = tk.Tk()
    root.title("Homestead")
    root.minsize(600, 420)
    content = ttk.Frame(root, padding=24)
    content.pack(fill="both", expand=True)

    def clear() -> None:
        for child in content.winfo_children():
            child.destroy()

    def show_cover() -> None:
        window.close()
        clear()
        ttk.Label(content, text="Homestead", font=("TkDefaultFont", 22)).pack(anchor="w")
        ttk.Label(content, text="The affairs you handle yourself.").pack(anchor="w", pady=(4, 24))
        ttk.Label(content, text="Nothing is open.", foreground="grey").pack(anchor="w")
        ttk.Button(content, text="Open custody matter", command=show_list).pack(anchor="w", pady=(24, 0))

    def show_list() -> None:
        clear()
        window.open_list(store.records(demo.MATTER))
        ttk.Label(content, text="custody", font=("TkDefaultFont", 16)).pack(anchor="w")
        # one indicator per surface, not per row (I-33): the pane says an L4 is
        # present in its derived form, never a badge on every line.
        has_l4 = any(row.rung.value == "L4" for row in window.rows)
        ttk.Label(
            content,
            text="showing derived · L4 present" if has_l4 else "showing",
            foreground="grey",
        ).pack(anchor="w", pady=(0, 12))

        listbox = tk.Listbox(content, height=12)
        listbox.pack(fill="both", expand=True)
        rows = window.rows
        for row in rows:
            listbox.insert("end", f"[{row.rung.value}]  {row.text}")

        def on_open(_event: object = None) -> None:
            selection = listbox.curselection()
            if selection:
                show_detail(rows[selection[0]].ref)

        listbox.bind("<Double-Button-1>", on_open)
        ttk.Button(content, text="Open", command=on_open).pack(anchor="w", pady=(12, 0))
        ttk.Button(content, text="Close", command=show_cover).pack(anchor="w", pady=(4, 0))

    def show_detail(ref) -> None:
        served = window.open_detail(ref)
        clear()
        ttk.Label(content, text=f"{ref[1]}", font=("TkDefaultFont", 16)).pack(anchor="w")
        ttk.Label(content, text=served.rung.value, foreground="grey").pack(anchor="w", pady=(0, 12))
        body = (
            str(served.value)
            if served.disposition is Disposition.RENDER
            else "This record is sealed and is not shown here."
        )
        ttk.Label(content, text=body, wraplength=520, justify="left").pack(anchor="w")
        # A non-blocking advisory: if the stored content is shaped for a higher
        # rung than it was declared at (an SSN in an L4 note), say so where the
        # operator is already looking. A muted note, never a dialog and never a
        # block — the record is open regardless. Silence draws nothing (no "clean"
        # line): an empty result is *no pattern matched*, not a safety claim.
        for line in advisories.advisory_lines(store, ref):
            ttk.Label(
                content, text=line, foreground="grey", wraplength=520, justify="left"
            ).pack(anchor="w", pady=(8, 0))
        ttk.Button(content, text="Back", command=show_list).pack(anchor="w", pady=(24, 0))

    show_cover()
    root.mainloop()
    return 0
