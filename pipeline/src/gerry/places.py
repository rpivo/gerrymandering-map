"""The cities, towns and other named places in each district, from 2020 Census blocks.

The 2020 redistricting file (PL 94-171) gives every block the code of the place it lies in,
if any, and has one record per place with its name and population. Places are incorporated
cities, towns, villages and boroughs, plus census-designated places (CDPs): communities the
Census Bureau names for statistics that have no government of their own, such as Metairie,
Louisiana, or every community in Hawaii. Blocks are already placed in districts (see
gerry.population), so adding up a place's blocks by district says how many of its people live
in each district. Districts follow block lines, so this count is exact for each 2020 block.
"""

import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# Each district page lists at most this many places, largest first.
MAX_PLACES = 10

# 0-based field positions in the PL 94-171 geoheader.
_PLACE_FIELDS = {
    "sumlev": 2, "place": 29, "basename": 86, "name": 87, "pop": 90, "lat": 92, "lon": 93,
}  # fmt: skip
_PLACE = "160"
# The Census type of a place is its full name minus its base name: "Abbeville city".
_KIND_WORDS = {"CDP": "community"}
# Types a consolidated city's base name can end with, longest first so "metro government"
# isn't read as "government". The Census writes these into the base name itself.
_TYPES = sorted(
    ["city and borough", "metropolitan government", "metro government", "unified government",
     "consolidated government", "urban county", "metro township", "municipality", "borough",
     "village", "town", "city"],
    key=len, reverse=True,
)  # fmt: skip


def place_name_and_kind(name: str, basename: str) -> tuple[str, str]:
    """Return a place's name and its Census type in plain words.

    The type is "city", "town", "village", "community" (a census-designated place) and so
    on, or "" for a place whose name has none, such as Carson City. "(balance)" marks the
    main part of a consolidated city outside its other cities, such as Indianapolis; readers
    don't need it, and the Census puts it and the type in the base name, which is undone here.
    """
    full = name.replace("(balance)", "").strip()
    base = basename.replace("(balance)", "").strip()
    kind = full.removeprefix(base).strip()
    if not kind and "(balance)" in basename:
        for t in _TYPES:
            if base.endswith(f" {t}"):
                base, kind = base.removesuffix(f" {t}"), t
                break
    return base, _KIND_WORDS.get(kind, kind)


# Kinds of place that are a city and county merged into one government.
_CONSOLIDATED = {"metropolitan government", "metro government", "unified government",
                 "consolidated government", "urban county"}  # fmt: skip


def map_label(name: str, kind: str) -> str:
    """Return a place's short name for a map label.

    A city merged with its county carries both names ("Nashville-Davidson",
    "Louisville/Jefferson County"); a map labels it by the city alone.
    """
    if kind in _CONSOLIDATED or name.endswith(" County"):
        return re.split(r"[-/,]", name, maxsplit=1)[0].strip()
    return name


def read_pl_places(path: Path) -> pd.DataFrame:
    """Read every place in a state's PL 94-171 zip.

    Returns:
        place (the 5-digit code blocks carry), name (without its type), kind (see
        place_kind), pop (2020 population, all ages), and lat and lon (the Census's
        internal point, a spot inside the place, in degrees), in file order.
    """
    with zipfile.ZipFile(path) as zf:
        geo_name = next(n for n in zf.namelist() if n.endswith("geo2020.pl"))
        with zf.open(geo_name) as f:
            geo = pd.read_csv(
                f,
                sep="|",
                header=None,
                dtype=str,
                encoding="latin-1",
                usecols=list(_PLACE_FIELDS.values()),
                keep_default_na=False,
            )
    # read_csv keeps file order whatever order usecols lists, so name columns by position.
    geo = geo.rename(columns={i: n for n, i in _PLACE_FIELDS.items()})
    places = geo[geo["sumlev"] == _PLACE].reset_index(drop=True)
    named = [
        place_name_and_kind(n, b) for n, b in zip(places["name"], places["basename"], strict=True)
    ]
    return pd.DataFrame({
        "place": places["place"], "name": [n for n, _ in named], "kind": [k for _, k in named],
        "pop": places["pop"].astype(int), "lat": places["lat"].astype(float),
        "lon": places["lon"].astype(float),
    })  # fmt: skip


