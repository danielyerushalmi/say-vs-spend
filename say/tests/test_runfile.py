"""Tests for say.runfile using the FAKE TEST DATA fixture. No network."""
import copy
import json
import os
import tempfile
import unittest

from say import runfile

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "FAKE_TEST_DATA_panel.json")


def load():
    panel = runfile.load_panel(FIXTURE)
    return panel, panel["fake_brands"]


class RunFileTests(unittest.TestCase):
    def setUp(self):
        self.panel, self.brands = load()
        self.run = runfile.build_run(self.brands, self.panel, [], None, "sample")

    def test_fixture_is_clearly_fake(self):
        self.assertEqual(self.panel["panel_id"], "FAKE TEST DATA")
        self.assertTrue(all(r["persona_id"].startswith("FAKE-") for r in self.panel["responses"]))
        self.assertEqual(runfile.panel_problems(self.panel), [])

    def test_validate_passes_on_fixture_run(self):
        self.assertEqual(runfile.validate_run(self.run), [])
        self.assertEqual(self.run["mode"], "sample")
        self.assertEqual(self.run["agreement"]["n_brands"], 8)
        self.assertEqual(self.run["panel"]["panel_id"], "FAKE TEST DATA")

    def test_contract_field_names(self):
        b = self.run["brands"][0]
        for k in ("intent_mean", "rank_intent", "rank_fame_source", "fame_guess"):
            self.assertIn(k, b)
        self.assertNotIn("do_mean", b)
        self.assertEqual(self.run["trust_card"]["metric"][:17], "intent spearman =")
        self.assertIn("rule", self.run["trust_card"])

    def test_fake_panel_cannot_claim_recorded(self):
        run = copy.deepcopy(self.run)
        run["mode"] = "recorded"
        self.assertTrue(any("sample" in e for e in runfile.validate_run(run)))

    def test_validate_catches_breakage(self):
        run = copy.deepcopy(self.run)
        del run["questions"]
        self.assertTrue(runfile.validate_run(run))
        run = copy.deepcopy(self.run)
        run["questions"]["say"]["text"] = "changed"
        self.assertTrue(runfile.validate_run(run))
        run = copy.deepcopy(self.run)
        run["agreement"]["n_brands"] = 3
        self.assertTrue(runfile.validate_run(run))

    def test_failed_and_incomplete_brands_left_out(self):
        brands = copy.deepcopy(self.brands)
        brands[0]["pass"] = False
        brands[1]["revenue_usd"] = None
        run = runfile.build_run(brands, self.panel, [], None, "sample")
        ids = [b["id"] for b in run["brands"]]
        self.assertNotIn(brands[0]["id"], ids)
        self.assertNotIn(brands[1]["id"], ids)
        self.assertEqual(run["agreement"]["n_brands"], 6)
        self.assertEqual(runfile.validate_run(run), [])

    def test_missing_values_are_skipped_not_fatal(self):
        panel = copy.deepcopy(self.panel)
        for r in panel["responses"][:50]:
            r["intent"] = None
        run = runfile.build_run(self.brands, panel, [], None, "sample")
        self.assertEqual(runfile.validate_run(run), [])

    def test_personas_answers_only(self):
        ps = self.run["personas"]
        self.assertTrue(ps)
        brand_ids = {b["id"] for b in self.run["brands"]}
        for p in ps:
            self.assertEqual(set(p), {"n", "label", "answers"})
            self.assertEqual(p["label"], "FAKE TEST DATA")
            self.assertTrue(set(p["answers"]) <= brand_ids)
            for a in p["answers"].values():
                self.assertEqual(set(a), {"say", "intent", "aware", "buy"})

    def test_same_input_same_output(self):
        again = runfile.build_run(self.brands, self.panel, [], None, "sample")
        self.assertEqual(again["agreement"], self.run["agreement"])
        self.assertEqual(again["brands"], self.run["brands"])

    def test_write_run_atomic_and_readable(self):
        with tempfile.TemporaryDirectory() as d:
            path = runfile.write_run(self.run, d)
            self.assertTrue(os.path.basename(path).startswith("say_say-"))
            self.assertEqual(sorted(os.listdir(d)), sorted([os.path.basename(path), "say_latest.json"]))
            with open(os.path.join(d, "say_latest.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["run_id"], self.run["run_id"])

    def test_write_run_refuses_invalid(self):
        run = copy.deepcopy(self.run)
        run["mode"] = "bogus"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                runfile.write_run(run, d)
            self.assertEqual(os.listdir(d), [])

    def test_build_rejects_bad_mode(self):
        with self.assertRaises(ValueError):
            runfile.build_run(self.brands, self.panel, [], None, "demo")


BUY_CSV = os.path.join(os.path.dirname(__file__), "..", "fixtures", "FAKE_TEST_DATA_export_buy.csv")


class BuyRunFileTests(unittest.TestCase):
    def setUp(self):
        from say import flashpoint_import as fi
        names = [("figs", 400), ("allbirds", 300), ("1800flowers", 200), ("casper", 100)]
        self.brands = [{"id": i, "name": i, "aliases": [], "pass": True, "revenue_usd": r * 10**6,
                        "fiscal_year": "FAKE", "filing_url": "x", "online_note": "FAKE", "description": "FAKE"}
                       for i, r in names]
        self.panel = fi.import_export(BUY_CSV, self.brands)
        self.run = runfile.build_run(self.brands, self.panel, [], None, "sample")

    def test_buy_fields_present_and_valid(self):
        run = self.run
        self.assertEqual(runfile.validate_run(run), [])
        self.assertEqual(run["questions"]["buy"], {"text": "Is this a kind of product you buy?", "scale": "yes/no"})
        self.assertTrue(any(l.startswith("Buyers-only agreement") for l in run["limits"]))
        by = {b["id"]: b for b in run["brands"]}
        self.assertEqual(by["figs"]["buy_share"], 0.8)
        self.assertIs(by["figs"]["niche"], False)
        self.assertEqual(by["casper"]["buy_share"], 0.3)
        self.assertIs(by["casper"]["niche"], False)  # exactly 0.30 is not niche
        self.assertEqual(by["figs"]["labels"]["buy"], "FAKE TEST DATA")
        ab = run["agreement_buyers"]
        self.assertEqual(ab["min_yes_respondents"], 10)
        self.assertEqual(ab["n_brands"], 3)  # casper has only 6 buyers
        self.assertEqual(set(ab["intent"]), set(runfile.AGREEMENT_KEYS))

    def test_trust_card_ignores_buy_data(self):
        from say import compare
        no_buy = copy.deepcopy(self.panel)
        for r in no_buy["responses"]:
            r["buy"] = None
        plain = runfile.build_run(self.brands, no_buy, [], None, "sample")
        self.assertEqual(self.run["trust_card"], plain["trust_card"])
        self.assertEqual(self.run["agreement"], plain["agreement"])
        v = compare.trust_verdict(self.run["agreement"]["intent"]["spearman"], self.run["agreement"]["intent"]["wobble_low"],
                                  self.run["agreement"]["intent"]["wobble_high"])
        self.assertEqual(self.run["trust_card"]["verdict"], v["verdict"])

    def test_buy_fields_absent_without_buy_data(self):
        panel, brands = load()
        run = runfile.build_run(brands, panel, [], None, "sample")
        self.assertIsNone(run["agreement_buyers"])
        self.assertNotIn("buy", run["questions"])
        self.assertFalse(any(l.startswith("Buyers-only") for l in run["limits"]))
        for b in run["brands"]:
            self.assertNotIn("buy_share", b)
            self.assertNotIn("niche", b)
            self.assertNotIn("buy", b["labels"])
        self.assertEqual(runfile.validate_run(run), [])
        # a file with no agreement_buyers key at all (older file) is still valid
        del run["agreement_buyers"]
        self.assertEqual(runfile.validate_run(run), [])

    def test_validate_catches_bad_niche(self):
        run = copy.deepcopy(self.run)
        run["brands"][0]["niche"] = True
        self.assertTrue(runfile.validate_run(run))


if __name__ == "__main__":
    unittest.main()
