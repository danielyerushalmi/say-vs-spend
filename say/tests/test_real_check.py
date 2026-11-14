"""Tests for say.real_check on the FAKE fixture (invented answers, not real people). No network."""
import json
import math
import os
import tempfile
import unittest

from say import real_check as rc

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "..", "fixtures", "FAKE_TEST_DATA_real_check.csv")

# A small run file shaped like frontend/runs/say_latest.json (only the fields real_check reads).
# intent_mean / revenue_usd chosen so rank_intent and rank_revenue match the real 12:17 run.
RUN = {
    "run_id": "FAKE-run",
    "trust_card": {
        "draft_question": "In the past 12 months, have you bought anything from ThredUp's website?",
        "draft_question_brand": "thredup",
    },
    "brands": [
        {"id": "hims", "name": "Hims & Hers", "intent_mean": 3.635, "revenue_usd": 600, "rank_intent": 3, "rank_revenue": 1},
        {"id": "stitchfix", "name": "Stitch Fix", "intent_mean": 3.72, "revenue_usd": 500, "rank_intent": 2, "rank_revenue": 2},
        {"id": "revolve", "name": "Revolve", "intent_mean": 2.845, "revenue_usd": 400, "rank_intent": 6, "rank_revenue": 3},
        {"id": "bark", "name": "BARK", "intent_mean": 2.975, "revenue_usd": 300, "rank_intent": 5, "rank_revenue": 4},
        {"id": "thredup", "name": "ThredUp", "intent_mean": 4.255, "revenue_usd": 200, "rank_intent": 1, "rank_revenue": 5},
        {"id": "petmeds", "name": "PetMed Express", "intent_mean": 3.4, "revenue_usd": 100, "rank_intent": 4, "rank_revenue": 6},
    ],
}
IDS = {b["id"] for b in RUN["brands"]}


def fixture_text():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


class WilsonTests(unittest.TestCase):
    def test_z_is_exact_90(self):
        self.assertAlmostEqual(rc.Z90, 1.6448536269514722, places=12)

    def test_zero_yes_closed_form(self):
        # 0/n: low = 0, high = z^2 / (n + z^2)
        low, high = rc.wilson_interval(0, 11)
        z2 = rc.Z90 ** 2
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, z2 / (11 + z2), places=12)
        self.assertAlmostEqual(high, 0.197405, places=6)

    def test_all_yes_closed_form(self):
        # n/n: low = n / (n + z^2), high = 1
        low, high = rc.wilson_interval(12, 12)
        self.assertAlmostEqual(low, 12 / (12 + rc.Z90 ** 2), places=12)
        self.assertAlmostEqual(low, 0.816019, places=6)
        self.assertEqual(high, 1.0)

    def test_reference_values(self):
        # Wilson 90% for 3/12 and 1/12 (also checked against scipy.stats.norm.ppf(0.95) by hand)
        low, high = rc.wilson_interval(3, 12)
        self.assertAlmostEqual(low, 0.104653, places=6)
        self.assertAlmostEqual(high, 0.487338, places=6)
        low, high = rc.wilson_interval(1, 12)
        self.assertAlmostEqual(low, 0.018816, places=6)
        self.assertAlmostEqual(high, 0.301168, places=6)

    def test_contains_share_and_symmetry(self):
        low, high = rc.wilson_interval(5, 15)
        self.assertLess(low, 5 / 15)
        self.assertGreater(high, 5 / 15)
        l2, h2 = rc.wilson_interval(10, 15)
        self.assertAlmostEqual(low, 1 - h2, places=12)
        self.assertAlmostEqual(high, 1 - l2, places=12)

    def test_empty_and_bad(self):
        self.assertIsNone(rc.wilson_interval(0, 0))
        with self.assertRaises(ValueError):
            rc.wilson_interval(5, 3)


class PIITests(unittest.TestCase):
    def assertPII(self, text):
        with self.assertRaises(rc.PIIError):
            rc.parse_csv_text(text, IDS)

    def test_name_column_refused(self):
        self.assertPII("respondent_n,brand_id,bought_12m,name\n1,thredup,yes,Alex\n")

    def test_first_name_column_refused(self):
        self.assertPII("respondent_n,brand_id,bought_12m,First Name\n1,thredup,yes,Alex\n")

    def test_email_column_refused(self):
        self.assertPII("respondent_n,brand_id,bought_12m,Email\n1,thredup,yes,\n")

    def test_phone_column_refused(self):
        self.assertPII("respondent_n,brand_id,bought_12m,phone_number\n1,thredup,yes,\n")

    def test_handle_column_refused(self):
        self.assertPII("respondent_n,brand_id,bought_12m,instagram_handle\n1,thredup,yes,\n")

    def test_email_value_refused_even_in_allowed_column(self):
        self.assertPII("respondent_n,brand_id,bought_12m,age_band\n1,thredup,yes,someone@example.com\n")

    def test_phone_value_refused(self):
        self.assertPII("respondent_n,brand_id,bought_12m,age_band\n1,thredup,yes,(555) 123-4567\n")

    def test_pii_is_a_realcheck_error(self):
        self.assertTrue(issubclass(rc.PIIError, rc.RealCheckError))


