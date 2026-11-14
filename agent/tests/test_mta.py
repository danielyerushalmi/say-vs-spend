import json
import tempfile
import unittest
import urllib.parse
from unittest import mock

from agent import mta

WINDOW = {"start": "2026-10-05T00:00:00", "end": "2026-10-31T00:00:00", "hour_from": 6, "hour_to": 10}


def fake_rows():
    """Station '1': every weekday 100, except Wednesdays 200. Weekends 10."""
    rows = []
    from datetime import date, timedelta
    d = date(2026, 10, 5)
    while d < date(2026, 10, 31):
        n = 10 if d.weekday() >= 5 else (200 if d.weekday() == 2 else 100)
        rows.append({"station_complex_id": "1", "station_complex": "Test St", "borough": "Queens",
                     "day": d.isoformat() + "T00:00:00.000", "r": str(n)})
        d += timedelta(days=1)
    return rows


class MtaTests(unittest.TestCase):
    def test_url_has_filters_and_exclusions(self):
        url = mta._daily_url(["1", "41"], WINDOW, ["2026-10-12"])
        q = urllib.parse.unquote(url)
        self.assertIn("station_complex_id IN ('1','41')", q)
        self.assertIn("date_extract_hh(transit_timestamp) >= 6", q)
        self.assertIn("date_extract_hh(transit_timestamp) < 10", q)
        self.assertIn("NOT (transit_timestamp >= '2026-10-12T00:00:00' AND transit_timestamp < '2026-10-13T00:00:00')", q)

    def test_shares_sum_to_one_and_ignore_weekends(self):
        daily, _ = mta._rows_to_daily(fake_rows())
        shares, totals, counts = mta.compute_shares(daily["1"])
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=9)
        self.assertEqual(counts, {d: 4 for d in mta.DAYS})
        self.assertEqual(totals["Wed"], 800)
        self.assertAlmostEqual(shares["Wed"], 200 / 600)
        self.assertAlmostEqual(shares["Mon"], 100 / 600)

    def test_missing_day_does_not_bias_shares(self):
        daily, _ = mta._rows_to_daily(fake_rows())
        del daily["1"]["2026-10-12"]  # a Monday
        shares, totals, counts = mta.compute_shares(daily["1"])
        self.assertEqual(counts["Mon"], 3)
        self.assertAlmostEqual(shares["Mon"], 100 / 600)

    def test_fetch_measured_and_cache(self):
        coords = [{"station_complex_id": "1", "lat": "40.77", "lon": "-73.91"}]
        calls = []

        def fake_http(url):
            calls.append(url)
            return coords if "max(latitude)" in urllib.parse.unquote(url) else fake_rows()

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mta, "_http_get", fake_http):
            out = mta.fetch_measured(["1"], WINDOW, cache_dir=tmp)
            self.assertEqual(len(calls), 2)
            mta.fetch_measured(["1"], WINDOW, cache_dir=tmp)
            self.assertEqual(len(calls), 2, "second call should come from the cache")
            daily = mta.fetch_daily(["1"], WINDOW, cache_dir=tmp)
        rec = out["1"]
        self.assertEqual(rec["name"], "Test St")
        self.assertEqual(rec["lat"], 40.77)
        self.assertIn("data.ny.gov", rec["query_url"])
        self.assertEqual(daily["1"]["2026-10-05"], 100)

    def test_http_retries_then_raises(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("boom")), \
             mock.patch("time.sleep"):
            with self.assertRaises(RuntimeError):
                mta._http_get("http://example.invalid")


if __name__ == "__main__":
    unittest.main()
