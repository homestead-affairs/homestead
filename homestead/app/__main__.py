"""S1 — the window. Phase 0: it opens, and it shows nothing.

**I-21: no auto-render on start.** The record is not drawn before a human asks.
The resting state is a cover, and at Phase 0 the cover is all there is — which
is the correct order to build it in. An app that renders the queue on mount and
grows a cover later has already shipped the failure once.

**I-29: the surface holds no domain logic.** Everything here composes and
renders. When this file starts calculating, something has leaked out of
`homestead.keep`, and law-gazelle's 1,296-line `app.py` is what that looks like
at the end.
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    # Imported inside main so the module stays importable on a headless box —
    # the test suite reads this file, it does not open a display.
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Homestead")
    root.minsize(560, 360)

    cover = ttk.Frame(root, padding=48)
    cover.pack(fill="both", expand=True)
    ttk.Label(cover, text="Homestead", font=("TkDefaultFont", 22)).pack(anchor="w")
    ttk.Label(cover, text="The affairs you handle yourself.").pack(anchor="w", pady=(4, 24))
    # Phase 0 shows no counts. Counts are L2 only after the re-identification
    # check (I-31), and there is nothing yet to check.
    ttk.Label(cover, text="Nothing is open.", foreground="grey").pack(anchor="w")

    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
