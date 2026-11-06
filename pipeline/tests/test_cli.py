import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box
from test_state_audit import row

from gerry import __main__ as cli
from gerry.fetch import Source
from gerry.state_audit import COLUMNS
from gerry.state_maps import BlockAssignmentMap, StateMap
from gerry.states import STATES

ME_LAND = box(0, 0, 2, 1)
ME_SOURCE = Source("me-test-2026", "https://example.gov/me.zip", "Maine", "PD", "Test")
ME_BLOCKS = Source("census-blocks-test-23", "https://example.gov/b.zip", "Census", "PD", "Blocks")


def write_audit(repo_root: Path, rows: list[dict[str, str]]) -> None:
    path = repo_root / "data" / "sources" / "states.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(COLUMNS)] + [",".join(r[c] for c in COLUMNS) for r in rows]
    path.write_text("\n".join(lines) + "\n")


def audit_rows(changed: tuple[str, ...] = ()) -> list[dict[str, str]]:
    """All-unchanged audit rows, with the given states marked as changed for 2026."""
    rows = []
    for s in sorted(STATES, key=lambda s: s.usps):
        extra = (
            {"changed_since_2024": "yes", "first_used": "2026", "enacted": "2025-10-01"}
            if s.usps in changed
            else {}
        )
        rows.append(row(s.usps, **extra))
    return rows


def maine_plan(right_edge: float = 2.0) -> gpd.GeoDataFrame:
    """Maine's replacement file: two districts, extending 0.5 into the water."""
    return gpd.GeoDataFrame(
        {"CD": [1, 2]},
        geometry=[box(-0.5, -0.5, 1, 1.5), box(1, -0.5, right_edge, 1.5)],
        crs="EPSG:4269",
    )


@pytest.fixture
def fake_pipeline(monkeypatch, valid_districts, tmp_path):
    calls = {"fetched": [], "districts": valid_districts, "plan": maine_plan()}

    def fake_fetch(source, raw_dir, manifest):
        calls["fetched"].append((source.id, raw_dir, manifest))
        return Path(f"/fake/{source.id}.zip")

    monkeypatch.setattr(cli, "fetch", fake_fetch)
    monkeypatch.setattr(cli, "load_districts", lambda path: calls["districts"])
    monkeypatch.setattr(cli, "load_state_outlines", lambda path: {"ME": ME_LAND})
    monkeypatch.setattr(cli, "read_state_map", lambda path, member=None: calls["plan"])
    monkeypatch.setattr(cli, "STATE_MAPS", {})
    monkeypatch.setattr(cli, "PENDING", {})
    write_audit(tmp_path, audit_rows())
    return calls


def run(tmp_path) -> int:
    return cli.main(["boundaries", "--repo-root", str(tmp_path)])


def output(tmp_path) -> gpd.GeoDataFrame:
    return gpd.read_file(tmp_path / "data" / "build" / "districts.gpkg")


def test_boundaries_fetches_census_files_and_writes_the_map(fake_pipeline, tmp_path, capsys):
    assert run(tmp_path) == 0
    ids = [source_id for source_id, _, _ in fake_pipeline["fetched"]]
    assert ids == ["census-cd119-cb-2025-500k", "census-states-cb-2025-500k"]
    _, raw_dir, manifest = fake_pipeline["fetched"][0]
    assert raw_dir == tmp_path / "data" / "raw"
    assert manifest == tmp_path / "data" / "sources" / "sources.csv"
    out = capsys.readouterr().out
    assert "435 districts in 50 states" in out
    assert "Current maps swapped in: none" in out
    written = output(tmp_path)
    assert len(written) == 435
    assert set(written["map_source"]) == {"census-cd119-cb-2025-500k"}


def test_boundaries_swaps_in_registered_state_maps(fake_pipeline, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "STATE_MAPS", {"ME": StateMap("ME", ME_SOURCE, "CD")})
    write_audit(tmp_path, audit_rows(changed=("ME",)))
    assert run(tmp_path) == 0
    assert "Current maps swapped in: ME" in capsys.readouterr().out
    written = output(tmp_path)
    maine = written[written["state"] == "ME"].sort_values("district_id")
    assert list(maine["map_source"]) == ["me-test-2026"] * 2
    assert maine.geometry.iloc[0].hausdorff_distance(box(0, 0, 1, 1)) < 1e-9  # clipped to land
    assert len(written) == 435


