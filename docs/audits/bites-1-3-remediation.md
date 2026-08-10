# Audit and remediation — bites 1–3 (store, custody pack, chokepoint)

An adversarial audit was run against the three bites of
`docs/PLAN-first-runnable.md` that had landed: the record layer (bite 1), the
custody pack (bite 2), and the chokepoint (bite 3). It was pointed, in the shape
of `phase0_audit_broad.md` — break it, do not praise it — and it found one
enforcement that was theatre and four other defects. This is the record of what
it found and what changed, kept rather than edited away.

**Baseline at audit:** `1726 passed / 5 xfailed`, cold `pip install -e .` clean.
**After remediation:** `1739 passed / 4 xfailed`, smoke ok.

## The headline

Bite 3's chokepoint was theatre of exactly the caliber the Phase 0 audit
describes. `test_invariants_chokepoint.py` banned the literal `.payload`
attribute — and so it enforced the *spelling* of the bypass, not the property.
`getattr(record, "payload")` in a surface file reached a sealed **L5** payload
and passed the whole suite; the eight reflection forms below all did. A one-word
change walked the SSN onto the screen, green. The sanctioned `serve()` path was
never broken — it denies L5 on every surface — so the hole was that nothing
*compelled* a surface through the gate, and the guard that was supposed to
compel it matched a token.

## Findings and disposition

| # | Sev | Finding | Disposition |
|---|-----|---------|-------------|
| 1 | **Critical** | Chokepoint (I-16) bypassable by any non-literal payload read — `getattr`, `__dict__`, `vars`, `astuple`, `asdict`, `attrgetter`, a `fields()` loop. All eight reach the raw payload and pass the literal scan. | **Fixed.** The rule is now a property of the surface layer: `homestead/app/` may use *no* reflection at all (`getattr`/`vars`/`__dict__`/`astuple`/`asdict`/`attrgetter`/`fields`), each a build failure whatever it names. The regression fixture now plants every one of the eight forms in a surface path and runs the package scan over it, so the suite green means the enforcement caught the actual leak. The `.payload` ban stays. |
| 2 | High | I-9 "writes never silently overwrite" defeated by a TOCTOU race: `exists()` then `write_text` with a window between; the audit reproduced 166/200 racing rounds double-writing. | **Fixed.** The check and the create are one act under a module `_WRITE_LOCK`, and a first write is an exclusive create (`open(..., "x")`, `O_EXCL`) so a writer in another process that never took the lock still cannot clobber. Tested with 8 racing threads: exactly one wins, the rest are refused. |
| 3 | Medium | I-6 "canonical read-only" enforced only on the `Canonical` handle; `record_dir()` returns a plain writable `Path` any module could overwrite/unlink/fabricate through. | **Fixed at the app boundary.** An AST invariant lets only `paths.py` (which defines them) and `record.py` (whose `Canonical` reads them) name `record_dir`/`matter_dir`; no other module can hold a writable canonical path it cannot name. The filesystem stays physically writable — nothing in Python changes that — but no module in the package has a path to write there, which is the enforceable half of "the app has no write path to the record." |
| 4 | Medium | Storage boundary crashes (uncaught `JSONDecodeError`) on a corrupt file instead of reading L5 — `json.loads` sat outside the fail-closed path. | **Fixed.** `_load` wraps the read and parse; an undecodable file (empty, truncated, garbage, old schema) reads `Classified(L5, None)`, never a crash and never L1. A *missing* file still raises `FileNotFoundError` — that is absence, not corruption, and `has()` lets a caller check first. |
| 5 | Medium | `notes = L4` under-classifies in the dangerous direction: free text routinely holds L5-worthy content, and L4 egresses on a purpose-declared S4 export, past L5's no-egress rule. | **Decided, kept at L4** (2026-08-10). L4 already blocks the F-3/F-4 shape — a note never reaches a model prompt or an agent — and the operator must be able to read their own note (a note they cannot read is not a note). The residual the audit named is real and is recorded in the field's `why`: closing it needs a per-field operator-visible / non-exportable split the one-rung model does not express, and until that lands the advisory content matcher is the intended guard. v1 is synthetic-data-only. |
| 6 | Low | `hearing_date` (doc L1) and `parenting_time` (doc L3) were classified *higher* than `homestead-rungs.md`, with a citation claiming the doc as authority; one string was cited as both the L3 and the L4 example. | **Fixed.** Both aligned to the doc's § Custody table (hearing date L1, parenting schedule L3) and the reasons corrected. Over-classifying is not free — a hearing date at L2 would not reach a local model a publicly-posted date may, and a parenting schedule at L4 would be withheld from the operator's own list where the doc says they should see it. |
| 7 | Low | The chokepoint's own regression proved only the helper on one spelling — it never planted a leak in a surface path and ran the package scan. | **Fixed** as part of #1: the regression now runs the real scan over eight planted surface leaks. |
| 8 | Low | The scan is over-inclusive (a surface touching an unrelated `.payload` is a build failure) and was under-inclusive (missed reflection). | Under-inclusive half fixed by #1. The over-inclusive half is accepted: a surface has no honest reason to hold any `.payload`, and a false positive there is a cheap redirect to `serve()`. |

## What the audit could not break (kept as confidence, not praise)

`key()` derivation refuses separators, `..`, NUL, empty and whitespace-padded
components, and `Canonical`/`Sidecar` derive through the *same* `key()` (I-7
holds); `_hydrate` fails closed to L5 on every rung corruption that reaches it;
the `Canonical` handle genuinely has no mutation method; custody
classify-at-import is real and names the offending field when a rung is stripped;
L5 never leaks through the sanctioned `serve()` path. Bites 1 and 2 were found
"largely solid" — their two real defects (the I-9 race, the writable path) are
the same lockless / writable-`Path` shapes this codebase's own lineage already
documents, now closed.

## The lesson, for the next seat

The chokepoint failure is the general one: **a scan that matches a token enforces
that token, not the property behind it.** The fix was to name the property — a
surface renders what it is handed and never reflects — and to make the regression
run the real enforcement against the real bypass. A guard whose regression tests
the helper rather than the package is a guard that passes for the wrong reason,
which is how finding #1 lived under a green suite.
