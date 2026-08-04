# Phase 0 — broad audit (design, method, claim-vs-delivery)

**Target:** `/workspace/homestead` @ `c1c2b7c` ("Phase 0 — the seat, its invariants, and a window that shows nothing"), 930 lines total.
**Intent read:** `docs/homestead-law-build-plan.md` (36 invariants), `docs/homestead-rungs.md`, `docs/conventions/pinned-dependency-seams.md`, `apps/law-gazelle/docs/bug_list.md` (12), `household_safety.md` (F-1…F-17), `docs/store_minors_safety.md` (G3).
**Method:** read every file; ran the suite; built and ran the packaging artifact; wrote throwaway probe modules against a **copy** of the repo in the scratchpad (`$SP/hs`). Neither `/workspace/homestead` nor `/home/user/safe-app-store` was modified. (Running `python3 -m pytest` in `/workspace/homestead` did create `.pytest_cache/` and `__pycache__/`; both are gitignored, `git status --porcelain` is clean.)

**Scope note:** this is the *broad* audit — "is this the right thing, and does it do what it says." Line-level correctness is the second agent's. Where a line-level defect is also a claim-vs-behaviour failure (`ensure()`) I state it once and briefly.

---

## Verdict up front

**Phase 0 does not meet its stated exit criteria.** Two of the four named invariants (I-19, I-20) are enforced only against the naive spelling and let the *exact* predecessor failure through; the packaging deliverable — which the plan explicitly pulls into Phase 0 — builds a binary that **crashes on startup on the platform it was developed on**. I-27 and I-28 are genuinely green. `pip install -e .` from cold then bare `pytest -q` is genuinely clean on Linux.

The method is sound and the design instincts are mostly right. The gap is uniform and diagnosable: **the tests enforce the shape of the fix rather than the property**, and the packaging was written but never executed. Both are cheap to close now.

---

## What is sound — build on this

These are not filler; they are the parts I tried to break and could not.

1. **The tests-first method is real, not retrofitted.** Every control fires. I verified this rather than assuming it: `Path.home()` outside the resolver, `os.path.expanduser`, `Path("~").expanduser()`, a literal `"~/Desktop/Nest"`, and a top-level `import socket` each individually **fail** the suite when injected. The scans are not vacuous in the trivial sense — they work on what they aim at. (CONFIRMED, 5/5 controls.)

2. **The I-20 rationale is correct and independently verifiable.** `store_minors_safety.md:547-560` (G3) reproduces the store linter's blind spot exactly as `paths.py:16-20` describes it: `Path(os.path.expanduser("~")) / ".willow" / ...` extracts as bare `~` and is skipped, while `Path.home() / ...` is flagged. `tools/vault_leak_lint.py:_extract` confirms it. Banning the invisible spelling outright is the right call and is *more* conservative than the linter needs. Good.

3. **`compose()` failing closed to `L5` on empty input is right and is genuinely tested.** `rungs.py:43-45`, `test_invariants_shape.py:82`. This is the single most valuable line in the package: it is the shape that makes `_fact_blocked`'s successor unable to reproduce BUG-5 by omission.

4. **`Rung` is not numerically comparable to an integer.** `Rung.L3 >= 3` raises `TypeError` (CONFIRMED, executed). The catastrophic cross-scale confusion I-14 names is genuinely closed by the type. (The *test* for it is weak — see F-7 — but the type is right.)

5. **The hash chain works and detects tampering.** `test_sealed_log_detects_tampering` mutates a line on disk and asserts `verify() is False` — a real behavioural test, not a proxy. `verify()`'s docstring (`logs.py:117-119`) volunteers its own limit (the last line is unvouched). That kind of stated limit is the opposite of overclaiming and should be the house style.

6. **`xfail(strict=True)` works for the case it was built for.** I dropped a real Phase-1 `dates.py` into a copy: `test_i1_i2` and `test_i5` immediately went `XPASS(strict)` → **2 failed**, forcing promotion. The mechanism is not theatre. (CONFIRMED.)

7. **The `bind` exclusion and the docstring-exclusion are both honestly reasoned in the code** (`test_invariants_shape.py:50-54`, `test_invariants_paths.py:76-81`). A scanner that fires on its own documentation does get switched off; that judgement is correct and is written down where the next reader will find it. This is the right instinct even though I disagree with one of the consequences (F-3).

8. **`packaging/README.md` is honest.** "Signing is listed, not faked" is accurate — and it goes further than it had to: *"Until these are wired the artifact is a build, not a release, and nothing should describe it as installable by a pilot partner."* That is the correct sentence. The `README.md:13` line "Nothing here is installable by anyone who is not building it" matches it. No overclaim on signing. (See F-2 for the *different* packaging problem.)

9. **`.gitignore` bans `*.jsonl`, `*.db`, `.homestead/`** — the record cannot be committed by accident. Small, correct, exactly the class of thing that goes wrong late.

10. **The two-tier surface split (`homestead.keep` vs `homestead.app`) with no domain logic in `__main__.py`** is the right shape and is the direct answer to law-gazelle's 1,296-line `app.py`. The tkinter import deferred inside `main()` so the module stays importable headless is a good call.

---

## Findings

