"""Command line entry point: `python -m gerry <command>`.

Commands:
    boundaries  Build the map in effect for 2026: the Census 2024 districts with the
                redrawn states swapped in, validated, written to data/build/.
    audit       Validate data/sources/states.csv and list states with new 2026 maps.
    scores      Score the built map; write site/src/data/districts.json.
    calibrate   Re-derive the map generalization settings from Census files.
    votes       Place 2024 presidential votes in districts; write data/build/.
    fairness    Score each state's map for partisan fairness from the votes.
    population  Add up 2020 voting-age population by race per district; write data/build/.
"""

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry.base import BaseGeometry

from gerry.blocks import assemble_districts, read_block_assignment, read_blocks
from gerry.boundaries import load_districts, load_state_outlines
from gerry.calibrate import calibrate
from gerry.export import (
    write_districts_json,
    write_fairness_json,
    write_shapes_json,
    write_sources_json,
    write_states_json,
)
from gerry.fairness import MIN_DISTRICTS, state_fairness
from gerry.fetch import CENSUS_CD119, CENSUS_STATES, fetch, read_manifest
from gerry.generalize import absorb_fragments, simplify_to_census
from gerry.population import (
    assign_blocks,
    district_population,
    pl_source,
    population_problems,
    read_pl_blocks,
)
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
from gerry.states import STATES
from gerry.validate import validate_districts
from gerry.votes import (
    HOUSE_2024,
    KING_COUNTY_2024,
    OFFICIAL_RESULTS,
    PRESIDENT_2024,
    assign_to_districts,
    calibrate_to_county_totals,
    check_reference,
    district_totals,
    district_weights,
    drop_aggregate_rows,
    one_count_per_precinct,
    read_king_county,
    read_official_results,
    read_precinct_returns,
    replace_county,
    state_quality,
    two_party_by_precinct,
    unopposed_districts,
)

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


# The join must reproduce Texas's official 2024 results to within this many points.
TX_CHECK_TOLERANCE_PTS = 0.1
# States with more than this share of votes in catch-all rows, or any lost votes, need a fix.
MAX_BIG_ROW_PCT = 2.0


