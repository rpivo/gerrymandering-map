import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from gerry.states import STATES

SIZE = 0.05  # degrees; squares are spaced 0.1 apart so they never touch


def square(row: int, col: int):
    x, y = -120 + col * 0.1, 30 + row * 0.1
    return box(x, y, x + SIZE, y + SIZE)


@pytest.fixture
def valid_districts() -> gpd.GeoDataFrame:
    """A normalized, valid set of 435 districts: one non-overlapping square each."""
    rows = []
    for i, state in enumerate(STATES):
        for n in range(1, state.seats + 1):
            number = None if state.seats == 1 else n
            suffix = "AL" if number is None else f"{n:02d}"
            rows.append(
                {
                    "district_id": f"{state.usps}-{suffix}",
                    "state": state.usps,
                    "number": number,
                    "geometry": square(i, n),
                }
            )
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4269")
    gdf["number"] = pd.array(gdf["number"], dtype="Int64")
    return gdf
