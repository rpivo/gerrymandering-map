import json

import pandas as pd

HEADER = (
    "OID_ZCTA5_20|GEOID_ZCTA5_20|NAMELSAD_ZCTA5_20|AREALAND_ZCTA5_20|AREAWATER_ZCTA5_20|"
    "MTFCC_ZCTA5_20|CLASSFP_ZCTA5_20|FUNCSTAT_ZCTA5_20|OID_TABBLOCK_20|GEOID_TABBLOCK_20|"
    "NAMELSAD_TABBLOCK_20|AREALAND_TABBLOCK_20|AREAWATER_TABBLOCK_20|MTFCC_TABBLOCK_20|"
    "FUNCSTAT_TABBLOCK_20|AREALAND_PART|AREAWATER_PART\n"
)


def rel_row(zcta: str, block: str, land_part: int = 100) -> str:
    return f"1|{zcta}|ZCTA5 {zcta}|0|0|G6350|B5|S|2|{block}|Block 1|0|0|G5040|S|{land_part}|0\n"


def test_reads_each_block_and_its_zip_area_as_numbers(tmp_path):
    from gerry.zips import read_zcta_blocks

    path = tmp_path / "rel.txt"
    path.write_text(
        "﻿"
        + HEADER
        + rel_row("00601", "720010001001000")
        + "||||||||3|720010001001001|Block 1001|0|0|G5040|S|0|50\n"  # in no ZIP area
    )
    table = read_zcta_blocks(path)
    assert table.to_dict("records") == [{"block": 720010001001000, "zcta": 601}]


def test_a_block_split_between_zip_areas_goes_to_the_one_with_more_of_its_land(tmp_path):
    from gerry.zips import read_zcta_blocks

    path = tmp_path / "rel.txt"
    path.write_text(
        HEADER + rel_row("78221", "484530001001000", 10) + rel_row("78222", "484530001001000", 90)
    )
    assert read_zcta_blocks(path)["zcta"].tolist() == [78222]


def placed_blocks() -> pd.DataFrame:
    return pd.DataFrame({
        "geoid": ["484530001001000", "484530001001001", "484530001001002", "484530001001003"],
        "district_id": ["TX-35", "TX-35", "TX-20", "TX-20"],
        "state": ["TX"] * 4,
        "pop": [100, 50, 50, 0],
    })  # fmt: skip


def zcta_blocks() -> pd.DataFrame:
    return pd.DataFrame({
        "block": [484530001001000, 484530001001001, 484530001001002, 484530001001003],
        "zcta": [78221, 78222, 78222, 78223],
    })  # fmt: skip


def test_counts_each_zip_areas_residents_in_each_district():
    from gerry.zips import district_zctas

    table = district_zctas(placed_blocks(), zcta_blocks())
    assert table.sort_values(["district_id", "zcta"]).to_dict("records") == [
        {"district_id": "TX-20", "zcta": 78222, "pop": 50},
        {"district_id": "TX-35", "zcta": 78221, "pop": 100},
        {"district_id": "TX-35", "zcta": 78222, "pop": 50},
    ]  # 78223 has no residents, so it's left out


def test_shares_are_of_the_zip_areas_residents_across_every_district_and_state():
    from gerry.zips import zcta_shares

    counts = pd.DataFrame({
        "district_id": ["TX-35", "TX-20", "OK-04"],
        "zcta": [78222, 78222, 78222],
        "pop": [50, 30, 20],
    })  # fmt: skip
    shares = zcta_shares(counts).set_index("district_id")["share"].to_dict()
    assert shares == {"TX-35": 0.5, "TX-20": 0.3, "OK-04": 0.2}


def test_zips_json_lists_each_districts_zip_codes_in_order_with_split_shares(tmp_path):
    from gerry.export import write_zips_json
    from gerry.zips import zcta_shares

    counts = pd.DataFrame({
        "district_id": ["TX-35", "TX-35", "TX-20", "VT-AL"],
        "zcta": [78222, 78221, 78222, 5401],
        "pop": [2, 100, 1, 9],
    })  # fmt: skip
    path = tmp_path / "zips.json"
    write_zips_json(zcta_shares(counts), path)
    data = json.loads(path.read_text())
    assert data["districts"] == {
        "TX-20": [["78222", 0.33]],
        "TX-35": [["78221", 1], ["78222", 0.67]],
        "VT-AL": [["05401", 1]],
    }


def test_a_split_share_never_rounds_to_all_or_nothing(tmp_path):
    from gerry.export import write_zips_json
    from gerry.zips import zcta_shares

    counts = pd.DataFrame({"district_id": ["A-01", "A-02"], "zcta": [1, 1], "pop": [9999, 1]})
    path = tmp_path / "zips.json"
    write_zips_json(zcta_shares(counts), path)
    data = json.loads(path.read_text())["districts"]
    assert data == {"A-01": [["00001", 0.99]], "A-02": [["00001", 0.01]]}


def test_sources_json_marks_the_zip_area_file_as_zips(tmp_path):
    from gerry.export import write_sources_json

    entry = {"id": "census-zcta520-tabblock20", "url": "https://c/z", "publisher": "Census",
        "license": "PD", "description": "ZCTAs", "downloaded": "2026-11-06",
        "sha256": "f" * 64}  # fmt: skip
    path = tmp_path / "sources.json"
    write_sources_json({entry["id"]: entry}, path)
    assert json.loads(path.read_text())["sources"][0]["role"] == "zips"
