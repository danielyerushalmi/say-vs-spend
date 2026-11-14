"""Tests for say.compare. Hand-checked numbers; no network."""
import math
import unittest

from say import compare as c


class RanksTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(c.ranks([10, 30, 20]), [3, 1, 2])

    def test_lower_is_better(self):
        self.assertEqual(c.ranks([10, 30, 20], higher_is_better=False), [1, 3, 2])

    def test_ties_get_average_rank(self):
        # values 4 > 2 = 2 > 1 -> ranks 1, 2.5, 2.5, 4
        self.assertEqual(c.ranks([2, 4, 2, 1]), [2.5, 1, 2.5, 4])
        self.assertEqual(c.ranks([5, 5, 5]), [2, 2, 2])


class SpearmanTests(unittest.TestCase):
    def test_perfect(self):
        self.assertAlmostEqual(c.spearman([1, 2, 3, 4], [1, 2, 3, 4]), 1.0)

    def test_reversed(self):
        self.assertAlmostEqual(c.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)

    def test_hand_checked_with_ties(self):
        # values [1,2,2,4] vs [1,2,3,4]: ranks [4,2.5,2.5,1] vs [4,3,2,1]
        # cov 4.5, var 4.5 and 5 -> 4.5 / sqrt(22.5) = sqrt(0.9) = 0.948683...
        rho = c.spearman_from_values([1, 2, 2, 4], [1, 2, 3, 4])
        self.assertAlmostEqual(rho, math.sqrt(0.9), places=9)

    def test_textbook_no_ties(self):
        # d = [0,1,-1,0,0] on 5 items -> 1 - 6*2/(5*24) = 0.9
        self.assertAlmostEqual(c.spearman([1, 2, 3, 4, 5], [1, 3, 2, 4, 5]), 0.9)

    def test_none_cases(self):
        self.assertIsNone(c.spearman([1, 2], [1, 2]))            # fewer than 3
        self.assertIsNone(c.spearman([2, 2, 2], [1, 2, 3]))      # zero variance
        self.assertIsNone(c.spearman([1, 2, 3], [1, 2]))         # unequal lengths


class WobbleTests(unittest.TestCase):
    PAIRS = [(9, 100), (7, 90), (8, 60), (5, 50), (6, 40), (3, 30), (4, 20), (2, 10)]

    def test_contains_point_estimate_and_reproducible(self):
        rho = c.spearman_from_values([p[0] for p in self.PAIRS], [p[1] for p in self.PAIRS])
        low, high = c.bootstrap_wobble(self.PAIRS, n_boot=1000, seed=1)
        self.assertLessEqual(low, rho)
        self.assertGreaterEqual(high, rho)
        self.assertEqual((low, high), c.bootstrap_wobble(self.PAIRS, n_boot=1000, seed=1))

    def test_perfect_agreement_has_no_wobble_below_one(self):
        pairs = [(i, i * 10) for i in range(1, 9)]
        low, high = c.bootstrap_wobble(pairs, n_boot=300, seed=3)
        self.assertEqual((low, high), (1.0, 1.0))

    def test_too_few_brands(self):
        self.assertIsNone(c.bootstrap_wobble([(1, 1), (2, 2)]))

    def test_all_resamples_degenerate(self):
        self.assertIsNone(c.bootstrap_wobble([(5, 1), (5, 2), (5, 3)], n_boot=50))

    def test_could_be_chance(self):
        self.assertTrue(c.could_be_chance(-0.1, 0.8))
        self.assertTrue(c.could_be_chance(0.0, 0.8))   # touching 0 counts
        self.assertFalse(c.could_be_chance(0.2, 0.9))
        self.assertTrue(c.could_be_chance(None, None))


class PlacesAndGapsTests(unittest.TestCase):
    def test_avg_places_off(self):
        self.assertEqual(c.avg_places_off([1, 2, 3], [3, 2, 1]), (2 + 0 + 2) / 3)
        self.assertIsNone(c.avg_places_off([], []))

    def test_top_gaps_ordering(self):
        brands = [
            {"id": "a", "rank_intent": 1, "rank_revenue": 2},   # 1 off
            {"id": "b", "rank_intent": 2, "rank_revenue": 9},   # 7 off
            {"id": "c", "rank_intent": 8, "rank_revenue": 3},   # 5 off
            {"id": "d", "rank_intent": 4, "rank_revenue": 4},   # 0 off
            {"id": "e", "rank_intent": 6, "rank_revenue": 1},   # 5 off, ties with c: id order
        ]
        gaps = c.top_gaps(brands, "intent", k=3)
        self.assertEqual([g["brand_id"] for g in gaps], ["b", "c", "e"])
        self.assertEqual(gaps[0]["places_off"], -7)


