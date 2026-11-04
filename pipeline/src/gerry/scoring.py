"""Turn district shapes into compactness percentiles, an irregularity score and ranks.

For each of Polsby-Popper, Reock and convex hull, a district's percentile (0 to 100)
is where it falls among the districts that have lines: everything except the six
at-large states, whose single district is the whole state. Higher means more compact.
The irregularity score is 100 minus the average of the three percentiles, rounded:
0 for the most compact district, near 100 for the least. Percentiles put the three
metrics on one scale; their raw values sit in very different ranges.
"""

import geopandas as gpd
import pandas as pd

from gerry.metrics import compactness

RANKED_METRICS = ("polsby_popper", "reock", "convex_hull")


def _with_percentiles(scores: pd.DataFrame) -> pd.DataFrame:
    """Add a 0 to 100 percentile column per ranked metric, and the irregularity score."""
    lined = ~scores["at_large"]
    for metric in RANKED_METRICS:
        scores[f"{metric}_pct"] = scores.loc[lined, metric].rank(pct=True) * 100
    mean_pct = scores[[f"{m}_pct" for m in RANKED_METRICS]].mean(axis=1, skipna=False)
    scores["compactness_pct"] = mean_pct
    scores["irregularity"] = (100 - mean_pct).round().astype("Int64")
    return scores


def _with_ranks(scores: pd.DataFrame) -> pd.DataFrame:
    """Add national and within-state ranks: 1 is the most irregular district."""
    order = scores[~scores["at_large"]].sort_values(
        ["irregularity", "compactness_pct", "district_id"], ascending=[False, True, True]
    )
    scores["rank_national"] = pd.Series(range(1, len(order) + 1), index=order.index, dtype="Int64")
    scores["rank_state"] = (
        order.groupby("state").cumcount().add(1).reindex(scores.index).astype("Int64")
    )
    return scores


def score_districts(districts: gpd.GeoDataFrame) -> pd.DataFrame:
    """Score every district.

    Args:
        districts: One row per district with `district_id`, `state`, `number` (null for
            at-large) and `geometry`. Any other columns, such as `map_source`, are kept.

    Returns:
        One row per district, sorted by `district_id`, without geometry: the raw
        metrics, each ranked metric's percentile, `compactness_pct`, `irregularity`
        and the ranks. At-large districts have raw metrics but no percentiles,
        score or ranks.
    """
    metrics = pd.DataFrame(
        [compactness(geometry, districts.crs) for geometry in districts.geometry],
        index=districts.index,
    )
    scores = pd.concat([pd.DataFrame(districts.drop(columns="geometry")), metrics], axis=1)
    scores["at_large"] = scores["number"].isna()
    scores = _with_ranks(_with_percentiles(scores))
    return scores.sort_values("district_id", ignore_index=True)
