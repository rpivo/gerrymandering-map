import zipfile

import pandas as pd
import pytest

from gerry.export import places_records
from gerry.places import (
    MAX_PLACES,
    district_places,
    map_label,
    place_name_and_kind,
    place_problems,
    read_pl_places,
)
from gerry.population import read_pl_blocks

# PL 94-171 geoheader positions (0-based) used here.
SUMLEV, LOGRECNO, GEOCODE, PLACE, BASENAME, NAME, POP100, LAT, LON = 2, 7, 9, 29, 86, 87, 90, 92, 93


def geo_row(
    sumlev: str,
    logrecno: str,
    place: str,
    pop: int,
    basename: str = "",
    name: str = "",
    lat: str = "+30.0",
    lon: str = "-91.0",
) -> str:
    fields = [""] * 97
    fields[0], fields[1] = "PLST", "LA"
    fields[SUMLEV], fields[LOGRECNO], fields[GEOCODE] = sumlev, logrecno, f"22{logrecno}"
    fields[PLACE], fields[BASENAME], fields[NAME] = place, basename, name
    fields[POP100], fields[LAT], fields[LON] = str(pop), lat, lon
    return "|".join(fields)


def write_zip(tmp_path, rows: list[str]):
    seg2 = []
    for row in rows:
        fields = row.split("|")
        # Everyone is of voting age, so population tables have something to divide by.
        p4 = [fields[POP100]] + ["0"] * 72
        seg2.append(
            "|".join(["PLST", "LA", "000", "02", fields[LOGRECNO], *["0"] * 71, *p4, "0", "0", "0"])
        )
    path = tmp_path / "la2020.pl.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("lageo2020.pl", "\n".join(rows) + "\n")
        zf.writestr("la000022020.pl", "\n".join(seg2) + "\n")
    return path


class TestReadPlaces:
    def test_reads_each_place_with_its_name_type_population_and_point(self, tmp_path):
        path = write_zip(tmp_path, [
            geo_row("040", "0000001", "", 4657757),
            geo_row("160", "0000002", "00100", 11186, "Abbeville", "Abbeville city",
                    "+29.9751", "-092.1343"),
            geo_row("160", "0000003", "50115", 143507, "Metairie", "Metairie CDP",
                    "+29.9977", "-090.1780"),
            geo_row("750", "0000004", "00100", 20),
        ])  # fmt: skip
        places = read_pl_places(path)
        assert places.to_dict("records") == [
            {
                "place": "00100",
                "name": "Abbeville",
                "kind": "city",
                "pop": 11186,
                "lat": 29.9751,
                "lon": -92.1343,
            },
            {
                "place": "50115",
                "name": "Metairie",
                "kind": "community",
                "pop": 143507,
                "lat": 29.9977,
                "lon": -90.178,
            },
        ]

    def test_blocks_carry_their_place_code_or_none(self, tmp_path):
        path = write_zip(tmp_path, [
            geo_row("750", "0000001", "00100", 20),
            geo_row("750", "0000002", "99999", 5),
        ])  # fmt: skip
        blocks = read_pl_blocks(path)
        assert blocks["place"].tolist() == ["00100", None]


@pytest.mark.parametrize(
    ("name", "basename", "expected"),
    [
        ("Abbeville city", "Abbeville", ("Abbeville", "city")),
        ("Metairie CDP", "Metairie", ("Metairie", "community")),
        ("Urban Honolulu CDP", "Urban Honolulu", ("Urban Honolulu", "community")),
        # Consolidated cities: the Census puts the type, and "(balance)", in the base name too.
        ("Indianapolis city (balance)", "Indianapolis city (balance)", ("Indianapolis", "city")),
        ("Louisville/Jefferson County metro government (balance)",
         "Louisville/Jefferson County metro government (balance)",
         ("Louisville/Jefferson County", "metro government")),
        ("Butte-Silver Bow (balance)", "Butte-Silver Bow (balance)", ("Butte-Silver Bow", "")),
        # A name that is all name keeps it, even one ending in a word like "City".
        ("Carson City", "Carson City", ("Carson City", "")),
        ("Hill town", "Hill town", ("Hill town", "")),
    ],
)  # fmt: skip
def test_place_name_and_kind_in_plain_words(name, basename, expected):
    assert place_name_and_kind(name, basename) == expected


