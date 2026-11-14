"""Tests for say/extras.py. All data here is FAKE TEST DATA (tiny temp files)."""
import json
import os
import shutil
import tempfile
import unittest

from say import compare, extras


def _tmpdir(test):
    d = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, d, ignore_errors=True)
    return d


def _resp(brand_vals, n=10):
    """brand_vals: {brand: (say, intent, aware_bool)}; n identical personas."""
    return [{"persona_id": f"P{i}", "brand_id": b, "say": v[0], "intent": v[1], "aware": v[2]}
            for i in range(n) for b, v in brand_vals.items()]


# ----------------------------------------------------------------------------- exact permutation p

class ExactPermTests(unittest.TestCase):
    def test_perfect_order_n4(self):
        # Only 2 of 24 orderings reach |rho| = 1.
        self.assertAlmostEqual(extras.exact_perm_p([1, 2, 3, 4], [10, 20, 30, 40]), 2 / 24)

    def test_ties_and_limits(self):
        p = extras.exact_perm_p([1, 1, 2, 3], [5, 6, 7, 8])
        self.assertTrue(0 < p <= 1)
        self.assertIsNone(extras.exact_perm_p([1, 2], [1, 2]))
        self.assertIsNone(extras.exact_perm_p(list(range(9)), list(range(9))))
        self.assertIsNone(extras.exact_perm_p([1, 1, 1], [1, 2, 3]))  # all tied: undefined


# ----------------------------------------------------------------------------- 1. sensitivity

class SensitivityTests(unittest.TestCase):
    def setUp(self):
        self.dir = _tmpdir(self)
        files = {
            "a": {"id": "a", "name": "A", "revenue_usd": 400, "pass": True},
            "b": {"id": "b", "name": "B", "revenue_usd": 300, "pass": True},
            "c": {"id": "c", "name": "C", "revenue_usd": 200, "pass": True},
            "x": {"id": "x", "name": "X", "revenue_usd": 350, "pass": False, "recheck_pass": True},
            "y": {"id": "y", "name": "Y", "revenue_usd": 50, "pass": False, "recheck_pass": False},
        }
        for bid, f in files.items():
            with open(os.path.join(self.dir, f"{bid}.json"), "w") as fh:
                json.dump(f, fh)
        self.resp = _resp({"a": (8, 8, True), "b": (7, 7, True), "c": (6, 6, False),
                           "x": (1, 1, False), "y": (5, 5, True)})
        stats = compare.brand_stats(self.resp)
        brands = [{"id": b, "name": b.upper(), "revenue_usd": r, **stats[b]}
                  for b, r in (("a", 400), ("b", 300), ("c", 200))]
        self.run = {"brands": brands,
                    "agreement": {q: compare.agreement(brands, q) for q in compare.QUESTIONS},
                    "trust_card": {"verdict": "ask_real_people"}}
        for q in compare.QUESTIONS:  # run files store rounded numbers
            self.run["agreement"][q] = {k: (round(v, 4) if isinstance(v, float) else v)
                                        for k, v in self.run["agreement"][q].items()}

    def test_adds_only_recheck_pass_brands(self):
        out = extras.sensitivity_view(self.run, self.resp, self.dir)
        self.assertEqual(out["added_brands"], ["x"])
        self.assertEqual(out["brands"], ["a", "b", "c", "x"])
        self.assertEqual(out["n_brands"], 4)
        self.assertTrue(out["label"].startswith("SENSITIVITY CHECK"))
        self.assertIn("summary", out)
        self.assertTrue(out["display_only"])
        self.assertTrue(out["reproduces_main"], out["reproduce_mismatches"])

    def test_spearman_and_verdict(self):
        out = extras.sensitivity_view(self.run, self.resp, self.dir)
        # crowd intent order a>b>c>x ; revenue a>x>b>c -> rho = 1 - 6*(0+1+1+4)/(4*15) = 0.4
        self.assertAlmostEqual(out["agreement"]["intent"]["spearman"], 0.4)
        self.assertEqual(out["main_verdict"], "ask_real_people")
        self.assertIn(out["verdict_if_8"]["verdict"], ("trust", "verify", "ask_real_people"))
        self.assertEqual(out["verdict_would_change"], out["verdict_if_8"]["verdict"] != "ask_real_people")
        x = [r for r in out["table"] if r["id"] == "x"][0]
        self.assertTrue(x["added_after_results"])
        self.assertEqual(x["rank_revenue"], 2)

    def test_mismatch_is_reported(self):
        self.run["agreement"]["intent"]["spearman"] = 0.123
        out = extras.sensitivity_view(self.run, self.resp, self.dir)
        self.assertFalse(out["reproduces_main"])
        self.assertIn("intent.spearman", out["reproduce_mismatches"])

    def test_ties_in_added_brand(self):
        # x ties with c on every question -> shared average rank 3.5 (4 brands)
        resp = _resp({"a": (8, 8, True), "b": (7, 7, True), "c": (6, 6, False), "x": (6, 6, False)})
        out = extras.sensitivity_view(self.run, resp, self.dir)
        ranks = {r["id"]: r["rank_intent"] for r in out["table"]}
        self.assertEqual(ranks["c"], 3.5)
        self.assertEqual(ranks["x"], 3.5)


