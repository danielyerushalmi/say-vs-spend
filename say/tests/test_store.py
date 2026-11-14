import json
import os
import tempfile
import unittest

from say import store as S
from say import trust_text

STORE = json.load(open(S.DEFAULT_STORE_PATH, encoding="utf-8"))
BRANDS = [
    {"id": "a", "name": "A", "say_mean": 8.0, "intent_mean": 7.0, "aware_share": 0.9},
    {"id": "b", "name": "B", "say_mean": 6.0, "intent_mean": 5.0, "aware_share": 0.5},
    {"id": "c", "name": "C", "say_mean": 4.0, "intent_mean": 5.0, "aware_share": 0.1},
]


class StoreTests(unittest.TestCase):
    def test_stats_math(self):
        rows = [
            {"persona_id": "1", "brand_id": "demo-store", "say": 6, "intent": 4, "aware": True},
            {"persona_id": "2", "brand_id": "demo-store", "say": 8, "intent": 5, "aware": False},
            {"persona_id": "3", "brand_id": "demo-store", "say": 7, "intent": None, "aware": False},
            {"persona_id": "4", "brand_id": "other", "say": 1, "intent": 1, "aware": True},
        ]
        s = S.store_stats(rows, "demo-store")
        self.assertAlmostEqual(s["say_mean"], 7.0)
        self.assertAlmostEqual(s["intent_mean"], 4.5)
        self.assertAlmostEqual(s["aware_share"], 1 / 3)
        self.assertEqual(s["n"], 3)
        self.assertEqual(S.store_stats([], "demo-store")["n"], 0)

    def test_placement_order_and_ties(self):
        p = S.placement({"say_mean": 7.0, "intent_mean": 5.0, "aware_share": 0.95}, BRANDS)
        self.assertEqual(p["say"]["rank"], 2)
        self.assertEqual(p["fame"]["rank"], 1)
        self.assertEqual(p["intent"]["rank"], 3.0)  # tied with B and C: places 2,3,4 -> 3
        self.assertEqual(sorted(p["intent"]["tied_with"]), ["B", "C"])
        self.assertEqual(p["intent"]["of"], 4)
        self.assertEqual(p["label"], "SYNTHETIC")
        self.assertIn("No answer key for this store", p["caveat"])

    def test_placement_missing_value(self):
        p = S.placement({"say_mean": None, "intent_mean": 5, "aware_share": 0.2}, BRANDS)
        self.assertIsNone(p["say"])

    def test_block_label_note_exact(self):
        b = S.build_store_block(STORE, {"say_mean": 7, "intent_mean": 5, "aware_share": 0.2, "n": 100},
                                "verify", BRANDS)
        self.assertEqual(b["label"], "FICTIONAL DEMO STORE")
        self.assertEqual(b["note"], "No answer key for this store; trust level comes from the brand test.")
        self.assertEqual(b["verdict"], "verify")
        self.assertIn("placement", b)
        with self.assertRaises(ValueError):
            S.build_store_block(STORE, {}, "maybe", BRANDS)

    def test_refuse_missing_or_wrong_label(self):
        for bad in ({k: v for k, v in STORE.items() if k != "label"}, {**STORE, "label": "Real store"}):
            with self.assertRaises(ValueError):
                S.check_store(bad)
            with self.assertRaises(ValueError):
                S.flashpoint_brief(bad)
            with self.assertRaises(ValueError):
                S.build_store_block(bad, {}, "trust")

    def test_brief(self):
        t = S.flashpoint_brief(STORE)
        for need in ("do not publish", "do not recruit", "no paid steps", "demo-store", "SAY", "INTENT",
                     "AWARE", "1-10", "Yes / No"):
            self.assertIn(need.lower(), t.lower())
        # The fictional label is for OUR screen; respondents must not be told (it would bias answers).
        self.assertNotIn("fictional", t.lower())
        self.assertNotIn("not a real", t.lower())

    def test_fixture_has_note(self):
        self.assertIn("not verified", STORE["name_check_note"])


if __name__ == "__main__":
    unittest.main()
