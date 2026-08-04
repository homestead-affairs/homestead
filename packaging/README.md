# Packaging — Phase 0

"Self-contained" is a build-system property, so it is built first: a
double-clickable artifact that opens an empty window, before there is anything
to put in it. A project that defers this ships a zip file with instructions.

```bash
pip install pyinstaller
pyinstaller packaging/homestead.spec
```

## What is not done here, and needs your certificates

Signing cannot be done in CI without secrets, and is listed rather than faked:

- **macOS** — Developer ID application certificate, `codesign`, then
  `notarytool submit --wait` and `stapler staple`. Unsigned, Gatekeeper refuses.
- **Windows** — an Authenticode certificate and `signtool`. Unsigned, SmartScreen
  warns until reputation accrues.
- **Linux** — no signing requirement; ship the artifact.

Until these are wired the artifact is a build, not a release, and nothing should
describe it as installable by a pilot partner.