# ----------------------------------------------------------------------------- 2. order effect

def _order_csv(test, personas, brands=("a", "b", "c"), header_repeat=True):
    """personas: list of (pid, order list, {brand: (say, intent)})."""
    cols = ["ID"] + [f"SAY__{b}" for b in brands] + [f"INTENT__{b}" for b in brands] + ["Display Order"]
    lines = [",".join(cols)]
    if header_repeat:  # Flashpoint style: header again, with a longer order-column label
        lines.append(",".join(cols[:-1] + ["Display Order/Loop order: Brand Evaluation"]))
    for pid, order, sc in personas:
        lines.append(",".join([pid] + [str(sc[b][0]) for b in brands] + [str(sc[b][1]) for b in brands]
                              + ["|".join(order)]))
    path = os.path.join(_tmpdir(test), "export.csv")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


class OrderEffectTests(unittest.TestCase):
    def test_no_effect_when_scores_ignore_position(self):
        orders = [["a", "b", "c"], ["b", "c", "a"], ["c", "a", "b"]] * 4
        ps = [(f"P{i}", o, {"a": (5, 5), "b": (5, 5), "c": (5, 5)}) for i, o in enumerate(orders)]
        out = extras.order_effect(_order_csv(self, ps), ["a", "b", "c"], n_boot=200, n_perm=50)
        self.assertEqual(out["label"], "SYNTHETIC")
        self.assertEqual(out["n_personas"], 12)
        self.assertEqual(out["rows_skipped"]["header_rows"], 1)
        q = out["questions"]["say"]
        self.assertEqual(q["slope_per_position"], 0)
        self.assertEqual(q["mean_by_position"], [5, 5, 5])
        self.assertEqual(q["n_by_position"], [12, 12, 12])
        self.assertTrue(q["could_be_chance"])
        self.assertIn("summary", out)

    def test_detects_position_bias(self):
        # Score = 9 when shown 1st, 6 when 2nd, 3 when 3rd, for every brand: slope -3 exactly.
        orders = [["a", "b", "c"], ["b", "c", "a"], ["c", "a", "b"], ["a", "c", "b"]] * 5
        ps = []
        for i, o in enumerate(orders):
            sc = {b: (9 - 3 * o.index(b), 9 - 3 * o.index(b)) for b in "abc"}
            ps.append((f"P{i}", o, sc))
        out = extras.order_effect(_order_csv(self, ps), ["a", "b", "c"], n_boot=200, n_perm=200)
        q = out["questions"]["intent"]
        self.assertAlmostEqual(q["slope_per_position"], -3.0)
        self.assertEqual(q["slope_low"], -3.0)
        self.assertEqual(q["slope_high"], -3.0)
        self.assertFalse(q["could_be_chance"])
        self.assertEqual(q["mean_first"], 9)
        self.assertEqual(q["mean_last"], 3)
        self.assertEqual(q["first_minus_last"], 6)
        self.assertEqual(q["drift_first_to_last"], -6)
        self.assertLess(q["any_position_effect_p"], 0.05)
        self.assertIn("position bias", out["summary"])

    def test_brand_centering_removes_brand_imbalance(self):
        # Brand a is always first and best; no real position effect beyond brand identity.
        ps = [(f"P{i}", ["a", "b", "c"] if i % 2 else ["a", "c", "b"],
               {"a": (9, 9), "b": (3, 3), "c": (3, 3)}) for i in range(10)]
        out = extras.order_effect(_order_csv(self, ps), ["a", "b", "c"], n_boot=100, n_perm=50)
        q = out["questions"]["say"]
        self.assertLess(q["slope_per_position"], 0)          # raw slope is fooled by brand a
        self.assertAlmostEqual(q["slope_brand_centered"], 0)  # centered slope is not

    def test_header_repeat_absent_and_subset_of_brands(self):
        orders = [["a", "b", "c"], ["c", "b", "a"]]
        ps = [(f"P{i}", o, {"a": (4, 4), "b": (5, 5), "c": (6, 6)}) for i, o in enumerate(orders)]
        out = extras.order_effect(_order_csv(self, ps, header_repeat=False), ["a", "c"], n_boot=50, n_perm=20)
        self.assertEqual(out["n_personas"], 2)
        self.assertEqual(out["rows_skipped"]["header_rows"], 0)
        self.assertEqual(out["n_positions"], 3)
        self.assertEqual(out["questions"]["say"]["n_by_position"], [2, 0, 2])
        self.assertIsNone(out["questions"]["say"]["mean_by_position"][1])

    def test_missing_order_column_raises(self):
        path = os.path.join(_tmpdir(self), "x.csv")
        with open(path, "w") as f:
            f.write("ID,SAY__a\nP1,5\n")
        with self.assertRaises(ValueError):
            extras.order_effect(path, ["a"])


# ----------------------------------------------------------------------------- 3. compression

