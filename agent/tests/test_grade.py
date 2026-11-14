import unittest

from agent import grade
from agent.grade import DAYS

UNIFORM = {d: 0.2 for d in DAYS}


def shares(mon=0.0, tue=0.0, wed=0.0, thu=0.0, fri=0.0):
    """Uniform shares shifted by the given fractions (should sum to zero)."""
    return {"Mon": 0.2 + mon, "Tue": 0.2 + tue, "Wed": 0.2 + wed, "Thu": 0.2 + thu, "Fri": 0.2 + fri}


def station(sid, borough, measured, split="train", x=0, synthetic=None):
    return {"id": sid, "borough": borough, "split": split,
            "features": {"borough": borough, "x": x},
            "synthetic": synthetic or dict(UNIFORM), "measured": measured}


class TestBasics(unittest.TestCase):
    def test_normalize_ignores_none(self):
        s = grade.normalize({"Mon": 10, "Tue": 20, "Wed": 10, "Thu": 0, "Fri": 0, "None": 60})
        self.assertEqual(s, {"Mon": 0.25, "Tue": 0.5, "Wed": 0.25, "Thu": 0.0, "Fri": 0.0})

    def test_normalize_all_zero_raises(self):
        with self.assertRaises(ValueError):
            grade.normalize({"None": 5})

    def test_gap_pp_hand_computed(self):
        a = {"Mon": 0.3, "Tue": 0.2, "Wed": 0.2, "Thu": 0.2, "Fri": 0.1}
        # |.1| + 0 + 0 + 0 + |-.1| = .2; /5 = .04 -> 4.0 pp
        self.assertAlmostEqual(grade.gap_pp(a, UNIFORM), 4.0)
        self.assertAlmostEqual(grade.gap_pp(a, a), 0.0)

    def test_apply_rules_add_and_renormalize(self):
        synth = {"Mon": 0.30, "Tue": 0.20, "Wed": 0.20, "Thu": 0.20, "Fri": 0.10}
        rule = {"id": "r", "when": None, "adjust": {"Mon": -5, "Tue": 0, "Wed": 0, "Thu": 0, "Fri": 5}}
        out = grade.apply_rules(synth, {}, [rule])
        self.assertAlmostEqual(out["Mon"], 0.25)
        self.assertAlmostEqual(out["Fri"], 0.15)
        self.assertAlmostEqual(sum(out.values()), 1.0)

    def test_apply_rules_clips_at_zero_then_renormalizes(self):
        synth = {"Mon": 0.30, "Tue": 0.20, "Wed": 0.20, "Thu": 0.20, "Fri": 0.10}
        rule = {"id": "r", "when": None, "adjust": {"Mon": -40, "Tue": 0, "Wed": 0, "Thu": 0, "Fri": 10}}
        out = grade.apply_rules(synth, {}, [rule])
        # raw = 0, .2, .2, .2, .2 (total .8) -> 0, .25, .25, .25, .25
        self.assertEqual(out["Mon"], 0.0)
        for d in DAYS[1:]:
            self.assertAlmostEqual(out[d], 0.25)

    def test_apply_rules_condition_and_missing_feature(self):
        rule = {"id": "r", "when": {"feature": "borough", "op": "==", "value": "Queens"},
                "adjust": {"Mon": 5, "Tue": -5, "Wed": 0, "Thu": 0, "Fri": 0}}
        self.assertEqual(grade.apply_rules(UNIFORM, {"borough": "Bronx"}, [rule]), UNIFORM)
        self.assertEqual(grade.apply_rules(UNIFORM, {}, [rule]), UNIFORM)  # feature missing
        self.assertAlmostEqual(grade.apply_rules(UNIFORM, {"borough": "Queens"}, [rule])["Mon"], 0.25)

    def test_all_ops(self):
        cases = [("==", 5, True), ("!=", 5, False), (">", 4, True), ("<", 4, False),
                 (">=", 5, True), ("<=", 4, False)]
        for op, value, expected in cases:
            self.assertEqual(grade._matches({"feature": "x", "op": op, "value": value}, {"x": 5}), expected, op)

    def test_type_mismatch_is_no_match(self):
        self.assertFalse(grade._matches({"feature": "x", "op": ">", "value": 3}, {"x": "Brooklyn"}))

    def test_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            grade._matches({"feature": "x", "op": "~", "value": 1}, {"x": 1})
        with self.assertRaises(ValueError):
            grade.apply_rules(UNIFORM, {}, [{"when": {"feature": "x", "op": "contains", "value": 1},
                                             "adjust": {}}])

    def test_fit_adjust_no_match_is_zero(self):
        rule = {"when": {"feature": "borough", "op": "==", "value": "Mars"}}
        st = [station("a", "Queens", shares(0.05, -0.05))]
        self.assertEqual(grade.fit_adjust(rule, st), {d: 0.0 for d in DAYS})

    def test_fit_adjust_skips_missing_shares(self):
        rule = {"when": None}
        st = [station("a", "Queens", shares(0.04, -0.04)),
              {"id": "b", "features": {}, "synthetic": None, "measured": None}]
        adj = grade.fit_adjust(rule, st)
        self.assertAlmostEqual(adj["Mon"], 4.0)
        self.assertAlmostEqual(adj["Tue"], -4.0)


