import json
import tempfile
import unittest

from agent import features as f

HEADER = list(f.VARIABLES) + ["state", "county", "tract"]


def acs_payload(**over):
    vals = {f.WORKERS: "1000", f.WFH: "200", f.TRANSIT: "500", f.INCOME: "80000",
            f.HOUSEHOLDS: "800", f.POP25: "2000", "B15003_022E": "300", "B15003_023E": "100",
            "B15003_024E": "50", "B15003_025E": "50"}
    vals.update(over)
    return [HEADER, [vals[v] for v in f.VARIABLES] + ["36", "047", "000100"]]


GEO = {"result": {"geographies": {"Census Tracts": [
    {"STATE": "36", "COUNTY": "047", "TRACT": "000100", "GEOID": "36047000100"}]}}}


class FakeHttp:
    def __init__(self, acs_by_year):
        self.acs_by_year = acs_by_year
        self.calls = 0

    def __call__(self, url):
        self.calls += 1
        if "geocoding" in url:
            return json.dumps(GEO)
        for year, payload in self.acs_by_year.items():
            if f"/{year}/" in url:
                if payload is None:
                    raise RuntimeError("boom")
                return json.dumps(payload)
        raise RuntimeError("unexpected url " + url)


class TestParsing(unittest.TestCase):
    def test_sentinels_are_missing(self):
        for bad in ("-666666666", "-999999999", None, "", "abc"):
            self.assertIsNone(f.clean_number(bad))
        self.assertEqual(f.clean_number("12"), 12.0)

    def test_measures(self):
        m = f.tract_measures(f.parse_acs_row(acs_payload()))
        self.assertAlmostEqual(m["wfh_share_pct"], 20.0)
        self.assertAlmostEqual(m["transit_share_pct"], 50.0)
        self.assertAlmostEqual(m["bachelors_pct"], 25.0)  # 500 / 2000
        self.assertEqual(m["median_income_local"], 80000.0)

    def test_sentinel_income_gives_none(self):
        m = f.tract_measures(f.parse_acs_row(acs_payload(**{f.INCOME: "-666666666"})))
        self.assertIsNone(m["median_income_local"])

    def test_missing_bachelor_part_gives_none(self):
        m = f.tract_measures(f.parse_acs_row(acs_payload(B15003_023E="-666666666")))
        self.assertIsNone(m["bachelors_pct"])

    def test_zero_workers_gives_none(self):
        m = f.tract_measures(f.parse_acs_row(acs_payload(**{f.WORKERS: "0"})))
        self.assertIsNone(m["wfh_share_pct"])


class TestWeighting(unittest.TestCase):
    def test_income_household_weighted(self):
        a = {"median_income_local": 100000, "households": 300, "wfh_share_pct": 10, "workers": 100,
             "transit_share_pct": 0, "bachelors_pct": 0, "pop25": 1}
        b = {"median_income_local": 40000, "households": 100, "wfh_share_pct": 30, "workers": 300,
             "transit_share_pct": 0, "bachelors_pct": 0, "pop25": 1}
        c = f.combine_tracts([a, b])
        self.assertAlmostEqual(c["median_income_local"], 85000.0)
        self.assertAlmostEqual(c["wfh_share_pct"], 25.0)

    def test_missing_tract_is_skipped(self):
        a = {"median_income_local": None, "households": 300, "workers": 0}
        b = {"median_income_local": 50000, "households": 100, "workers": 0}
        self.assertEqual(f.combine_tracts([a, b])["median_income_local"], 50000)


class TestStationFeatures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.st = [{"id": "41", "lat": 40.67, "lon": -73.98}]

    def test_happy_path_and_cache(self):
        http = FakeHttp({2023: acs_payload()})
        out = f.station_features(self.st, self.tmp.name, http)["41"]
        self.assertEqual(out["tracts"], ["36047000100"])
        self.assertEqual(out["acs_year"], 2023)
        self.assertAlmostEqual(out["wfh_share_pct"], 20.0)
        self.assertEqual(len(out["source_urls"]), 2)
        calls = http.calls
        f.station_features(self.st, self.tmp.name, http)
        self.assertEqual(http.calls, calls)  # second run fully cached

    def test_falls_back_to_2022(self):
        http = FakeHttp({2023: None, 2022: acs_payload()})
        out = f.station_features(self.st, self.tmp.name, http)["41"]
        self.assertEqual(out["acs_year"], 2022)

    def test_failure_is_reported_not_raised(self):
        http = FakeHttp({2023: None, 2022: None})
        out = f.station_features(self.st, self.tmp.name, http)["41"]
        self.assertIn("error", out)

    def test_no_coordinates(self):
        out = f.station_features([{"id": "9", "lat": None, "lon": None}], self.tmp.name, FakeHttp({}))
        self.assertIn("error", out["9"])


if __name__ == "__main__":
    unittest.main()