def _place_president_2024(raw: Path, manifest: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join the MIT precinct files. Returns per-district totals and per-state quality."""
    pres, house = (
        drop_aggregate_rows(one_count_per_precinct(read_precinct_returns(fetch(s, raw, manifest))))
        for s in (PRESIDENT_2024, HOUSE_2024)
    )
    two, weights = two_party_by_precinct(pres), district_weights(house)
    # King County is one county-wide row in MIT's file; its own file has every precinct.
    king = read_king_county(fetch(KING_COUNTY_2024, raw, manifest))
    two, weights = replace_county(two, weights, *king)
    # MIT's New Jersey counts are short in some counties (Mercer has no early votes).
    nj = manifest.parent / "votes" / "nj-2024-president-by-county.csv"
    two = calibrate_to_county_totals(two, pd.read_csv(nj, dtype={"county_fips": str}))
    assigned = assign_to_districts(two, weights, unopposed_districts(weights))
    return district_totals(assigned), state_quality(assigned)


def votes(repo_root: Path) -> int:
    """Place 2024 presidential votes in districts for states that kept their 2024 lines."""
    data = repo_root / "data"
    totals, quality = _place_president_2024(data / "raw", data / "sources" / "sources.csv")
    reference = pd.read_csv(data / "checks" / "tx-planc2193-president-2024.csv")
    problems = check_reference(totals, "TX", reference, TX_CHECK_TOLERANCE_PTS)
    if problems:
        _print_problems(
            problems, " in the Texas check (2024 map vs the Legislative Council report)"
        )
        return 1
    print(
        f"Texas check passed: all {len(reference)} districts within "
        f"{TX_CHECK_TOLERANCE_PTS} points."
    )
    redrawn = set(changed_states(read_state_audit(data / "sources" / "states.csv"))["yes"])
    # Redrawn states' precincts carry their 2024 districts; at-large states (and DC) have no lines.
    lined = {s.usps for s in STATES if s.seats > 1} - redrawn
    # An official report replaces the precinct join, which only works on unchanged lines.
    both = sorted(set(OFFICIAL_RESULTS) & lined)
    if both:
        _print_problems([f"{s}: has an official report but kept its 2024 lines." for s in both])
        return 1
    keep = totals["state"].isin(lined)
    votes_dir = data / "sources" / "votes"
    official = [read_official_results(votes_dir / name) for name in OFFICIAL_RESULTS.values()]
    out = data / "build" / "president-2024-by-district.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([totals[keep], *official], ignore_index=True).to_csv(out, index=False)
    quality = quality[quality["state"].isin(lined)]
    quality.to_csv(out.with_name("president-2024-quality.csv"), index=False)
    shaky = quality[(quality["big_row_pct"] > MAX_BIG_ROW_PCT) | (quality["lost_pct"] > 0)]
    print(
        f"{keep.sum()} districts in {totals[keep]['state'].nunique()} states kept their 2024 lines."
    )
    print(f"Official reports for redrawn states: {', '.join(OFFICIAL_RESULTS)}.")
    for r in shaky.itertuples():
        print(
            f"Needs a fix: {r.state}, {r.big_row_pct}% in catch-all rows, {r.lost_pct}% unplaced."
        )
    print(f"Wrote {out.relative_to(repo_root)} and its quality report")
    return 0


def fairness(repo_root: Path) -> int:
    """Score partisan fairness per state from data/build/president-2024-by-district.csv."""
    build = repo_root / "data" / "build"
    votes_csv = build / "president-2024-by-district.csv"
    if not votes_csv.exists():
        print(f"{votes_csv.relative_to(repo_root)} not found. Run make votes first.")
        return 1
    table = state_fairness(pd.read_csv(votes_csv))
    out = build / "fairness-2024.csv"
    table.to_csv(out, index=False)
    site_json = repo_root / "site" / "src" / "data" / "fairness.json"
    write_fairness_json(table, read_state_audit(repo_root / "data/sources/states.csv"), site_json)
    shown = table.sort_values("efficiency_gap", key=abs, ascending=False)
    print(
        f"Scored {len(table)} states with {MIN_DISTRICTS}+ districts. Positive favors Republicans."
    )
    print(shown[["state", "districts", "dem_seats", "efficiency_gap", "mean_median", "declination"]]
          .round(3).to_string(index=False))  # fmt: skip
    print(f"Wrote {out.relative_to(repo_root)} and {site_json.relative_to(repo_root)}")
    return 0


def population(repo_root: Path) -> int:
    """Add up 2020 voting-age population by race in each built district (gerry.population)."""
    build = repo_root / "data" / "build"
    built = build / "districts.gpkg"
    if not built.exists():
        print(f"{built.relative_to(repo_root)} not found. Run make boundaries first.")
        return 1
    districts = gpd.read_file(built).to_crs("EPSG:4269")
    raw, manifest = repo_root / "data" / "raw", repo_root / "data" / "sources" / "sources.csv"
    tables = []
    for state in STATES:
        blocks = read_pl_blocks(fetch(pl_source(state.usps), raw, manifest))
        blocks["state"] = state.usps
        tables.append(district_population(assign_blocks(blocks, districts)))
    table = pd.concat(tables, ignore_index=True)
    out = build / "population-by-district.csv"
    table.to_csv(out, index=False)
    problems = population_problems(table)
    if problems:
        _print_problems(problems, " in the 2020 population check")
    nearest = table["nearest_pop"].sum() / table["pop"].sum()
    print(f"Placed {table['pop'].sum():,} people in {len(table)} districts "
          f"({nearest:.3%} by nearest district). Wrote {out.relative_to(repo_root)}")  # fmt: skip
    return 1 if problems else 0


COMMANDS = {
    "boundaries": (boundaries, "Build and validate the 2026 district map."),
    "audit": (audit, "Validate the state map audit and list changed states."),
    "scores": (scores, "Score the built map and write the site's data."),
    "calibrate": (calibrate, "Re-derive the settings in gerry.generalize from Census files."),
    "votes": (votes, "Place 2024 presidential votes in districts."),
    "fairness": (fairness, "Score each state's map for partisan fairness."),
    "population": (population, "Add up 2020 voting-age population by race per district."),
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