class TestDumbFix(unittest.TestCase):
    D = [0.02, 0.04, 0.06, 0.08]

    def train(self):
        return [station(str(i), "Queens", shares(d, -d)) for i, d in enumerate(self.D)]

    def test_dumb_fix_is_mean_error(self):
        rule = grade.dumb_fix(self.train())
        self.assertIsNone(rule["when"])
        self.assertAlmostEqual(rule["adjust"]["Mon"], 5.0)   # mean of 2,4,6,8 pp
        self.assertAlmostEqual(rule["adjust"]["Tue"], -5.0)
        self.assertAlmostEqual(rule["adjust"]["Wed"], 0.0)

    def test_dumb_fix_loo_gap_hand_computed(self):
        # A rule with when=None IS the dumb fix, so its LOO gap must equal loo_gap_dumb.
        # For station with error d (pp), others' mean m = (20 - d)/3; leftover gap = 2*|d - m|/5.
        expected = sum(2 * abs(d - (20 - d) / 3) / 5 for d in (2, 4, 6, 8)) / 4
        res = grade.evaluate_rule({"id": "x", "text": "", "when": None, "adjust": {}}, self.train())
        self.assertAlmostEqual(res["loo_gap_dumb"], expected)
        self.assertAlmostEqual(res["loo_gap"], expected)
        self.assertFalse(res["beats_dumb_fix"])  # equal, not strictly better
        self.assertFalse(res["keep"])


def scenario():
    """8 training stations. Brooklyn (4) all err the same way; the other 4 are perfect."""
    brooklyn = [station(f"b{i}", "Brooklyn", shares(0.04, -0.04, 0, 0, 0), x=i % 2) for i in range(4)]
    others = [station(f"o{i}", "Queens", dict(UNIFORM), x=i % 2) for i in range(4)]
    return brooklyn + others


