"""Command line entry point: `python -m gerry <command>`.

Commands:
    boundaries  Build the map in effect for 2026: the Census 2024 districts with the
                redrawn states swapped in, validated, written to data/build/.
    audit       Validate data/sources/states.csv and list states with new 2026 maps.
    scores      Score the built map; write site/src/data/districts.json.
    calibrate   Re-derive the map generalization settings from Census files.
"""

import argparse
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from gerry.blocks import assemble_districts, read_block_assignment, read_blocks
from gerry.boundaries import load_districts, load_state_outlines
from gerry.calibrate import calibrate
from gerry.export import (
    write_districts_json,
    write_shapes_json,
    write_sources_json,
    write_states_json,
)
from gerry.fetch import CENSUS_CD119, CENSUS_STATES, fetch, read_manifest
from gerry.generalize import absorb_fragments, simplify_to_census
from gerry.replacement import (
    check_audit_match,
    clip_to_land,
    coverage_gap,
    normalize_state_map,
    replace_states,
)
from gerry.scoring import score_districts
from gerry.state_audit import changed_states, read_state_audit, validate_state_audit
from gerry.state_maps import PENDING, STATE_MAPS, BlockAssignmentMap, StateMap, read_state_map
from gerry.validate import validate_districts

# pipeline/src/gerry/__main__.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
# Replacement districts may leave at most this share of a state's land uncovered.
MAX_COVERAGE_GAP = 0.005


def _read_plan(
    state_map: StateMap | BlockAssignmentMap, raw: Path, manifest: Path
) -> tuple[gpd.GeoDataFrame, str]:
    """Fetch one state's current map. Returns the plan and its district field name."""
    path = fetch(state_map.source, raw, manifest)
    if isinstance(state_map, StateMap):
        return read_state_map(path, state_map.member), state_map.district_field
    assignment = read_block_assignment(
        path, state_map.member, state_map.block_column, state_map.district_column
    )
    blocks = read_blocks(fetch(state_map.blocks, raw, manifest))
    return assemble_districts(blocks, assignment), "DISTRICT"


def _load_replacement(
    state_map: StateMap | BlockAssignmentMap, land: BaseGeometry, raw: Path, manifest: Path
) -> tuple[gpd.GeoDataFrame, list[str]]:
    """Fetch, normalize and clip one state's current map. Returns rows and problems."""
    plan, field = _read_plan(state_map, raw, manifest)
    rows = normalize_state_map(plan, state_map.state, field)
    # Same footing as Census districts: land only, no clipping slivers, Census-level detail.
    rows = simplify_to_census(absorb_fragments(clip_to_land(rows, land)))
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


def scores(repo_root: Path) -> int:
    """Score the built map and write the site's data files and data/build/scores.csv."""
    built = repo_root / "data" / "build" / "districts.gpkg"
    if not built.exists():
        print(f"{built.relative_to(repo_root)} not found. Run make boundaries first.")
        return 1
    data = repo_root / "data"
    land = load_state_outlines(fetch(CENSUS_STATES, data / "raw", data / "sources" / "sources.csv"))
    districts = gpd.read_file(built)
    table = score_districts(districts, land)
    site_data = repo_root / "site" / "src" / "data"
    write_districts_json(table, site_data / "districts.json")
    write_shapes_json(districts, site_data / "shapes.json")
    write_states_json(read_state_audit(data / "sources" / "states.csv"), site_data / "states.json")
    write_sources_json(read_manifest(data / "sources" / "sources.csv"), site_data / "sources.json")
    table.to_csv(built.parent / "scores.csv", index=False)
    ranked = table[~table["at_large"]].sort_values("rank_national")
    print(
        f"Scored {len(table)} districts ({len(ranked)} ranked, {table['at_large'].sum()} at-large)."
    )
    top = ", ".join(f"{r.district_id} ({r.irregularity})" for r in ranked.head(10).itertuples())
    print(f"Most irregular: {top}")
    print("Wrote site/src/data/ (districts, shapes, states, sources) and data/build/scores.csv")
    return 0


COMMANDS = {
    "boundaries": (boundaries, "Build and validate the 2026 district map."),
    "audit": (audit, "Validate the state map audit and list changed states."),
    "scores": (scores, "Score the built map and write the site's data."),
    "calibrate": (calibrate, "Re-derive the settings in gerry.generalize from Census files."),
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
