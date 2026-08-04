# Phase 0 — remediation

**Phase 0 does not meet its exit criteria.** Two independent audits
(`docs/audits/`, 2026-08-04) found that the implementations are roughly right
and **the enforcement is theatre**: every claimed guarantee is weaker than its
documentation, and in three cases the documentation is the defect.

> **R-1 through R-7 are done (2026-08-04).** The suite is **27 passed / 13
> xfailed**, up from 19/13, with every new test a regression against a defect
> the audits demonstrated. **The one open decision below is still open** — the
> sealed log's threat model — and until it is made, `SealedLog`'s docstring
> states its limits rather than its ambition.
>
> Two false positives surfaced while fixing, both from my own new scans and both
> the same family: the literal check fired on `paths.py`'s docstring (which
> documents the banned pattern) and then on the string `"home"` inside
> `__all__` (a symbol name, not a path). Both were fixed by narrowing scope, not
> by editing the code being scanned. **A scan broad enough to catch its own
> vocabulary gets switched off, and a switched-off scan is worse than none.**

---

## Independently reproduced

Not taken on report. Each of these was re-run by a second reader before landing:

**The path scans miss the exact failure they exist to prevent.** Injecting
`Path(os.environ["HOME"]) / "Desktop" / "Nest"` into the package yields
**19 passed**. That is `household_safety.md`'s Desktop leak — the worst safety
finding in the predecessor — reintroduced in idiomatic pathlib, undetected. The
call-name ban never sees a `Subscript`, and the literal ban only catches
slash-concatenated strings, so `/ "Desktop"` contains no slash.

**The sealed log breaks itself under ordinary use.** Eight threads × 20 appends:
160 lines written, none lost, **72 duplicate `prev` links**, `verify()` →
**False**. `append()` reads the tail then writes with no lock. This is
`nestor/cascade.py:ledger_append`'s documented failure — *"an audit trail that
indicts itself, on a system whose whole claim is the trail"* — reproduced in a
codebase whose lineage contains the fix.

**`ensure()`'s containment check is lexical.** `.parents` does not normalize, so
`ensure(home()/".."/".."/"x")` passes the guard and `mkdir` creates the
directory at the filesystem root. Absolute-outside is correctly refused: this is
a normalization bug, not a missing check. Compounded — `ensure` is not in
`__all__`, so the one function carrying a security check is the one function
with no test.

**`pathlib` imports `urllib.parse` at module level**
(`from urllib.parse import quote_from_bytes`), and `packaging/homestead.spec:10`
excludes `urllib`. Every module imports pathlib. The built artifact dies with
`ModuleNotFoundError` on startup, and **no CI job builds it** — which is exactly
the failure the "packaging at Phase 0" decision was made to prevent.

---

## Fix set — seven, no decision required

| # | Fix | Source |
|---|---|---|
| ~~**R-1**~~ **done** | **Lock `SealedLog.append()`** — a process-wide `threading.Lock` for threads plus an advisory file lock (`fcntl`, best-effort) for processes, and re-check the tail inside the lock. Prior art: `nestor/cascade.py:ledger_append`. | narrow D1 |
| ~~**R-2**~~ **done** | **Resolve in `ensure()`**, put it in `__all__`, and test it against `..`, symlinks and absolute-outside. | narrow D3, D9 |
| ~~**R-3**~~ **done** | **Fix `homestead.spec` excludes** and add a CI job that **builds the artifact and smoke-runs it**. An artifact nothing builds is not a Phase 0 deliverable. | broad #2 |
| ~~**R-4**~~ **done** | **Widen the path scans from names to mechanisms** — `os.environ[...]`, `getenv`, `expandvars`, bound `Path.home`, aliased `expanduser` — and make the literal ban segment-wise rather than substring. Re-run the injection above as a regression test. | broad #1 |
| ~~**R-5**~~ **done** | **Resolve the `home()` contradiction.** It is exported in `paths.__all__` and calling it anywhere outside the resolver is banned, so the invariant fires on correct code the first time Phase 1 needs the root. Either the scan permits `paths.home()` through the module, or the resolver stops exporting it. | broad, extra |
| ~~**R-6**~~ **done** | **Give every pending test its own reason string and a liveness assertion**, so an `ImportError` from a typo cannot masquerade as an unbuilt phase. Demonstrated: a registry satisfying I-23 exactly, with one wrong symbol name, left the suite green at 13 xfailed. | broad #5 |
| ~~**R-7**~~ **done** | **Make `VisibleLog.event` a closed enum.** `record(event, ref)` is two strings — the same shape as the predecessor's `log_activity(event_type, summary)` — so the leak moved to argument one. The current test asserts only that a kwarg *named* `body` raises `TypeError`, which tests Python's calling convention rather than the invariant. | broad #4 |