class TestEvaluateRule(unittest.TestCase):
    def test_real_borough_rule_is_kept(self):
        rule = {"id": "r1", "text": "Brooklyn rides more on Monday",
                "when": {"feature": "borough", "op": "==", "value": "Brooklyn"}, "adjust": {}}
        res = grade.evaluate_rule(rule, scenario())
        self.assertEqual(res["stations_matching"], 4)
        self.assertEqual(res["stations_improved"], 4)
        self.assertAlmostEqual(res["loo_gap"], 0.0)       # others' mean error is exactly the error
        self.assertGreater(res["loo_gap_dumb"], res["loo_gap"])
        self.assertTrue(res["beats_dumb_fix"])
        self.assertTrue(res["keep"])
        self.assertIn("kept", res["reason"])

    def test_noise_rule_is_thrown_out(self):
        # x == 1 stations alternate their error sign, so no stable correction exists.
        errs = [0.03, -0.03, 0.03, -0.03]
        noisy = [station(f"n{i}", "Queens", shares(e, 0, 0, 0, -e), x=1) for i, e in enumerate(errs)]
        calm = [station(f"c{i}", "Bronx", dict(UNIFORM), x=0) for i in range(4)]
        rule = {"id": "r2", "text": "x==1 stations ride more on Monday",
                "when": {"feature": "x", "op": "==", "value": 1}, "adjust": {}}
        res = grade.evaluate_rule(rule, noisy + calm)
        self.assertEqual(res["stations_matching"], 4)
        self.assertEqual(res["stations_improved"], 0)
        self.assertFalse(res["keep"])
        self.assertIn("thrown out", res["reason"])

    def test_zero_matching_stations(self):
        rule = {"id": "r3", "text": "", "when": {"feature": "borough", "op": "==", "value": "Mars"}, "adjust": {}}
        res = grade.evaluate_rule(rule, scenario())
        self.assertEqual(res["stations_matching"], 0)
        self.assertFalse(res["keep"])

    def test_too_few_matching_is_not_kept(self):
        train = scenario()
        rule = {"id": "r4", "text": "", "when": {"feature": "x", "op": "==", "value": 99}, "adjust": {}}
        train[0]["features"]["x"] = 99
        train[1]["features"]["x"] = 99
        res = grade.evaluate_rule(rule, train)
        self.assertEqual(res["stations_matching"], 2)
        self.assertFalse(res["keep"])

    def test_missing_feature_never_matches(self):
        train = scenario()
        for s in train:
            s["features"].pop("borough")
        rule = {"id": "r5", "text": "", "when": {"feature": "borough", "op": "==", "value": "Brooklyn"},
                "adjust": {}}
        self.assertEqual(grade.evaluate_rule(rule, train)["stations_matching"], 0)

    def test_stations_without_measured_are_skipped(self):
        train = scenario() + [{"id": "z", "features": {"borough": "Brooklyn"}, "synthetic": None,
                               "measured": None}]
        rule = {"id": "r6", "text": "", "when": {"feature": "borough", "op": "==", "value": "Brooklyn"},
                "adjust": {}}
        self.assertEqual(grade.evaluate_rule(rule, train)["stations_matching"], 4)

    def test_unknown_op_raises(self):
        rule = {"id": "r7", "text": "", "when": {"feature": "x", "op": "??", "value": 1}, "adjust": {}}
        with self.assertRaises(ValueError):
            grade.evaluate_rule(rule, scenario())

    def test_empty_train(self):
        res = grade.evaluate_rule({"id": "r", "when": None, "adjust": {}}, [])
        self.assertFalse(res["keep"])


