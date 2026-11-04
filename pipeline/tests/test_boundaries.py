import geopandas as gpd
import pytest
from shapely.geometry import box

from gerry.boundaries import district_id, load_districts, normalize_districts


def raw(rows: list[tuple[str, str]], column: str = "CD119FP") -> gpd.GeoDataFrame:
    """Census-shaped rows of (STATEFP, district code), one unit square each."""
    return gpd.GeoDataFrame(
        {
            "STATEFP": [s for s, _ in rows],
            column: [c for _, c in rows],
            "NAMELSAD": ["x"] * len(rows),
            "geometry": [box(i, 0, i + 1, 1) for i in range(len(rows))],
        },
        crs="EPSG:4269",
    )


class TestDistrictId:
    def test_numbered_district_is_zero_padded(self):
        assert district_id("CA", "07") == "CA-07"
        assert district_id("TX", "35") == "TX-35"

    def test_census_code_00_is_at_large(self):
        assert district_id("WY", "00") == "WY-AL"

    @pytest.mark.parametrize("code", ["98", "ZZ", "", "7", "100"])
    def test_rejects_non_district_codes(self, code):
        with pytest.raises(ValueError, match="district code"):
            district_id("TX", code)


class TestNormalizeDistricts:
    def test_keeps_states_and_drops_dc_and_territories(self):
        gdf = normalize_districts(raw([("48", "35"), ("11", "98"), ("72", "98"), ("56", "00")]))
        assert list(gdf["district_id"]) == ["TX-35", "WY-AL"]

    def test_output_columns_types_and_order(self):
        gdf = normalize_districts(raw([("56", "00"), ("06", "07"), ("06", "52")]))
        assert list(gdf.columns) == ["district_id", "state", "number", "geometry"]
        assert list(gdf["district_id"]) == ["CA-07", "CA-52", "WY-AL"]
        assert list(gdf["state"]) == ["CA", "CA", "WY"]
        assert gdf["number"].tolist()[:2] == [7, 52]
        assert gdf["number"].isna().tolist() == [False, False, True]
        assert str(gdf["number"].dtype) == "Int64"
        assert list(gdf.index) == [0, 1, 2]

    def test_keeps_geometry_and_crs(self):
        source = raw([("48", "01")])
        gdf = normalize_districts(source)
        assert gdf.crs == source.crs
        assert gdf.geometry.iloc[0].equals(source.geometry.iloc[0])

    def test_finds_the_district_column_for_other_congresses(self):
        gdf = normalize_districts(raw([("48", "01")], column="CD120FP"))
        assert list(gdf["district_id"]) == ["TX-01"]

    def test_fails_without_a_district_column(self):
        with pytest.raises(ValueError, match="district column"):
            normalize_districts(raw([("48", "01")], column="DISTRICT"))

    def test_fails_on_unexpected_district_code_in_a_state(self):
        with pytest.raises(ValueError, match="district code"):
            normalize_districts(raw([("48", "ZZ")]))


def test_load_districts_reads_a_file_and_normalizes(tmp_path):
    path = tmp_path / "districts.gpkg"
    raw([("48", "02"), ("11", "98")]).to_file(path)
    gdf = load_districts(path)
    assert list(gdf["district_id"]) == ["TX-02"]
