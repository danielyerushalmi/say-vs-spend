import json
import os
import unittest

from agent.llm import LLM, NoKey
from say import predict as P

ROWS = [{"id": f"b{i}", "name": f"Brand {i}", "description": f"Sells thing {i}.",
         "say_mean": 6.0 + i * 0.1, "intent_mean": 3.0 + i * 0.2} for i in range(5)]
DATA = {"brands": ROWS}


class Fake:
    def __init__(self, obj):
        self.obj, self.payloads = obj, []

    def __call__(self, payload, timeout):
        self.payloads.append(payload)
        return 200, {"content": [{"type": "text", "text": json.dumps(self.obj)}],
                     "usage": {"input_tokens": 1, "output_tokens": 1}}


def no_key(payload, timeout):
    raise NoKey("no key")


class PredictTests(unittest.TestCase):
    def test_baseline_leave_one_out_is_exact(self):
        b = P.baseline_loo(ROWS)
        # say values 6.0..6.4: hiding the end brand misses by 0.25, middle by 0
        self.assertAlmostEqual(b["say_mean"], round((0.25 + 0.125 + 0 + 0.125 + 0.25) / 5, 3))

    def test_no_validation_uses_average_and_says_so(self):
        out = P.predict("Candles", DATA, None, LLM(transport=no_key))
        self.assertEqual(out["predicted_website_score"], 6.2)
        self.assertIn("code: average", out["method"]["website"])
        self.assertIn("not tested", out["why"][0])
        self.assertIn("ESTIMATE", out["label"])
        self.assertIn("0.03", out["reality_note"])

    def test_model_used_only_where_it_beat_the_average(self):
        val = {"ok": True, "model_error": {"say_mean": 0.1, "intent_mean": 0.9},
               "model_beats_baseline": {"say_mean": True, "intent_mean": False}}
        t = Fake({"say": 6.35, "intent": 9.0})
        out = P.predict("Candles", DATA, val, LLM(transport=t))
        self.assertEqual(out["predicted_website_score"], 6.35)
        self.assertIn("model", out["method"]["website"])
        self.assertEqual(out["predicted_buy_score"], 3.4)          # average, not the model's 9.0
        self.assertIn("did not beat", out["why"][1])

    def test_no_key_never_claims_model_used(self):
        val = {"ok": True, "model_error": {"say_mean": 0.1, "intent_mean": 0.4},
               "model_beats_baseline": {"say_mean": False, "intent_mean": True}}
        out = P.predict("Candles", DATA, val, LLM(transport=no_key))
        self.assertIn("code: average", out["method"]["buy"])
        self.assertNotIn("(model used)", out["why"][1])
        self.assertIn("No usable model prediction".lower(), out["why"][1].lower())

    def test_model_numbers_are_checked_and_clamped(self):
        rng = P.scale_range(ROWS)
        p = P.model_predict("x", ROWS, LLM(transport=Fake({"say": 9.9, "intent": 1.0})))
        self.assertEqual(p["say_mean"], round(rng["say_mean"][1] + 0.5, 2))
        self.assertEqual(p["intent_mean"], round(rng["intent_mean"][0] - 0.5, 2))
        self.assertIsNone(P.model_predict("x", ROWS, LLM(transport=Fake({"say": 42, "intent": 3}))))
        self.assertIsNone(P.model_predict("x", ROWS, LLM(transport=Fake({"say": "high", "intent": 3}))))

    def test_prompt_has_no_revenue(self):
        t = Fake({"say": 6, "intent": 3})
        P.model_predict("Candles", ROWS, LLM(transport=t))
        text = (t.payloads[0]["system"] + json.dumps(t.payloads[0]["messages"])).lower()
        self.assertNotIn("revenue", text)

    def test_validate_hides_each_brand(self):
        t = Fake({"say": 6.2, "intent": 3.4})
        v = P.validate(ROWS, LLM(transport=t))
        self.assertTrue(v["ok"])
        self.assertEqual(len(t.payloads), len(ROWS))
        for payload, r in zip(t.payloads, ROWS):
            examples = json.dumps(payload["messages"]).split("New store:")[0]
            self.assertNotIn(r["name"] + ":", examples)              # the hidden brand is not an example
        self.assertEqual(set(v["model_beats_baseline"]), set(P.FIELDS))

    def test_validate_reports_failure_without_key(self):
        v = P.validate(ROWS, LLM(transport=no_key))
        self.assertFalse(v["ok"])

    def test_empty_store_rejected(self):
        with self.assertRaises(ValueError):
            P.predict("  ", DATA, None, LLM(transport=no_key))

    @unittest.skipUnless(os.path.exists(P.DATA), "12-brand data not built")
    def test_saved_data_matches_a_fresh_build(self):
        if not os.path.exists(P.EXPORT):
            self.skipTest("raw export not present")
        self.assertEqual(P.load(P.DATA)["brands"], P.build_data()["brands"])


if __name__ == "__main__":
    unittest.main()
