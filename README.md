# gerrymandering-map

A website that lists every US congressional district, shows its shape, and scores how irregular that shape is compared with every other district. A later phase adds partisan fairness scores for each state's map.

The scores describe shape, not intent. An irregular district isn't proof of a gerrymander, and a compact one isn't proof against it.

**Status:** early setup. The pipeline downloads and validates the Census district boundaries. Scoring and the real site come next.

## Layout

| Path | What's there |
|---|---|
| `pipeline/` | Python data pipeline: downloads boundaries, computes scores, exports JSON |
| `data/sources/sources.csv` | Every raw data source: URL, publisher, license, download date and SHA-256 checksum |
| `site/` | Astro + TypeScript static site, built from the pipeline's exported JSON |
| `tools/` | Repo checks run in CI: function length and PR size limits |
| `.github/workflows/ci.yml` | CI: lint, tests and limit checks on every PR |
| `.claude/` | Claude Code settings, including a hook that blocks commits when checks fail |
| `CLAUDE.md` | The rules for working on this repo |

## Setup

You need [uv](https://docs.astral.sh/uv/), Node 24 or newer, [pnpm](https://pnpm.io/) 10, and GNU Make. uv installs Python 3.13 itself if it's missing.

The site only installs package versions that have been published for at least two weeks (`minimumReleaseAge` in `site/pnpm-workspace.yaml`), as a guard against freshly published malicious releases.

```bash
make setup
```

## Commands

Run these from the repo root.

| Command | What it does |
|---|---|
| `make setup` | Installs the pipeline's Python environment and the site's packages |
| `make check` | Everything CI runs: pipeline lint, tests and function length, plus the full site check |
| `make site-dev` | Starts the site's dev server at http://localhost:4324 |
| `make site-check` | Site lint (including function length and docstrings), typecheck, tests and build |
| `make boundaries` | Downloads the Census district boundaries (once, then cached in `data/raw/`) and checks them: 435 districts, each state's count, valid shapes, no overlaps |
| `make test` | Runs the Python tests (`pipeline/tests` and `tools/tests`) |
| `make lint` | Checks Python style and docstrings with ruff, without changing files |
| `make format` | Fixes Python style and formatting in place |
| `make check-functions` | Fails if any Python function is longer than 100 lines |
| `make pr-size` | Counts this branch's changed lines against `origin/main` (limit 1000, lockfiles and generated data excluded) |

## Data

Raw downloads go in `data/raw/`, which is not committed. Every source is recorded in `data/sources/sources.csv` with its SHA-256 checksum. If a source changes upstream, the pipeline stops rather than quietly using different data.

Current boundaries: the U.S. Census Bureau's 2025 cartographic boundary file for the 119th Congress (1:500,000, clipped to the shoreline). Several states redrew their maps in 2025 and 2026, so some of these lines may not match the ones used in the 2026 election. That audit is the next step.

## License

Not chosen yet.
