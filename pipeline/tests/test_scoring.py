import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon, box

from gerry.scoring import score_districts


def at(lon: float, lat: float, shape: str):
    """A small district shape near (lon, lat): round, square, or an L with a bite."""
    if shape == "round":
        return Point(lon, lat).buffer(0.1, quad_segs=64)
    if shape == "square":
        return box(lon - 0.1, lat - 0.1, lon + 0.1, lat + 0.1)
    s = 0.1
    return Polygon(
        [(lon, lat), (lon + 2 * s, lat), (lon + 2 * s, lat + s), (lon + s, lat + s),
         (lon + s, lat + 2 * s), (lon, lat + 2 * s)]
    )  # fmt: skip


def districts(rows) -> gpd.GeoDataFrame:
    """Rows of (district_id, number or None, shape name)."""
    return gpd.GeoDataFrame(
        {
            "district_id": [r[0] for r in rows],
            "state": [r[0][:2] for r in rows],
            "number": pd.array([r[1] for r in rows], dtype="Int64"),
            "map_source": "census",
        },
        geometry=[at(-100 + 2 * i, 41, r[2]) for i, r in enumerate(rows)],
        crs="EPSG:4269",
    )


def test_two_districts_give_percentiles_of_50_and_100():
    scores = score_districts(districts([("ME-01", 1, "round"), ("ME-02", 2, "L")]))
    by_id = scores.set_index("district_id")
    for metric in ["polsby_popper", "reock", "convex_hull"]:
        assert by_id.loc["ME-01", f"{metric}_pct"] == pytest.approx(100)
        assert by_id.loc["ME-02", f"{metric}_pct"] == pytest.approx(50)
    assert by_id.loc["ME-01", "irregularity"] == 0
    assert by_id.loc["ME-02", "irregularity"] == 50


def test_less_compact_districts_score_more_irregular():
    scores = score_districts(
        districts([("NE-01", 1, "round"), ("NE-02", 2, "square"), ("NE-03", 3, "L")])
    ).set_index("district_id")
    assert scores.loc["NE-03", "irregularity"] > scores.loc["NE-02", "irregularity"]
    assert scores.loc["NE-02", "irregularity"] > scores.loc["NE-01", "irregularity"]


def test_raw_metrics_and_schwartzberg_are_included():
    scores = score_districts(districts([("ME-01", 1, "square"), ("ME-02", 2, "L")]))
    square = scores.set_index("district_id").loc["ME-01"]
    assert square["convex_hull"] == pytest.approx(1, abs=1e-6)
    assert square["schwartzberg"] == pytest.approx(1 / square["polsby_popper"] ** 0.5)


def test_at_large_districts_are_measured_but_not_ranked_or_compared():
    scores = score_districts(
        districts([("ME-01", 1, "round"), ("ME-02", 2, "L"), ("WY-AL", None, "L")])
    ).set_index("district_id")
    wy = scores.loc["WY-AL"]
    assert bool(wy["at_large"])
    assert wy["polsby_popper"] > 0
    for column in ["polsby_popper_pct", "irregularity", "rank_national", "rank_state"]:
        assert pd.isna(wy[column])
    # WY's L shape doesn't count toward anyone's percentile.
    assert scores.loc["ME-02", "irregularity"] == 50


def test_ranks_run_from_most_irregular_nationally_and_within_each_state():
    scores = score_districts(
        districts(
            [
                ("ME-01", 1, "round"),
                ("ME-02", 2, "L"),
                ("NH-01", 1, "square"),
                ("NH-02", 2, "round"),
            ]
        )
    ).set_index("district_id")
    assert scores["rank_national"].astype(int).sort_values().tolist() == [1, 2, 3, 4]
    assert scores.loc["ME-02", "rank_national"] == 1
    assert scores.loc["ME-02", "rank_state"] == 1
    assert scores.loc["ME-01", "rank_state"] == 2
    assert scores.loc["NH-01", "rank_state"] == 1


def test_ties_are_broken_by_district_id():
    scores = score_districts(
        # Listed out of order, so a stable sort can't produce the right order by luck.
        districts([("ME-02", 2, "square"), ("ME-01", 1, "square"), ("NH-01", 1, "L")])
    ).set_index("district_id")
    assert scores.loc["ME-01", "irregularity"] == scores.loc["ME-02", "irregularity"]
    assert scores.loc["ME-01", "rank_national"] < scores.loc["ME-02", "rank_national"]


def test_output_is_one_row_per_district_sorted_with_map_source_kept():
    scores = score_districts(districts([("ME-02", 2, "L"), ("ME-01", 1, "round")]))
    assert list(scores["district_id"]) == ["ME-01", "ME-02"]
    assert list(scores["map_source"]) == ["census", "census"]
    assert "geometry" not in scores.columns
