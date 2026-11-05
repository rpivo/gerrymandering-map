# gerrymandering-map

A website that lists every US congressional district, shows its shape, and scores how irregular that shape is compared with every other district. Each state page also scores the state's map for partisan fairness (efficiency gap, mean-median difference and declination) from the 2024 presidential vote.

The scores describe shape, not intent. An irregular district isn't proof of a gerrymander, and a compact one isn't proof against it.

**Status:** the site is built: a searchable grid of all 435 districts under a clickable US map that opens each state's page, a page for every district and state (with partisan fairness scores for the 28 states that can be scored so far), and a methodology page. It's live at https://gerrymandering-map.ryanpivovar.workers.dev (see Deploy below). Run `make site-dev` to see it locally at http://localhost:4324.

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
| `make scores` | Scores the built map: Polsby-Popper, Reock and convex hull for every district, percentiles among the 429 districts with lines, a 0 to 100 irregularity score and ranks, plus the share of each district's border on the state's edge (shown as context, not scored). Writes the site's data to `site/src/data/` (committed: `districts.json` scores, `shapes.json` SVG outlines and state maps, with Hawaii's drawn without the Northwestern Hawaiian Islands so the main islands are visible (noted beside them; scores use the full shape), `us-map.json` the 50 states as one map for the home page, with Alaska and Hawaii as insets, `states.json` state details) and `data/build/scores.csv` |
| `make data` | `make boundaries` then `make scores` |
| `make votes` | Places 2024 presidential votes in districts for the states that kept their 2024 lines, from MIT's precinct files (about 590 MB, cached). Checks Texas against the Legislative Council's official report for its 2024 map and stops if they differ. Adds Texas and North Carolina from their legislatures' official reports on the 2026 maps (`data/sources/votes/`). Writes `data/build/president-2024-by-district.csv` (with a `method` column: precinct join or official report) and `president-2024-quality.csv`, and lists states that need a fix |
| `make fairness` | Scores each state with 4 or more districts for partisan fairness from `make votes`'s output: efficiency gap, mean-median difference and declination, where positive favors Republicans. Writes `data/build/fairness-2024.csv` and the site's `site/src/data/fairness.json` (committed: every state, scored or with the reason it isn't, such as too few districts or a map redrawn for 2026). `pipeline/src/gerry/fairness.py` defines each measure |
| `make population` | Adds up 2020 Census voting-age population by race and Hispanic origin, and residents of each city, town and census-designated community, in each built district, from the Census redistricting file (PL 94-171) for every state (about 1.3 GB, downloaded once). Each block goes to the district containing its center point. Fails if a district's 2020 population is more than 3% off its state's average, since every map in use was drawn to equal 2020 populations (states that count prisoners at their home addresses, such as California, run up to 2.3% off on raw counts). Also fails if a place's residents across districts don't add up to its 2020 total. Writes `data/build/population-by-district.csv` and `places-by-district.csv` and, if the checks pass, the site's `site/src/data/population.json` (committed: each district's voting-age shares and whether one minority group, or all minority groups together, are a majority) and `places.json` (committed: each district's 10 largest places by residents in the district, for the district page's "Cities and towns" list) and `cities.json` (committed: each state's 60 largest places as points on its state map, from which the site marks up to 10 that fit without overlapping labels) and `district-cities.json` (committed: each district's 20 largest places by residents in the district, as points on its district page outline, each at the census block nearest the population center of that place's part of the district). `pipeline/src/gerry/population.py` and `pipeline/src/gerry/places.py` document the method |
| `make test` | Runs the Python tests (`pipeline/tests` and `tools/tests`) |
| `make lint` | Checks Python style and docstrings with ruff, without changing files |
| `make format` | Fixes Python style and formatting in place |
| `make check-functions` | Fails if any Python function is longer than 100 lines |
| `make pr-size` | Counts this branch's changed lines against `origin/main` (limit 1000, lockfiles and generated data excluded) |

## Data

Raw downloads go in `data/raw/`, which is not committed. Every source is recorded in `data/sources/sources.csv` with its SHA-256 checksum. If a source changes upstream, the pipeline stops rather than quietly using different data.

Current boundaries: the U.S. Census Bureau's 2025 cartographic boundary file for the 119th Congress (1:500,000, clipped to the shoreline). These are the lines used in the 2024 election. Nine states used a different map in the 2026 election (`data/sources/states.csv` records each with a source). For eight of them (Alabama, California, Florida, Louisiana, North Carolina, Tennessee, Texas and Utah) the pipeline downloads the state's official 2026 shapefile and swaps it in. Ohio publishes its map only as a block assignment file, so the pipeline joins it to the Census 2020 block shapes and merges the blocks into districts. Each state's districts are then put on the same footing as the Census districts: clipped to the Census outline of the state (land only), with clipping slivers merged into their neighbors, and internal borders simplified to the Census file's level of detail. Without that last step, the more detailed state files would score about 2% less compact on average for no real reason. `make calibrate` re-derives both settings from the Census Bureau's own full-detail and generalized versions of the same districts. Missouri and Virginia passed new maps that were not used in 2026.

Votes (for the partisan fairness scores, shown on state pages from `site/src/data/fairness.json`): 2024 presidential results by precinct from the MIT Election Data and Science Lab (CC0). Their House file says which district each precinct voted in, so the two files together give presidential votes by district wherever the 2024 lines were used again in 2026. `pipeline/src/gerry/votes.py` documents the join's rules. Two states need official data on top: King County's own public-domain precinct results replace its single county-wide row in Washington, and New Jersey's counties are scaled to the official county totals in `data/sources/votes/` (MIT's file is missing Mercer County's early votes). For redrawn states the precinct join doesn't apply; Texas and North Carolina published official 2024 results on their new maps, transcribed in `data/sources/votes/`. The other seven redrawn states published none and will use 2026 House results. `data/checks/` holds published results the pipeline checks itself against (see its README).

Population (for the "Who lives here" note on majority-minority district pages): the 2020 Census redistricting file (PL 94-171), public domain, one per state. It has every census block's voting-age population by race and Hispanic origin and a point inside the block, so the same method works for the 2024 lines and the 9 redrawn maps.

## Scores

Each district gets three standard compactness measures, computed in an equal-area projection centered on the district:

- **Polsby-Popper:** area compared with perimeter. Low for jagged or snaking shapes.
- **Reock:** area compared with the smallest circle around the district. Low for stretched shapes.
- **Convex hull:** area compared with a rubber band stretched around the district. Low for shapes with bites or tentacles.

Reock and convex hull are measured against land: only the part of the circle or rubber band that falls on the district's own state counts. Water between islands or beyond a coastline is space no district could use, so it doesn't count against a district, while land a district leaves out still does. Without this, island districts such as Hawaii's 2nd or the Florida Keys ranked among the least compact for their geography alone.

For each measure, a district's percentile is where it falls among the 429 districts that have lines (the six at-large states have one district covering the whole state, so they are measured but not ranked). The irregularity score is 100 minus the average of the three percentiles: 0 is the most compact district, near 100 the least. A score describes shape, not intent: a ragged coastline still lowers Polsby-Popper, and the Voting Rights Act can call for irregular districts.

## Deploy

The site is a Cloudflare Worker that serves the Astro build as static files (no Worker script), connected to this GitHub repo with Workers Builds. Every merge to `main` deploys to production at https://gerrymandering-map.ryanpivovar.workers.dev. Branches and PRs don't get preview builds: check changes on the local dev server (`make site-dev`) instead.

The Worker's config is `site/wrangler.json`. Build settings in the Cloudflare dashboard (Workers & Pages, Create application, Continue with GitHub):

| Setting | Value |
|---|---|
| Project name | `gerrymandering-map` (must match `name` in `wrangler.json`) |
| Production branch | `main` |
| Root directory | `site` |
| Build command | `pnpm build` |
| Deploy command | `pnpm exec wrangler deploy` |
| Builds for Preview branches (under "Previews Base") | Off |
| API token | `gerrymandering-map build token` (used only by this project) |

Preview builds are off because Cloudflare's preview setup (in open beta in November 2026) failed for this static-assets-only Worker: `wrangler preview` stopped at the asset upload, and `wrangler versions upload` reported a Worker name mismatch even though the names match. If they're turned back on, `wrangler preview` also needs an empty `"previews": {}` block in `wrangler.json`. Wrangler is a pinned dev dependency, so deploys use the locked version. Cloudflare reads the Node version from `site/.nvmrc` and the pnpm version from `packageManager` in `site/package.json`. Response headers (security headers, and long-term caching for any Astro asset files) are in `site/public/_headers`, which Workers static assets honor. Astro builds each page as a file (`tx/35.html`), so `/tx/35` is served without a redirect, and unknown addresses get `404.html`.

### Light and dark mode

The site opens in light mode for everyone, whatever their device prefers. A sun and moon switch in the header (announced to screen readers as a "Dark mode" switch) changes it and remembers the choice in that browser (`localStorage`). The colors for both modes are in `site/src/styles/global.css` (dark ones under `:root[data-theme="dark"]`), and `site/src/lib/theme.ts` holds the two small inline scripts: one in the page head applies a saved dark choice before the page draws, so it never flashes light, and one runs the switch. Without JavaScript the switch stays hidden and the site is light. Link preview images are always light.

### Map tooltips

Hovering a district on a state map shows a tooltip beside it: the irregularity score, how many districts it's less compact than, its rank in the state, and short notes where they apply (10% or more of its border on the state's edge, majority-minority, new lines for 2026). It uses no JavaScript. Every tooltip is built into the page, placed next to its district at build time (`site/src/lib/tooltip.ts`), and shown with CSS while that district is hovered. On narrow screens a tooltip spans the map's width. Tooltips are hidden from screen readers, since the districts table on the same page has the same information.

