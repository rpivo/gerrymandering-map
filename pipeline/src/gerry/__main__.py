"""Command line entry point: `python -m gerry <command>`.

Commands:
    boundaries  Download the Census district boundaries and validate them.
    audit       Validate data/sources/states.csv and list states with new 2026 maps.
"""

import argparse
import sys
from pathlib import Path

from gerry.boundaries import load_districts
from gerry.fetch import CENSUS_CD119, fetch
from gerry.state_audit import changed_states, read_state_audit, validate_state_audit
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


def audit(repo_root: Path) -> int:
    """Validate the state map audit and list states whose 2026 map differs from 2024."""
    rows = read_state_audit(repo_root / "data" / "sources" / "states.csv")
    problems = validate_state_audit(rows)
    if problems:
        print(f"{len(problems)} problems in states.csv:")
        print("\n".join(f"  {p}" for p in problems))
        return 1
    changed = changed_states(rows)
    print(f"{len(rows)} states audited. All checks passed.")
    print(f"Changed since 2024 ({len(changed['yes'])}): {', '.join(changed['yes']) or 'none'}")
    print(f"Unclear ({len(changed['unclear'])}): {', '.join(changed['unclear']) or 'none'}")
    return 0


COMMANDS = {
    "boundaries": (boundaries, "Download and validate district boundaries."),
    "audit": (audit, "Validate the state map audit and list changed states."),
}


def main(argv: list[str]) -> int:
    """Run a pipeline command. Returns the process exit code."""
    parser = argparse.ArgumentParser(prog="gerry", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    return COMMANDS[args.command][0](args.repo_root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