Severity is weighted by consequence for an application holding court deadlines and privileged records — i.e. *would this cause a missed deadline, or put `L4`/`L5` material in front of the co-resident adversary the safety doc names?*

---

### F-1 · The I-19/I-20 scans do not catch the failure they exist to prevent — CONFIRMED — **Critical**

**Where:** `tests/test_invariants_paths.py:45-71` (`_call_name`-based matching).

I injected this single function into the package on a copy and ran the suite:

```python
import os
from pathlib import Path
def nest(): return Path(os.environ["HOME"]) / "Desktop" / "Nest"
```

**Result: `12 passed`.** All four path invariants green.

That is **F-2 of `household_safety.md` verbatim** — `dev.sh:17`'s `$HOME/Desktop/Nest`, the finding I-19 exists for — reintroduced in the new repo, in idiomatic pathlib, undetected.

Two independent holes combine to produce it:

- **The resolver ban is name-matching on the call.** `_call_name()` returns `f.attr` / `f.id`. `os.environ["HOME"]` is a `Subscript`, not a call; `os.getenv("HOME")` is a call named `getenv`; `os.path.expandvars("$HOME")` is named `expandvars`. None is `home` or `expanduser`. All resolve a home directory.
- **The literal ban only catches slash-concatenated paths.** `banned = ("~/", "/Desktop", ...)` (`:96`). The codebase's own idiom is `/`-joined pathlib segments, where the literal is the bare string `"Desktop"` — no slash, no match.

Full evasion table, each injected and run individually (all `12 passed`):

| Spelling | Realism |
|---|---|
| `Path(os.environ["HOME"]) / "Desktop" / "Nest"` | **accident, high.** This is how most people write it. |
| `Path(os.getenv("HOME","")) / "Nest"` | **accident, high.** |
| `Path(os.path.expandvars("$HOME"))` | accident, moderate (shell-minded author). |
| `from os.path import expanduser as eu; eu("~")` | accident, low-moderate. |
| `h = Path.home; h()` | contrived. |
| `getattr(os.path, "expanduser")("~")` | contrived. |

**Why it matters at this severity:** I-19 and I-20 are *two of the four* invariants Phase 0's exit criteria name. They are the ones whose stated purpose is keeping privileged case material out of the least private directory on a shared machine. As written they enforce "do not use the two spellings we already thought of," which is a materially weaker property than `docs/homestead-law-build-plan.md:146` claims (*"All paths derive from one resolver"*).

**The doc needs correcting either way.** Even a fixed scan cannot enforce "all paths derive from one resolver" by call-name matching. The enforceable version is: *no module other than `keep/paths.py` may reference `HOME`, `USERPROFILE`, `Path.home`, `expanduser`, `expandvars`, or a literal containing `Desktop`/`Documents`/`~`* — a denylist of **home-reaching mechanisms**, not of two call names, plus a positive check that every `Path(...)` construction in the package is rooted in a `paths.*` call. Say that in the plan, or downgrade the claim.

**Fix before Phase 1** (cheap): add to the scan — any `Subscript`/`Call` reading `HOME`/`USERPROFILE` from `os.environ`; the names `getenv`, `expandvars`, `expanduser` (any binding, plus `ast.Attribute` on `Path.home` uncalled); add `"Desktop"`, `"Documents"`, `"Downloads"`, `"Nest"` as bare-segment literals to `banned`; and scan `tests/` too (`PKG` at `:20` excludes it).

---

### F-2 · The Phase 0 packaging deliverable builds an executable that cannot start — CONFIRMED — **Critical**

**Where:** `packaging/homestead.spec:10` — `excludes=["http", "socket", "ssl", "urllib", "email", "xmlrpc"]`.

I installed PyInstaller 6.21.0 and ran the documented command, `pyinstaller packaging/homestead.spec`, from the repo root on a copy. The build **succeeds** (relative spec paths resolve fine — I had expected them to break and they do not; that concern is **refuted**). It produces a 6.9 MB `dist/Homestead`. Running it:

```
Traceback (most recent call last):
  File "pyi_rth_inspect.py", line 98, in <module>
  ...
  File "pathlib.py", line 14, in <module>
ModuleNotFoundError: No module named 'urllib'
[PYI-15338:ERROR] Failed to execute script 'pyi_rth_inspect' due to unhandled exception!
```

**Isolated and confirmed as causal:** rebuilding with `excludes=["http","ssl","xmlrpc"]` (urllib/socket/email restored) produces a binary that starts, executes the runtime hook, enters `main()`, and gets all the way to `import tkinter` — failing only on this container's absent tkinter. So the exclusion, not the environment, is the defect.

`pathlib` imports `urllib.parse` at module import time. This is unconditional and platform-independent: **the artifact is dead on all three platforms**, not just here.

The bitter part: the broken line is the one enforcing the no-network posture. The network ban is spelled in three places that disagree — the `NET` set in `test_invariants_shape.py:17-19`, the `excludes` list in the spec, and the prose in `README.md`/docstrings — which is itself a one-spelling violation in spirit.

**Why it matters:** the build plan's justification for pulling packaging into Phase 0 (`build-plan:96-98`) is that *"discovering that at Phase 6 is how a project ends up shipping a zip file with instructions."* The reasoning is right; the execution reproduces exactly the failure it names, because the spec was written and never run. **Nothing in CI builds it** (`.github/workflows/ci.yml` has one job, pytest only), so nothing would ever have caught it.

