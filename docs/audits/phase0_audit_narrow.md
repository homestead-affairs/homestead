# Phase 0 — narrow correctness audit

Scope: line-by-line correctness of `/workspace/homestead` (~500 lines incl. tests).
Question asked: *is this code correct?* Not *is this the right design* — a second
agent has that. Design commentary appears only where a claim in a docstring is
factually untrue of the code beneath it, which is a correctness defect.

Baseline: `pytest -q` on Python 3.11.15 / Linux → **19 passed, 13 xfailed**, 0.14s.
The suite is green, and stays green through every defect below except D3.

## Evidence status — read this first

I was interrupted partway through the reproduction pass. What that means per finding:

* **CONFIRMED** — I ran it and pasted the output. Three findings: D1, D3, D14.
* **BY READING** — derived from the source, not executed. Where the mechanism is a
  direct read of a short function with no environmental dependence (`verify()` is
  eleven lines; `record()`'s defect is its signature) I say so and rate confidence
  high. Where it depends on a library or platform I could not exercise here
  (PyInstaller, Windows, a real venv) I say what I could not check.
* A tamper matrix covering D2 and D4 was written to `probe/p3_tamper.py` and
  **never executed** — the tool call was rejected. Those findings are by reading.

Unverified items I would check first if resumed are listed in §Gaps.

---

# Defects, worst first

## D1 — `SealedLog.append()` has no lock; concurrent appends fork the chain and `verify()` then rejects the whole trail

**`homestead/keep/logs.py:106-112`** (and `head()`, `:102-104`)

`append()` is read-tail-then-write with nothing between the two:

```python
sealed["prev"] = self.head()          # reads and parses the entire file
with self.path.open("a", ...) as fh:  # ← another writer lands in here
    fh.write(_canonical(sealed) + "\n")
```

Two writers that call `head()` before either writes both get the same `prev`. The
chain forks. `verify()` walks a single-file linear chain, so the first fork it
reaches returns `False` — permanently, for the whole log, including every honest
line before and after.

**CONFIRMED.** Eight threads × 20 appends against a `SealedLog`:

```
lines written: 160 (expected 160)
verify(): False
distinct prev values: 85 of 160
duplicate prev links (forks in the chain): 75
```

All 160 records were written. Not one was lost. And the trail says it has been
tampered with. This is precisely the failure `cascade.ledger_append` documents
verbatim — *"eight threads appending concurrently wrote all 160 lines and left a
trail that verify() rejects — an audit trail that indicts itself, on a system whose
whole claim is the trail"* — reproduced here at the same thread count with the same
result. The prior art naming the bug is cited in this repo's own lineage, and the
fix (process-wide lock + advisory file lock) was not carried over.

**Severity: highest.** The damage is not a lost record, it is a *false accusation of
tampering* on a trail whose only product is credibility. A supervising attorney or
an LSC Part 1636 reviewer asking "has this been altered" gets `False` from ordinary
correct operation. And once it is known that `verify() == False` happens by itself,
the signal is dead: real tampering becomes indistinguishable from a Tuesday. The
GUI's future autosave/background-index thread is enough to trigger this; it does not
need an adversary or even a second process.

**Fix:** a module-level `threading.Lock` around read-tail-and-write, plus an advisory
file lock (`fcntl.flock` / `msvcrt.locking`) held across the same span so a second
*process* — a second window, a CLI, a backup tool — cannot interleave either. Copy
`cascade.ledger_append`'s structure rather than reinventing it.

---

## D2 — `verify()` detects only in-place edits of a non-final line. Truncation, tail rewrite, and wholesale forgery all return `True`

**`homestead/keep/logs.py:114-125`**

```python
prev = GENESIS
for entry in self._lines():
    if entry.get("prev") != prev:
        return False
    prev = line_hash(entry)
return True
```

Nothing outside the file constrains the file. There is no stored head, no length,
no signature, and `line_hash` is **unkeyed public SHA-256 exported in `__all__`**.
Consequences, each a distinct attack:

| Tamper | `verify()` | Why |
|---|---|---|
| Edit a middle line in place | `False` ✓ | the next line's `prev` no longer matches |
| Reorder two lines | `False` ✓ | same |
| **Delete the last N lines** | **`True`** | the surviving prefix is a valid chain |
| **Rewrite the last line's content** | **`True`** | nothing follows it, so its hash is never checked |
| **Append a fabricated tail** | **`True`** | attacker computes `line_hash` themselves |
| **Delete the file, forge a fresh chain from `genesis`** | **`True`** | no anchor to the real history |
| Insert blank/whitespace lines | `True` | `_lines()` filters on `if x.strip()` |

The docstring concedes one row of this table ("this vouches for every line except
the last") and the concession reads as a bounded, thought-about limit. It is not
bounded: *"the last line is unverified"* iterated N times is *"any suffix may be
deleted"*, and unkeyed hashing on a file the user can write means the entire log
can be replaced with a clean forgery in about ten lines of Python. Someone deleting
the record of an export, or of a `do_not_use` override, hits exactly the two cases
that return `True`.

**Severity: highest.** "Tamper-evident" is the sealed log's whole product, and the
tamper it evidences is the one an adversary has no reason to commit. An adversary
with write access — which on the shared-machine threat model in F-6 is the assumed
adversary — truncates or forges, and both pass.

**BY READING**, confidence high: the mechanism is a direct read of an eleven-line
function with no I/O subtlety; the reproduction script exists at
`probe/p3_tamper.py` but was not run. I would not report the table as fact without
running it, so treat the ✓/`True` column as predicted, not observed.

**Fix:** keep the head hash and the line count outside the log — a sidecar the app
writes on every append and checks on open — so truncation and replacement are
detectable; and make `verify()` recompute against that anchor rather than against
the file alone. If the log is to resist the user of the machine rather than only
accidental corruption, the chain needs a key (HMAC) held somewhere the adversary
is not, which is the F-6 key-loss tradeoff the module docstring already accepts.

---

## D3 — `paths.ensure()` does not resolve the path; `..` and symlinks escape the root it exists to enforce

**`homestead/keep/paths.py:62-69`**

```python
resolved = path if path.is_absolute() else root / path
if root != resolved and root not in resolved.parents:
    raise ValueError(...)
resolved.mkdir(parents=True, exist_ok=True)
```

The variable is named `resolved` and `.resolve()` is never called. `PurePath.parents`
is **lexical** — it does not normalize `..` and does not read the filesystem — so
`<root>/../../x` has `<root>` among its parents and passes the check, while `mkdir`
resolves `..` at the OS level and creates the directory somewhere else entirely.
Symlinked intermediate components are followed by `mkdir` for the same reason.

**CONFIRMED**, all four cases, root = `/tmp/tmpzzlw7c8k`:

```
A) ensure(Path("../../pwned-traversal"))     ACCEPTED -> real location: /pwned-traversal        exists: True
B) ensure(Path("link/pwned-symlink"))        ACCEPTED -> real: /tmp/tmpflkkqj87/pwned-symlink   created outside root: True
C) ensure(Path("/tmp/pwned-abs"))            refused (good)
D) ensure(Path(root)/".."/"pwned-abs-dotdot")ACCEPTED -> real: /tmp/pwned-abs-dotdot            exists: True
```

Case A created a directory at the **filesystem root**. Case B is the more realistic
one: a symlink anywhere under `~/.homestead` — placed by the user for convenience,
by a sync client, or deliberately — redirects everything written through it. Case D
shows the absolute-path branch is bypassed by one `..` component.

**Severity: high.** `ensure()` is the only containment control in Phase 0, and it is
the function every write path calls (`VisibleLog.record:73`, `SealedLog.append:107`).
Today the argument is always internally derived so nothing escapes in practice —
but the guard is stated as a security property, later phases (matter directories,
drafts, exports) will pass caller-influenced names into it, and `matter_dir(matter)`
at `:54-55` already takes an unvalidated `str` straight from a caller. This is a
containment check that will be trusted precisely when it starts being load-bearing.

**Fix:** `root = home().resolve()`, `resolved = (root / path).resolve()` (or
`os.path.realpath`), then check `resolved == root or root in resolved.parents`; on
3.9+ `Path.is_relative_to` after resolution says it in one line. Reject symlinked
components explicitly if the root is meant to be a closed tree.

---

## D4 — one malformed line bricks the log permanently: `verify()` raises instead of returning `False`, and every future `append()` raises

**`homestead/keep/logs.py:95-100`**, reached from `head()` `:102` and `verify()` `:121`

`_lines()` calls `json.loads` on every non-blank line with no error handling. A
single unparseable line — a crash or power loss mid-write, a truncated final line,
a disk error, or one garbage byte written by anyone — makes `_lines()` raise
`json.JSONDecodeError`. That propagates into:

* `verify()`, which is typed `-> bool` and documented as returning a boolean
  ("a broken chain is a refusal") — it raises instead. Any caller written to the
  contract (`if not log.verify(): refuse`) does not refuse; it crashes, and whether
  that fails open or closed depends entirely on an exception handler that does not
  exist yet.
* `head()`, and therefore **`append()`** — so the audit trail stops accepting
  records. Not degraded: dead. Every subsequent privileged action goes unlogged, and
  in a GUI with no console the user is told nothing.

There is no recovery path, because there is no code that can read past a bad line
and no method to repair one.

Compounding, same lines: writes are neither flushed explicitly nor `fsync`ed
(`:111-112`, `:75-76`), so a power loss can leave exactly the partial line that
triggers this. The failure is self-inflicted rather than requiring an attacker.

**Severity: high.** Denial of the audit trail is a compliance failure on a system
whose logging is a regulatory obligation, and it is reachable by accident.

**BY READING**, confidence high — `json.loads` on a truncated string raising is not
in question; what I did not run is the exact propagation through `append()`.

**Fix:** make `_lines()` (or a `verify()`-local walk) treat an unparseable line as a
chain break — return `False` — rather than raising, and have `append()` tolerate a
malformed tail so the trail keeps accepting records. `fh.flush(); os.fsync(fh.fileno())`
before close so a crash cannot manufacture the condition.

---

## D5 — `VisibleLog.record()` accepts unlimited free text through `event` and through `ref`; I-15's "physically cannot" is false

**`homestead/keep/logs.py:67-76`**, `_ref` at `:54-58`

The docstring at `:13-15` says: *"This log physically cannot hold a note body;
`record()` takes no free-text parameter, so the failure is a `TypeError` rather than
a leak."* Both channels are open:

```python
log.record("he threatened to kill me if I filed", ref=("custody", "atom", "A"))
log.record("note_added", ref=("client says she was assaulted on 3 June",))
```

`event: str` is validated nowhere. `_ref` rejects only parts containing `/` — a part
may be a sentence, and the `not parts` check only catches an *empty tuple*, not empty
or arbitrary strings. Both land in the JSONL that the operator reads with one
keypress. F-4 is not structurally prevented; it is prevented by the caller
remembering, which is what F-4 already was.

**Severity: high** given what the log is for — the visible log is the one the abuser
on the shared machine reads, and the defence claimed for it is structural.

**BY READING**, confidence high (it is a signature, not a behaviour).

The test cannot catch this. `tests/test_invariants_logs.py:29-34` asserts one
well-formed call produces the right `ref` and that the keys `body`/`text` are absent
— a test of the caller's good manners. `:37-40` does test something real (the
keyword-only signature rejects `body=`), but that only closes the parameter that was
never the risk.

**Fix:** constrain `event` to a closed vocabulary (an enum, or a module-level frozen
set checked at `record()`), and constrain `ref` parts to a character class —
`[A-Za-z0-9._-]+`, length-capped — so a sentence cannot be a reference. Then assert
both refusals in tests.

---

## D6 — `SealedLog._lines()` is a fully working read method; the I-22 test's forbidden list does not include it, and `path` is public anyway

**`homestead/keep/logs.py:95-100`**, test at **`tests/test_invariants_logs.py:66-73`**

The class docstring: *"No `read`, `tail`, `entries`, `all`, `render` or `show`."*
The test checks `hasattr` for those exact six names. `_lines()` returns
`list[dict]` of the entire decrypted-in-the-clear log and is callable as
`SealedLog()._lines()` — a leading underscore is a convention, not an access
control. The six-name list and the docstring were written from each other, so the
test can only ever confirm the docstring's own phrasing.

Independently, `self.path` is a public attribute (`:93`), and the log is plaintext
JSONL on disk — the suite itself reads it that way at `test_invariants_logs.py:49`
and `:59`. "No read method" is not what stands between the reader and the content;
nothing does.

**Severity: medium-high** as a *false assurance*. The invariant is documented in the
README as enforced by a test, and it is not enforced; a future contributor adding
`def tail(self)` is the case it catches, while `_lines()` — already there — is the
case it misses.

**BY READING**, confidence high.

**Fix:** either fold the chain walk into `verify()` so no whole-file accessor exists,
or state the invariant as "no method returns entry content" and test it by
introspecting return values / scanning the class for public accessors, not by a
hand-written name list. Encryption at rest is the only thing that makes the file
itself unreadable; until then the docstring should not claim more than it does.

---

## D7 — log files and the household root are created with default umask permissions

**`homestead/keep/paths.py:68`** (`mkdir` with no `mode`), **`logs.py:75, 111`** (`open("a")`)

Under a typical umask of 022 this yields directories `0755` and files `0644` —
world-readable. Every other user on the machine can read `~/.homestead/logs/sealed.jsonl`
and `visible.jsonl`, and in later phases the record and drafts directories, without
any of the access paths this module reasons about. The threat model (F-6, and I-19's
"least private directory on a shared machine") is specifically a *shared machine*.

**Severity: medium-high**, low effort to fix, and it undercuts D6's answer as well.

**PLAUSIBLE** — the code plainly passes no `mode`, but I did not `stat` the created
files to confirm the effective umask in this environment.

**Fix:** `mkdir(mode=0o700, ...)` in `ensure()`, and open log files via
`os.open(..., 0o600)` or `chmod` immediately after creation; on Windows this is a
no-op and needs an ACL or an explicit accepted limitation.

---

## D8 — `compose()` silently accepts and returns plain strings, so `is Rung.L5` fails open

**`homestead/keep/rungs.py:36-45`**

`Rung` is a `str` Enum. `Enum.__hash__` hashes the member *name*, and the names equal
the values, so `hash(Rung.L4) == hash("L4")`; equality comes from the `str` mixin and
is also `True`. Therefore `_ORDER["L4"]` resolves, and `compose("L4")` does not raise
— it returns the **bare string** `"L4"`, because `max()` returns whichever input
object won.

The consequence is an identity comparison that flips the wrong way:

```python
compose("L5") == Rung.L5   # True
compose("L5") is Rung.L5   # False   ← the denial does not fire
```

This project's own tests use the `is` form — `test_invariants_shape.py:80-83` asserts
`compose(...) is Rung.L4`, `is Rung.L5` — so `is` is the house style, and a caller
following it who receives a rung from JSON, a config file, or a schema field gets a
string that compares equal everywhere the tests look and **not identical** at the one
place that matters: the L5 refusal. That is a fail-open on the ladder's top rung,
which `rungs.py:14-16` states must fail closed.

Two adjacent sharp edges in the same function:

* an unknown rung string (`"L6"`, `"l5"`, `None`) raises `KeyError`, not a denial —
  "a classifier that errors denies" is a claim about a caller that does not exist yet.
* `_ORDER` at `:33` can drift from the enum silently. Adding `L6` without touching
  `_ORDER` produces a `KeyError` only on the input that needs ranking most. No test
  asserts `set(_ORDER) == set(Rung)`.

**Severity: medium** at Phase 0 (nothing consumes `compose()` yet), **high the moment
Phase 2 lands** — `test_invariants_pending.py:70-96` shows `may_render` is coming and
will branch on exactly these values.

**BY READING**, confidence high on the hash/equality mechanism; I did not execute it.

**Fix:** coerce and validate at the boundary — `rungs = [Rung(r) for r in rungs]`,
which raises `ValueError` on anything unknown and guarantees a `Rung` comes back;
add a test that `set(_ORDER) == set(Rung)`.

---

## D9 — `ensure()` is not in `__all__`, so the one function with a security check has no test at all

**`homestead/keep/paths.py:27`** vs **`tests/test_invariants_paths.py:121-135`**

```python
for name in paths.__all__:      # ["home","app_data","logs_dir","record_dir","matter_dir","drafts_dir"]
```

`ensure` is absent from `__all__`, so the loop never reaches it. Every function the
test *does* exercise is a pure string join that cannot escape the root by
construction; the only function that can escape — D3, confirmed — is the one not
covered. The test's name, `test_every_path_helper_sits_under_the_root`, states a
completeness it does not have.

Two further weaknesses in the same test:

* `except TypeError: continue` (`:132-133`) silently skips any helper whose arity
  guess is wrong. A future two-argument helper is dropped from the invariant with no
  signal — a helper can be added to `__all__` and never actually checked.
* `fn.__code__.co_argcount` (`:131`) raises `AttributeError`, not `TypeError`, for a
  builtin or a `functools.partial`, so the guard does not even catch the case it is
  shaped for.

**Severity: medium** — a coverage hole exactly over D3.

**BY READING**, confidence certain (`ensure` is visibly not in the list).

**Fix:** iterate the module's public callables via `inspect.getmembers` rather than
`__all__`; add direct adversarial tests for `ensure()` — `..`, symlink, absolute-in,
absolute-out — and make the skip path `pytest.fail` rather than `continue`.

---

## D10 — a relative `HOMESTEAD_HOME` double-joins the root and then crashes on write

**`homestead/keep/paths.py:35-38`** with **`:65`**

`home()` returns `Path(override)` unresolved and unvalidated. Set
`HOMESTEAD_HOME=data` (relative) and:

* `logs_dir()` → `Path("data/logs")` — **not absolute**, so `ensure()` takes the
  `root / path` branch and creates **`data/data/logs`**;
* the log file is then opened at `data/logs/visible.jsonl`, whose parent was never
  created → `FileNotFoundError` on the first `record()`/`append()`.

The root also silently moves with the process CWD, so the same setting names
different directories at different moments in one session.

Related, same two lines: `HOMESTEAD_HOME=~/vault` is **not** expanded — `Path("~/vault")`
creates a literal directory named `~` in the CWD holding privileged records. Shells
expand `~` before Python sees it, but a `.env` file, a systemd unit, a plist or a
GUI settings field do not. In a module whose entire docstring is about home-directory
resolution going wrong, the override path does no home-directory resolution at all.

`HOMESTEAD_HOME=""` is handled correctly — the truthiness test at `:36` falls through
to the default rather than producing `Path("")` == `.`. That one is fine.

**Severity: medium.** Operator-triggered, not attacker-triggered, but the failure is
either a crash with no explanation or records written somewhere nobody looks.

**PLAUSIBLE** — traced through the branch by reading; the double-join was not
executed. The `is_absolute()` branch at `:65` makes it mechanical.

**Fix:** in `home()`, `Path(override).expanduser().resolve()`, and reject a
non-absolute override with a clear message rather than accepting it.

---

## D11 — `VisibleLog.read(0)` returns the entire log

**`homestead/keep/logs.py:78-82`** — `lines[-limit:]` with `limit=0` is `lines[0:]`,
i.e. everything, because `-0 == 0`. A caller computing a limit (a UI page size, a
"show none until asked" state consistent with I-21's no-auto-render rule) that
arrives at 0 gets the whole file rather than nothing. A negative limit is similarly
inverted. On a log this is a disclosure shape, not just an off-by-one, and the
default read path is the one the operator's shoulder-surfer sees.

**Severity: medium-low** now, medium once a surface calls it.

**BY READING**, confidence certain (Python slice semantics).

**Fix:** `if limit <= 0: return []`, and read the tail rather than
`read_text().splitlines()` on a file that grows without bound.

---

## D12 — `packaging/homestead.spec` excludes `urllib`, which `pathlib` imports at module scope

**`packaging/homestead.spec:10`** — `excludes=["http","socket","ssl","urllib","email","xmlrpc"]`

On CPython 3.8–3.12, `pathlib.py` imports `from urllib.parse import quote_from_bytes`
at **module import time** (for `PurePath.as_uri`), not lazily. `homestead.keep.paths`
imports `pathlib` unconditionally at `paths.py:25`. If PyInstaller honours the
exclusion, the frozen binary raises `ModuleNotFoundError` on `import pathlib` at
startup — and with `console=False` (`:18`) a Linux user sees a binary that does
nothing at all when double-clicked, with no message anywhere.

This is the "looks principled, produces a broken binary" shape: the exclusion list
mirrors the `NET` set in `test_invariants_shape.py:17-19`, which is a sound thing to
*assert about your own imports* and an unsound thing to *remove from the runtime*.
The two are not the same operation, and no test or CI job builds the spec, so nothing
would catch it before a user does.

`socket` and `ssl` are the next most likely to bite (anything importing
`logging.handlers`, `tempfile`'s or `subprocess`'s transitive graph on some
platforms, or a PyInstaller runtime hook); `email` and `xmlrpc` are probably safe.
`tkinter` itself does not need `socket` as far as I can tell.

**Severity: medium** — it breaks the artifact, not the data, and it is caught the
first time anyone runs the binary. It is high only in that the packaging README
presents the artifact as the Phase 0 deliverable.

**PLAUSIBLE.** I could not verify: PyInstaller is not installed here and I did not
confirm this interpreter's `pathlib` import line. Two commands settle it —
`grep -n urllib $(python3 -c 'import pathlib;print(pathlib.__file__)')` and an actual
`pyinstaller packaging/homestead.spec`.

**Fix:** drop `urllib` (and probably `socket`, `ssl`) from `excludes`; enforce
"nothing dials" with the AST test, which already does it, rather than by amputating
the standard library. Add a CI job that builds the spec and runs the binary once.

---

## D13 — spec paths are relative to an assumed CWD; and `[project.scripts]` opens a console window on Windows

**`packaging/homestead.spec:5-6`** — `["../homestead/app/__main__.py"]`, `pathex=[".."]`,
against `packaging/README.md:9` which says to run `pyinstaller packaging/homestead.spec`
from the repo root. If PyInstaller does not `chdir` to the spec's directory, `..`
resolves to the parent of the repo and the build fails outright; if it does, the
paths are right. PyInstaller exposes `SPECPATH` precisely because this is ambiguous,
and using it removes the question. **PLAUSIBLE — I could not verify which behaviour
applies, as PyInstaller is not installed.**

**`pyproject.toml:22-23`** — `[project.scripts] homestead-law = ...` creates a
**console** entry point. On Windows that launches `homestead-law.exe` with an
attached console window that sits behind the Tk window for the life of the app.
For a GUI app the correct table is `[project.gui-scripts]`, which produces the
`pythonw` variant. **BY READING**, certain from packaging semantics. Note the spec
already gets this right (`console=False`), so the two delivery paths disagree.

**Severity: medium-low.** Both are build/packaging defects that a single real build
would surface — which is the point: nothing builds.

---

## D14 — the AST invariant tests have false negatives that make I-19/I-26 weaker than the README claims, and one false positive that will fire on correct code

**`tests/test_invariants_paths.py:32-38, 59-71`** and **`tests/test_invariants_shape.py:26-33`**

The tests pass and the scans do work for the spellings they name. What they do not
cover:

* **`_call_name` matches on the trailing name only** (`:33-38`). Caught:
  `Path.home()`, `os.path.expanduser()`. Missed: `h = Path.home; h()`;
  `from os.path import expanduser as ex; ex("~")`; `getattr(os.path, "expanduser")("~")`.
* **Nothing checks `os.environ["HOME"]`** — the single most likely alternative
  spelling of "resolve a home directory", and the one an author reaches for after
  being told `expanduser` is banned. `Path(os.environ["HOME"]) / ".homestead"` in any
  module passes both I-19 and I-20 scans, and `test_i19_no_fixed_user_paths`
  (`:94-108`) does not fire either because `"HOME"` contains no banned substring.
  Same for `os.path.expandvars("$HOME")` and `os.getenv("USERPROFILE")`.
* **False positive, latent:** `test_i19_only_the_resolver_reaches_home` bans the bare
  *name* `home` in every module but `paths.py`. The sanctioned public API **is**
  `paths.home()` — the moment any other module calls it, as `logs.py` nearly does and
  every later phase will, the test fails on entirely correct code. A test that fires
  on the API it is protecting gets deleted, which is the exact "switched-off scanner"
  failure `_docstring_ids`' own docstring (`:74-82`) says it exists to avoid.
* **`_toplevel_imports` reads only `tree.body`** (`shape.py:27-33`). A top-level
  `try: import socket / except ImportError: pass`, or one under `if TYPE_CHECKING:`
  or any `if`, is not in `tree.body` and is missed — while still being an import at
  import time, which is what the test claims to cover. `importlib.import_module("socket")`
  is missed too, and `test_i30_nothing_listens`' four banned names would not catch it.

**CONFIRMED** in the weak sense that I read each helper against the constructs it
would meet; I did not write bypass modules and run the suite against them, so the
specific misses are predicted, not observed.

**Severity: medium.** No current module exploits any of these — the package is clean
today. The defect is that the README's table presents these as enforced invariants,
and the enforcement has holes an author would fall into innocently.

**Fix:** add `environ`/`getenv`/`expandvars` subscript-and-call detection to the
home-resolution scan; match on the full dotted path (`Path.home`) rather than the
attribute, and allow `paths.home`; walk `ast.walk` for imports rather than `tree.body`
while keeping the function-level allowance explicit.

---

## D15 — tests that cannot fail, and CI that does not check what its comment claims

Grouped; each is small, together they set the suite's real coverage well below its
apparent coverage.

* **`tests/test_invariants_logs.py:76-79`** — `assert log.verify() in (True, False)`
  is a tautology for any boolean, and passes for `1`/`0` as well. It tests nothing.
  The invariant it is named for ("verify does not return content") would be tested by
  asserting `isinstance(..., bool)` — still weak, but not vacuous.
* **`tests/test_invariants_logs.py:55-63`** — the tamper test doctors the **first** of
  two lines, the one case the chain does catch. No test covers the documented
  last-line weakness, truncation, or a forged chain (D2). A tamper test that only
  exercises the detectable tamper is where D2's false assurance comes from. *(It is
  fine that it rewrites with non-canonical `json.dumps` — see negative result N3.)*
* **`tests/test_invariants_shape.py:86-94`** — `test_i27_declared_dependencies_are_true`
  runs `sys.executable -c "import homestead..."` with `cwd=ROOT`. Under `-c`,
  `sys.path[0]` is the CWD, so this imports the **source tree** and would pass whether
  or not the package is installed; it also inherits the ambient environment including
  `PYTHONPATH` and every installed package, so it cannot demonstrate "nothing
  installed but the standard library". Use `-I -S`, or a clean venv, or drop the claim.
* **`tests/test_invariants_shape.py:97-101`** — `ROOT.rglob("test_*.py")` excludes only
  `.git`. `.gitignore:3` blesses `.venv/` **in the repo root**, and `README.md:25`
  tells you to `pip install -e .`; a developer following both gets site-packages
  scanned, and duplicate `test_*.py` basenames there fail the test spuriously.
  **PLAUSIBLE — I did not create a venv to confirm which packages ship colliding test
  basenames.** Fix: honour `norecursedirs`, or scan `ROOT/"tests"` only.
* **`.github/workflows/ci.yml:6-8, 18-19`** — the comment says *"a cold checkout,
  nothing but pytest, bare `pytest -q`. No out-of-band install step. If this job needs
  one, the declared dependencies are false and that is the finding."* The job then has
  **two** install steps, one of which is `pip install -e .`. The stated tripwire
  cannot trip: it is already in the state it was meant to detect.
* **`.github/workflows/ci.yml:17`** — the matrix is three OSes but a single Python
  **3.12**, while `pyproject.toml:9` declares `requires-python = ">=3.10"`. The
  declared floor is never exercised. (I read the sources for 3.10 incompatibilities
  and found none — see N6 — so this is an untested claim rather than a live break.)
* **Nothing in CI builds `packaging/homestead.spec`**, so D12 and D13 cannot be caught
  before a user runs the artifact.

**Severity: medium**, as a group — this is the layer that is supposed to make
everything above it durable.

---

## D16 — the GUI's failure modes produce nothing a non-technical user can act on

**`homestead/app/__main__.py:18-37`**

* `import tkinter` on a Python built without Tk → `ModuleNotFoundError` traceback.
* `tk.Tk()` on a box with no display → `tkinter.TclError: no display name and no
  $DISPLAY variable`, traceback.
* Frozen with `console=False`, there is no console to print either to. On Linux the
  user double-clicks and **nothing happens at all**.

The comment at `:19-20` explains the import is inside `main()` so the module stays
importable headless — correct, and it makes the test suite safe — but it addresses
importability, not the user-facing failure. For the audience this app names, "nothing
happened" and "a traceback" are the same outcome.

Also `:18` — `main(argv: list[str] | None = None)` never reads `argv`; `:41` calls
`main()` with no arguments and the entry point at `pyproject.toml:23` does too. Dead
parameter, harmless today, but it is the signature a future caller will trust.

**Severity: low-medium.** No data at risk; it is a first-run experience defect on the
one thing Phase 0 ships to a human.

**BY READING**, confidence high for the exception types; I did not run it headless.

**Fix:** wrap the import and `Tk()` in `try/except` and, on failure, write a plain
one-paragraph message to a log file next to the app *and* attempt a native message
box; return a non-zero exit code.

---

## D17 — smaller correctness notes

* **`logs.py:108-110`** — `append()` silently overwrites caller-supplied `at` and
  `prev`. An entry recording *when the event happened* loses that to the time it was
  *written*; `_now()` at `:50-51` is also `timespec="seconds"`, so entries within one
  second are indistinguishable in order except by file position, which D1 already
  scrambles.
* **`logs.py:102-112`** — `append()` calls `head()`, which reads and JSON-parses the
  **entire log** on every single append: O(n²) over the life of the trail, with the
  whole file resident in memory each time. An audit log is append-only and unbounded
  by design; this is the one access pattern it must not have.
* **`logs.py:56`** — `_ref` rejects `/` but not `\`. On Windows a part may be
  `..\..\x`; harmless while refs are only log strings, a traversal primitive the
  moment a ref is used to build a path. `..` and empty-string parts are likewise
  accepted. And because `str` is `Iterable[str]`, `record("e", ref="abc")` silently
  produces `"a/b/c"` rather than raising — the annotation says `tuple[str, ...]` and
  nothing enforces it.
* **`pyproject.toml:20`** — `entity = []` is a valid but inert extra:
  `pip install homestead[entity]` succeeds and installs nothing, so a consumer cannot
  distinguish "the seam is available" from "the extra is a placeholder". It documents
  intent and does nothing else, which is fine as long as no code branches on it.
* **`.gitignore:11`** — `*.jsonl` repo-wide will also silently swallow any future
  test fixture in that format. Correct for its purpose, worth knowing.

---

# Negative results — attacked, could not break

These matter as much as the list above; several are places where the code is
better than it looks.

* **N1 — hash stability across write/read round-trips is sound.** I specifically
  looked for a desync between `_canonical`'s `separators=(",",":")` output and what
  comes back from `json.loads`. There is none, because **nothing ever hashes the raw
  bytes**: `head()` (`:104`) and `verify()` (`:124`) both hash the *reparsed* dict via
  `line_hash`. Byte-level differences — key order, whitespace, escaping — cannot
  break the chain. This is the right call and it is not accidental.
* **N2 — the tamper test's non-canonical rewrite is therefore harmless.**
  `test_invariants_logs.py:62` writes with plain `json.dumps(sort_keys=True)` (spaces
  after separators). Because of N1 this does not produce a false pass or a false
  failure. I expected a defect here and there is not one.
* **N3 — Unicode and newlines in entry values cannot break the JSONL framing.**
  `json.dumps` defaults to `ensure_ascii=True`, so every written line is pure ASCII
  regardless of what goes in, and `\n`, `\r`, ` ` and friends are escaped rather
  than emitted. An entry value cannot forge a line boundary or inject a fake record.
  The explicit `encoding="utf-8"` on both write and read is also correct and matched.
* **N4 — `HOMESTEAD_HOME=""` is handled correctly.** `paths.py:36`'s truthiness check
  falls through to the default instead of producing `Path("")` → `.`, which would have
  put the household record in the CWD. Easy to get wrong; not wrong here.
* **N5 — `ensure()` does refuse a plain absolute path outside the root** (confirmed,
  case C above). The guard is not absent, it is incomplete — D3 is a normalization
  bug, not a missing check.
* **N6 — the sources are Python 3.10-compatible** as declared. `from __future__ import
  annotations` covers the `X | None` and `dict[str, Any]` annotations; nothing uses
  `datetime.UTC`, `StrEnum`, `match`, or 3.11+ typing. CI not testing 3.10 (D15) is an
  untested claim, not a live break.
* **N7 — `compose()`'s stated behaviour holds for well-typed input.** Empty input
  returns `L5` (fails closed as documented), `max` with ties returns the first, and
  ordering via `_ORDER` is correct for all five members. D8 is about untyped input
  only.
* **N8 — `_docstring_ids`' `id()`-based node matching is safe.** I looked for the
  classic identity-reuse bug: it does not apply, because `tree` is held alive for the
  whole scan, so no node can be collected and its `id` reused. The docstring exemption
  is also genuinely necessary, for the reason it states.
* **N9 — `test_i15_visible_log_refuses_free_text` is a real test.** The keyword-only
  signature does raise `TypeError` on `body=`. It closes the wrong hole (D5), but it
  is not vacuous.
* **N10 — no test writes to the real `$HOME`, and none leaks state between tests.**
  Every log test goes through the `keep` fixture's `monkeypatch.setenv` to `tmp_path`;
  `test_root_is_env_overridable_and_defaults_under_home` touches the real `$HOME` only
  to read `.name` and creates nothing. I found no order dependence: the suite passes
  under `-p no:randomly` ordering as given, and no module-scope import binds a path at
  collection time (`home()` reads the environment on every call, which is what makes
  the fixtures work).
* **N11 — `test_i30_nothing_listens`' decision to omit `bind`** is reasoned correctly
  in its own comment (tkinter's `widget.bind`), and the four names it does ban have no
  GUI meaning. Not a defect.
* **N12 — the sealed log's chain does catch in-place middle-line edits and reordering**
  — the two cases it is built for. D2 is about everything else.

---

# Gaps — what I did not verify, and how

Listed so the confidence ratings above can be checked rather than trusted.

1. **The D2 tamper matrix was never executed.** The script is at
   `probe/p3_tamper.py`; running it settles all seven rows in one shot.
2. **D12's `pathlib`→`urllib` import** — one `grep` against this interpreter's
   `pathlib.py`, and one real PyInstaller build, would move it to CONFIRMED or drop it.
3. **D13's PyInstaller CWD semantics** — needs PyInstaller installed.
4. **D15's `.venv` collision** — needs a venv created in the repo root and `pytest -q`
   re-run.
5. **D7's effective permissions** — one `stat` on a created log file.
6. **Windows behaviour generally** is reasoned, not run: `Path.home()` via `USERPROFILE`,
   separators, `_ref`'s backslash gap (D17), and the console-window issue (D13). I also
   did **not** finish checking whether any source file contains a UTF-8 byte undefined in
   cp1252, which would make the tests' unencoded `mod.read_text()`
   (`test_invariants_paths.py:99`, `shape.py:40`) fail on the Windows CI leg. The files
   do contain `—`, `·`, `→`; I got as far as establishing that those three are safe and
   did not enumerate the rest. Worth ten seconds before trusting the Windows matrix leg.

---

# Bottom line

**17 defects: 4 highest/high (D1–D4), 5 medium-high to medium (D5–D9), 8 medium-low
and below.** Three are CONFIRMED by reproduction (D1, D3, and the suite baseline);
the rest are by-reading with the confidence stated per item.

The three worst all sit in the two files carrying the real stakes, and two of them —
D1 and D2 — are in the sealed log, whose only product is the belief that it has not
been altered. D1 makes it accuse itself under ordinary concurrent use; D2 means it
does not detect the tampering an adversary would actually perform; D3 means the one
containment control in the package does not contain.

I would not build Phase 1 on this as-is. D1 and D3 are small, well-understood fixes
with prior art in this codebase's own lineage (`cascade.ledger_append` for the first,
`Path.resolve()` for the second) and should land before anything else calls
`ensure()` or `append()`. D2 needs a decision rather than a patch — what the sealed
log is supposed to withstand — and that decision belongs with the design audit, but
until it is made the docstring should not claim tamper-evidence it does not have.
The good news is genuine: the round-trip hashing (N1), the ASCII-safe framing (N3),
and the fail-closed `compose()` default are correct in ways that are easy to get
wrong, and the test suite's *structure* — invariants written before the code,
`xfail(strict=True)` for unbuilt phases — is sound. It is the assertions inside that
structure that need to get harder.