def district_places(placed: pd.DataFrame, places: pd.DataFrame) -> pd.DataFrame:
    """Count each place's people in each district.

    Args:
        placed: Blocks with district_id, state, place (None outside any place) and pop.
        places: From read_pl_places, plus a state column.

    Returns:
        One row per district and place with people there: district_id, state, place, name,
        kind, pop (the place's people in the district) and place_pop (all of its people).
        A block in a place missing from `places` keeps a blank name (see place_problems).
    """
    counts = (
        placed.dropna(subset=["place"])
        .groupby(["district_id", "state", "place"], as_index=False)["pop"]
        .sum()
    )
    counts = counts[counts["pop"] > 0]
    named = places.rename(columns={"pop": "place_pop"})
    return counts.merge(named, on=["state", "place"], how="left").reset_index(drop=True)[
        ["district_id", "state", "place", "name", "kind", "pop", "place_pop"]
    ]


def place_problems(placed: pd.DataFrame, table: pd.DataFrame, places: pd.DataFrame) -> list[str]:
    """Return a problem for every place whose people don't add up.

    Every block's place must have a record, and a place's people across districts must equal
    its 2020 total. A mismatch means blocks were read or placed wrongly.
    """
    problems = []
    unnamed = table[table["name"].isna()]
    for (state, place), rows in unnamed.groupby(["state", "place"]):
        problems.append(
            f"{state}: {rows['pop'].sum():,} people in blocks of a place with no name ({place})"
        )
    in_blocks = placed.dropna(subset=["place"]).groupby(["state", "place"])["pop"].sum()
    for row in places.itertuples():
        counted = int(in_blocks.get((row.state, row.place), 0))
        if counted != row.pop:
            problems.append(
                f"{row.state} {row.name} ({row.place}): {counted:,} people in districts, "
                f"{row.pop:,} in the Census"
            )
    return problems


def piece_points(placed: pd.DataFrame) -> pd.DataFrame:
    """Return a point for each part of a place in each district, where its people live.

    Args:
        placed: Blocks from gerry.population.assign_blocks: district_id, state, place, lon,
            lat and pop.

    Returns:
        district_id, state, place, pop (residents of the place in the district), and lon and
        lat: the point of the block nearest the part's population center. A block's point
        lies in its district, unlike the center itself, which can fall outside a curved part.
        Parts with no residents are left out.
    """
    keys = ["district_id", "state", "place"]
    return _nearest_blocks(placed, keys).astype({"pop": int}).reset_index(drop=True)


def populated_points(places: pd.DataFrame, placed: pd.DataFrame) -> pd.DataFrame:
    """Return places with each point moved to where its people live.

    The Census's internal point can sit far from any resident: San Francisco's is in the
    Pacific, since most of the city's area is water. So a place with residents moves to the
    block nearest its population center, across all its districts.

    Args:
        places: From read_pl_places, plus a state column.
        placed: Blocks with state, place, lon, lat and pop.

    Returns:
        A copy of places, in the same order, with lon and lat (degrees) replaced for every
        place with residents. A place nobody lives in keeps its internal point.
    """
    nearest = _nearest_blocks(placed, ["state", "place"]).set_index(["state", "place"])
    keys = pd.MultiIndex.from_frame(places[["state", "place"]])
    out = places.copy()
    for col in ("lon", "lat"):
        moved = nearest[col].reindex(keys).to_numpy()
        out[col] = np.where(np.isnan(moved), places[col].to_numpy(), moved)
    return out


def _nearest_blocks(placed: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Return, per group of keys, its residents (pop) and the block nearest its population center.

    A block always lies inside the place and where people live, unlike the center itself,
    which can fall outside a curved place. Returns keys, pop, and lon and lat in degrees.
    """
    blocks = placed[placed["place"].notna() & (placed["pop"] > 0)].copy()
    blocks["wlon"], blocks["wlat"] = blocks["lon"] * blocks["pop"], blocks["lat"] * blocks["pop"]
    sums = blocks.groupby(keys, sort=True)[["pop", "wlon", "wlat"]].sum()
    centers = (sums[["wlon", "wlat"]].div(sums["pop"], axis=0)).rename(
        columns={"wlon": "clon", "wlat": "clat"}
    )
    blocks = blocks.join(centers, on=keys)
    # Degrees of longitude shrink toward the poles; scale them so "nearest" is about right.
    scale = np.cos(np.radians(blocks["clat"]))
    dx, dy = (blocks["lon"] - blocks["clon"]) * scale, blocks["lat"] - blocks["clat"]
    blocks["dist"] = dx**2 + dy**2
    nearest = blocks.sort_values("dist", kind="stable").groupby(keys, sort=True).head(1)
    out = nearest.set_index(keys)[["lon", "lat"]].join(sums["pop"]).reset_index()
    return out[[*keys, "pop", "lon", "lat"]]