class TestExam(unittest.TestCase):
    def setUp(self):
        grade._reset_exam_for_tests_only()

    def tearDown(self):
        grade._reset_exam_for_tests_only()

    def exam_inputs(self):
        train = scenario()
        rule = {"id": "r1", "text": "", "when": {"feature": "borough", "op": "==", "value": "Brooklyn"},
                "adjust": {}}
        kept = grade.refit_rules([rule], train)
        dumb = grade.dumb_fix(train)
        stations = [station("e1", "Brooklyn", shares(0.04, -0.04), split="exam"),
                    station("e2", "Queens", dict(UNIFORM), split="exam")]
        return stations, kept, dumb

    def test_exam_numbers(self):
        stations, kept, dumb = self.exam_inputs()
        res = grade.exam(stations, kept, dumb)
        e1, e2 = res["per_station"]
        self.assertAlmostEqual(e1["gap_before_pp"], 1.6)       # 2*4pp/5
        self.assertAlmostEqual(e1["gap_after_pp"], 0.0)        # Brooklyn rule fits exactly
        self.assertAlmostEqual(e2["gap_before_pp"], 0.0)
        self.assertAlmostEqual(e2["gap_after_pp"], 0.0)        # Queens untouched by the rule
        self.assertGreater(e2["gap_dumbfix_pp"], 0.0)          # dumb fix wrongly shifts Queens
        self.assertAlmostEqual(res["gap_before"], 0.8)
        self.assertAlmostEqual(res["gap_after"], 0.0)
        self.assertTrue(res["helped"])

    def test_exam_twice_raises(self):
        stations, kept, dumb = self.exam_inputs()
        grade.exam(stations, kept, dumb)
        with self.assertRaises(RuntimeError):
            grade.exam(stations, kept, dumb)

    def test_exam_with_no_rules_does_not_help(self):
        stations, _, dumb = self.exam_inputs()
        res = grade.exam(stations, [], dumb)
        self.assertAlmostEqual(res["gap_after"], res["gap_before"])
        self.assertFalse(res["helped"])

    def test_exam_missing_measured(self):
        stations, kept, dumb = self.exam_inputs()
        stations.append({"id": "e3", "features": {}, "synthetic": None, "measured": None})
        res = grade.exam(stations, kept, dumb)
        self.assertIsNone(res["per_station"][2]["gap_before_pp"])
        self.assertAlmostEqual(res["gap_before"], 0.8)  # e3 excluded from the mean

    def test_summarize_exam(self):
        stations, kept, dumb = self.exam_inputs()
        summary, fields = grade.summarize_exam(grade.exam(stations, kept, dumb))
        self.assertEqual(set(summary), {"exam_gap_before_pp", "exam_gap_after_pp",
                                        "exam_gap_dumbfix_pp", "coaching_helped"})
        self.assertTrue(summary["coaching_helped"])
        self.assertEqual(set(fields), {"e1", "e2"})
        self.assertAlmostEqual(fields["e1"]["gap_before_pp"], 1.6)




class TestCoachDirections(unittest.TestCase):
    """fit_adjust must respect the days and directions the coach named."""

    def test_only_named_days_move_and_wrong_sign_is_zeroed(self):
        from agent.grade import fit_adjust
        st = {"synthetic": {"Mon": .2, "Tue": .2, "Wed": .2, "Thu": .2, "Fri": .2},
              "measured": {"Mon": .18, "Tue": .23, "Wed": .23, "Thu": .22, "Fri": .14},
              "features": {"borough": "Brooklyn"}}
        rule = {"id": "r", "text": "", "when": None,
                "adjust": {"Mon": 0.0, "Tue": -1.0, "Wed": 0.0, "Thu": 0.0, "Fri": -1.0}}
        adj = fit_adjust(rule, [st])
        self.assertAlmostEqual(adj["Fri"], -6.0)   # named, data agrees
        self.assertEqual(adj["Tue"], 0.0)          # named "down" but data says up
        self.assertEqual(adj["Mon"], 0.0)          # not named


if __name__ == "__main__":
    unittest.main()


class TestNoiseAndBands(unittest.TestCase):
    def test_noise_is_positive_and_shrinks_with_bigger_panels(self):
        small = grade.noise_pp({"Mon": 6, "Tue": 6, "Wed": 6, "Thu": 6, "Fri": 6}, seed=1)
        big = grade.noise_pp({"Mon": 600, "Tue": 600, "Wed": 600, "Thu": 600, "Fri": 600}, seed=1)
        self.assertGreater(small, big)
        self.assertGreater(big, 0)

    def test_noise_none_for_empty_panel(self):
        self.assertIsNone(grade.noise_pp({"Mon": 0, "None": 5}))

    def test_band_hits_counts_inside_only(self):
        rows = [{"gap_after_pp": 1.0, "predicted_error_band_pp": [0.5, 1.5]},
                {"gap_after_pp": 2.0, "predicted_error_band_pp": [0.5, 1.5]},
                {"gap_after_pp": None, "predicted_error_band_pp": [0, 1]}]
        self.assertEqual(grade.band_hits(rows), (1, 2))
