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
- Merging: never merge with a check that is failing or still pending. Once all checks pass, merge without asking again. `main` requires the Pipeline, Site and PR size checks, so GitHub enforces this:
  - Right after opening a PR, turn on auto-merge (`gh pr merge --auto --squash`). GitHub then squash-merges it once every required check passes, and deletes the branch.
  - If GitHub refuses because the PR is already ready (all checks passed), merge it directly with `gh pr merge --squash`.
  - If a check fails, fix it on the branch. Auto-merge stays on and merges once the fix passes.
  - Never bypass or remove the required checks. When a CI job is added or renamed, tell Ryan so its name can be added to the required checks on `main`.
- Keep each PR to one milestone or one concern. Don't bundle unrelated fixes.
- A PR must not exceed 1000 changed lines (added plus removed). If it would, split it into smaller PRs that each make sense alone, and merge them in order. Lockfiles and generated files (`site/src/data/*`) don't count toward the limit, but say in the PR description when a PR includes them.
- When a decision changes the plan (a new data source, a different metric, a changed milestone), update `plans/PLAN.md` in the same piece of work.
- Ask before adding a dependency. Say what it's for and why the existing stack doesn't cover it.

## Data integrity

- Compute every score from full-resolution geometry. Simplified shapes are for display only.
- Measure area and perimeter in an equal-area projection centered on each district, never on raw latitude and longitude.
- Never commit `data/raw/`. Every source goes in `data/sources/` with its URL, the publisher, the date it was downloaded, and its license.
- Never hand-edit generated files (`site/src/data/*`). Change the pipeline and regenerate.
- The pipeline must be reproducible: the same inputs always give the same outputs. Pin source versions and avoid unseeded randomness.
- Keep the validation checks passing: exactly 435 districts, each state's count matching its apportionment, unique IDs, valid geometry.
- When a state's map is in question (redrawn, in court, or a replacement), record its status and source in `data/sources/states.csv` rather than guessing.

## Testing (test-driven development)

- Write the test first for any new behavior, in the pipeline or the site. Run it and confirm it fails for the expected reason (not an import error or a typo) before writing the code. Then write the smallest code that makes it pass, then tidy up with the tests still green.
- When fixing a bug, first write a test that reproduces it and fails, then fix it.
- Tests must be able to fail. For any check that guards against something (a validation, an absence check, a race or edge case), prove it works by temporarily breaking the code it guards and watching the test fail. Then restore the code. A test that has only ever passed proves nothing.
- Every new or changed metric needs a known-answer test (a circle, a square, an L shape, a multi-part district).
- Metric functions are pure: geometry in, number out, with no I/O.
- Any change to the scoring formula must also update the methodology page.
- In the PR description, say which tests were written first and which guards were checked by breaking the code.

## Documentation

- Any change to setup, commands or project structure updates the README and the Commands section of this file in the same PR.
- Every public Python function and exported TypeScript function has a short docstring saying what it does and what it returns, including units where they matter (meters, square kilometers, a 0 to 1 ratio).
- Comments explain why, not what. Don't restate what the code already says.
- A PR that changes behavior visible on the site, or a data source, updates the matching docs (the methodology page, `data/sources/`, the README) in the same PR. A PR that changes neither says "No docs needed" in its description, so the check is never skipped silently.

## UI changes

- After any change that affects what the site looks like or how it behaves in the browser, run the local dev server and check the change in the browser before calling it done. Check the browser console for errors too.
- Show Ryan every UI change with:
  - **Screenshots** of each changed page at desktop width and phone width, plus dark mode when colors or theming change. Send them as files, so they reach Ryan on any device.
  - **A local server link** straight to each changed page (for example `http://localhost:4324/tx/35`), not just the home page.
- The local link only works on this Mac. If Ryan is working from another device, say so, and rely on the screenshots.
- Leave the dev server running after reporting, so the link still works when Ryan opens it.
- In the PR description, list the pages that were checked and at which widths.
- The dev server is started from `.claude/launch.json` (added in M0).

## Copy and tone

The site is a neutral reference tool. Scores describe shape, not intent.

- Never write "X% gerrymandered" or call a specific district a gerrymander. Write "less compact than X% of districts" or "irregularity score".
- Every displayed score carries its context: the coastal, VRA, at-large and redrawn-mid-decade notes where they apply, and a link to the methodology page.
- Never let color carry meaning alone. Always show the number next to it.
- Credit every data source on the methodology page.
- No em dashes in any user-facing copy, in commit messages, or in PR descriptions. Use commas, colons, parentheses, or two sentences instead.
- Use American English spellings in all docs: README, this file, docstrings and comments, site copy, data notes, commit messages and PR descriptions (color, center, meter, neighbor, behavior, labeled). Names you don't control keep their spelling, such as the HTML attribute `aria-labelledby` or a package name.
- Write in plain language for a general audience. Explain any technical term the first time it appears.

## Code

- No function may exceed 100 lines. This applies to Python, TypeScript, and the script parts of Astro components. If a function would be longer, break it into smaller named functions.
- Keep the pipeline and the site separate. The site reads only exported JSON, never raw data, and never runs Python.
- Use TypeScript strict mode in `site/`, and type hints in `pipeline/`.
- Pages must work at phone width, in light and dark mode, and by keyboard.
- Prefer build-time work over browser JavaScript. Only search, sort and filter need client-side code.

## Commands

Run from the repo root. The README describes each one.

- Set up: `make setup`
- Before every commit: `make check` (pipeline lint, tests and function length, plus the site check). A hook in `.claude/settings.json` runs it on every `git commit` and blocks the commit if it fails.
- Tests only: `make test`
- Build and validate the 2026 district map: `make boundaries` (`python -m gerry boundaries`), written to `data/build/districts.gpkg`. Redrawn states are registered in `pipeline/src/gerry/state_maps.py`, and must match the audit.
- Re-derive the map generalization settings: `make calibrate` (`python -m gerry calibrate`). Rerun it if the Census source files change.
- Score the built map: `make scores` (`python -m gerry scores`), which writes the site's data files in `site/src/data/` (`districts.json`, `shapes.json`, `states.json`). `make data` runs boundaries then scores.
- Validate the state map audit: `make audit` (`python -m gerry audit`). `make test` also validates the committed `states.csv` and `sources.csv`.
- Fix formatting: `make format`
- PR size against `main`: `make pr-size`
- Site dev server: `make site-dev` (http://localhost:4324), or the `site` entry in `.claude/launch.json`
- Site lint, typecheck, tests and build: `make site-check`
- Full rebuild: `make all` (planned)

CI runs `make check` and the PR size check on every PR. Cloudflare Pages builds a preview of every PR and deploys `main` to production (see the README's Deploy section).
