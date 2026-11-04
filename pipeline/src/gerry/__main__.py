"""Command line entry point: `python -m gerry <command>`.

Commands:
    boundaries  Download the Census district boundaries and validate them.
"""

import argparse
import sys
from pathlib import Path

from gerry.boundaries import load_districts
from gerry.fetch import CENSUS_CD119, fetch
from gerry.validate import validate_districts

# pipeline/src/gerry/__main__.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]


def boundaries(repo_root: Path) -> int:
    """Fetch and validate the district boundaries. Returns the process exit code."""
    data = repo_root / "data"
    path = fetch(CENSUS_CD119, data / "raw", data / "sources" / "sources.csv")
    districts = load_districts(path)
    problems = validate_districts(districts)
    if problems:
        print(f"{len(problems)} problems in {path.name}:")
        print("\n".join(f"  {p}" for p in problems))
        return 1
    states = districts["state"].nunique()
    print(f"{len(districts)} districts in {states} states. All checks passed.")
    return 0


def main(argv: list[str]) -> int:
    """Run a pipeline command. Returns the process exit code."""
    parser = argparse.ArgumentParser(prog="gerry", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("boundaries", help="Download and validate district boundaries.")
    run.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    return boundaries(args.repo_root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