class ValidationTests(unittest.TestCase):
    def bad(self, text):
        with self.assertRaises(rc.RealCheckError):
            rc.parse_csv_text(text, IDS)

    def test_unknown_column(self):
        self.bad("respondent_n,brand_id,bought_12m,notes\n1,thredup,yes,hi\n")

    def test_missing_column(self):
        self.bad("respondent_n,brand_id\n1,thredup\n")

    def test_bad_answer(self):
        self.bad("respondent_n,brand_id,bought_12m\n1,thredup,maybe\n")

    def test_unknown_brand(self):
        self.bad("respondent_n,brand_id,bought_12m\n1,amazon,yes\n")

    def test_bad_age_band(self):
        self.bad("respondent_n,brand_id,bought_12m,age_band\n1,thredup,yes,17\n")

    def test_respondent_not_a_counter(self):
        self.bad("respondent_n,brand_id,bought_12m\nAlex,thredup,yes\n")

    def test_duplicate_answer(self):
        self.bad("respondent_n,brand_id,bought_12m\n1,thredup,yes\n1,thredup,no\n")

    def test_empty(self):
        self.bad("# only a comment\n")
        self.bad("respondent_n,brand_id,bought_12m\n")

    def test_case_and_spaces_ok(self):
        rows = rc.parse_csv_text("respondent_n, brand_id ,bought_12m\n1, ThredUp , YES \n", IDS)
        self.assertEqual(rows, [{"respondent_n": 1, "brand_id": "thredup", "bought": True, "age_band": None}])


class FixtureScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = fixture_text()
        assert "FAKE TEST DATA" in text
        cls.rows = rc.parse_csv_text(text, IDS)
        cls.out = rc.score(cls.rows, RUN)
        cls.by_id = {b["id"]: b for b in cls.out["brands"]}

    def test_labels_and_counts(self):
        self.assertEqual(self.out["label"], "REAL (convenience sample)")
        self.assertEqual(self.out["n_people"], 12)
        self.assertEqual(self.out["display_label"], "REAL (n=12, convenience sample)")
        self.assertIn("NOT representative", self.out["caveat"])
        self.assertEqual(len(self.rows), 12 * 2 + 11 * 4)

    def test_per_brand_share_and_interval(self):
        t = self.by_id["thredup"]
        self.assertEqual((t["n_asked"], t["n_yes"], t["real_share"]), (12, 3, 0.25))
        self.assertAlmostEqual(t["ci90_low"], 0.1047, places=4)
        self.assertAlmostEqual(t["ci90_high"], 0.4873, places=4)
        self.assertEqual(t["label"], "REAL (n=12, convenience sample)")
        b = self.by_id["bark"]
        self.assertEqual((b["n_asked"], b["n_yes"], b["real_share"], b["ci90_low"]), (11, 0, 0.0, 0.0))
        self.assertAlmostEqual(b["ci90_high"], 0.1974, places=4)

    def test_draft_question_wording_comes_from_run(self):
        self.assertEqual(self.by_id["thredup"]["question"], RUN["trust_card"]["draft_question"])
        self.assertEqual(self.by_id["bark"]["question"],
                         "Have you bought anything from BARK's website in the past 12 months?")
        self.assertIn(RUN["trust_card"]["draft_question"], rc.script_text(RUN))

    def test_real_ranks(self):
        # shares: revolve 3/11, thredup 3/12, stitchfix 2/11, petmeds 1/11, hims 1/12, bark 0/11
        got = {k: v["rank_real"] for k, v in self.by_id.items()}
        self.assertEqual(got, {"revolve": 1, "thredup": 2, "stitchfix": 3, "petmeds": 4, "hims": 5, "bark": 6})

    def test_spearman_hand_checked(self):
        # real [hims5, sf3, rev1, bark6, thred2, pet4] vs intent [3,2,6,5,1,4]: sum d^2 = 32
        #   -> 1 - 6*32/(6*35) = 0.085714
        # vs revenue [1,2,3,4,5,6]: sum d^2 = 38 -> 1 - 6*38/210 = -0.085714
        self.assertAlmostEqual(self.out["agreement_with_crowd"]["spearman"], 0.0857, places=4)
        self.assertAlmostEqual(self.out["agreement_with_revenue"]["spearman"], -0.0857, places=4)
        self.assertEqual(self.out["agreement_with_crowd"]["n_brands"], 6)
        self.assertTrue(self.out["agreement_with_crowd"]["could_be_chance"])

    def test_age_bands(self):
        self.assertEqual(self.out["age_bands"], {"under 25": 5, "25-44": 3, "45+": 1, "not given": 3})

    def test_too_few_brands_no_ranking(self):
        rows = rc.parse_csv_text("respondent_n,brand_id,bought_12m\n1,thredup,yes\n2,thredup,no\n1,hims,no\n", IDS)
        out = rc.score(rows, RUN)
        self.assertIsNone(out["agreement_with_crowd"]["spearman"])
        self.assertEqual(out["agreement_with_crowd"]["n_brands"], 2)
        self.assertIsNone(self_by(out, "bark")["real_share"])

    def test_all_no_gives_no_ranking(self):
        text = "respondent_n,brand_id,bought_12m\n" + "".join(f"1,{b},no\n" for b in sorted(IDS))
        out = rc.score(rc.parse_csv_text(text, IDS), RUN)
        self.assertIsNone(out["agreement_with_revenue"]["spearman"])


def self_by(out, bid):
    return next(b for b in out["brands"] if b["id"] == bid)


class CLITests(unittest.TestCase):
    def test_cli_writes_json_and_refuses_pii(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = os.path.join(d, "run.json")
            with open(run_path, "w") as f:
                json.dump(RUN, f)
            out_path = os.path.join(d, "real.json")
            self.assertEqual(rc.main(["--csv", FIXTURE, "--run", run_path, "--out", out_path]), 0)
            with open(out_path) as f:
                got = json.load(f)
            self.assertEqual(got["n_people"], 12)
            bad = os.path.join(d, "bad.csv")
            with open(bad, "w") as f:
                f.write("respondent_n,brand_id,bought_12m,email\n1,thredup,yes,\n")
            self.assertEqual(rc.main(["--csv", bad, "--run", run_path, "--out", out_path]), 2)


if __name__ == "__main__":
    unittest.main()
