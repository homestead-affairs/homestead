"""S1 — the window's entry point.

**I-21: no auto-render on start.** The record is not drawn before a human asks.
The resting state is a cover; `view.run` opens on it and draws the list only when
the operator opens a matter.

**I-29: the surface holds no domain logic.** The entry point routes to `view`,
which composes through `Window` and calculates nothing. When a surface file starts
calculating, something has leaked out of `homestead.keep`, and law-gazelle's
1,296-line `app.py` is what that looks like at the end.

Four ways in:
  * `--smoke` — start, prove every import survived packaging, exit without a
    display. What CI runs against the built artifact.
  * `--demo` — seed a synthetic custody matter into a throwaway store and print
    the list and a detail, composed through the gate. The pipeline, headless.
  * `integrity init-key|verify` — the E5 keyed-integrity CLI. Domain logic
    (key generation, chain verification) stays in `homestead.keep.logs`;
    `_integrity_main` only parses argv and prints, never key material — see
    `docs/DECISION-integrity-key-management.md`.
  * default — open the tkinter view on the cover.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _integrity_main(argv: list[str]) -> int:
    """`homestead integrity init-key|verify` — see
    docs/DECISION-integrity-key-management.md. Neither subcommand ever prints
    key material: `init-key` reports only the path it wrote to, `verify`
    reports only keyed/unkeyed and the boolean result.

    Three exit codes, because `verify()` gives three answers and collapsing
    them would make a cron job read "cannot tell" as "tampered" (or worse,
    the other way round): **0** clean, **1** the chain or the anchor does not
    hold, **2** this command line does not parse, **3** refused by name — an
    `IntegrityKeyError`, which is "the key needed to even ask the question is
    missing or broken," never a finding about the log.
    """
    from homestead.keep import export
    from homestead.keep.logs import IntegrityKeyError, IntegrityLog, init_key

    usage = "usage: homestead integrity init-key | verify [--path PATH]"
    if not argv or argv[0] not in ("init-key", "verify"):
        print(usage, file=sys.stderr)
        return 2

    if argv[0] == "init-key":
        if argv[1:]:
            print(usage, file=sys.stderr)
            return 2
        try:
            path = init_key()
        except IntegrityKeyError as exc:
            print(f"homestead integrity init-key: refused — {exc}", file=sys.stderr)
            return 3
        print(f"homestead: integrity key created at {path}")
        return 0

    # verify. An argument this does not understand is a usage error, never a
    # silent fall-through to the default ledger: `verify --pat x` answering
    # "ok" about a log the operator did not name is the worst failure this
    # command has (I-11 — refuse, never default).
    rest = argv[1:]
    custom_path = None
    if rest:
        if rest[0] != "--path" or len(rest) != 2:
            print(usage, file=sys.stderr)
            return 2
        custom_path = rest[1]
    log = IntegrityLog(Path(custom_path)) if custom_path else export.ledger()
    try:
        ok = log.verify()
    except IntegrityKeyError as exc:
        print(f"homestead integrity verify: refused — {exc}", file=sys.stderr)
        return 3
    kind = "keyed" if log.keyed else "unkeyed"
    print(f"homestead: {kind} — verify: {'ok' if ok else 'FAILED'}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv[:1] == ["integrity"]:
        return _integrity_main(argv[1:])

    if "--smoke" in argv:
        # Prove the interpreter and every import survived packaging, including
        # the surface layer and the export writer, and exit without a display —
        # the check that would have caught the excludes that made the first
        # binary die on startup.
        from homestead.app import demo, theme, view, window  # noqa: F401
        from homestead.keep import (  # noqa: F401
            advise, export, household, logs, paths, record, rungs, sync,
        )
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
