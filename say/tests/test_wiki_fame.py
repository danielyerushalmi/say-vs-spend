"""Tests for say.fame.wiki. No network."""
import datetime as dt
import io
import json
import os
import tempfile
import unittest
import urllib.error

from say.fame import wiki


class FakeResp(io.BytesIO):
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False


def ok_resp(views):
    return FakeResp(json.dumps({"items": [{"views": v} for v in views]}).encode())


class UrlTests(unittest.TestCase):
    def test_window_365_days_ending_yesterday(self):
        s, e = wiki.window(dt.date(2026, 11, 14))
        self.assertEqual((s, e), ("20251114", "20261113"))
        d = (dt.datetime.strptime(e, "%Y%m%d") - dt.datetime.strptime(s, "%Y%m%d")).days
        self.assertEqual(d, 364)  # 365 days inclusive

    def test_build_url(self):
        u = wiki.build_url("Hims_&_Hers_Health", "20251114", "20261113")
        self.assertEqual(u, "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Hims_%26_Hers_Health/daily/20251114/20261113")
        self.assertIn("Figs_(company)", wiki.build_url("Figs_(company)", "a", "b"))


class FetchTests(unittest.TestCase):
    def test_sums_and_null_title(self):
        sleeps = []
        res = wiki.fetch({"a": "A", "b": None}, dt.date(2026, 11, 14),
                         opener=lambda req, timeout=0: ok_resp([1, 2, 3]), sleep=sleeps.append)
        self.assertEqual(res["a"]["views_365d"], 6)
        self.assertEqual(res["a"]["status"], "ok")
        self.assertIsNone(res["b"]["views_365d"])
        self.assertEqual(res["b"]["status"], "no_article")

    def test_pacing_between_requests(self):
        sleeps = []
        wiki.fetch({"a": "A", "b": "B"}, dt.date(2026, 11, 14),
                   opener=lambda req, timeout=0: ok_resp([1]), sleep=sleeps.append)
        self.assertTrue(any(s >= 1.5 for s in sleeps))

    def test_429_retry_once_then_success(self):
        calls = []
        def opener(req, timeout=0):
            calls.append(1)
            if len(calls) == 1:
                raise urllib.error.HTTPError(req.full_url, 429, "x", {}, None)
            return ok_resp([5])
        sleeps = []
        res = wiki.fetch({"a": "A"}, dt.date(2026, 11, 14), opener=opener, sleep=sleeps.append)
        self.assertEqual(len(calls), 2)
        self.assertIn(10, sleeps)
        self.assertEqual(res["a"]["views_365d"], 5)

    def test_429_twice_stops(self):
        calls = []
        def opener(req, timeout=0):
            calls.append(1)
            raise urllib.error.HTTPError(req.full_url, 429, "x", {}, None)
        res = wiki.fetch({"a": "A", "b": "B"}, dt.date(2026, 11, 14), opener=opener, sleep=lambda s: None)
        self.assertEqual(len(calls), 2)  # one try + one retry, then stop
        self.assertEqual(res["a"]["status"], "error_429")
        self.assertIsNone(res["b"]["views_365d"])
        self.assertIn("Skipped", res["b"]["note"])

    def test_404_recorded(self):
        def opener(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, 404, "x", {}, None)
        res = wiki.fetch({"a": "A"}, dt.date(2026, 11, 14), opener=opener, sleep=lambda s: None)
        self.assertEqual(res["a"]["status"], "no_data")


BRANDS = [{"id": "a", "revenue_usd": 100}, {"id": "b", "revenue_usd": 200},
          {"id": "c", "revenue_usd": 300}, {"id": "d", "revenue_usd": 400}, {"id": "e", "revenue_usd": 500}]


class AgreementTests(unittest.TestCase):
    def test_perfect_agreement(self):
        r = wiki.wiki_fame_agreement(BRANDS, {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}, n_boot=200)
        self.assertAlmostEqual(r["spearman"], 1.0)
        self.assertEqual(r["avg_places_off"], 0)
        self.assertEqual(r["n_brands"], 5)
        for k in ("wobble_low", "wobble_high", "could_be_chance"):
            self.assertIn(k, r)

    def test_reversed(self):
        r = wiki.wiki_fame_agreement(BRANDS, {"a": 5, "b": 4, "c": 3, "d": 2, "e": 1}, n_boot=200)
        self.assertAlmostEqual(r["spearman"], -1.0)

    def test_null_views_left_out(self):
        r = wiki.wiki_fame_agreement(BRANDS, {"a": 1, "b": None, "c": 3, "d": 4}, n_boot=200)
        self.assertEqual(r["n_brands"], 3)

    def test_too_few(self):
        r = wiki.wiki_fame_agreement(BRANDS, {"a": 1, "b": 2}, n_boot=200)
        self.assertIsNone(r["spearman"])
        self.assertTrue(r["could_be_chance"])
        self.assertEqual(r["n_brands"], 2)


class FameBlockTests(unittest.TestCase):
    def _file(self, views):
        doc = {"start": "20251114", "end": "20261113",
               "brands": {k: {"views_365d": v, "url": "u-" + k} for k, v in views.items()}}
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(doc, f); f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_block(self):
        path = self._file({"a": 1, "b": 2, "c": 3, "d": 4, "e": None})
        run = {"brands": BRANDS, "agreement": {"intent": {"spearman": 0.5}}}
        b = wiki.fame_block(run, path)
        self.assertEqual(b["label"], "MEASURED (Wikipedia pageviews, last 365 days)")
        self.assertEqual(b["window"], {"start": "20251114", "end": "20261113"})
        self.assertIsNone(b["views"]["e"])
        self.assertEqual(b["urls"]["a"], "u-a")
        self.assertEqual(b["agreement"]["n_brands"], 4)
        self.assertAlmostEqual(b["agreement"]["spearman"], 1.0)
        self.assertFalse(b["crowd_beat_wiki_fame"])  # 0.5 < 1.0

    def test_crowd_beats(self):
        path = self._file({"a": 3, "b": 1, "c": 2, "d": 4, "e": 5})
        run = {"brands": BRANDS, "agreement": {"intent": {"spearman": 0.99}}}
        self.assertTrue(wiki.fame_block(run, path)["crowd_beat_wiki_fame"])

    def test_missing_is_false(self):
        path = self._file({"a": 1})
        run = {"brands": BRANDS, "agreement": {"intent": {"spearman": 0.9}}}
        self.assertFalse(wiki.fame_block(run, path)["crowd_beat_wiki_fame"])


if __name__ == "__main__":
    unittest.main()
