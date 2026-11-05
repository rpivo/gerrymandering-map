import math

import pandas as pd
import pytest

from gerry.fairness import (
    MIN_DISTRICTS,
    declination,
    efficiency_gap,
    mean_median,
    state_fairness,
)

# Packed and cracked: Democrats win 54% of the vote but one of five seats, by packing 90% of
# one district and losing the other four 45-55. Every measure should lean Republican (> 0).
PACKED_DEM = [90, 45, 45, 45, 45]
PACKED_REP = [10, 55, 55, 55, 55]


def test_efficiency_gap_known_answer():
    # Wasted Democratic votes: 40 surplus in the packed district + 45 x 4 losing = 220.
    # Wasted Republican votes: 10 losing + 5 surplus x 4 = 30. Gap = (220 - 30) / 500.
    assert efficiency_gap(PACKED_DEM, PACKED_REP) == pytest.approx(0.38)


def test_mean_median_known_answer():
    # Mean Democratic share 0.54, median 0.45.
    shares = [d / (d + r) for d, r in zip(PACKED_DEM, PACKED_REP, strict=True)]
    assert mean_median(shares) == pytest.approx(0.09)


def test_declination_known_answer():
    # Republican-won districts average 0.45 over 4/5 of the seats; the Democratic one is 0.90.
    # theta_R = atan(0.05 / 0.4), theta_D = atan(0.40 / 0.1);
    # declination = 2/pi (theta_D - theta_R).
    shares = [d / (d + r) for d, r in zip(PACKED_DEM, PACKED_REP, strict=True)]
    expected = 2 / math.pi * (math.atan(4.0) - math.atan(0.125))
    assert declination(shares) == pytest.approx(expected)


def test_a_symmetric_map_scores_zero_on_every_measure():
    dem, rep = [30, 40, 60, 70], [70, 60, 40, 30]
    shares = [0.3, 0.4, 0.6, 0.7]
    assert efficiency_gap(dem, rep) == pytest.approx(0)
    assert mean_median(shares) == pytest.approx(0)
    assert declination(shares) == pytest.approx(0)


def test_swapping_the_parties_flips_every_sign():
    shares = [d / (d + r) for d, r in zip(PACKED_DEM, PACKED_REP, strict=True)]
    flipped = [1 - s for s in shares]
    assert efficiency_gap(PACKED_REP, PACKED_DEM) == pytest.approx(-0.38)
    assert mean_median(flipped) == pytest.approx(-0.09)
    assert declination(flipped) == pytest.approx(-declination(shares))


def test_declination_is_undefined_when_one_party_wins_every_seat():
    assert declination([0.3, 0.4, 0.45, 0.2]) is None
    assert declination([0.6, 0.7, 0.55, 0.8]) is None


def test_efficiency_gap_counts_votes_not_shares():
    # Same shares, but the packed district has twice the turnout (200 voters, 100 to win): it
    # wastes 80 Democratic and 20 Republican votes, so the gap is (80 + 180 - 20 - 20) / 600.
    heavy = efficiency_gap([180, 45, 45, 45, 45], [20, 55, 55, 55, 55])
    assert heavy == pytest.approx(220 / 600)


def test_state_fairness_scores_states_with_enough_districts_only():
    rows = [
        ("AA", d, dem, rep, "precinct join")
        for d, (dem, rep) in enumerate(zip(PACKED_DEM, PACKED_REP, strict=True), 1)
    ]
    rows += [("BB", d, 50, 50, "official report") for d in range(1, MIN_DISTRICTS)]
    totals = pd.DataFrame(rows, columns=["state", "district", "dem", "rep", "method"])
    totals["dem_share"] = totals["dem"] / (totals["dem"] + totals["rep"])
    out = state_fairness(totals).set_index("state")
    assert list(out.index) == ["AA"]
    aa = out.loc["AA"]
    assert (aa["districts"], aa["dem_seats"]) == (5, 1)
    assert aa["dem_vote_share"] == pytest.approx(0.54)
    assert aa["efficiency_gap"] == pytest.approx(0.38)
    assert aa["mean_median"] == pytest.approx(0.09)
    assert aa["method"] == "precinct join"