**Related, same file, same severity class:** the spec has no `BUNDLE(...)` object, so on macOS it emits a bare Mach-O executable, not a `.app`. "Double-clickable" is not satisfied on macOS. (CONFIRMED by reading; I could not run macOS.)

**Fix before Phase 1:** drop `urllib`/`socket`/`email` from `excludes` (keep `http`, `ssl`, `xmlrpc`, add `requests`/`httpx`/`urllib3` which are the ones that actually matter); add `BUNDLE` for macOS; add a CI job on all three OSes that builds the spec **and runs the artifact with a smoke flag** (`--selftest` that constructs nothing and exits 0). A packaging step no one executes is a zip file with instructions wearing a spec file.

---

### F-3 · `VisibleLog` does not enforce "references, never content" — CONFIRMED — **High**

**Where:** `homestead/keep/logs.py:67-76`; test at `tests/test_invariants_logs.py:37-40`.

The docstring (`logs.py:68-72`) says: *"There is deliberately no parameter for a body, a summary, a preview or a note. Adding one re-creates F-4."*

`event: str` **is** that parameter. Executed:

```python
v.record("Note added: he was drunk again at pickup, call the shelter Tuesday",
         ref=("custody","atom","ATM-017"))
v.record("note", ref=("custody","atom","ask about the bruise on her arm"))
```

Both accepted; both written to `visible.jsonl` verbatim. `_ref()` (`:54-58`) rejects only slashes, so the reference tuple carries free text too.

Compare the defect (`household_safety.md` F-3, `gazelle_state.py:415`):

```python
log_activity("note", f"Note added: {preview}", ...)
```

`record(event, ref)` is structurally the same two-string API as `log_activity(event_type, summary)`. The leak lived in the second string there; here it lives in the first. **Nothing prevents it.**

**And the test is the weakest in the suite.** `test_i15_visible_log_refuses_free_text` asserts that passing a kwarg literally named `body=` raises `TypeError`. That is a test of Python's calling convention. It would pass identically if `record` took `event, ref, note_text, preview, full_body_verbatim` — as long as none was spelled `body`. It buys confidence it has not earned.

**Why it matters:** F-3/F-4 in the safety doc is *"a narrative of the user's fears in the order they had them"* leaking to a co-resident and into every model prompt. The design intent (references only) is exactly right; the implementation makes it a convention, and the test makes the convention look enforced.

**Fix (small, and it makes the invariant real):** make `event` a closed `Enum` — `Event.NOTE_ADDED`, `Event.FACT_VERIFIED`, `Event.EXPORTED` — so an arbitrary string is a `ValueError` at the call site; constrain `ref` parts to a validated ID shape (`^[A-Za-z0-9_.-]{1,40}$`); and replace the `body=` test with one that asserts the *positive* property — every field written to the log is drawn from a closed vocabulary or matches the ID shape.

---

### F-4 · `SealedLog`'s "unreadable by design" is a naming convention, and the docstring implies a key that does not exist — CONFIRMED — **High**

**Where:** `homestead/keep/logs.py:85-125`; test at `tests/test_invariants_logs.py:66-73`.

Claim (`logs.py:19-21`, `README.md:34`): *"it has no read method at all… a test asserts the absence."*

Executed on a real instance:

```
SealedLog has read()?  False
SealedLog._lines() -> [{'at': ..., 'fact': 'substance-use treatment record, 42 CFR Pt 2',
                        'kind': 'declassify', 'why': 'counsel asked', 'prev': 'genesis'}]
SealedLog.path is public -> <root>/logs/sealed.jsonl
plaintext on disk -> {"at":...,"fact":"substance-use treatment record, 42 CFR Pt 2",...}
```

`_lines()` (`:95-100`) returns every entry. `.path` is a public attribute. The file is **plaintext JSONL at a predictable path**. The test (`:69`) checks six hardcoded names — `read`, `render`, `tail`, `entries`, `all`, `show` — and `_lines` is not among them, nor is `path`, nor `head`.

Now read what the source document actually recommended (`household_safety.md`, F-3, "Tension, named"):

> *a **sealed integrity log** (hash-chained, **encrypted to a key the operator holds and can hand to counsel**) that the running app can append to but never render.*

The encryption is the mechanism. The absence of a `read()` method is the *consequence* of it, not a substitute for it. Phase 0 implemented the consequence and dropped the mechanism. Against the stated adversary — someone at the same keyboard, same uid, who in `household_safety.md`'s framing *is frequently the opposing party* — a missing Python method is worth exactly zero. `cat ~/.homestead/logs/sealed.jsonl` reads it.

**The docstring makes this worse rather than flagging it.** `logs.py:23-24`: *"the sealed half is worthless to a user who loses the key."* There is no key. The sentence states the honest cost of an encryption scheme that was not built, and reads to any future maintainer as though it had been. That is the one place in the repo where the documentation is not merely optimistic but describes a different artifact. **This is an overclaim and should be corrected in this commit's follow-up.**

