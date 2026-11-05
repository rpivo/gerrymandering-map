import zipfile

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from gerry.population import (
    GROUPS,
    assign_blocks,
    district_population,
    pl_source,
    population_problems,
    read_pl_blocks,
)

# PL 94-171 geoheader: 97 fields. Only these positions matter here (0-based).
SUMLEV, LOGRECNO, GEOCODE, POP100, LAT, LON = 2, 7, 9, 90, 92, 93


def geo_row(sumlev: str, logrecno: str, geocode: str, pop: int, lat: str, lon: str) -> str:
    fields = [""] * 97
    fields[0], fields[1] = "PLST", "WY"
    fields[SUMLEV], fields[LOGRECNO], fields[GEOCODE] = sumlev, logrecno, geocode
    fields[POP100], fields[LAT], fields[LON] = str(pop), lat, lon
    return "|".join(fields)


def seg2_row(logrecno: str, p4: list[int]) -> str:
    """Segment 2: five ID fields, P3 (71 counts), P4 (73), H1 (3)."""
    p3 = [0] * 71
    p4 = p4 + [0] * (73 - len(p4))
    return "|".join(["PLST", "WY", "000", "02", logrecno] + [str(n) for n in p3 + p4 + [0, 0, 0]])


# P4 order: total 18+, Hispanic, not Hispanic, not Hispanic one race, then white, Black,
# American Indian and Alaska Native, Asian, Native Hawaiian and Pacific Islander, some other
# race, two or more races, two races, then white and Black (index 12), white and AIAN, ...
BLOCK_A = [
    100,
    10,
    90,
    85,
    60,
    20,
    1,
    3,
    1,
    0,
    5,
    5,
    4,
    0,
    1,
]  # 4 white and Black, 1 white and Asian
BLOCK_B = [50, 30, 20, 20, 5, 10, 0, 5, 0]


def write_pl_zip(tmp_path) -> "pathlib.Path":  # noqa: F821
    geo = [
        geo_row("040", "0000001", "56", 150, "+43.0", "-107.5"),  # the state: not a block
        geo_row("750", "0000002", "560019627001000", 130, "+41.2997749", "-105.6110411"),
        geo_row("750", "0000003", "560019627001001", 70, "+41.3018774", "-105.6141790"),
    ]
    seg2 = [seg2_row("0000003", BLOCK_B), seg2_row("0000001", [150]), seg2_row("0000002", BLOCK_A)]
    path = tmp_path / "wy2020.pl.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("wygeo2020.pl", "\n".join(geo) + "\n")
        zf.writestr("wy000012020.pl", "")
        zf.writestr("wy000022020.pl", "\n".join(seg2) + "\n")
    return path


def test_pl_source_points_at_the_states_folder():
    source = pl_source("NY")
    assert source.id == "census-pl94171-2020-36"
    assert source.url.endswith("/New_York/ny2020.pl.zip")


def test_reads_only_blocks_and_joins_counts_by_record_number(tmp_path):
    blocks = read_pl_blocks(write_pl_zip(tmp_path)).set_index("geoid")
    assert list(blocks.index) == ["560019627001000", "560019627001001"]
    a = blocks.loc["560019627001000"]
    assert (a["pop"], a["vap"], a["hispanic"]) == (130, 100, 10)
    # White is white alone; the other groups count people of that race alone or with others.
    assert [a[g] for g in GROUPS[1:]] == [60, 24, 1, 4, 1]
    b = blocks.loc["560019627001001"]
    assert (b["pop"], b["vap"], b["nh_black"], b["nh_asian"]) == (70, 50, 10, 5)
    assert a["lat"] == pytest.approx(41.2997749) and a["lon"] == pytest.approx(-105.6110411)


def blocks_at(points: list[tuple[float, float]], pops: list[int], state: str = "WY"):
    rows = []
    for i, ((lon, lat), pop) in enumerate(zip(points, pops, strict=True)):
        rows.append({"geoid": f"b{i}", "state": state, "lat": lat, "lon": lon, "pop": pop,
                     "vap": pop, **{g: 0 for g in GROUPS}})  # fmt: skip
    return pd.DataFrame(rows)


def two_districts(state: str = "WY") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"district_id": [f"{state}-01", f"{state}-02"], "state": [state, state]},
        geometry=[box(-106, 41, -105, 42), box(-105, 41, -104, 42)],
        crs="EPSG:4269",
    )


class TestAssignBlocks:
    def test_places_each_block_in_the_district_containing_its_point(self):
        placed = assign_blocks(
            blocks_at([(-105.5, 41.5), (-104.5, 41.5)], [10, 20]), two_districts()
        )
        assert placed["district_id"].tolist() == ["WY-01", "WY-02"]
        assert placed["placed"].tolist() == ["inside", "inside"]

    def test_a_block_just_off_a_simplified_coast_goes_to_the_nearest_district(self):
        placed = assign_blocks(
            blocks_at([(-104.01, 41.5), (-103.99, 41.5)], [10, 20]), two_districts()
        )
        assert placed["district_id"].tolist() == ["WY-02", "WY-02"]
        assert placed["placed"].tolist() == ["inside", "nearest"]

    def test_nearest_stays_within_the_blocks_own_state(self):
        colorado = two_districts("CO")
        colorado["geometry"] = colorado.translate(xoff=0.01)  # CO-02 now covers the block
        districts = gpd.GeoDataFrame(pd.concat([two_districts("WY"), colorado]), crs="EPSG:4269")
        blocks = blocks_at([(-103.995, 41.5)], [5], state="WY")
        assert assign_blocks(blocks, districts)["district_id"].tolist() == ["WY-02"]

    def test_keeps_every_block(self):
        blocks = blocks_at([(-105.5, 41.5), (-90, 30)], [10, 0])
        assert len(assign_blocks(blocks, two_districts())) == 2


def test_district_population_adds_up_groups_and_the_minority_count():
    blocks = blocks_at([(-105.5, 41.5), (-105.4, 41.5), (-104.5, 41.5)], [100, 50, 70])
    blocks[GROUPS] = [[10, 60, 20, 1, 3, 1], [30, 5, 10, 0, 5, 0], [0, 70, 0, 0, 0, 0]]
    placed = assign_blocks(blocks, two_districts())
    placed.loc[1, "placed"] = "nearest"
    table = district_population(placed).set_index("district_id")
    one = table.loc["WY-01"]
    assert (one["pop"], one["vap"], one["hispanic"], one["nh_white"]) == (150, 150, 40, 65)
    assert one["minority"] == 150 - 65
    assert one["nearest_pop"] == 50
    assert one["state"] == "WY"
    assert table.loc["WY-02", "minority"] == 0


class TestPopulationProblems:
    def table(self, pops: dict[str, int]) -> pd.DataFrame:
        return pd.DataFrame(
            {"district_id": list(pops), "state": [d[:2] for d in pops], "pop": list(pops.values())}
        )

    def test_equal_districts_pass(self):
        assert (
            population_problems(
                self.table({"KS-01": 1000, "KS-02": 1010, "KS-03": 990, "KS-04": 1000})
            )
            == []
        )

    def test_a_district_off_the_average_is_reported(self):
        problems = population_problems(
            self.table({"KS-01": 985, "KS-02": 1045, "KS-03": 985, "KS-04": 985})
        )
        assert len(problems) == 1 and "KS-02" in problems[0] and "+4.5%" in problems[0]

    def test_a_missing_district_is_reported(self):
        problems = population_problems(self.table({"KS-01": 1000, "KS-02": 1000, "KS-03": 1000}))
        assert any("KS" in p and "3 of 4" in p for p in problems)
