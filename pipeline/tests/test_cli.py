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
