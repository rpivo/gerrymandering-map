import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import box

from gerry.boundaries import load_state_outlines
from gerry.fetch import Source
from gerry.state_maps import STATE_MAPS, StateMap, read_state_map
from gerry.states import STATES_BY_USPS


def write_shapefile_zip(path, layers: dict[str, gpd.GeoDataFrame]):
    """Write each frame as a shapefile and zip them all together."""
    folder = path.parent / "shp"
    folder.mkdir()
    with zipfile.ZipFile(path, "w") as zf:
        for name, gdf in layers.items():
            gdf.to_file(folder / f"{name}.shp")
            for part in folder.glob(f"{name}.*"):
                zf.write(part, f"plans/{part.name}")


def districts(values):
    return gpd.GeoDataFrame(
        {"DISTRICT": values, "geometry": [box(i, 0, i + 1, 1) for i in range(len(values))]},
        crs="EPSG:4269",
    )


def test_load_state_outlines_keeps_the_fifty_states(tmp_path):
    path = tmp_path / "states.gpkg"
    gpd.GeoDataFrame(
        {"STATEFP": ["48", "11", "72"], "STUSPS": ["TX", "DC", "PR"]},
        geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)],
        crs="EPSG:4269",
    ).to_file(path)
    outlines = load_state_outlines(path)
    assert list(outlines) == ["TX"]
    assert outlines["TX"].equals(box(0, 0, 1, 1))


def test_read_state_map_picks_the_named_layer_in_a_zip(tmp_path):
    path = tmp_path / "plan.zip"
    write_shapefile_zip(path, {"congress": districts([1, 2]), "senate": districts([1, 2, 3])})
    raw = read_state_map(path, member="plans/congress.shp")
    assert sorted(raw["DISTRICT"]) == [1, 2]


def test_read_state_map_reads_a_single_layer_zip_without_a_member(tmp_path):
    path = tmp_path / "plan.zip"
    write_shapefile_zip(path, {"congress": districts([1, 2])})
    assert sorted(read_state_map(path)["DISTRICT"]) == [1, 2]


def test_read_state_map_needs_a_member_when_a_zip_has_several_layers(tmp_path):
    path = tmp_path / "plan.zip"
    write_shapefile_zip(path, {"congress": districts([1, 2]), "senate": districts([1, 2, 3])})
    with pytest.raises(ValueError, match="member"):
        read_state_map(path)


def test_read_state_map_reads_geojson(tmp_path):
    path = tmp_path / "plan.geojson"
    districts([1, 2]).to_file(path, driver="GeoJSON")
    assert sorted(read_state_map(path)["DISTRICT"]) == [1, 2]


@pytest.mark.parametrize("state_map", STATE_MAPS.values(), ids=lambda m: m.state)
def test_registered_maps_are_well_formed(state_map: StateMap):
    assert state_map.state in STATES_BY_USPS
    assert isinstance(state_map.source, Source)
    assert state_map.source.url.startswith("https://")
    assert state_map.source.id.startswith(f"{state_map.state.lower()}-")
    assert state_map.district_field


def test_source_ids_are_unique():
    ids = [m.source.id for m in STATE_MAPS.values()]
    assert len(ids) == len(set(ids))
