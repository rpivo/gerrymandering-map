"""Official 2026 district files for states that redrew after the 2024 election."""

import zipfile
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd

from gerry.fetch import Source

LAYER_SUFFIXES = (".shp", ".geojson", ".json", ".gpkg", ".kml")


@dataclass(frozen=True)
class StateMap:
    """Where to get one state's current district file and how to read it."""

    state: str
    source: Source
    district_field: str
    member: str | None = None


@dataclass(frozen=True)
class BlockAssignmentMap:
    """A state whose current map is published only as a block assignment file."""

    state: str
    source: Source
    member: str | None
    block_column: str | int
    district_column: str | int
    blocks: Source


NO_LICENSE = "No license stated (public government record)"


def _source(state: str, slug: str, url: str, publisher: str, description: str, **kw) -> Source:
    """Build a state map Source with a `<state>-<slug>` ID and a zip filename."""
    return Source(
        id=f"{state.lower()}-{slug}",
        url=url,
        publisher=publisher,
        license=kw.get("license", NO_LICENSE),
        description=description,
        filename=f"{state.lower()}-{slug}.zip",
    )


_MAPS = [
    StateMap(
        "AL",
        _source(
            "AL",
            "2023-sb5-congress",
            "https://alabamaredistrictingplans-algeohub.hub.arcgis.com/api/download/v1/items/"
            "cf6612d18f4f4a97b8f2b1392c70654a/shapefile?layers=0",
            "Alabama GeoHub (Alabama Redistricting Plans, linked from the Alabama "
            "Legislature's reapportionment page)",
            "2023 Alabama Congressional Plan (SB 5, Livingston Plan 3), reinstated for 2026. "
            "Page: https://alabamaredistrictingplans-algeohub.hub.arcgis.com/datasets/"
            "cf6612d18f4f4a97b8f2b1392c70654a_0",
        ),
        "DISTRICT",
    ),
    StateMap(
        "CA",
        _source(
            "CA",
            "2025-ab604-congress",
            "https://selc.senate.ca.gov/system/files/2025-08/ab604.zip",
            "California State Senate Elections and Constitutional Amendments Committee",
            "AB 604 congressional districts (Proposition 50 map), chaptered 2025-08-21. "
            "Page: https://selc.senate.ca.gov/node/1171",
        ),
        "DISTRICT",
        member="AB604/AB604.shp",
    ),
    StateMap(
        "FL",
        _source(
            "FL",
            "2026-eogpcrp2026-congress",
            "https://www.edr.state.fl.us/Content/redistricting/2026redistricting/EOGPCRP2026.zip",
            "Florida Legislature, Office of Economic and Demographic Research",
            "2026 congressional plan EOGPCRP2026 (HB 1-D), revised 2026-05-04. Page: "
            "https://www.edr.state.fl.us/Content/redistricting/2026redistricting/index.cfm",
        ),
        "DISTRICT",
    ),
    StateMap(
        "LA",
        _source(
            "LA",
            "2026-act2-congress",
            "https://redist.legis.la.gov/2026_Files/Act2Congress/Shapefile/"
            "Shapefile%20-%20Act_2_(2026_RS).zip",
            "Louisiana Legislature",
            "Congress Act 2 (SB 121), 2026 Regular Session. Page: "
            "https://redist.legis.la.gov/2026_Files/2026CONGRESSACT2.aspx",
        ),
        "DISTRICT_I",
    ),
    StateMap(
        "NC",
        _source(
            "NC",
            "2025-sl2025-95-congress",
            "https://webservices.ncleg.gov/ViewBillDocument/2025/7667/0/SL%202025-95%20-%20Shapefile",
            "North Carolina General Assembly",
            "S.L. 2025-95 (SB 249) congressional plan, labeled for the 2026 election. "
            "Page: https://www.ncleg.gov/Redistricting",
        ),
        "DISTRICT",
    ),
    StateMap(
        "TN",
        _source(
            "TN",
            "2026-hb7003-congress",
            "https://tn-tnmap.opendata.arcgis.com/api/download/v1/items/"
            "90e4742978674ef4aaf08eb9f9f845bb/shapefile?layers=2",
            "State of Tennessee, TNMap (Office for Information Resources)",
            "TN Congressional Districts, 2026 boundaries (HB 7003). Page: "
            "https://hub.arcgis.com/datasets/90e4742978674ef4aaf08eb9f9f845bb_2",
        ),
        "DISTRICT",
    ),
    StateMap(
        "TX",
        _source(
            "TX",
            "2025-planc2333-congress",
            "https://data.capitol.texas.gov/dataset/748c952b-e926-4f44-8d01-a738884b3ec8/"
            "resource/5712ebe1-d777-4d4a-b836-0534e17bca01/download/planc2333.zip",
            "Texas Legislative Council",
            "PLANC2333, enacted by the 89th Legislature, 2nd Called Session, 2025. Page: "
            "https://data.capitol.texas.gov/dataset/planc2333",
        ),
        "District",
    ),
    StateMap(
        "UT",
        _source(
            "UT",
            "2026-map1a-congress",
            "https://opendata.gis.utah.gov/api/download/v1/items/"
            "d3388c1f7d894ab789247f6442855d66/shapefile?layers=0",
            "Utah Geospatial Resource Center (UGRC)",
            "Utah US Congress Districts 2026 to 2032 (court-adopted Map 1A). Page: "
            "https://gis.utah.gov/products/sgid/political/us-congressional-districts/",
        ),
        "DISTRICT",
    ),
]
_BLOCK_MAPS = [
    BlockAssignmentMap(
        "OH",
        _source(
            "OH",
            "2025-orc-congress",
            "https://redistricting.ohio.gov/api/public/districtmaps/430/download",
            "Ohio Redistricting Commission",
            "Congressional Redistricting Plan adopted 2025-10-31 (block assignment file). "
            "Page: https://redistricting.ohio.gov/maps",
        ),
        member="October 31 2025 CD BAF.xlsx",
        block_column="Block",
        district_column="DistrictID:1",
        blocks=Source(
            id="census-blocks-2020-39",
            url="https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_39_tabblock20.zip",
            publisher="U.S. Census Bureau",
            license="Public domain (U.S. Government work)",
            description="TIGER/Line 2020 census blocks, Ohio. Used to build Ohio's districts.",
        ),
    ),
]
STATE_MAPS: dict[str, StateMap | BlockAssignmentMap] = {m.state: m for m in _MAPS + _BLOCK_MAPS}

# States the audit marks as changed whose current map can't be loaded yet, with why.
# The build keeps their 2024 lines and says so; check_audit_match allows only these.
PENDING: dict[str, str] = {}


def read_state_map(path: Path, member: str | None = None) -> gpd.GeoDataFrame:
    """Read a state's district file (zipped shapefile, GeoJSON or GeoPackage).

    Args:
        path: The downloaded file.
        member: Path of the layer inside a zip, for zips that hold several plans.
    """
    if path.suffix != ".zip":
        return gpd.read_file(path)
    return gpd.read_file(f"zip://{path}!{member or _only_layer(path)}")


def _only_layer(path: Path) -> str:
    """Return the single map layer inside a zip, so callers needn't name it.

    Raises:
        ValueError: if the zip holds no layer or several (name one with `member`).
    """
    with zipfile.ZipFile(path) as zf:
        layers = [n for n in zf.namelist() if n.lower().endswith(LAYER_SUFFIXES)]
    if len(layers) != 1:
        raise ValueError(f"{path.name}: expected one map layer, found {layers}; set member.")
    return layers[0]
