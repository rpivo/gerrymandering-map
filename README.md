# gerrymandering-map

A website that lists every US congressional district, shows its shape, and scores how irregular that shape is compared with every other district. A later phase adds partisan fairness scores for each state's map.

The scores describe shape, not intent. An irregular district isn't proof of a gerrymander, and a compact one isn't proof against it.

**Status:** early setup. The data pipeline is scaffolded. The site and the scoring code come next.

## Layout

| Path | What's there |
|---|---|
| `pipeline/` | Python data pipeline: downloads boundaries, computes scores, exports JSON |
| `tools/` | Repo checks run in CI: function length and PR size limits |
| `.github/workflows/ci.yml` | CI: lint, tests and limit checks on every PR |
| `.claude/` | Claude Code settings, including a hook that blocks commits when checks fail |
| `CLAUDE.md` | The rules for working on this repo |

## Setup

You need [uv](https://docs.astral.sh/uv/) and GNU Make. uv installs Python 3.13 itself if it's missing.

```bash
make setup
```

## Commands

Run these from the repo root.

| Command | What it does |
|---|---|
| `make setup` | Installs the pipeline's Python environment |
| `make check` | Everything CI runs on the pipeline: lint, tests and the function length check |
| `make test` | Runs the Python tests (`pipeline/tests` and `tools/tests`) |
| `make lint` | Checks Python style and docstrings with ruff, without changing files |
| `make format` | Fixes Python style and formatting in place |
| `make check-functions` | Fails if any Python function is longer than 100 lines |
| `make pr-size` | Counts this branch's changed lines against `origin/main` (limit 1000, lockfiles and generated data excluded) |

## License

Not chosen yet.