def test_boundaries_generalizes_only_swapped_in_states(fake_pipeline, monkeypatch, tmp_path):
    steps = []

    def record(name):
        def step(districts, *args, **kwargs):
            steps.append((name, sorted(set(districts["state"]))))
            return districts

        return step

    monkeypatch.setattr(cli, "absorb_fragments", record("absorb"))
    monkeypatch.setattr(cli, "simplify_to_census", record("simplify"))
    monkeypatch.setattr(cli, "STATE_MAPS", {"ME": StateMap("ME", ME_SOURCE, "CD")})
    write_audit(tmp_path, audit_rows(changed=("ME",)))
    assert run(tmp_path) == 0
    assert steps == [("absorb", ["ME"]), ("simplify", ["ME"])]


def test_boundaries_names_pending_states_it_could_not_swap(
    fake_pipeline, monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(cli, "PENDING", {"ME": "No shapefile published yet."})
    write_audit(tmp_path, audit_rows(changed=("ME",)))
    assert run(tmp_path) == 0
    assert (
        "Still on 2024 lines (pending): ME. No shapefile published yet." in capsys.readouterr().out
    )
    written = output(tmp_path)
    assert set(written.loc[written["state"] == "ME", "map_source"]) == {"census-cd119-cb-2025-500k"}


def test_boundaries_fails_when_a_pending_state_is_unchanged(
    fake_pipeline, monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(cli, "PENDING", {"ME": "No shapefile published yet."})
    assert run(tmp_path) == 1
    assert "ME: marked pending but the audit says unchanged." in capsys.readouterr().out


def test_boundaries_builds_a_state_from_blocks(fake_pipeline, monkeypatch, tmp_path, capsys):
    blocks = gpd.GeoDataFrame(
        {"GEOID20": ["a", "b", "c", "d"], "ALAND20": [1, 1, 1, 1]},
        geometry=[box(0, 0, 0.5, 1), box(0.5, 0, 1, 1), box(1, 0, 1.5, 1), box(1.5, 0, 2, 1)],
        crs="EPSG:4269",
    )
    assignment = pd.Series({"a": "1", "b": "1", "c": "2", "d": "2"})
    seen = {}

    def fake_assignment(path, member, block_column, district_column):
        seen["assignment"] = (path, member, block_column, district_column)
        return assignment

    monkeypatch.setattr(cli, "read_block_assignment", fake_assignment)
    monkeypatch.setattr(cli, "read_blocks", lambda path: blocks)
    block_map = BlockAssignmentMap("ME", ME_SOURCE, "BAF.xlsx", "Block", "District", ME_BLOCKS)
    monkeypatch.setattr(cli, "STATE_MAPS", {"ME": block_map})
    write_audit(tmp_path, audit_rows(changed=("ME",)))
    assert run(tmp_path) == 0
    assert seen["assignment"] == (Path("/fake/me-test-2026.zip"), "BAF.xlsx", "Block", "District")
    fetched = [source_id for source_id, _, _ in fake_pipeline["fetched"]]
    assert "census-blocks-test-23" in fetched
    maine = output(tmp_path).query("state == 'ME'").sort_values("district_id")
    assert maine.geometry.iloc[0].hausdorff_distance(box(0, 0, 1, 1)) < 1e-9
    assert list(maine["map_source"]) == ["me-test-2026"] * 2


def test_boundaries_fails_when_a_replacement_leaves_land_uncovered(
    fake_pipeline, monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(cli, "STATE_MAPS", {"ME": StateMap("ME", ME_SOURCE, "CD")})
    write_audit(tmp_path, audit_rows(changed=("ME",)))
    fake_pipeline["plan"] = maine_plan(right_edge=1.5)
    assert run(tmp_path) == 1
    assert "ME: districts leave 25.0% of the state's land uncovered" in capsys.readouterr().out
    assert not (tmp_path / "data" / "build" / "districts.gpkg").exists()


def test_boundaries_fails_when_the_audit_and_registry_disagree(fake_pipeline, tmp_path, capsys):
    write_audit(tmp_path, audit_rows(changed=("ME",)))
    assert run(tmp_path) == 1
    assert "ME: changed since 2024 but no replacement map is registered." in capsys.readouterr().out


def test_boundaries_fails_and_lists_problems(fake_pipeline, valid_districts, tmp_path, capsys):
    fake_pipeline["districts"] = valid_districts[valid_districts["state"] != "WY"]
    assert run(tmp_path) == 1
    out = capsys.readouterr().out
    assert "WY: 0 districts, expected 1." in out
    assert "435 districts in 50 states" not in out


def test_audit_lists_changed_and_unclear_states(tmp_path, capsys):
    rows = audit_rows(changed=("TX",))
    rows = [
        row("UT", changed_since_2024="unclear", confidence="low", notes="Pending")
        if r["state"] == "UT"
        else r
        for r in rows
    ]
    write_audit(tmp_path, rows)
    assert cli.main(["audit", "--repo-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "50 states audited" in out
    assert "Changed since 2024 (1): TX" in out
    assert "Unclear (1): UT" in out


def test_audit_fails_on_problems(tmp_path, capsys):
    write_audit(tmp_path, [row("TX")])
    assert cli.main(["audit", "--repo-root", str(tmp_path)]) == 1
    assert "WY: missing." in capsys.readouterr().out


def test_default_repo_root_is_the_repository():
    assert (cli.REPO_ROOT / "CLAUDE.md").exists()


def test_scores_writes_site_json_and_csv(valid_districts, monkeypatch, tmp_path, capsys):
    fetched = []
    monkeypatch.setattr(cli, "fetch", lambda source, *a: fetched.append(source.id) or Path("/f"))
    outlines = {s: g.buffer(0.01) for s, g in valid_districts.dissolve("state").geometry.items()}
    monkeypatch.setattr(cli, "load_state_outlines", lambda path: outlines)
    real_score, seen = cli.score_districts, {}

    def spy(districts, land=None):
        seen["land"] = land
        return real_score(districts, land)

    monkeypatch.setattr(cli, "score_districts", spy)
    build = tmp_path / "data" / "build"
    build.mkdir(parents=True)
    valid_districts.assign(map_source="census-cd119-cb-2025-500k").to_file(build / "districts.gpkg")
    write_audit(tmp_path, audit_rows())
    assert cli.main(["scores", "--repo-root", str(tmp_path)]) == 0
    site_data = tmp_path / "site" / "src" / "data"
    shapes = json.loads((site_data / "shapes.json").read_text())
    assert len(shapes["districts"]) == 435 and len(shapes["states"]) == 50
    us = json.loads((site_data / "us-map.json").read_text())
    assert len(us["paths"]) == 50 and len(us["labels"]) == 50
    assert json.loads((site_data / "states.json").read_text())["count"] == 50
    data = json.loads((tmp_path / "site" / "src" / "data" / "districts.json").read_text())
    assert data["count"] == 435
    scored = [d for d in data["districts"] if not d["at_large"]]
    assert len(scored) == 429
    assert sorted(d["rank_national"] for d in scored) == list(range(1, 430))
    assert len(pd.read_csv(build / "scores.csv")) == 435
    out = capsys.readouterr().out
    assert "Scored 435 districts (429 ranked, 6 at-large)." in out
    assert "Most irregular:" in out
    assert fetched == ["census-states-cb-2025-500k"]
    assert seen["land"] is outlines


def test_scores_needs_the_built_map_first(tmp_path, capsys):
    assert cli.main(["scores", "--repo-root", str(tmp_path)]) == 1
    assert "make boundaries" in capsys.readouterr().out


VOTES_HEADER = (
    "precinct,office,party_simplified,mode,votes,county_fips,jurisdiction_fips,district,state_po,"
    "party_detailed,candidate\n"
)


def write_votes_repo(tmp_path: Path, tx_harris: int) -> Path:
    """A repo with tiny precinct files (TX and WA, two districts each) and a TX reference."""
    pres = (
        VOTES_HEADER
        + "".join(
            f"{st}{d},US PRESIDENT,{party},TOTAL,{v},{c},{c},STATEWIDE,{st},{party},\n"
            for st, c in (("TX", "48001"), ("WA", "53001"))
            for d in (1, 2)
            for party, v in (("DEMOCRAT", 60 * d), ("REPUBLICAN", 40))
        )
        + "WY1,US PRESIDENT,DEMOCRAT,TOTAL,9,56001,56001,STATEWIDE,WY,DEMOCRAT,\n"
    )
    house = VOTES_HEADER + "".join(
        f"{st}{d},US HOUSE,DEMOCRAT,TOTAL,5,{c},{c},00{d},{st},DEMOCRAT,\n"
        for st, c in (("TX", "48001"), ("WA", "53001"))
        for d in (1, 2)
    )
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "pres.csv").write_text(pres)
    (raw / "house.csv").write_text(house)
    (raw / "kc.csv").write_text(
        "Precinct,Race,LegislativeDistrict,CountyCouncil,CongressionalDistrict,CounterGroup,"
        "CounterType,SumOfCount\n"
        "SEA 1,President and Vice President,37,2,1,Total,Kamala D. Harris / Tim Walz,6\n"
    )
    votes = tmp_path / "data" / "sources" / "votes"
    votes.mkdir(parents=True)
    (votes / "nj-2024-president-by-county.csv").write_text(
        "state,county_fips,county,harris,trump\n"
    )
    (votes / "tx-planc2333-president-2024.csv").write_text(
        "state,district,harris,trump\nTX,1,30,70\n"
    )
    (votes / "nc-s249-president-2024.csv").write_text("state,district,harris,trump\n")
    checks = tmp_path / "data" / "checks"
    checks.mkdir(parents=True)
    (checks / "tx-planc2193-president-2024.csv").write_text(
        f"district,harris,trump\n1,{tx_harris},40\n2,120,40\n"
    )
    write_audit(tmp_path, audit_rows(changed=("TX", "NC")))
    return raw


def fake_votes_fetch(raw: Path):
    def fetch(source, *_args, **_kwargs):
        if "king-county" in source.id:
            return raw / "kc.csv"
        return raw / ("pres.csv" if "president" in source.id else "house.csv")

    return fetch


def test_votes_writes_unchanged_states_and_checks_texas(tmp_path, monkeypatch, capsys):
    raw = write_votes_repo(tmp_path, tx_harris=60)
    monkeypatch.setattr(cli, "fetch", fake_votes_fetch(raw))
    assert cli.main(["votes", "--repo-root", str(tmp_path)]) == 0
    out = pd.read_csv(tmp_path / "data" / "build" / "president-2024-by-district.csv")
    # Texas redrew, so its precinct join (on the 2024 map) is only for the check; its official
    # report is used. Wyoming's one at-large district is the whole state.
    assert sorted(out["state"].unique()) == ["TX", "WA", "WY"]
    wy = out[out["state"] == "WY"]
    assert wy[["district", "dem", "rep", "method"]].values.tolist() == [[0, 9, 0, "statewide"]]
    wa = out[out["state"] == "WA"]
    # King County's one precinct (6 Harris votes, district 1) joins WA's other precincts.
    assert wa[["district", "dem", "rep"]].values.tolist() == [[1, 66, 40], [2, 120, 40]]
    assert set(wa["method"]) == {"precinct join"}
    tx = out[out["state"] == "TX"]
    assert tx[["district", "dem", "rep", "method"]].values.tolist() == [
        [1, 30, 70, "official report"]
    ]
    printed = capsys.readouterr().out
    assert "Texas check passed" in printed
    assert "WY" not in printed


def test_votes_fails_when_texas_stops_matching_the_official_report(tmp_path, monkeypatch, capsys):
    raw = write_votes_repo(tmp_path, tx_harris=10)
    monkeypatch.setattr(cli, "fetch", fake_votes_fetch(raw))
    assert cli.main(["votes", "--repo-root", str(tmp_path)]) == 1
    assert "TX-01" in capsys.readouterr().out


def test_votes_refuses_an_official_report_for_a_state_that_kept_its_lines(
    tmp_path, monkeypatch, capsys
):
    raw = write_votes_repo(tmp_path, tx_harris=60)
    write_audit(tmp_path, audit_rows())  # Texas not marked as redrawn
    monkeypatch.setattr(cli, "fetch", fake_votes_fetch(raw))
    assert cli.main(["votes", "--repo-root", str(tmp_path)]) == 1
    assert "TX" in capsys.readouterr().out


def test_fairness_scores_states_from_the_votes_output(tmp_path, capsys):
    build = tmp_path / "data" / "build"
    build.mkdir(parents=True)
    sources = tmp_path / "data" / "sources"
    sources.mkdir()
    (sources / "states.csv").write_text((cli.REPO_ROOT / "data/sources/states.csv").read_text())
    rows = ["state,district,dem,rep,dem_share,method"]
    rows += [
        f"AR,{d},{v},{100 - v},{v / 100},precinct join" for d, v in enumerate([90, 45, 45, 45], 1)
    ]
    rows += ["NH,1,50,50,0.5,official report", "NH,2,60,40,0.6,official report"]
    (build / "president-2024-by-district.csv").write_text("\n".join(rows) + "\n")
    assert cli.main(["fairness", "--repo-root", str(tmp_path)]) == 0
    out = pd.read_csv(build / "fairness-2024.csv")
    assert out["state"].tolist() == ["AR"]
    site = json.loads((tmp_path / "site/src/data/fairness.json").read_text())
    by_state = {r["state"]: r for r in site["states"]}
    assert len(by_state) == 50
    assert by_state["AR"]["status"] == "scored"
    assert by_state["AR"]["efficiency_gap"] == pytest.approx(out.loc[0, "efficiency_gap"], abs=1e-4)
    assert by_state["NH"]["status"] == "too_few_districts"
    assert "AR" in capsys.readouterr().out
    # Each district's own result, for its page.
    president = json.loads((tmp_path / "site/src/data/president-2024.json").read_text())
    assert president["districts"]["NH-02"] == {
        "harris": 0.6,
        "trump": 0.4,
        "method": "official report",
    }
    assert len(president["districts"]) == 6


def test_fairness_asks_for_the_votes_first(tmp_path, capsys):
    assert cli.main(["fairness", "--repo-root", str(tmp_path)]) == 1
    assert "make votes" in capsys.readouterr().out


@pytest.fixture(autouse=True)
def no_zcta_file(monkeypatch):
    """Commands that place blocks read the national ZCTA file; tests give them none."""
    monkeypatch.setattr(
        cli, "read_zcta_blocks", lambda path: pd.DataFrame({"block": [], "zcta": []})
    )


def test_population_places_census_blocks_in_the_built_districts(tmp_path, monkeypatch, capsys):
    from shapely.geometry import box as shape_box
    from test_population import write_pl_zip

    from gerry.states import STATES_BY_USPS

    build = tmp_path / "data" / "build"
    build.mkdir(parents=True)
    gpd.GeoDataFrame(
        {"district_id": ["WY-AL"], "state": ["WY"], "number": [None], "map_source": ["x"]},
        geometry=[shape_box(-106, 41, -105, 42)],
        crs="EPSG:4269",
    ).to_file(build / "districts.gpkg")
    pl_zip = write_pl_zip(tmp_path)
    fetched = []

    def fake_fetch(source, raw, manifest):
        fetched.append(source.id)
        return pl_zip

    monkeypatch.setattr(cli, "fetch", fake_fetch)
    monkeypatch.setattr(cli, "STATES", [STATES_BY_USPS["WY"]])
    zctas = pd.DataFrame({"block": [560019627001000, 560019627001001], "zcta": [82070, 82072]})
    monkeypatch.setattr(cli, "read_zcta_blocks", lambda path: zctas)
    assert cli.main(["population", "--repo-root", str(tmp_path)]) == 0
    assert fetched == ["census-zcta520-tabblock20", "census-pl94171-2020-56"]
    zips = json.loads((tmp_path / "site/src/data/zips.json").read_text())
    assert zips["districts"] == {"WY-AL": [["82070", 1], ["82072", 1]]}
    table = pd.read_csv(build / "population-by-district.csv")
    assert table["district_id"].tolist() == ["WY-AL"]
    assert (table.loc[0, "pop"], table.loc[0, "vap"], table.loc[0, "minority"]) == (200, 150, 85)
    assert "WY-AL" not in capsys.readouterr().out  # no problems to report
    site = json.loads((tmp_path / "site/src/data/population.json").read_text())
    assert [r["id"] for r in site["districts"]] == ["WY-AL"]
    assert site["districts"][0]["minority"] == round(85 / 150, 3)


def test_population_writes_no_site_data_when_a_check_fails(tmp_path, monkeypatch):
    from shapely.geometry import box as shape_box
    from test_population import write_pl_zip

    from gerry.states import STATES_BY_USPS

    build = tmp_path / "data" / "build"
    build.mkdir(parents=True)
    # Kansas has 4 districts, so a single one fails the district count check.
    gpd.GeoDataFrame(
        {"district_id": ["KS-01"], "state": ["KS"], "number": [1], "map_source": ["x"]},
        geometry=[shape_box(-106, 41, -105, 42)],
        crs="EPSG:4269",
    ).to_file(build / "districts.gpkg")
    monkeypatch.setattr(cli, "fetch", lambda source, raw, manifest: write_pl_zip(tmp_path))
    monkeypatch.setattr(cli, "STATES", [STATES_BY_USPS["KS"]])
    assert cli.main(["population", "--repo-root", str(tmp_path)]) == 1
    assert (build / "population-by-district.csv").exists()
    assert not (tmp_path / "site/src/data/population.json").exists()


def _places_run(tmp_path, monkeypatch, abbeville_pop: int) -> int:
    from shapely.geometry import box as shape_box
    from test_places import geo_row, write_zip

    from gerry.states import STATES_BY_USPS

    build = tmp_path / "data" / "build"
    build.mkdir(parents=True)
    gpd.GeoDataFrame(
        {"district_id": ["WY-AL"], "state": ["WY"], "number": [None], "map_source": ["x"]},
        geometry=[shape_box(-92, 29, -90, 31)],
        crs="EPSG:4269",
    ).to_file(build / "districts.gpkg")
    pl_zip = write_zip(tmp_path, [
        geo_row("160", "0000001", "00100", abbeville_pop, "Abbeville", "Abbeville city"),
        geo_row("750", "0000002", "00100", 20),
        geo_row("750", "0000003", "99999", 5),
    ])  # fmt: skip
    monkeypatch.setattr(cli, "fetch", lambda source, raw, manifest: pl_zip)
    monkeypatch.setattr(cli, "STATES", [STATES_BY_USPS["WY"]])
    return cli.main(["population", "--repo-root", str(tmp_path)])


def test_population_lists_the_places_in_each_district(tmp_path, monkeypatch):
    assert _places_run(tmp_path, monkeypatch, abbeville_pop=20) == 0
    site = json.loads((tmp_path / "site/src/data/places.json").read_text())
    assert site["districts"] == [{
        "id": "WY-AL",
        "places": [{"name": "Abbeville", "kind": "city", "pop": 20, "place_pop": 20}],
        "more": 0,
        "in_places": 0.8,
    }]  # fmt: skip
    table = pd.read_csv(tmp_path / "data/build/places-by-district.csv", dtype={"place": str})
    assert table[["district_id", "place", "pop"]].values.tolist() == [["WY-AL", "00100", 20]]


def test_population_writes_no_site_data_when_places_dont_add_up(tmp_path, monkeypatch, capsys):
    assert _places_run(tmp_path, monkeypatch, abbeville_pop=21) == 1
    assert "Abbeville" in capsys.readouterr().out
    assert not (tmp_path / "site/src/data/places.json").exists()
    assert not (tmp_path / "site/src/data/population.json").exists()


def test_population_asks_for_the_built_map_first(tmp_path, capsys):
    assert cli.main(["population", "--repo-root", str(tmp_path)]) == 1
    assert "make boundaries" in capsys.readouterr().out
