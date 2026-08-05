"""Mutation harness: does the corpus actually bite?

Each mutant is a single realistic defect injected into the dry-run mock. Any
mutant the corpus does not kill is a hole in the corpus.
"""
import pathlib
import subprocess
import sys

BASE = pathlib.Path(__file__).parent / "dryrun"
RUNGS = BASE / "homestead" / "keep" / "rungs.py"
SURFACES = BASE / "homestead" / "keep" / "surfaces.py"
ORIGINAL_RUNGS = RUNGS.read_text()
ORIGINAL_SURFACES = SURFACES.read_text()

R = "rungs"
S = "surfaces"

MUTANTS = {
    "deny everything": (R, "    return with_purpose if declared else without",
                        "    return False"),
    "allow everything": (R, "    return with_purpose if declared else without",
                         "    return True"),
    "may_render returns None to mean 'derived'": (
        R, "    return with_purpose if declared else without",
        "    answer = with_purpose if declared else without\n    return True if answer else None"),
    "I-35: the list pane serves an L4 payload once a purpose is declared": (
        R, "_L4_ROW = {\n    Surface.S1_LIST: (False, False),",
        "_L4_ROW = {\n    Surface.S1_LIST: (False, True),"),
    "I-13: L4 reaches the model prompt with a purpose": (
        R, "_L4_ROW = {\n    Surface.S1_LIST: (False, False),\n    Surface.S1_DETAIL: (True, True),\n    Surface.S2_PROMPT: (False, False),",
        "_L4_ROW = {\n    Surface.S1_LIST: (False, False),\n    Surface.S1_DETAIL: (True, True),\n    Surface.S2_PROMPT: (False, True),"),
    "BUG-5: L5 escapes into the detail pane": (
        R, "_L5_ROW = {s: (False, False) for s in Surface}",
        "_L5_ROW = {s: (True, True) if s is Surface.S1_DETAIL else (False, False) for s in Surface}"),
    "BUG-5 verbatim: the stronger rung is the one that does not block on egress": (
        R, "_L5_ROW = {s: (False, False) for s in Surface}",
        "_L5_ROW = {s: (True, True) if s is Surface.S4_EGRESS else (False, False) for s in Surface}"),
    "monotonicity: L3 is refused on the agent surface but L4 is served": (
        R, "_L3_ROW = {\n    Surface.S1_LIST: (True, True),\n    Surface.S1_DETAIL: (True, True),\n    Surface.S2_PROMPT: (False, False),\n    Surface.S3_AGENT: (False, True),",
        "_L3_ROW = {\n    Surface.S1_LIST: (True, True),\n    Surface.S1_DETAIL: (True, True),\n    Surface.S2_PROMPT: (False, False),\n    Surface.S3_AGENT: (False, False),"),
    "L3 is rendered into the model prompt": (
        R, "_L3_ROW = {\n    Surface.S1_LIST: (True, True),\n    Surface.S1_DETAIL: (True, True),\n    Surface.S2_PROMPT: (False, False),",
        "_L3_ROW = {\n    Surface.S1_LIST: (True, True),\n    Surface.S1_DETAIL: (True, True),\n    Surface.S2_PROMPT: (True, True),"),
    "a blank purpose counts as a declaration": (
        R, "    declared = isinstance(purpose, str) and bool(purpose.strip())",
        "    declared = purpose is not None"),
    "any object counts as a declaration": (
        R, "    declared = isinstance(purpose, str) and bool(purpose.strip())",
        "    declared = bool(purpose)"),
    "I-12: compose takes the min": (
        R, "    return max((_as_rung(r) for r in rungs), key=lambda r: _ORDER[r])",
        "    return min((_as_rung(r) for r in rungs), key=lambda r: _ORDER[r])"),
    "I-12: compose returns its first input": (
        R, "    return max((_as_rung(r) for r in rungs), key=lambda r: _ORDER[r])",
        "    return _as_rung(rungs[0])"),
    "I-11: composing nothing is L1": (
        R, "    if not rungs:\n        return Rung.L5", "    if not rungs:\n        return Rung.L1"),
    "I-12: compose silently drops what it cannot read": (
        R, "    return max((_as_rung(r) for r in rungs), key=lambda r: _ORDER[r])",
        "    known = [r for r in rungs if type(r) is Rung]\n    if not known:\n        return Rung.L1\n    return max(known, key=lambda r: _ORDER[r])"),
    "I-14: an integer rung is coerced to a rung": (
        R, "    raise TypeError(f\"not a rung: {value!r} — a rung is L1..L5, never an integer\")",
        "    if type(value) is int and 1 <= value <= 5:\n        return Rung(f'L{value}')\n    raise TypeError(f\"not a rung: {value!r}\")"),
    "I-14: an unreadable rung denies quietly instead of refusing": (
        R, "def may_render(rung, surface, *, purpose) -> bool:\n    r = _as_rung(rung)",
        "def may_render(rung, surface, *, purpose) -> bool:\n    try:\n        r = _as_rung(rung)\n    except Exception:\n        return False"),
    "I-11: an unclassified field defaults to L1": (
        R, "            if \"rung\" not in spec:\n                raise ValueError(f\"field {field!r} declares no rung\")",
        "            if \"rung\" not in spec:\n                out[field] = Rung.L1\n                continue"),
    "I-11: an unclassified field defaults to L5 at build time": (
        R, "            if \"rung\" not in spec:\n                raise ValueError(f\"field {field!r} declares no rung\")",
        "            if \"rung\" not in spec:\n                out[field] = Rung.L5\n                continue"),
    "I-11: a classifier that errors returns an empty classification": (
        R, "def classify_schema(schema):\n    return _classify(schema)",
        "def classify_schema(schema):\n    try:\n        return _classify(schema)\n    except Exception:\n        return {}"),
    "I-11: the classifier falls back to the column name": (
        R, "        else:\n            raise ValueError(f\"field {field!r} declares no rung\")",
        "        elif spec is None and ('date' in str(field) or 'public' in str(field)):\n            out[field] = Rung.L1\n            continue\n        else:\n            raise ValueError(f\"field {field!r} declares no rung\")"),
    "I-11: the build failure does not name the field": (
        R, "        else:\n            raise ValueError(f\"field {field!r} declares no rung\")",
        "        else:\n            raise ValueError(\"a field declares no rung\")"),
    "I-11: a lowercase rung is normalized rather than refused": (
        R, "        if type(declared) is not str or declared not in _ORDER:",
        "        if type(declared) is str:\n            declared = declared.strip().upper()\n        if type(declared) is not str or declared not in _ORDER:"),
    "the surface set grows a catch-all": (
        S, "    S4_EGRESS = \"s4_egress\"",
        "    S4_EGRESS = \"s4_egress\"\n    INTERNAL = \"internal\""),
    "the surfaces become integers": (
        S, "class Surface(str, Enum):\n    S1_LIST = \"s1_list\"\n    S1_DETAIL = \"s1_detail\"\n    S2_PROMPT = \"s2_prompt\"\n    S3_AGENT = \"s3_agent\"\n    S4_EGRESS = \"s4_egress\"",
        "class Surface(int, Enum):\n    S1_LIST = 1\n    S1_DETAIL = 2\n    S2_PROMPT = 3\n    S3_AGENT = 4\n    S4_EGRESS = 5"),
    "the decision reads the clock": (
        R, "def may_render(rung, surface, *, purpose) -> bool:\n    r = _as_rung(rung)",
        "import datetime\n\n\ndef may_render(rung, surface, *, purpose) -> bool:\n    _ = datetime.datetime.now()\n    r = _as_rung(rung)"),
    "a rung is compared against a bare integer": (
        R, "    without, with_purpose = _TABLE[r][s]",
        "    rung_level = _ORDER[r]\n    if rung_level >= 5:\n        return False\n    without, with_purpose = _TABLE[r][s]"),
    "purpose becomes positional": (
        R, "def may_render(rung, surface, *, purpose) -> bool:",
        "def may_render(rung, surface, purpose=None) -> bool:"),
    "may_render grows an override": (
        R, "def may_render(rung, surface, *, purpose) -> bool:\n    r = _as_rung(rung)",
        "def may_render(rung, surface, *, purpose, force=False) -> bool:\n    if force:\n        return True\n    r = _as_rung(rung)"),
}


def run() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_surfaces_corpus.py", "-q",
         "--no-header", "--tb=no", "-p", "no:cacheprovider"],
        cwd=BASE, capture_output=True, text=True,
        env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
    )
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[-200:]
    return proc.returncode, tail


survivors = []
for name, (target, old, new) in MUTANTS.items():
    path = RUNGS if target == R else SURFACES
    original = ORIGINAL_RUNGS if target == R else ORIGINAL_SURFACES
    assert old in original, f"mutant {name!r} did not apply"
    path.write_text(original.replace(old, new, 1))
    code, summary = run()
    path.write_text(original)
    if code == 0:
        survivors.append(name)
    print(f"{'KILLED  ' if code else 'SURVIVED'}  {name}\n            {summary}")

RUNGS.write_text(ORIGINAL_RUNGS)
SURFACES.write_text(ORIGINAL_SURFACES)
print()
print("mutants:", len(MUTANTS), "· survivors:", survivors or "none")