def places_table() -> pd.DataFrame:
    return pd.DataFrame([
        {"state": "LA", "place": "001", "name": "Big City", "kind": "city", "pop": 1000},
        {"state": "LA", "place": "002", "name": "Suburb", "kind": "community", "pop": 300},
        {"state": "LA", "place": "003", "name": "Empty", "kind": "town", "pop": 0},
    ])  # fmt: skip


def placed_blocks() -> pd.DataFrame:
    rows = [
        ("LA-01", "001", 600), ("LA-01", "001", 100), ("LA-02", "001", 300),
        ("LA-02", "002", 300), ("LA-02", None, 400), ("LA-01", "003", 0),
    ]  # fmt: skip
    return pd.DataFrame(
        [{"district_id": d, "state": "LA", "place": p, "pop": n} for d, p, n in rows]
    )


def test_district_places_counts_each_places_people_in_each_district():
    table = district_places(placed_blocks(), places_table())
    got = {(r.district_id, r.name): (r.pop, r.place_pop, r.kind) for r in table.itertuples()}
    # Blocks with nobody in them don't put a place in a district.
    assert got == {
        ("LA-01", "Big City"): (700, 1000, "city"),
        ("LA-02", "Big City"): (300, 1000, "city"),
        ("LA-02", "Suburb"): (300, 300, "community"),
    }


class TestPlaceProblems:
    def test_counts_that_add_up_pass(self):
        table = district_places(placed_blocks(), places_table())
        assert place_problems(placed_blocks(), table, places_table()) == []

    def test_a_place_whose_districts_dont_add_up_to_its_total_is_reported(self):
        places = places_table()
        places.loc[0, "pop"] = 1001
        table = district_places(placed_blocks(), places)
        problems = place_problems(placed_blocks(), table, places)
        assert problems == ["LA Big City (001): 1,000 people in districts, 1,001 in the Census"]

    def test_a_block_in_an_unknown_place_is_reported(self):
        blocks = pd.concat([placed_blocks(), pd.DataFrame(
            [{"district_id": "LA-01", "state": "LA", "place": "999", "pop": 7}]
        )])  # fmt: skip
        table = district_places(blocks, places_table())
        assert place_problems(blocks, table, places_table()) == [
            "LA: 7 people in blocks of a place with no name (999)"
        ]


class TestPlacesRecords:
    def test_lists_the_largest_places_first_with_the_share_in_any_place(self):
        table = district_places(placed_blocks(), places_table())
        districts = pd.DataFrame({"district_id": ["LA-01", "LA-02"], "pop": [700, 1000]})
        records = {r["id"]: r for r in places_records(table, districts)}
        assert records["LA-02"] == {
            "id": "LA-02",
            "places": [
                {"name": "Big City", "kind": "city", "pop": 300, "place_pop": 1000},
                {"name": "Suburb", "kind": "community", "pop": 300, "place_pop": 300},
            ],
            "more": 0,
            "in_places": 0.6,
        }
        assert records["LA-01"]["in_places"] == 1.0

    def test_keeps_only_the_largest_and_counts_the_rest(self):
        n = MAX_PLACES + 3
        table = pd.DataFrame({
            "district_id": "LA-01", "state": "LA", "place": [f"{i:03}" for i in range(n)],
            "name": [f"Place {i:02}" for i in range(n)], "kind": "town",
            "pop": list(range(n, 0, -1)), "place_pop": 100,
        })  # fmt: skip
        records = places_records(table, pd.DataFrame({"district_id": ["LA-01"], "pop": [1000]}))
        assert [p["name"] for p in records[0]["places"]] == [
            f"Place {i:02}" for i in range(MAX_PLACES)
        ]
        assert records[0]["more"] == 3

    def test_a_district_with_no_places_still_gets_a_record(self):
        empty = district_places(placed_blocks().iloc[:0], places_table())
        records = places_records(empty, pd.DataFrame({"district_id": ["AK-AL"], "pop": [733391]}))
        assert records == [{"id": "AK-AL", "places": [], "more": 0, "in_places": 0.0}]


