from gerry.states import STATES, STATES_BY_FIPS, TOTAL_SEATS


def test_fifty_states_with_unique_codes():
    assert len(STATES) == 50
    assert len({s.usps for s in STATES}) == 50
    assert len({s.fips for s in STATES}) == 50


def test_seats_add_up_to_435():
    assert TOTAL_SEATS == 435
    assert sum(s.seats for s in STATES) == 435


def test_at_large_states():
    assert {s.usps for s in STATES if s.seats == 1} == {"AK", "DE", "ND", "SD", "VT", "WY"}


def test_lookup_by_fips_excludes_dc_and_territories():
    assert STATES_BY_FIPS["48"].usps == "TX"
    assert STATES_BY_FIPS["48"].seats == 38
    assert STATES_BY_FIPS["06"].name == "California"
    for fips in ["11", "60", "66", "69", "72", "78"]:
        assert fips not in STATES_BY_FIPS