class CompressionTests(unittest.TestCase):
    def test_numbers(self):
        resp = [{"brand_id": "a", "say": v, "intent": 1} for v in (5, 6, 7, 10)] + \
               [{"brand_id": "b", "say": v, "intent": 2} for v in (1, 6, 6, 6)] + \
               [{"brand_id": "b", "say": None, "intent": 11}]  # skipped: missing / out of range
        out = extras.compression(resp)
        self.assertEqual(out["label"], "SYNTHETIC")
        s = out["questions"]["say"]
        self.assertEqual(s["n_answers"], 8)
        self.assertEqual(s["share_5_to_7"], 0.75)
        self.assertEqual(s["counts_1_to_10"]["6"], 4)
        self.assertEqual(sum(s["counts_1_to_10"].values()), 8)
        self.assertEqual(s["brand_mean_spread"], 2.25)  # 7.0 - 4.75
        self.assertEqual(s["mean"], 5.875)
        self.assertAlmostEqual(s["sd"], 2.4749, places=4)
        i = out["questions"]["intent"]
        self.assertEqual(i["n_answers"], 8)
        self.assertEqual(i["share_5_to_7"], 0)
        self.assertEqual(i["brand_mean_spread"], 1)
        self.assertIsNone(out["real_reference"])
        self.assertIn("no claim about real people", out["summary"])

    def test_brand_filter_and_ties(self):
        resp = _resp({"a": (6, 6, True), "b": (6, 6, True), "c": (2, 2, False)}, n=3)
        out = extras.compression(resp, brand_ids=["a", "b"])
        s = out["questions"]["say"]
        self.assertEqual(s["n_brands"], 2)
        self.assertEqual(s["brand_mean_spread"], 0)
        self.assertEqual(s["share_5_to_7"], 1)
        self.assertEqual(s["sd"], 0)

    def test_real_reference_needs_source(self):
        with self.assertRaises(ValueError):
            extras.compression([], real_reference={"sd": 2.0})
        out = extras.compression([], real_reference={"source": "https://example.org/x", "sd": 2.0})
        self.assertEqual(out["real_reference"]["source"], "https://example.org/x")
        self.assertIsNone(out["real_reference_note"])


# ----------------------------------------------------------------------------- 4. crowd vs crowd

class CrowdVsCrowdTests(unittest.TestCase):
    REV = {"a": 400, "b": 300, "c": 200, "d": 100}

    def test_crowds_agree_but_not_with_revenue(self):
        main = _resp({"a": (1, 1, False), "b": (2, 2, False), "c": (3, 3, True), "d": (4, 4, True)})
        rep = _resp({"a": (1, 1, False), "b": (2, 2, False), "c": (3, 3, True), "d": (4, 4, True)})
        out = extras.crowd_vs_crowd(main, rep, list(self.REV), self.REV, n_boot=200)
        q = out["questions"]["intent"]
        self.assertEqual(out["label"], "SYNTHETIC")
        self.assertEqual(q["crowd_vs_crowd"], 1)
        self.assertEqual(q["main_vs_revenue"], -1)
        self.assertEqual(q["gap"], 2)
        self.assertTrue(q["higher_than_both"])
        self.assertAlmostEqual(q["crowd_vs_crowd_perm_p"], 2 / 24, places=4)
        self.assertIn("something other than spending", out["summary"])

    def test_not_higher_when_crowds_disagree(self):
        main = _resp({"a": (4, 4, True), "b": (3, 3, True), "c": (2, 2, False), "d": (1, 1, False)})
        rep = _resp({"a": (4, 4, True), "b": (1, 1, True), "c": (3, 3, False), "d": (2, 2, False)})
        out = extras.crowd_vs_crowd(main, rep, list(self.REV), self.REV, n_boot=200)
        q = out["questions"]["intent"]
        self.assertEqual(q["main_vs_revenue"], 1)
        self.assertLess(q["gap"], 0)
        self.assertFalse(q["higher_than_both"])
        self.assertFalse(q["clearly_higher"])
        self.assertIn("do not agree", out["summary"])

    def test_ties_and_missing_brand(self):
        main = _resp({"a": (5, 5, True), "b": (5, 5, True), "c": (2, 2, False), "d": (1, 1, False)})
        rep = _resp({"a": (5, 5, True), "b": (5, 5, True), "c": (2, 2, False)})  # d missing
        out = extras.crowd_vs_crowd(main, rep, list(self.REV), self.REV, n_boot=100)
        q = out["questions"]["say"]
        self.assertEqual(q["n_brands"], 3)
        self.assertEqual(q["crowd_vs_crowd"], 1)       # identical tied ranks
        self.assertAlmostEqual(q["main_vs_revenue"], 0.866, places=3)  # ranks 1.5,1.5,3 vs 1,2,3

    def test_too_few_brands(self):
        main = _resp({"a": (5, 5, True), "b": (4, 4, True)})
        out = extras.crowd_vs_crowd(main, main, ["a", "b"], self.REV, n_boot=10)
        self.assertIsNone(out["questions"]["intent"]["gap"])
        self.assertIn("Not enough", out["summary"])


if __name__ == "__main__":
    unittest.main()