@pytest.mark.parametrize(
    ("name", "kind", "expected"),
    [
        ("Nashville-Davidson", "metropolitan government", "Nashville"),
        ("Louisville/Jefferson County", "metro government", "Louisville"),
        ("Lexington-Fayette", "urban county", "Lexington"),
        ("Augusta-Richmond County", "consolidated government", "Augusta"),
        ("Macon-Bibb County", "", "Macon"),
        ("Lynchburg, Moore County", "metropolitan government", "Lynchburg"),
        # Ordinary hyphenated and slashed names stay whole.
        ("Winston-Salem", "city", "Winston-Salem"),
        ("Wilkes-Barre", "city", "Wilkes-Barre"),
        ("Urban Honolulu", "community", "Urban Honolulu"),
    ],
)
def test_map_label_drops_the_county_from_consolidated_city_names(name, kind, expected):
    assert map_label(name, kind) == expected


def piece_blocks(*rows: tuple) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["district_id", "state", "place", "lon", "lat", "pop"])


class TestPiecePoints:
    def test_puts_each_part_of_a_place_at_a_block_near_its_population_center(self):
        from gerry.places import piece_points

        placed = piece_blocks(
            ("LA-01", "LA", "00100", -90.0, 30.0, 1),
            ("LA-01", "LA", "00100", -89.0, 30.0, 2),
            ("LA-01", "LA", "00100", -88.0, 30.0, 1),
            ("LA-02", "LA", "00100", -85.0, 31.0, 5),
            ("LA-02", "LA", None, -84.0, 31.0, 50),  # outside any place
            ("LA-02", "LA", "00200", -83.0, 31.0, 0),  # nobody lives here
        )
        pieces = piece_points(placed)
        assert pieces.to_dict("records") == [
            {"district_id": "LA-01", "state": "LA", "place": "00100", "pop": 4, "lon": -89.0,
             "lat": 30.0},
            {"district_id": "LA-02", "state": "LA", "place": "00100", "pop": 5, "lon": -85.0,
             "lat": 31.0},
        ]  # fmt: skip

    def test_never_puts_the_point_in_the_empty_middle_of_a_crescent(self):
        from gerry.places import piece_points

        # The population center (-89, 30) is between the blocks, possibly outside the district.
        placed = piece_blocks(
            ("LA-01", "LA", "00100", -90.0, 30.0, 3),
            ("LA-01", "LA", "00100", -88.0, 30.0, 3),
        )
        (point,) = piece_points(placed)[["lon", "lat"]].itertuples(index=False)
        assert tuple(point) in {(-90.0, 30.0), (-88.0, 30.0)}


class TestPopulatedPoints:
    def test_moves_a_place_to_the_block_nearest_where_all_its_people_live(self):
        from gerry.places import populated_points

        # San Francisco's internal point is in the ocean; its people live on land, in 2 districts.
        places = pd.DataFrame({
            "state": ["CA", "CA"], "place": ["67000", "00500"], "name": ["San Francisco", "Empty"],
            "kind": ["city", "city"], "pop": [9, 0], "lat": [37.73, 38.0], "lon": [-123.03, -121.0],
        })  # fmt: skip
        placed = piece_blocks(
            ("CA-11", "CA", "67000", -122.50, 37.75, 1),
            ("CA-11", "CA", "67000", -122.42, 37.77, 4),
            ("CA-15", "CA", "67000", -122.40, 37.72, 4),
            ("CA-15", "CA", "00500", -121.00, 38.50, 0),  # a place with nobody in it
        )
        moved = populated_points(places, placed)
        assert moved[["place", "lon", "lat"]].to_dict("records") == [
            {"place": "67000", "lon": -122.42, "lat": 37.77},
            {"place": "00500", "lon": -121.0, "lat": 38.0},  # keeps its internal point
        ]
        assert moved[["name", "kind", "pop"]].equals(places[["name", "kind", "pop"]])