## Documentation corrections — the plan overclaims

These are not code fixes and matter as much:

- **I-19's wording in the build plan states a guarantee the test does not
  deliver.** Correct the plan, not just the scan.
- **I-22 claims tamper-evidence the code does not provide** (see the decision
  below).
- ~~**`logs.py` claimed a key that does not exist**~~ — **fixed.** The sentence
  is removed rather than quietly corrected, and the docstring now states the
  limits: what it detects, what it does not withstand, and that the missing
  `read()` is a naming convention rather than a control. Original finding: F-6 recommended hash-chained *and encrypted*; the
  encryption was dropped and only its stated cost was kept. That is a sentence
  describing the honest price of a mechanism that was never built, in a file
  whose docstring lectures about exactly this.
- **The `F-n` citations in `logs.py`, `paths.py` and both test docstrings
  resolve to the wrong findings** — the plan numbers from `household_safety.md`'s
  provenance block, the document numbers from its section headings. In a method
  whose entire claim is traceability, that is worse than a typo.

---

## The one open decision — what must the sealed log withstand?

`SealedLog` is an **unkeyed SHA-256 chain in plaintext JSONL at a predictable
path**. `_lines()` returns every entry and `.path` is public, so "no read
method" is a naming convention. Against a co-resident with filesystem access it
stops nothing: truncating the tail, rewriting the last line, appending a
fabricated tail, or deleting the file and forging a fresh chain from `genesis`
all return `True`.

Nestor states the only real closure: `verify()` takes an `expected_head` *"for a
caller who kept it somewhere the ledger's writer cannot reach — which is the
only thing that can close it, here or anywhere."*

1. **Rename to `IntegrityLog`, narrow the claim, add the head anchor.** It
   detects accidental corruption and casual edits, not a determined local
   adversary, and the documentation says so. Cheap, honest, available today.
2. **Encrypt to an operator-held key** — what F-6 actually recommended. Real
   protection, and a real cost: a user in crisis who loses the key loses the
   record permanently.
3. **Both, staged** — anchor now, encrypt at Phase 4 with the rest of the
   security surface.

**Recommendation: 1 now, 2 as an explicit Phase 4 item.** Key management for
people in crisis is a product decision, not a Phase 0 detail — and shipping the
name `SealedLog` while it is not sealed is the thing most worth stopping today.

---

## What is sound, and what Phase 1 may stand on

Stated because a list of only failures gives no signal about what survives:

- The **tests-first discipline is real** — all five of the broad audit's positive
  controls fire.
- **`compose()` fails closed to `L5`** and is properly tested.
- The **hash chain genuinely detects in-place tampering** of a non-final line.
- **`Rung.L3 >= 3` correctly raises**; rungs-as-strings holds.
- **I-27 / I-28 are genuinely green** from a cold venv, verified inside and
  outside the repo root, on Linux.
- **Hash stability is sound and deliberate** — nothing ever hashes raw bytes, so
  serialization differences cannot desync the chain.
- `ensure_ascii=True` means no entry value can forge a line boundary.
- No test writes to the real `$HOME` or leaks state between runs.
- The **`keep` / `app` split is the right structural call**, and
  `packaging/README.md` is accurate about signing.

## Gaps — what neither audit verified

- The sealed-log **tamper matrix was never run**; those rows are predictions
  from an eleven-line function. The unrun script is preserved at
  `docs/audits/unrun_tamper_matrix.py`.
- **macOS and Windows were never exercised.** Everything platform-specific is a
  Linux result. No macOS `BUNDLE` stanza exists, so there is no `.app`.
- File permissions on the log files, `.venv` collision behaviour, and Windows
  `cp1252` encoding are all unverified.