### Link previews

Every page has a 1200 by 630 preview image for social sites and chat apps: one per district, one per state, and one for the home and methodology pages (the 404 page uses the home image). They're drawn as SVG in `site/src/lib/og.ts` and turned into PNGs at build time by `@resvg/resvg-js` in `site/src/pages/og/[...image].png.ts`, so they land in `dist/og/` (about 9 MB). Text uses the Inter font committed in `site/src/assets/fonts/` (SIL Open Font License, in `OFL.txt` there) with system fonts turned off, so the images look the same on every machine; the build stops if the font can't load. Preview tags need absolute URLs, so the site's address is `SITE_URL` in `og.ts`: change it if the domain changes.

The pipeline doesn't run on Cloudflare: the site builds only from the committed data in `site/src/data/`, so a data change ships by committing regenerated files.

To check a deploy locally without uploading: `cd site && pnpm build && pnpm exec wrangler deploy --dry-run`.

## License

- **Code:** MIT License, in [`LICENSE`](LICENSE).
- **Data the project produces** (scores, ranks, simplified shapes, the state map audit and the preview images): Creative Commons Attribution 4.0 (CC BY 4.0), in [`LICENSE-DATA.md`](LICENSE-DATA.md), which also says how to credit it.
- **Source boundaries** keep their own terms: Census files are public domain, and each state file's license is in `data/sources/sources.csv`. The Inter font is under the SIL Open Font License.
