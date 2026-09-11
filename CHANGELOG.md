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

## [0.10.0](https://github.com/homestead-affairs/homestead/compare/v0.9.0...v0.10.0) (2026-09-11)


### Added

* IntegrityLog takes an optional HMAC-SHA256 key ([da74a93](https://github.com/homestead-affairs/homestead/commit/da74a937c7a73a2026dc24b10f40a09d4016e23a))


### Fixed

* a marker line this did not write cannot crash verify() ([6c4a862](https://github.com/homestead-affairs/homestead/commit/6c4a8629342d2f83a70cad994914ca524ecb1a10))
* a keyed log cannot be downgraded by deleting its boundary row ([ae960c9](https://github.com/homestead-affairs/homestead/commit/ae960c9bdee7628fface6bb7938aa0cba276d5a0))

## [0.9.0](https://github.com/homestead-affairs/homestead/compare/v0.8.0...v0.9.0) (2026-09-11)


### Added

* the fleet's own Postgres adapter and a never-listening ingest (E4-postgres-fleet) ([b95475b](https://github.com/homestead-affairs/homestead/commit/b95475b5ca2285a507f2bcd7781b47296606b221))


### Fixed

* audit E4-postgres-fleet — the confirm leaks no password, and a row is written by one code path ([56515e5](https://github.com/homestead-affairs/homestead/commit/56515e505cc9699a9a20a72735ed57d40a0e907f))

## [0.8.0](https://github.com/homestead-affairs/homestead/compare/v0.7.0...v0.8.0) (2026-09-11)


### Added

* sync core — SyncScope, Envelope, and a household id (E4-sync-core) ([d57b948](https://github.com/homestead-affairs/homestead/commit/d57b948c42e5336447abe7b89d6d790715870e48))


### Fixed

* audit E4-sync-core — an envelope is addressed by its content, and consent is True ([90a4a32](https://github.com/homestead-affairs/homestead/commit/90a4a32bdef4588fd3f098be65955e5eb4f74921))

## [0.7.0](https://github.com/homestead-affairs/homestead/compare/v0.6.0...v0.7.0) (2026-09-11)


### Added

* cover_counts takes an optional per-matter distribution (I-31) ([9120e50](https://github.com/homestead-affairs/homestead/commit/9120e5023e3f8864318fd8c9c289540f2c0bb6a9))


### Fixed

* the cover refuses a distribution it cannot check, and reads the roster as a set (I-31) ([61e5b20](https://github.com/homestead-affairs/homestead/commit/61e5b202d9d154ab2650577f3e76c34e72fe2e04))

## [0.6.0](https://github.com/homestead-affairs/homestead/compare/v0.5.0...v0.6.0) (2026-09-11)


### Added

* US-NM and US-OR join the deadline rule table ([4f28f78](https://github.com/homestead-affairs/homestead/commit/4f28f78c1a9c62e82a0885f21d2dd4fc0f761ce3))


### Fixed

* audit E1-dates-b — a state court reads its own state's holidays ([c4c9b3e](https://github.com/homestead-affairs/homestead/commit/c4c9b3e0547aee5248d70fe5c993acbaf7915adb))

## [0.5.0](https://github.com/homestead-affairs/homestead/compare/v0.4.0...v0.5.0) (2026-09-11)


### Added

* backward counting, mail days, business days, district-state holidays ([90bf4ca](https://github.com/homestead-affairs/homestead/commit/90bf4ca2c57c8351868a6410162816e35e0f6bae))


### Fixed

* audit E1-dates-a — say what VERIFIED means, and let the mail re-roll see the district ([ab21e33](https://github.com/homestead-affairs/homestead/commit/ab21e335c72ccf15e8605f7dd955aa11f14b8f5d))

## [0.4.0](https://github.com/homestead-affairs/homestead/compare/v0.3.0...v0.4.0) (2026-09-11)


### Added

* add Purpose.SYNC as an eighth member ([6d9230d](https://github.com/homestead-affairs/homestead/commit/6d9230db8f2bcf2fce4eaf9a748ff660e7424d7e))

## [0.3.0](https://github.com/homestead-affairs/homestead/compare/v0.2.3...v0.3.0) (2026-09-11)


### Added

* JURISDICTIONS tuple and derived-form key on engine packs ([21f8dd2](https://github.com/homestead-affairs/homestead/commit/21f8dd28668137e2fd5a2162ba6866915b1d3159))


### Fixed

* audit E1-pack-contract — a leaky derived form, a drifting jurisdiction copy, and derived_of held to the schema ([85b2151](https://github.com/homestead-affairs/homestead/commit/85b2151d2530c777474c3738961106e729925033))
* rename the engine console script to homestead, correct registry docs ([4f5d212](https://github.com/homestead-affairs/homestead/commit/4f5d212a68ce5ca06382e9edb70e34cbd7184006))

## [0.2.3](https://github.com/homestead-affairs/homestead/compare/v0.2.2...v0.2.3) (2026-08-25)

## [0.2.2](https://github.com/homestead-affairs/homestead/compare/v0.2.1...v0.2.2) (2026-08-25)

## [0.2.1](https://github.com/homestead-affairs/homestead/compare/v0.2.0...v0.2.1) (2026-08-24)


### Build

* **deps:** bump actions/upload-artifact from 4 to 7 ([f7c8628](https://github.com/homestead-affairs/homestead/commit/f7c8628d3a0edb22231e6e4b5405e1a43cfee1d1))
* **deps:** bump actions/checkout from 4 to 7 ([5246269](https://github.com/homestead-affairs/homestead/commit/5246269c491b3676c638ee1df3361733e21f4349))
* **deps:** bump actions/download-artifact from 4 to 8 ([f5f77ce](https://github.com/homestead-affairs/homestead/commit/f5f77cef8e2c935ffd239c6e17e71021fe2a6e87))
* **deps:** bump actions/setup-python from 5 to 7 ([20ab09c](https://github.com/homestead-affairs/homestead/commit/20ab09cee793b59210a1ae682f20def55bb0d66a))

## [0.2.0](https://github.com/rudi193-cmd/homestead/compare/v0.1.0...v0.2.0) (2026-08-18)


### Added

* add bankruptcy pack, proving the registry seam carries a real rung difference ([5d8caa9](https://github.com/rudi193-cmd/homestead/commit/5d8caa92c970f7d4120be599af09b1be4371dfb4))

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
