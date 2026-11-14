import json
import os
import unittest

from agent.llm import LLM, NoKey
from say import trust_check as tc

HERE = os.path.dirname(os.path.abspath(__file__))
REAL_RUN = os.path.join(HERE, "..", "..", "frontend", "runs", "say_latest.json")


def fake_run(intent=(0.0286, -0.94, 0.64, True), say=(0.77, 0.09, 1.0, True), fame=(0.72, 0.0, 1.0, True)):
    def line(t):
        return {"spearman": t[0], "wobble_low": t[1], "wobble_high": t[2], "p_exact": 0.5, "could_be_chance": t[3]}
    return {"agreement": {"intent": line(intent), "say": line(say), "fame": line(fame)},
            "brands": [{"id": str(i)} for i in range(6)], "trust_card": {"verdict": "ask_real_people"}}


class Fake:
    def __init__(self, obj):
        self.obj, self.payloads = obj, []

    def __call__(self, payload, timeout):
        self.payloads.append(payload)
        return 200, {"content": [{"type": "text", "text": json.dumps(self.obj)}],
                     "usage": {"input_tokens": 1, "output_tokens": 1}}


def no_key(payload, timeout):
    raise NoKey("no key")


class TrustCheckTests(unittest.TestCase):
    def test_model_picks_kind_and_question_code_picks_level_and_numbers(self):
        t = Fake({"kind": "buy", "question": "Have you bought a candle online in the past year?",
                  "verdict": "trust", "spearman": 0.99})
        out = tc.check("Hand-made soy candles", "Will people buy my new candle?", fake_run(), llm=LLM(transport=t))
        self.assertEqual(out["kind"], "buy")
        self.assertEqual(out["kind_source"], "model (claude-sonnet-5-5)")
        self.assertEqual(out["level"], "ask_real_people")          # the model's "trust" is ignored
        self.assertEqual(out["evidence"]["spearman"], 0.0286)       # number comes from the run file
        self.assertEqual(out["evidence"]["line"], "intent")
        self.assertTrue(out["evidence"]["pre_registered"])
        self.assertEqual(out["real_question"], "Have you bought a candle online in the past year?")
        self.assertIn("AI-generated", out["question_source"])
        self.assertEqual(len(t.payloads), 1)                         # one model call only

    def test_prompt_never_shows_revenue_or_numbers(self):
        t = Fake({"kind": "like", "question": "q?"})
        tc.check("Shoes", "Do people like my site?", fake_run(), llm=LLM(transport=t))
        text = (t.payloads[0]["system"] + json.dumps(t.payloads[0]["messages"])).lower()
        self.assertNotIn("revenue", text.replace("never mention revenue", ""))
        self.assertNotIn("0.0286", text)
        self.assertNotIn("0.77", text)

    def test_each_kind_uses_its_own_line_and_the_same_cutoffs(self):
        good = fake_run(say=(0.95, 0.8, 1.0, False))
        out = tc.check("Shoes", "Will they like my website?", good, llm=LLM(transport=Fake({"kind": "like", "question": "q?"})))
        self.assertEqual(out["evidence"]["line"], "say")
        self.assertEqual(out["level"], "trust")                    # low end 0.8 >= 0.7, not chance
        self.assertFalse(out["evidence"]["pre_registered"])
        self.assertIn("EXPLORATORY", out["evidence"]["label"])
        mid = fake_run(fame=(0.8, 0.5, 1.0, False))
        out = tc.check("Shoes", "Have people heard of us?", mid, llm=LLM(transport=Fake({"kind": "aware", "question": "q?"})))
        self.assertEqual((out["evidence"]["line"], out["level"]), ("fame", "verify"))

    def test_could_be_chance_never_earns_trust(self):
        run = fake_run(say=(0.95, 0.8, 1.0, True))
        out = tc.check("Shoes", "Do they like the site?", run, llm=LLM(transport=Fake({"kind": "like", "question": "q?"})))
        self.assertEqual(out["level"], "ask_real_people")

    def test_untested_kind_says_ask_real_people_with_no_number(self):
        out = tc.check("Shoes", "What price should I charge?", fake_run(),
                       llm=LLM(transport=Fake({"kind": "other", "question": "What would you pay?"})))
        self.assertEqual(out["kind"], "other")
        self.assertEqual(out["level"], "ask_real_people")
        self.assertIsNone(out["evidence"])
        self.assertIn("did not test", out["why"])

    def test_bad_model_kind_falls_back_to_code_keywords(self):
        out = tc.check("Shoes", "Would people buy these?", fake_run(),
                       llm=LLM(transport=Fake({"kind": "TRUST ME", "question": "Q?"})))
        self.assertEqual(out["kind"], "buy")
        self.assertEqual(out["kind_source"], "code keywords")

    def test_no_key_still_answers_with_code_only(self):
        out = tc.check("Hand-made candles", "Will people buy my candles?", fake_run(), llm=LLM(transport=no_key))
        self.assertEqual(out["kind"], "buy")
        self.assertEqual(out["kind_source"], "code keywords")
        self.assertEqual(out["level"], "ask_real_people")
        self.assertIn("code template", out["question_source"])
        self.assertTrue(out["real_question"].endswith("?"))
        self.assertEqual(len(out["check_steps"]), 3)

    def test_inputs_are_capped_and_required(self):
        with self.assertRaises(ValueError):
            tc.check("", "x", fake_run(), llm=LLM(transport=no_key))
        with self.assertRaises(ValueError):
            tc.check("x", "   ", fake_run(), llm=LLM(transport=no_key))
        t = Fake({"kind": "buy", "question": "q?"})
        out = tc.check("a" * 5000, "Will they buy? " + "b" * 5000, fake_run(), llm=LLM(transport=t))
        self.assertLessEqual(len(out["store"]), tc.MAX_LEN)
        self.assertLessEqual(len(json.dumps(t.payloads[0]["messages"])), 3 * tc.MAX_LEN)

    def test_output_is_labeled_and_honest(self):
        out = tc.check("Shoes", "Will they buy?", fake_run(), llm=LLM(transport=no_key))
        self.assertIn("Nothing was sent or bought", out["note"])
        self.assertTrue(any("6" in x for x in out["limits"]))
        self.assertIn("SYNTHETIC vs MEASURED", out["evidence"]["label"])

    def test_perception_rule_for_like_and_aware_only(self):
        run = fake_run(say=(0.77, 0.09, 1.0, True), fame=(0.72, 0.0, 1.0, True), intent=(0.9, 0.2, 1.0, True))
        run["repeat_run"] = {"stability": {"say_rank_spearman_between_panels": 0.77,
                                           "fame_rank_spearman_between_panels": 0.93,
                                           "intent_rank_spearman_between_panels": 0.89}}
        for kind, q in (("like", "Do they like my site?"), ("aware", "Have people heard of us?")):
            out = tc.check("Shoes", q, run, llm=LLM(transport=Fake({"kind": kind, "question": "q?"})))
            self.assertEqual(out["level"], "trust_perception")
            self.assertIn("exploratory", out["level_text"].lower())
            self.assertIn("could still be chance", out["why"])
            self.assertIn("EXPLORATORY", out["level_source"])
        out = tc.check("Shoes", "Will they buy?", run, llm=LLM(transport=Fake({"kind": "buy", "question": "q?"})))
        self.assertEqual(out["level"], "ask_real_people")             # buy never gets the perception rule
        run["repeat_run"]["stability"]["say_rank_spearman_between_panels"] = 0.5
        out = tc.check("Shoes", "Do they like my site?", run, llm=LLM(transport=Fake({"kind": "like", "question": "q?"})))
        self.assertEqual(out["level"], "ask_real_people")             # crowds must agree too

    def test_perception_answer_shows_second_crowd_vs_revenue(self):
        run = fake_run(say=(0.77, 0.09, 1.0, True))
        run["brands"] = [{"id": str(i), "say_mean": 6.0 + i * 0.1} for i in range(6)]
        run["repeat_run"] = {"stability": {"say_rank_spearman_between_panels": 0.77},
                             "agreement": {"say": {"spearman": 0.5429}}}
        out = tc.check("Shoes", "Do they like my site?", run, llm=LLM(transport=Fake({"kind": "like", "question": "q?"})))
        self.assertEqual(out["level"], "trust_perception")
        self.assertIn("own match with revenue was 0.54", out["why"])
        self.assertIn("6.0 to 6.5", out["why"])

    def test_template_question_reads_cleanly(self):
        out = tc.check("My online candle shop", "Do people like my website?", fake_run(), llm=LLM(transport=no_key))
        self.assertNotIn("my online", out["real_question"].lower())
        self.assertIn("candle", out["real_question"])

    @unittest.skipUnless(os.path.exists(REAL_RUN), "real run file not present")
    def test_real_run_buy_question_matches_the_study_verdict(self):
        with open(REAL_RUN) as f:
            run = json.load(f)
        out = tc.check("Online clothing resale", "Will people buy from my site?", run, llm=LLM(transport=no_key))
        self.assertEqual(out["level"], run["trust_card"]["verdict"])
        self.assertEqual(out["evidence"]["spearman"], run["agreement"]["intent"]["spearman"])


if __name__ == "__main__":
    unittest.main()
