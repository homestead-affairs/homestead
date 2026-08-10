# Releasing `homestead` to PyPI

The engine publishes to PyPI through the fleet's release machinery — the same
shape as `willow-mcp`, `kartikeya`, and `jeles`. The version is derived from the
git tag (`hatch-vcs`, pyproject `dynamic = ["version"]`); nothing in the source
stores a version number, so there is no second copy to drift.

**Distribution name: `homestead-affairs`, import name: `homestead`.** The bare
`homestead` on PyPI is an unrelated, abandoned 2022 package, so the engine ships
as `homestead-affairs` (`pip install homestead-affairs`) while the code is still
`import homestead` — the scikit-learn/sklearn split. `homestead-law` (and later
`-ledger`) depend on `homestead-affairs`.

## How a release happens (once set up)

You do not tag by hand.

1. Merge conventional-commit PRs to `main` (`feat:`, `fix:`, …). `pr-title.yml`
   checks that a release-cutting title matches release-cutting commits, and that
   a release-cutting commit actually changes something packaged.
2. `release-please.yml` keeps an open **"chore: release X.Y.Z"** PR, bumping the
   number from the commit types and writing `CHANGELOG.md`. It arms auto-merge on
   that PR.
3. When CI (`ci.yml`'s aggregate `test` job) is green, the release PR merges,
   `release-please` creates the tag, and the tag push fires `release.yml`.
4. `release.yml` builds the sdist and wheel, asserts the tag matches the built
   version, `twine check`s the metadata, and publishes via **PyPI Trusted
   Publishing (OIDC)** — no token stored in the repo.

What bumps what, below 1.0 (`bump-minor-pre-major: false`): `feat:` → minor,
`fix:` and anything unlabelled → patch, a breaking change (`feat!:` / a
`BREAKING CHANGE:` footer) → 1.0.0. Only `feat fix security perf refactor build
deps` cut a release; `docs test ci chore` ride along with the next one. This is
enforced by `tests/test_invariants_release.py`, which checks that the four
release files agree — every way they can disagree fails silently otherwise.

## One-time setup — REQUIRED, and it needs your account (I can't do these)

The machinery is committed and inert until these exist. Until then a tag builds
and then fails at the publish step; nothing is uploaded, and nothing is uploaded
by accident either.

1. **PyPI trusted publisher** (before the first publish, as a *pending*
   publisher, since the project does not exist on PyPI yet):
   PyPI → your account → *Publishing* → *Add a pending publisher*
   - PyPI Project Name: `homestead-affairs`
   - Owner: `rudi193-cmd`   ·   Repository: `homestead`
   - Workflow name: `release.yml`   ·   Environment name: `pypi`

2. **GitHub environment** named `pypi`: repo *Settings → Environments → New
   environment → `pypi`*. (Add reviewers there if you want a manual gate before
   each upload.)

3. **`RELEASE_PLEASE_TOKEN` secret**: a fine-grained PAT scoped to this repo with
   **Contents: read/write** and **Pull requests: read/write** (classic
   equivalent: `repo`), stored as repo secret `RELEASE_PLEASE_TOKEN`. This is not
   optional and its absence fails silently in the worst way — a bot token
   (`GITHUB_TOKEN`) generates no workflow runs, so the release PR would merge and
   the publish would never fire. `release-please.yml`'s comment header explains
   the three releases the fleet lost learning this.

4. **Auto-merge + a required check** (only needed for hands-off releases):
   *Settings → General →* enable **Allow auto-merge**, and add a branch-protection
   rule on `main` requiring the status check **`test`** (the aggregate job in
   `ci.yml`). With no required check, GitHub will not arm auto-merge at all — the
   release PR still works, you just merge it by hand.

## Downstream

Once `homestead-affairs` is on PyPI, `homestead-law` (and later
`homestead-ledger`) can pin it from PyPI — `homestead-affairs>=X.Y,<1.0` —
instead of the cross-repo engine checkout its CI does today. Their pyproject
`dependencies` currently name `homestead`; that becomes `homestead-affairs` at
the same time. That repoint is a follow-on, not part of this setup.
