# Run from the repo root. See README.md for what each target does.
UV := uv run --project pipeline
PY_PATHS := pipeline tools

.PHONY: setup lint format test check-functions check pr-size site-dev site-check

setup:
	uv sync --project pipeline
	pnpm --dir site install --frozen-lockfile

lint:
	$(UV) ruff check $(PY_PATHS)
	$(UV) ruff format --check $(PY_PATHS)

format:
	$(UV) ruff check --fix $(PY_PATHS)
	$(UV) ruff format $(PY_PATHS)

test:
	cd pipeline && uv run pytest

check-functions:
	$(UV) python tools/check_function_length.py $(PY_PATHS)

# Site: lint (including function length and docstrings), typecheck, tests, build.
site-check:
	pnpm --dir site check

site-dev:
	pnpm --dir site dev

# Everything CI runs. Must pass before every commit.
check: lint test check-functions site-check

pr-size:
	$(UV) python tools/check_pr_size.py origin/main
