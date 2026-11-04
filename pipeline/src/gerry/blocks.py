"""Build district shapes from a block assignment file and Census block shapes.

Some states publish their map only as a block assignment file: one row per 2020
Census block with the district it belongs to. Joining that to the Census TIGER block
shapes and merging the blocks gives the district boundaries.
"""

import io
import re
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

_BLOCK_GEOID = re.compile(r"^\d{15}$")


def _read_table(path: Path, member: str | None, header: bool) -> pd.DataFrame:
    """Read a CSV or XLSX file, optionally from inside a zip, with every value as text."""
    name = member or path.name
    raw: Path | io.BytesIO = path
    if member:
        with zipfile.ZipFile(path) as zf:
            raw = io.BytesIO(zf.read(member))
    options = {"dtype": str, "header": 0 if header else None}
    if name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(raw, **options)
    return pd.read_csv(raw, **options)


def read_block_assignment(
    path: Path, member: str | None, block_column: str | int, district_column: str | int
) -> pd.Series:
    """Read a block assignment file into a Series of district (text) by block GEOID.

    Args:
        path: The downloaded file: CSV, XLSX, or a zip holding one.
        member: Name of the file inside the zip, or None if path is the file itself.
        block_column: Column name, or position for a file with no header row.
        district_column: Same, for the district.

    Raises:
        ValueError: if a block ID is not a 15-digit GEOID or appears more than once.
    """
    table = _read_table(path, member, header=isinstance(block_column, str))
    blocks = table[block_column].str.strip()
    bad = blocks[~blocks.str.match(_BLOCK_GEOID)]
    if not bad.empty:
        raise ValueError(f"Block IDs must be 15-digit GEOIDs; found {list(bad[:3])}.")
    if blocks.duplicated().any():
        raise ValueError(
            f"Blocks assigned more than once: {list(blocks[blocks.duplicated()][:3])}."
        )
    return pd.Series(table[district_column].str.strip().to_numpy(), index=blocks.to_numpy())


def read_blocks(path: Path) -> gpd.GeoDataFrame:
    """Read a Census TIGER block file, keeping the GEOID, land area and shape."""
    location = f"zip://{path}" if path.suffix == ".zip" else path
    return gpd.read_file(location, columns=["GEOID20", "ALAND20"])


def assemble_districts(blocks: gpd.GeoDataFrame, assignment: pd.Series) -> gpd.GeoDataFrame:
    """Merge blocks into one shape per district.

    Returns:
        Columns `DISTRICT` (as in the assignment file) and `geometry`, sorted by
        district, in the blocks' CRS.

    Raises:
        ValueError: if a block with land is unassigned, or an assigned block ID is not
            in the block file. Unassigned water-only blocks are allowed.
    """
    missing = assignment.index.difference(blocks["GEOID20"])
    if len(missing):
        raise ValueError(
            f"{len(missing)} assigned blocks are not in the block file: {list(missing[:3])}."
        )
    district = blocks["GEOID20"].map(assignment)
    unassigned_land = blocks[district.isna() & (blocks["ALAND20"].astype(float) > 0)]
    if len(unassigned_land):
        raise ValueError(f"{len(unassigned_land)} blocks with land are unassigned.")
    assigned = blocks.assign(DISTRICT=district)[district.notna()]
    shapes = {
        name: shapely.coverage_union_all(group.geometry.to_numpy())
        for name, group in assigned.groupby("DISTRICT")
    }
    names = sorted(shapes, key=lambda n: (len(n), n))
    return gpd.GeoDataFrame(
        {"DISTRICT": names}, geometry=[shapes[n] for n in names], crs=blocks.crs
    )
