import zipfile

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from gerry.blocks import assemble_districts, read_block_assignment, read_blocks


def blocks_frame(ids, land=None) -> gpd.GeoDataFrame:
    """Unit-square blocks in a row, with land area 1 unless given."""
    return gpd.GeoDataFrame(
        {"GEOID20": ids, "ALAND20": land or [1] * len(ids)},
        geometry=[box(i, 0, i + 1, 1) for i in range(len(ids))],
        crs="EPSG:4269",
    )


class TestReadBlockAssignment:
    def write_xlsx_zip(self, tmp_path, frame: pd.DataFrame):
        xlsx = tmp_path / "baf.xlsx"
        frame.to_excel(xlsx, index=False)
        path = tmp_path / "plan.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.write(xlsx, "Plan BAF.xlsx")
            zf.writestr("Plan Map.pdf", b"%PDF")
        return path

    def test_reads_an_xlsx_inside_a_zip_keeping_leading_zeros(self, tmp_path):
        frame = pd.DataFrame({"Block": ["010010201001000", "010010201001001"], "District": [1, 2]})
        path = self.write_xlsx_zip(tmp_path, frame)
        assignment = read_block_assignment(path, "Plan BAF.xlsx", "Block", "District")
        assert assignment.to_dict() == {"010010201001000": "1", "010010201001001": "2"}

    def test_reads_a_headerless_csv(self, tmp_path):
        path = tmp_path / "baf.csv"
        path.write_text('"390010001001000","3"\n"390010001001001","14"\n')
        assignment = read_block_assignment(path, None, 0, 1)
        assert assignment.to_dict() == {"390010001001000": "3", "390010001001001": "14"}

    def test_strips_padding_around_values(self, tmp_path):
        path = tmp_path / "baf.csv"
        path.write_text('" 390010001001000 "," 3 "\n')
        assert read_block_assignment(path, None, 0, 1).to_dict() == {"390010001001000": "3"}

    def test_rejects_a_block_assigned_twice(self, tmp_path):
        path = tmp_path / "baf.csv"
        path.write_text("390010001001000,3\n390010001001000,4\n")
        with pytest.raises(ValueError, match="more than once"):
            read_block_assignment(path, None, 0, 1)

    def test_rejects_ids_that_are_not_15_digit_block_geoids(self, tmp_path):
        path = tmp_path / "baf.csv"
        path.write_text("39001000100100,3\n")
        with pytest.raises(ValueError, match="15-digit"):
            read_block_assignment(path, None, 0, 1)


def test_read_blocks_keeps_only_the_id_land_area_and_shape(tmp_path):
    path = tmp_path / "blocks.gpkg"
    blocks_frame(["1", "2"]).assign(NAME20=["a", "b"]).to_file(path)
    blocks = read_blocks(path)
    assert list(blocks.columns) == ["GEOID20", "ALAND20", "geometry"]
    assert len(blocks) == 2


class TestAssembleDistricts:
    def test_merges_blocks_into_one_shape_per_district(self):
        blocks = blocks_frame(["a", "b", "c", "d"])
        assignment = pd.Series({"a": "1", "b": "1", "c": "2", "d": "2"})
        districts = assemble_districts(blocks, assignment)
        assert list(districts.columns) == ["DISTRICT", "geometry"]
        assert list(districts["DISTRICT"]) == ["1", "2"]
        assert districts.geometry.iloc[0].equals(box(0, 0, 2, 1))
        assert districts.geometry.iloc[1].equals(box(2, 0, 4, 1))
        assert districts.crs == blocks.crs

    def test_unassigned_water_blocks_are_allowed(self):
        blocks = blocks_frame(["a", "b", "lake"], land=[1, 1, 0])
        districts = assemble_districts(blocks, pd.Series({"a": "1", "b": "2"}))
        assert list(districts["DISTRICT"]) == ["1", "2"]

    def test_unassigned_land_blocks_are_rejected(self):
        blocks = blocks_frame(["a", "b", "farm"])
        with pytest.raises(ValueError, match="1 blocks with land are unassigned"):
            assemble_districts(blocks, pd.Series({"a": "1", "b": "2"}))

    def test_assigned_ids_missing_from_the_block_file_are_rejected(self):
        blocks = blocks_frame(["a", "b"])
        with pytest.raises(ValueError, match="not in the block file"):
            assemble_districts(blocks, pd.Series({"a": "1", "b": "2", "zz": "2"}))
