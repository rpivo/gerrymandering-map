# gerrymandering-map

A website that lists every US congressional district, shows its shape, and scores how irregular that shape is compared with every other district. A later phase adds partisan fairness scores for each state's map.

The scores describe shape, not intent. An irregular district isn't proof of a gerrymander, and a compact one isn't proof against it.

**Status:** the site is built: a searchable grid of all 435 districts, a page for every district and state, and a methodology page. It isn't deployed yet. Run `make site-dev` to see it at http://localhost:4324.

## Layout

| Path | What's there |
|---|---|
| `pipeline/` | Python data pipeline: downloads boundaries, computes scores, exports JSON |
| `data/sources/sources.csv` | Every raw data source: URL, publisher, license, download date and SHA-256 checksum |
| `data/sources/states.csv` | Which congressional map each state used in the 2026 election, who drew it, when, and a source |
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
| `make boundaries` | Builds the 2026 district map into `data/build/districts.gpkg`: the Census districts with each redrawn state's official map swapped in, then checks it (435 districts, each state's count, valid shapes, no overlaps, full land coverage). Downloads are cached in `data/raw/` |
| `make audit` | Checks `data/sources/states.csv` and lists the states whose 2026 map differs from the Census boundaries |
| `make calibrate` | Re-derives the settings that bring state files to the Census level of detail, from Census files for 12 unchanged states |
| `make scores` | Scores the built map: Polsby-Popper, Reock and convex hull for every district, percentiles among the 429 districts with lines, a 0 to 100 irregularity score and ranks. Writes the site's data to `site/src/data/` (committed: `districts.json` scores, `shapes.json` SVG outlines and state maps, `states.json` state details) and `data/build/scores.csv` |
| `make data` | `make boundaries` then `make scores` |
| `make test` | Runs the Python tests (`pipeline/tests` and `tools/tests`) |
| `make lint` | Checks Python style and docstrings with ruff, without changing files |
| `make format` | Fixes Python style and formatting in place |
| `make check-functions` | Fails if any Python function is longer than 100 lines |
| `make pr-size` | Counts this branch's changed lines against `origin/main` (limit 1000, lockfiles and generated data excluded) |

## Data

Raw downloads go in `data/raw/`, which is not committed. Every source is recorded in `data/sources/sources.csv` with its SHA-256 checksum. If a source changes upstream, the pipeline stops rather than quietly using different data.

Current boundaries: the U.S. Census Bureau's 2025 cartographic boundary file for the 119th Congress (1:500,000, clipped to the shoreline). These are the lines used in the 2024 election. Nine states used a different map in the 2026 election (`data/sources/states.csv` records each with a source). For eight of them (Alabama, California, Florida, Louisiana, North Carolina, Tennessee, Texas and Utah) the pipeline downloads the state's official 2026 shapefile and swaps it in. Ohio publishes its map only as a block assignment file, so the pipeline joins it to the Census 2020 block shapes and merges the blocks into districts. Each state's districts are then put on the same footing as the Census districts: clipped to the Census outline of the state (land only), with clipping slivers merged into their neighbors, and internal borders simplified to the Census file's level of detail. Without that last step, the more detailed state files would score about 2% less compact on average for no real reason. `make calibrate` re-derives both settings from the Census Bureau's own full-detail and generalized versions of the same districts. Missouri and Virginia passed new maps that were not used in 2026.

## Scores

Each district gets three standard compactness measures, computed in an equal-area projection centered on the district:

- **Polsby-Popper:** area compared with perimeter. Low for jagged or snaking shapes.
- **Reock:** area compared with the smallest circle around the district. Low for stretched shapes.
- **Convex hull:** area compared with a rubber band stretched around the district. Low for shapes with bites or tentacles.

Reock and convex hull are measured against land: only the part of the circle or rubber band that falls on the district's own state counts. Water between islands or beyond a coastline is space no district could use, so it doesn't count against a district, while land a district leaves out still does. Without this, island districts such as Hawaii's 2nd or the Florida Keys ranked among the least compact for their geography alone.

For each measure, a district's percentile is where it falls among the 429 districts that have lines (the six at-large states have one district covering the whole state, so they are measured but not ranked). The irregularity score is 100 minus the average of the three percentiles: 0 is the most compact district, near 100 the least. A score describes shape, not intent: a ragged coastline still lowers Polsby-Popper, and the Voting Rights Act can call for irregular districts.

## Deploy

The site is a Cloudflare Worker that serves the Astro build as static files (no Worker script), connected to this GitHub repo with Workers Builds. Every merge to `main` deploys to production, and other branches get preview URLs.

The Worker's config is `site/wrangler.json`. Build settings in the Cloudflare dashboard (Workers & Pages, Create application, Continue with GitHub):

| Setting | Value |
|---|---|
| Project name | `gerrymandering-map` (must match `name` in `wrangler.json`) |
| Production branch | `main` |
| Root directory | `site` |
| Build command | `pnpm build` |
| Deploy command | `pnpm exec wrangler deploy` |
| Non-production branch deploy command | `pnpm exec wrangler versions upload` |

Wrangler is a pinned dev dependency, so deploys use the locked version. Cloudflare reads the Node version from `site/.nvmrc` and the pnpm version from `packageManager` in `site/package.json`. Response headers (security headers, and long-term caching for Astro's fingerprinted assets) are in `site/public/_headers`, which Workers static assets honor.

The pipeline doesn't run on Cloudflare: the site builds only from the committed data in `site/src/data/`, so a data change ships by committing regenerated files.

To check a deploy locally without uploading: `cd site && pnpm build && pnpm exec wrangler deploy --dry-run`.

## License

Not chosen yet.
