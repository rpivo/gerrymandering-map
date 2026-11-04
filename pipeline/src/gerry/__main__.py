"""Command line entry point: `python -m gerry <command>`.

Commands:
    boundaries  Build the map in effect for 2026: the Census 2024 districts with the
                redrawn states swapped in, validated, written to data/build/.
    audit       Validate data/sources/states.csv and list states with new 2026 maps.
"""

import argparse
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from gerry.boundaries import load_districts, load_state_outlines
from gerry.fetch import CENSUS_CD119, CENSUS_STATES, fetch
from gerry.replacement import (
    check_audit_match,
    clip_to_land,
    coverage_gap,
    normalize_state_map,
    replace_states,
)
from gerry.state_audit import changed_states, read_state_audit, validate_state_audit
from gerry.state_maps import PENDING, STATE_MAPS, StateMap, read_state_map
from gerry.validate import validate_districts

# pipeline/src/gerry/__main__.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
# Replacement districts may leave at most this share of a state's land uncovered.
MAX_COVERAGE_GAP = 0.005


def _load_replacement(
    state_map: StateMap, land: BaseGeometry, raw: Path, manifest: Path
) -> tuple[gpd.GeoDataFrame, list[str]]:
    """Fetch, normalize and clip one state's current map. Returns rows and problems."""
    path = fetch(state_map.source, raw, manifest)
    plan = read_state_map(path, state_map.member)
    rows = normalize_state_map(plan, state_map.state, state_map.district_field)
    rows = clip_to_land(rows, land)
    rows["map_source"] = state_map.source.id
    gap = coverage_gap(rows, land)
    if gap <= MAX_COVERAGE_GAP:
        return rows, []
    return rows, [f"{state_map.state}: districts leave {gap:.1%} of the state's land uncovered."]


def _print_problems(problems: list[str], where: str = "") -> None:
    """Print a numbered heading and one problem per line."""
    print(f"{len(problems)} problems{where}:")
    print("\n".join(f"  {p}" for p in problems))


def boundaries(repo_root: Path) -> int:
    """Build, validate and write the 2026 district map. Returns the process exit code."""
    data = repo_root / "data"
    raw, manifest = data / "raw", data / "sources" / "sources.csv"
    districts = load_districts(fetch(CENSUS_CD119, raw, manifest))
    districts["map_source"] = CENSUS_CD119.id
    outlines = load_state_outlines(fetch(CENSUS_STATES, raw, manifest))
    changed = changed_states(read_state_audit(data / "sources" / "states.csv"))
    problems = check_audit_match(changed, set(STATE_MAPS), set(PENDING))
    replacements = {}
    for state, state_map in STATE_MAPS.items():
        replacements[state], found = _load_replacement(state_map, outlines[state], raw, manifest)
        problems += found
    districts = replace_states(districts, replacements)
    problems += validate_districts(districts)
    if problems:
        _print_problems(problems)
        return 1
    out = data / "build" / "districts.gpkg"
    out.parent.mkdir(parents=True, exist_ok=True)
    districts.to_file(out, driver="GPKG")
    print(
        f"{len(districts)} districts in {districts['state'].nunique()} states. All checks passed."
    )
    print(f"Current maps swapped in: {', '.join(sorted(replacements)) or 'none'}")
    for state, reason in sorted(PENDING.items()):
        print(f"Still on 2024 lines (pending): {state}. {reason}")
    print(f"Wrote {out.relative_to(repo_root)}")
    return 0


def audit(repo_root: Path) -> int:
    """Validate the state map audit and list states whose 2026 map differs from 2024."""
    rows = read_state_audit(repo_root / "data" / "sources" / "states.csv")
    problems = validate_state_audit(rows)
    if problems:
        _print_problems(problems, " in states.csv")
        return 1
    changed = changed_states(rows)
    print(f"{len(rows)} states audited. All checks passed.")
    print(f"Changed since 2024 ({len(changed['yes'])}): {', '.join(changed['yes']) or 'none'}")
    print(f"Unclear ({len(changed['unclear'])}): {', '.join(changed['unclear']) or 'none'}")
    return 0


COMMANDS = {
    "boundaries": (boundaries, "Build and validate the 2026 district map."),
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
