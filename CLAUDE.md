# gerrymandering-map

A static website that lists every US congressional district, shows its shape, and scores how irregular it is. A second phase adds partisan fairness scores for each state's map.

- `pipeline/`: Python (geopandas, shapely, pyproj). Downloads raw data, computes scores, exports JSON.
- `site/`: Astro + TypeScript. Builds static pages from the exported JSON.
- `plans/PLAN.md`: the project plan. It's gitignored and local only. Read it before starting a milestone.

These rules apply to every change in this repo. If a request conflicts with one of them, say so and ask before going ahead.

## Workflow

- Never commit directly to `main`. Make a branch for each change (`m0-scaffold`, `fix-reock-multipolygon`) and open a PR.
- Before every commit, run the pipeline tests and the site build. Never commit with either one failing. If a failure is unrelated to the change, report it rather than working around it.
- Commit or push only when Ryan asks.
- Before merging a PR, wait for every check to finish. Never merge with a check that is failing or still pending. Once all checks pass, merge without asking again. If the repo has no checks configured, say so when merging.
- Keep each PR to one milestone or one concern. Don't bundle unrelated fixes.
- A PR must not exceed 1000 changed lines (added plus removed). If it would, split it into smaller PRs that each make sense alone, and merge them in order. Lockfiles and generated files (`site/src/data/*`) don't count toward the limit, but say in the PR description when a PR includes them.
- When a decision changes the plan (a new data source, a different metric, a changed milestone), update `plans/PLAN.md` in the same piece of work.
- Ask before adding a dependency. Say what it's for and why the existing stack doesn't cover it.

## Data integrity

- Compute every score from full-resolution geometry. Simplified shapes are for display only.
- Measure area and perimeter in an equal-area projection centred on each district, never on raw latitude and longitude.
- Never commit `data/raw/`. Every source goes in `data/sources/` with its URL, the publisher, the date it was downloaded, and its license.
- Never hand-edit generated files (`site/src/data/*`). Change the pipeline and regenerate.
- The pipeline must be reproducible: the same inputs always give the same outputs. Pin source versions and avoid unseeded randomness.
- Keep the validation checks passing: exactly 435 districts, each state's count matching its apportionment, unique IDs, valid geometry.
- When a state's map is in question (redrawn, in court, or a replacement), record its status and source in `data/sources/states.csv` rather than guessing.

## Metrics and tests

- Metric functions are pure: geometry in, number out, with no I/O.
- Every new or changed metric needs a known-answer test (a circle, a square, an L shape, a multi-part district).
- When fixing a bug in a metric or a validation check, first write a test that fails without the fix.
- Any change to the scoring formula must also update the methodology page.

## Copy and tone

The site is a neutral reference tool. Scores describe shape, not intent.

- Never write "X% gerrymandered" or call a specific district a gerrymander. Write "less compact than X% of districts" or "irregularity score".
- Every displayed score carries its context: the coastal, VRA, at-large and redrawn-mid-decade notes where they apply, and a link to the methodology page.
- Never let colour carry meaning alone. Always show the number next to it.
- Credit every data source on the methodology page.
- No em dashes in any user-facing copy, in commit messages, or in PR descriptions. Use commas, colons, parentheses, or two sentences instead.
- Write in plain language for a general audience. Explain any technical term the first time it appears.

## Code

- No function may exceed 100 lines. This applies to Python, TypeScript, and the script parts of Astro components. If a function would be longer, break it into smaller named functions.
- Keep the pipeline and the site separate. The site reads only exported JSON, never raw data, and never runs Python.
- Use TypeScript strict mode in `site/`, and type hints in `pipeline/`.
- Pages must work at phone width, in light and dark mode, and by keyboard.
- Prefer build-time work over browser JavaScript. Only search, sort and filter need client-side code.

## Commands

The M0 scaffold will fill these in.

- Pipeline tests: _TBD_
- Site build: _TBD_
- Full rebuild: `make all` (planned)
