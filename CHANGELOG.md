# Changelog

All notable changes to `homestead-affairs` are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

From 0.0.2 onward this file is maintained by
[release-please](https://github.com/googleapis/release-please), which builds each
entry from the [Conventional Commits](https://www.conventionalcommits.org/)
prefixes on `main` — see `release-please-config.json` for which types cut a
release. The version is derived from the git tag (pyproject `dynamic =
["version"]` + hatch-vcs); there is no version literal in the source to drift.

**Generated entries are sometimes corrected by hand, and this is why.** This repo
merges with merge commits rather than squashing, and GitHub writes the PR title
into the merge commit body — which release-please parses *alongside* the commit
it merges, so one change can produce two identical entries. The 0.0.2 "adopt
hatch-vcs" line was listed twice for exactly this reason (once for the commit,
once for the `#12` merge that carried its title) and deduped by hand here,
because there was no prior tag for `tools/changelog_dedup.py` to anchor its range
against. From 0.0.2 on there is one, so the tool handles it automatically.

## [0.1.0](https://github.com/rudi193-cmd/homestead/compare/v0.0.3...v0.1.0) (2026-08-11)


### Added

* app.theme — the shared surface theme (hoisted from homestead-ledger) ([6dfe288](https://github.com/rudi193-cmd/homestead/commit/6dfe28847ac3df618ffc5f6af859575efdd166fa))

## [0.0.3](https://github.com/rudi193-cmd/homestead/compare/v0.0.2...v0.0.3) (2026-08-11)


### Build

* relicense to Apache-2.0 ([8fad851](https://github.com/rudi193-cmd/homestead/commit/8fad851d3ed64f4b41dc66ce3aad1e1e8c36470b))

## [0.0.2](https://github.com/rudi193-cmd/homestead/compare/v0.0.1...v0.0.2) (2026-08-10)


### Build

* adopt hatch-vcs and the fleet's PyPI release automation ([df14049](https://github.com/rudi193-cmd/homestead/commit/df14049a7edf46f7eed4e80154181f31111f75f8))
* publish as homestead-affairs (the bare name is taken on PyPI) ([25e9de9](https://github.com/rudi193-cmd/homestead/commit/25e9de976210563adf96261825bb8fec2777bf41))
