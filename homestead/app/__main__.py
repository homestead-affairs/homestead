"""S1 — the window's entry point.

**I-21: no auto-render on start.** The record is not drawn before a human asks.
The resting state is a cover; `view.run` opens on it and draws the list only when
the operator opens a matter.

**I-29: the surface holds no domain logic.** The entry point routes to `view`,
which composes through `Window` and calculates nothing. When a surface file starts
calculating, something has leaked out of `homestead.keep`, and law-gazelle's
1,296-line `app.py` is what that looks like at the end.

Three ways in:
  * `--smoke` — start, prove every import survived packaging, exit without a
    display. What CI runs against the built artifact.
  * `--demo` — seed a synthetic custody matter into a throwaway store and print
    the list and a detail, composed through the gate. The pipeline, headless.
  * default — open the tkinter view on the cover.
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if "--smoke" in argv:
        # Prove the interpreter and every import survived packaging, including
        # the surface layer, and exit without a display — the check that would
        # have caught the excludes that made the first binary die on startup.
        from homestead.app import demo, view, window  # noqa: F401
        from homestead.keep import logs, paths, record, rungs  # noqa: F401
        print("homestead: smoke ok")
        return 0

    if "--demo" in argv:
        # A throwaway household root, so the demo writes synthetic data nowhere
        # real. Compose the surfaces through the gate and print what a view would
        # draw — the store → serve → surface pipeline, without a display.
        import os
        import tempfile

        from homestead.app import demo
        from homestead.keep.record import Sidecar

        with tempfile.TemporaryDirectory(prefix="homestead-demo-") as tmp:
            os.environ["HOMESTEAD_HOME"] = tmp
            print(demo.compose_demo(Sidecar()))
        return 0

    # Imported inside main so the module stays importable on a headless box —
    # the test suite reads these files, it does not open a display.
    from homestead.app import view

    return view.run()


if __name__ == "__main__":
    sys.exit(main())