class TrustTests(unittest.TestCase):
    # Rule (amended 12:10, before any result): cutoffs apply to wobble_low, not the point Spearman.
    def test_cutoffs_use_wobble_low(self):
        self.assertEqual(c.trust_verdict(0.9, 0.7, 0.95)["verdict"], "trust")          # low exactly 0.7
        self.assertEqual(c.trust_verdict(0.9, 0.6999, 0.95)["verdict"], "verify")
        self.assertEqual(c.trust_verdict(0.8, 0.4, 0.9)["verdict"], "verify")          # low exactly 0.4
        self.assertEqual(c.trust_verdict(0.8, 0.3999, 0.9)["verdict"], "ask_real_people")
        self.assertEqual(c.trust_verdict(-0.5, -0.9, 0.1)["verdict"], "ask_real_people")

    def test_high_point_low_wobble_is_downgraded(self):
        v = c.trust_verdict(0.8, -0.1, 0.95)
        self.assertEqual(v["verdict"], "ask_real_people")
        self.assertTrue(v["downgraded"])
        self.assertFalse(c.trust_verdict(0.75, 0.72, 0.9)["downgraded"])

    def test_point_spearman_never_upgrades(self):
        self.assertEqual(c.trust_verdict(0.2, -0.5, 0.7)["verdict"], "ask_real_people")

    def test_no_wobble(self):
        self.assertEqual(c.trust_verdict(None, None, None)["verdict"], "ask_real_people")
        self.assertEqual(c.trust_verdict(0.9, None, None)["verdict"], "ask_real_people")

    def test_rule_text_present(self):
        r = c.trust_verdict(0.9, 0.5, 1.0)["rule"]
        self.assertIn("0.7", r)
        self.assertIn("LOW end", r)

    def test_beat_fame_is_strict(self):
        self.assertTrue(c.crowd_beat_fame(0.8, 0.5))
        self.assertFalse(c.crowd_beat_fame(0.5, 0.5))
        self.assertFalse(c.crowd_beat_fame(None, 0.5))


class BrandStatsTests(unittest.TestCase):
    def test_means_and_missing_values_skipped(self):
        rows = [
            {"brand_id": "x", "say": 8, "intent": 6, "aware": True},
            {"brand_id": "x", "say": 4, "intent": None, "aware": False},
            {"brand_id": "x", "say": None, "intent": 2, "aware": None},
            {"brand_id": "x", "say": 99, "intent": "high", "aware": "yes"},  # unusable values
        ]
        s = c.brand_stats(rows)["x"]
        self.assertEqual(s["say_mean"], 6.0)
        self.assertEqual(s["n_say"], 2)
        self.assertEqual(s["intent_mean"], 4.0)
        self.assertEqual(s["n_intent"], 2)
        self.assertEqual(s["aware_share"], 0.5)
        self.assertEqual(s["n_aware"], 2)

    def test_brand_with_no_answers_has_none(self):
        s = c.brand_stats([{"brand_id": "y", "say": None}])["y"]
        self.assertIsNone(s["say_mean"])
        self.assertIsNone(s["aware_share"])


class BuyTests(unittest.TestCase):
    def test_buy_share(self):
        rows = [{"brand_id": "x", "buy": True}, {"brand_id": "x", "buy": False},
                {"brand_id": "x", "buy": None}, {"brand_id": "x", "buy": True}]
        s = c.brand_stats(rows)["x"]
        self.assertAlmostEqual(s["buy_share"], 2 / 3)
        self.assertEqual(s["n_buy"], 3)
        self.assertIsNone(c.brand_stats([{"brand_id": "y", "say": 5}])["y"]["buy_share"])

    def test_niche_boundary(self):
        self.assertEqual(c.NICHE_MAX, 0.30)
        self.assertIs(c.is_niche(0.30), False)
        self.assertIs(c.is_niche(0.2999), True)
        self.assertIs(c.is_niche(0.31), False)
        self.assertIsNone(c.is_niche(None))

    def _responses(self):
        # brand a: 10 yes (cutoff exactly met), b: 12 yes, c: 15 yes, d: 9 yes (excluded), e: 20 yes
        out = []
        for bid, n_yes, base in (("a", 10, 9), ("b", 12, 7), ("c", 15, 5), ("d", 9, 6), ("e", 20, 3)):
            for i in range(20):
                out.append({"brand_id": bid, "buy": i < n_yes, "intent": base if i < n_yes else 1})
        return out

    def test_buyers_intent_means_cutoff(self):
        m = c.buyers_intent_means(self._responses())
        self.assertEqual(m["a"], 9.0)      # exactly 10 buyers: kept
        self.assertIsNone(m["d"])          # 9 buyers: dropped
        self.assertEqual(m["e"], 3.0)

    def test_buyers_only_agreement_leaves_out_small_brands(self):
        brands = [{"id": "a", "revenue_usd": 500}, {"id": "b", "revenue_usd": 400}, {"id": "c", "revenue_usd": 300},
                  {"id": "d", "revenue_usd": 200}, {"id": "e", "revenue_usd": 100}]
        res = c.buyers_only_agreement(brands, self._responses(), n_boot=200)
        self.assertEqual(res["n_brands"], 4)
        self.assertAlmostEqual(res["spearman"], 1.0)  # a>b>c>e in intent, same order as revenue
        # too few buyers everywhere -> no agreement
        few = [{"brand_id": b["id"], "buy": True, "intent": 5} for b in brands]
        res = c.buyers_only_agreement(brands, few, n_boot=50)
        self.assertEqual(res["n_brands"], 0)
        self.assertIsNone(res["spearman"])


class SplitsTests(unittest.TestCase):
    def test_groups_with_fewer_than_three_brands_skipped(self):
        rev = {"a": 100, "b": 50, "c": 10}
        rows = []
        for bid, v in (("a", 9), ("b", 6), ("c", 2)):
            rows.append({"brand_id": bid, "say": v, "intent": v, "aware": True, "age_group": "young"})
        rows.append({"brand_id": "a", "say": 5, "intent": 5, "aware": True, "age_group": "old"})
        out = c.splits(rows, rev, n_boot=50)
        self.assertEqual([(s["by"], s["group"]) for s in out], [("age_group", "young")])
        self.assertAlmostEqual(out[0]["agreement"]["intent"]["spearman"], 1.0)


if __name__ == "__main__":
    unittest.main()