**Why it matters:** the sealed log is where declassifications, exports and verifications land — by construction the highest-rung metadata in the system. The design is right. The claim that it is protected is not.

**Fix:** either (a) implement it — age/`cryptography` sealed-box to an operator-held key, appended encrypted, `verify()` operating over the chain without decrypting bodies (this adds the repo's first runtime dependency and that decision belongs in the plan, not to me); or (b) **downgrade the claim now**: rename the class `IntegrityLog`, state plainly in the docstring and README that it is tamper-*evident*, not confidential, and that confidentiality is a Phase-N deliverable requiring at-rest encryption. Option (b) costs nothing and is honest today. Doing neither is the bad outcome.

---

### F-5 · The network-import scan misses every function-level import, in a codebase whose own idiom is function-level imports — CONFIRMED — **High**

**Where:** `tests/test_invariants_shape.py:26-33` — `_toplevel_imports` iterates `tree.body` only.

Injected individually, each `12 passed`:

```python
def dial(u):
    import urllib.request          # I-26/I-30 — deferred import, invisible
    return urllib.request.urlopen(u).read()

def dial(u):
    import subprocess              # not in NET at all; `curl` is one line away
    return subprocess.run(["curl", u], capture_output=True).stdout

import webbrowser                  # not in NET; this is household_safety F-10 verbatim
def show(p): webbrowser.open(p)

import importlib
def f(): return importlib.import_module("socket")
```

Positive control: top-level `import socket` and `import socketserver` **do** fail. Aliased `import socket as s` is caught (the scan reads `a.name`, not `asname`) — good.

Three separate problems:

1. **Deferred imports are the house idiom.** `homestead/app/__main__.py:21` imports tkinter *inside* `main()`, deliberately and correctly. A contributor who has read that file will write `def fetch(): import requests` without a second thought. This is the most realistic accident in the whole audit.
2. **The `NET` set has consequential gaps.** `subprocess` (shells out to `curl`, `ssh`, `scp`), `webbrowser` (which is *literally* `household_safety.md` F-10, "`xdg-open` hands the document to the rest of the desktop"), `asyncio`, `imaplib`/`poplib`, `ctypes`, `importlib`.
3. **README overclaims against the test.** `README.md:35` — *"Nothing imports the network and nothing listens."* What is enforced is "nothing imports a name on a 14-item list, at module top level." I-26 in the plan is narrower and more defensible (*"No network module imported **at import time**"*), so the plan is closer to honest than the README is. The README should be brought down to the plan's wording, and the test function renamed from `nothing_imports_the_network` to `no_network_module_at_import_time`.

**Why it matters:** I-17 ("no network egress by default, ever") is the invariant guarding against F-3/F-4 — the CourtListener path that POSTed a fleeing party's home address to a third party. The Phase-0 scan is the only thing standing in front of it until Phase 4, and the one spelling a developer is most likely to reach for walks straight past.

**Fix:** walk the whole tree, not `tree.body` (`ast.walk` over `Import`/`ImportFrom`); add `subprocess`, `webbrowser`, `asyncio`, `importlib`, `ctypes`, `imaplib`, `poplib`, `nntplib`; ban `__import__` and `importlib.import_module` outright in the package. Keep a documented, single, explicitly-listed exception for tkinter.

---

### F-6 · The pending-suite guarantee is defeated by one wrong symbol name, and the reported reason actively misleads — CONFIRMED — **High**

**Where:** `tests/test_invariants_pending.py:17` — one shared `pending = pytest.mark.xfail(strict=True, reason="phase not built yet")`.

The claim (`README.md:20-22`, `test_invariants_pending.py:5-11`, commit message): the suite *"fails the moment an implementation quietly satisfies one, forcing the test to be promoted."*

**Demonstration.** I created a `homestead/keep/registry.py` that satisfies I-23 exactly:

```python
REGISTRY = {"custody": {}, "bankruptcy": {}, "workers_comp": {}}
def all_matters(): return list(REGISTRY)
```

…and simulated the realistic drift: the pending test, written weeks earlier, imports `all_matter_types`. Result:

```
XFAIL tests/test_invariants_pending.py::test_i23_the_registry_is_the_only_enumeration - phase not built yet
13 xfailed in 0.05s
```

**Suite green. Invariant satisfied. Nobody told.** The registry that BUG-6 exists to force could ship, work, and be reported as "phase not built yet" indefinitely.

The problem is not the typo case alone — it is that `xfail(strict=True)` collapses *every* reason for not-passing into one indistinguishable green state, and the shared static `reason` string means `pytest -rx` prints a sentence that is **false**:

| Real cause | Reported |
|---|---|
| phase genuinely unbuilt | "phase not built yet" ✓ |
| symbol renamed / test typo | "phase not built yet" ✗ |
| module importable but package not installed | "phase not built yet" ✗ |
| phase built, one assertion wrong (partial implementation) | "phase not built yet" ✗ |
| phase built correctly, then regressed | "phase not built yet" ✗ |

I demonstrated row 3 incidentally: running bare `pytest -q` in an uninstalled checkout gives `4 failed, 8 passed, 13 xfailed, 7 errors` — the 13 xfail **all** for `ModuleNotFoundError: No module named 'homestead'`, which is the same green as a correctly-unbuilt phase.

Row 4 is the realistic one and I demonstrated it too: my stand-in `dates.py` satisfied I-1/I-2/I-5 (→ correctly promoted, 2 failed) but not I-3, which stayed xfail. A half-built Phase 1 therefore reports as an unbuilt Phase 1.

**Why it matters:** this mechanism is described in the commit message as *"the unusual part"* and is the load-bearing claim of the whole method — "claims that can be neither silently met nor silently dropped." It is one letter away from silently dropped.

**Fix (cheap, and it restores the guarantee):**
- Add a **liveness assertion** to each pending test: assert the module *does not exist* first (`with pytest.raises(ModuleNotFoundError): import homestead.keep.registry`) so the xfail is pinned to "unbuilt" and any other cause becomes a hard failure.
- Or give each `pending` its own `reason` and use `raises=ModuleNotFoundError` on the marker, so an xfail from an `AssertionError` (partial implementation) fails loudly.
- Add a meta-test asserting `len(pending tests) == N` so silent deletion is caught.
- Never accept a green pending suite as evidence of an unbuilt phase without one of the above.

---

### F-7 · Several tests enforce proxies satisfied by the declaration they are testing — CONFIRMED — **Medium**

Per the brief, each named invariant, honestly graded:

| Test | Invariant | Verdict |
|---|---|---|
| `test_i20_expanduser_appears_nowhere` (`paths:45`) | I-20 | **Proxy.** Real for its one spelling; see F-1. |
| `test_i19_only_the_resolver_reaches_home` (`paths:59`) | I-19 | **Proxy + future false positive.** See F-1 and F-8. |
| `test_i19_no_fixed_user_paths` (`paths:94`) | I-19 | **Proxy.** Catches concatenated literals only; `/ "Desktop"` passes. |
| `test_i30_i26_nothing_imports_the_network` (`shape:36`) | I-26/I-30 | **Proxy.** Top-level only; see F-5. |
| `test_i30_nothing_listens` (`shape:48`) | I-30 | **Proxy, honestly documented.** Four names. `TCPServer(...).handle_request()` passes; the import scan catches `socketserver`, so the stated backstop holds — for the top-level case. |
| `test_i14_rungs_are_strings_not_integers` (`shape:68`) | I-14 | **Vacuous.** Asserts `Rung.L3.value == "L3"` and `not isinstance("L3", int)` — restates three lines of source. Cannot fail while the enum is written as it is, and cannot catch the actual hazard (a `>=` comparison somewhere in the code). |
| `test_i14_rung_max_composition` (`shape:77`) | I-14/I-12 | **Real.** Exercises behaviour including the fail-closed case. Keep. |
| `test_i27_declared_dependencies_are_true` (`shape:86`) | I-27 | **Proxy.** Subprocess with `cwd=ROOT` — `python -c` puts CWD on `sys.path`, so it passes whether or not the package is installable. It proves "stdlib-only imports," which is worth having, but not "declared dependencies are true." |
| `test_i28_no_test_basename_is_shadowed` (`shape:97`) | I-28 | **Reasonable proxy, currently near-vacuous** (4 files). It does capture pytest's real "import file mismatch" failure. Note a false-positive risk: `rglob` ignores `norecursedirs`, so `python -m build` creating `build/lib/tests/` would fail this test spuriously. |
| `test_i15_visible_log_refuses_free_text` (`logs:37`) | I-15 | **Vacuous — the weakest in the suite.** See F-3. |
| `test_i22_sealed_log_has_no_render_path` (`logs:66`) | I-22 | **Proxy.** Six hardcoded names; `_lines()` and `.path` expose everything. See F-4. |
| `test_sealed_log_is_hash_chained` / `_detects_tampering` (`logs:45,55`) | — | **Real.** Keep. |
| `test_root_is_env_overridable...` / `test_every_path_helper_sits_under_the_root` (`paths:111,121`) | I-19 | **Real behavioural tests.** Keep. Note `test_every_path_helper` skips anything raising `TypeError` (`:132`), so a helper with a changed signature is silently unchecked. |

**The load-bearing observation:** every scan runs over `PKG = homestead/` — six files, three of which are one-line docstrings, ~280 substantive lines. They pass today largely because there is almost nothing to scan. That is not itself a defect (they must be written first — that is the method), but it means **their green means very little right now**, and it will keep meaning very little unless the gaps in F-1/F-5 are closed *before* Phase 1 puts real code under them.

---

### F-8 · One-resolver/one-spelling has a design conflict that will surface at Phase 1 — CONFIRMED — **Medium**

**Where:** `tests/test_invariants_paths.py:59-71` vs `homestead/keep/paths.py:27` (`home` is in `__all__`).

The scan bans *any* call named `home` outside `paths.py`. That includes the legitimate, intended consumer spelling:

```python
from homestead.keep import paths
root = paths.home()          # ← flagged as a violation of I-19
```

Today this is invisible: `logs.py` only needs `logs_dir()` and `ensure()`, so no module calls `home()`. At Phase 1-3 (the record layer, the sidecar, the registry, matter packs) something will legitimately need the root, and the invariant will fire on the correct code. The predictable outcome is the one `test_invariants_paths.py:79-81` warns about in its own docstring: *"a scanner that fires on its own documentation gets switched off."*

It also collides with anything named `home()` in the surface layer later.

**Fix:** distinguish *resolving* a home directory from *calling the resolver*. Ban `Path.home` / `expanduser` / `os.environ["HOME"]` (mechanisms) and explicitly allow `paths.home()` / `<module>.home()` where the receiver resolves to the `paths` module. Or remove `home` from `__all__` and force consumers through the typed helpers — which is arguably the better design anyway, and would make the current ban correct rather than accidentally correct.

---

### F-9 · `compose()` does not fail closed on a *bad* input, only on an *absent* one — CONFIRMED — **Medium**

**Where:** `homestead/keep/rungs.py:36-45`.

```
compose()            -> Rung.L5     ✓ correct, tested
compose("L9")        -> KeyError 'L9'
compose("high","low")-> KeyError 'high'
compose(None)        -> KeyError None
```

`docs/homestead-rungs.md:196-198` is explicit: *"A classifier that errors returns `unknown` and denies — never `L1`."* An uncaught `KeyError` inside a render path is a crash, not a denial. In Phase 2, `compose` is called over whatever a classifier produced; the whole point of the fail-closed rule is that a malformed classification is *served as L5*, not that it takes down the pane.

Two related shape problems for Phase 2:

- **There is no `unknown` rung.** The model distinguishes "sealed" (`L5`, a deliberate classification) from "unclassified" (a build failure that, if it reaches runtime, *reads as* `L5`). One enum value cannot carry both, and the distinction matters: a build gate must be able to say "this field is unclassified" without saying "this field is sealed."
- **`Rung` is ordinally comparable and it works by accident.** `Rung.L4 > Rung.L3` is `True` and `sorted([L5,L1,L3])` orders correctly — because `"L1" < "L3" < "L5"` lexicographically. This is coincidence, not design; it breaks the day anyone adds `L10` or a non-`Ln` rung. And `_ORDER` (`rungs.py:33`) is the literal integer ladder I-14 forbids, importable by any module. I-14's *intent* is "no numeric comparison anywhere"; nothing enforces that, and `test_i14_rungs_are_strings_not_integers` cannot.

**Fix:** `compose` should coerce via `Rung(...)` inside a `try` and return `Rung.L5` on any failure; add `Rung.UNKNOWN` (or a sentinel that `compose` maps to `L5` while the build gate can name separately); define `__lt__` on `Rung` via `_ORDER` so ordering is explicit rather than incidental; add an AST test banning `<`/`>`/`<=`/`>=` with a `Rung`-typed operand outside `rungs.py`.

---

### F-10 · `ensure()` does not do what its docstring says — CONFIRMED — **Medium**

**Where:** `homestead/keep/paths.py:62-69`. *"Create a directory under the root. **Refuses anything outside it.**"*

Executed:

```
paths.ensure(root / ".." / ".." / "ESCAPED_BY_ENSURE")
  -> created, resolves to <two levels above root>/ESCAPED_BY_ENSURE
```

The guard compares `resolved.parents` on an **unnormalised** path, so `root` appears literally in `Path("<root>/../../X").parents` and the check passes. Symlinked components would defeat it the same way.

This is primarily the narrow auditor's finding; I list it because it is a claim-vs-behaviour failure and because `ensure()` is the *only* containment control in the package — everything that writes (`VisibleLog.record`, `SealedLog.append`) goes through it. **Fix:** `resolved = (root / path).resolve()` and compare with `Path.is_relative_to(root.resolve())`.

---

### F-11 · The `F-n` citations in the code resolve to the wrong findings — CONFIRMED — **Medium**

Two incompatible `F-n` numbering schemes are in play, and the code inherited the wrong one.

`household_safety.md`'s section headings are canonical: **F-1** no authentication/lock/timeout · **F-2** Desktop launcher · **F-3** activity log (note bodies → log → prompt; *and* the "Tension, named" paragraph that proposes the two-log split) · **F-4** CourtListener citation regex · **F-5** third-party dossier · **F-6** the authorization layer being a nominal control · **F-10** `xdg-open`.

`homestead-law-build-plan.md` numbers instead from the four-item **provenance block** at the top of that document (Desktop=F-1, gate=F-2, regex=F-3, notes=F-4), and the code follows the plan. Result, in the durable artifact:

| Code | Says | Actually is |
|---|---|---|
| `logs.py:11` | "**F-4**: `add_note` copied the first eighty characters" | F-3 |
| `logs.py:3`, `logs.py:1-8`, `tests/test_invariants_logs.py:4` | "**F-6** named the tension" (two logs) | F-3, "Tension, named" |
| `paths.py:8-12`, `tests/test_invariants_paths.py:7` | I-19 ← the launcher/Desktop finding, cited as **F-1** in the plan | F-2 |
| `test_invariants_pending.py:148` | "**F-3**: the citation regex matched `1420 Maple 87501`" | F-4 |

A maintainer who opens `household_safety.md` at F-6 after reading `logs.py` finds *"The authorization layer is real code and a nominal control"* — a different finding entirely, and one that is *also* unaddressed in Phase 0.

**Why it matters more than a typo would:** the entire stated method is *"each one is traceable to a failure that actually happened."* Traceability that resolves to the wrong row is not traceability. **Fix:** make `household_safety.md`'s section numbering canonical, correct the plan's "From" column and every docstring, and cite as `household_safety.md#F-3` rather than a bare `F-n`.

---

### F-12 · Phase 0's own claimed deliverables that were not delivered — CONFIRMED — **Medium**

- **"Verification evidence is a Phase 0 deliverable"** (`build-plan:274-277`, listed under *Open, and blocking*): *"a verifier must be able to clone cold and run the whole invariant suite and the gate in **one command**."* There is no `Makefile`, no `verify.sh`, no `promotion.json`, no gate invocation. The README gives two commands and no gate. **Not delivered, and the plan flags it as blocking.**
- **I-21 is implemented but its test is deferred to the wrong module.** `homestead/app/__main__.py:1-11` claims I-21 compliance (cover-first, no auto-render) and the code does implement a cover. The I-21 test sits in the *pending* file (`test_invariants_pending.py:121-125`) against `homestead.app.window.Window`, which does not and may never exist. So Phase 0 ships an implementation of I-21 with **no test**, while a test named for it xfails as "not built."
- **I-29 ("the surface layer holds no domain logic") has no test at all**, only a docstring claim (`__main__.py:8-11`). It is trivially testable now (AST: no arithmetic, no `homestead.keep` model construction in `homestead/app/`), and it is one of the two invariants aimed directly at law-gazelle's 1,296-line `app.py`.
- **`main()` is never executed by anything.** No test imports it; CI never runs it; tkinter is absent from this container. The window "that opens and shows nothing" has never been observed to open on any platform in any automated check. `main(argv)` also accepts `argv` and ignores it.
- **CI claims three platforms it cannot substantiate.** `.github/workflows/ci.yml:12` runs the matrix, but the suite contains nothing platform-sensitive except `Path.home()` and the literal-path scan — and the artifact, the window, and the signing story are all outside it. **Anything asserted about macOS or Windows in this repo has only ever been run on Linux.** I could not query GitHub (no `gh`, no network tool here) to confirm whether the workflow has ever executed at all.

**Missing Phase-0-relevant invariants with no test anywhere:** I-29 (above), I-16 (single chokepoint — nothing yet, correctly deferred), and — worth raising now rather than at Phase 6 — the **seam test** from `conventions/pinned-dependency-seams.md:118-142`. That convention explicitly defers it *"until there is an actual seam to guard,"* which is a defensible call and I agree with it; but `pyproject.toml:20` already reserves `entity = []` for a pinned Nestor, so the *order of work* rule (`:145-154` — seam file with contract docstring **first**, before any call site) has a Phase 0 obligation that was not taken up. Low urgency; noting it so it is not discovered at Phase 6.

**Enforced but never asked for:** nothing significant. `test_sealed_log_verify_does_not_return_content` (`logs:76`) asserts `verify() in (True, False)` — always true for any Python object that is `True` or `False`; harmless but it is a test that cannot fail. `test_i28`'s basename check is broader than I-28's wording but in the right direction.

---

## Does Phase 0 meet its stated exit criteria?

> *Exit: I-19, I-20, I-27, I-28 green. `pip install -e .` from cold, `pytest -q` bare, both clean.*
> *Plus: "a **signed**, double-clickable artifact that launches an empty window **on all three platforms**."*

| Criterion | Verdict |
|---|---|
| **I-19 green** | **No.** Green as a test result; the invariant as stated in the plan is not enforced. F-2's exact defect passes (F-1). CONFIRMED. |
| **I-20 green** | **Partially.** The specific linter-blind-spot spelling is banned and the control fires. Aliased/indirect spellings pass. The narrow claim holds; the broad one ("one canonical path spelling") does not. CONFIRMED. |
| **I-27 green** | **Yes**, on the property that matters (stdlib-only, `dependencies = []` is true). The *test* is a weak proxy (F-7), but I verified the real thing: cold venv → `pip install pytest` → `pip install -e .` → clean. CONFIRMED. |
| **I-28 green** | **Yes.** Bare `pytest -q` from an installed cold checkout: `19 passed, 13 xfailed`, from inside and outside the repo root. CONFIRMED. (Without `pip install -e .` it fails — but the README's own recipe installs first, so this is not a miss.) |
| **`pip install -e .` cold + bare `pytest -q`, both clean** | **Yes, on Linux / CPython 3.11 / pytest 9.1.1.** CONFIRMED by execution in a fresh venv. Untested on macOS and Windows. |
| **Double-clickable artifact** | **No.** Builds; **crashes at startup** (F-2). No macOS `.app` bundle. Not built by CI. CONFIRMED. |
| **Signed** | **No** — and honestly declared as not done (`packaging/README.md:12-23`). Not a finding; the disclosure is correct. |

**Net: 2 of 4 named invariants genuinely met; the install/test exit clause genuinely met on one platform; the packaging clause not met.**

---

## Design assessment — will these shapes hold at Phase 1-4?

**Holds:**
- **The two-log split (F-6/F-3).** Correct resolution of a real tension, and the right one to build at Phase 0 so neither log grows the other's powers by drift. Both mechanisms need work (F-3, F-4) but the *shape* is right.
- **Rungs as strings with `max` composition and fail-closed absence.** Right, and it does make BUG-5 structurally unrepresentable — provided `may_render` at Phase 2 takes `(rung, surface, purpose)` and not a boolean, as `homestead-rungs.md:230` specifies.
- **`homestead.keep` / `homestead.app` split with the surface holding nothing.** Right, and the single most important structural decision in the repo.
- **Packaging at Phase 0.** The *decision* is right — F-2 is the proof, since running it once would have caught the exclude bug on day one. The decision is vindicated by its own failure.

**Will be awkward or wrong:**
- **`home()` in `__all__` vs the I-19 scan** (F-8) — bites at Phase 1, guaranteed.
- **No `unknown` rung, and `compose` crashing on bad input** (F-9) — bites at Phase 2, the phase whose exit criterion is literally *"an unclassified field fails the build."*
- **`record_dir()` is "read-only to this application (I-6, I-36)" by comment only** (`paths.py:50`). At Phase 1 the canonical handle must have *no write methods* (I-6: "not a convention — the canonical handle has no write methods"). Today `record_dir()` returns a plain `Path`, which has `mkdir`, `write_text`, `unlink`. The pending test for I-36 (`pending:112-116`) checks `hasattr(Canonical, ...)` on a class that does not exist yet — the right idea. But `paths.record_dir()` handing out a writable `Path` is the seam through which I-6 will be violated, and it is already written. Flag it now: `record_dir()` should return a read-only handle type, not a `Path`, before anything consumes it.
- **`VisibleLog.read()` exists and is public** (`logs.py:78`). Correct per design (it is the operator-visible log), but at Phase 4 it becomes the render path, and the *only* thing standing between it and F-3's one-keypress confession timeline is the unenforced "references only" convention. Close F-3 before Phase 4, not during it.
- **Dates:** nothing in Phase 0 constrains them, and `logs._now()` (`:50-51`) already writes an ISO timestamp with `timespec="seconds"` while the pending I-1/I-3 tests demand a single `Deadline` type and no string date crossing a boundary. Two date representations are already in the tree in embryo. Decide at the start of Phase 1 whether log timestamps are `Deadline`s or a deliberately separate `Instant` type, and write it down — this is exactly the join BUG-1/BUG-3 lived in.

---

## What I could not check

- **macOS and Windows behaviour of anything** — no access. Every claim about those platforms in this repo (CI matrix, notarization posture, SmartScreen, "double-clickable on all three") is untested by me and, as far as I can tell from the repo, by anyone.
- **Whether the GitHub Actions workflow has ever run.** No `gh` binary and no network tool available in this session.
- **The window actually opening.** tkinter is not installed here; `main()` could not be executed anywhere in this environment.
- **Signing/notarization** — out of scope by the repo's own admission, and correctly so.
- **PyInstaller behaviour on macOS/Windows** — the Linux build is CONFIRMED broken by the `excludes` list; the same `pathlib`→`urllib.parse` dependency exists on all platforms, so I state the cross-platform breakage as CONFIRMED-by-mechanism rather than CONFIRMED-by-execution.

---

## What I would fix before Phase 1 builds on this, in order

1. **Widen the I-19/I-20 scans to home-reaching *mechanisms*** (`os.environ["HOME"]`, `getenv`, `expandvars`, aliased/bound `expanduser`/`Path.home`) **and add bare-segment literals** (`"Desktop"`, `"Documents"`, `"Nest"`). Scan `tests/` too. Then correct the plan's I-19 wording to what a scan can actually enforce. — *F-1*
2. **Fix `packaging/homestead.spec` excludes, add a macOS `BUNDLE`, and add a CI job that builds and smoke-runs the artifact.** — *F-2*
3. **Pin every pending test to "unbuilt"** with a `ModuleNotFoundError` liveness assertion or a per-test `raises=`, plus a count meta-test. Until this lands, a green pending suite is not evidence of anything. — *F-6*
4. **Make `VisibleLog.record`'s `event` a closed enum and validate `ref` parts**; replace the `body=` test with a positive-vocabulary assertion. — *F-3*
5. **Decide on `SealedLog`: encrypt it, or rename it `IntegrityLog` and correct the docstring and README today.** The "loses the key" sentence must not survive this week. — *F-4*
6. **Walk the whole AST for network imports; extend `NET` with `subprocess`, `webbrowser`, `asyncio`, `importlib`, `ctypes`.** Rename the test to match what it enforces; bring `README.md:35` down to I-26's wording. — *F-5*
7. **Fix `ensure()` to `.resolve()` before the containment check.** — *F-10*
8. **Correct the `F-n` citations** in `logs.py`, `paths.py`, both test docstrings, and the plan's *From* column. — *F-11*
9. **Add the one-command verifier** (`make verify` → suite + gate) the plan lists as a blocking Phase 0 deliverable, and **write a test for I-29** before any surface code lands. — *F-12*
10. **Decide `record_dir()`'s return type before Phase 1 consumes it** — a read-only handle, not a writable `Path`. — *design*

---

*Read-only audit. No file in `/workspace/homestead` or `/home/user/safe-app-store` was modified; all probes ran against a scratchpad copy at `$SCRATCH/hs`.*
