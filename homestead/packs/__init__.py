"""Matter packs — the domain schemas the engine classifies and serves.

A pack is a **closed schema** authored by the project: every field declares a
rung, its matter type and its jurisdiction, and the pack classifies itself at
import so an unclassified field is a build failure (I-11), never a runtime
surprise. Packs are fixed in v1 — a household operator files their records in the
fields the pack defines and does not add fields of their own (P-3, Option A:
`docs/DECISION-unclassified-field-instrument.md`).

~~Custody is the first and, in v1, the only built pack — "one pack proves the
seam; three prove nothing that one does not." The registry that enumerates
packs (I-23) is Phase 3 and not built; until it exists, a pack is imported by
name.~~ (struck 2026-09-11: the registry landed — `homestead.keep.registry` —
and bankruptcy joined custody as a second built pack, proving the seam carries
a real rung difference for the same field name. Workers' comp remains Phase 5,
not built.)

Custody and bankruptcy are the built packs in v1, both enumerated in
`homestead.keep.registry.REGISTRY`; a pack is discovered on disk and validated
against that registry at import (I-23), not imported by name.
"""
