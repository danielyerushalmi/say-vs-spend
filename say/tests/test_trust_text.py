import json
import unittest

from agent.llm import LLM, NoKey
from say import trust_text as tt


class Fake:
    def __init__(self, obj):
        self.obj, self.payloads = obj, []

    def __call__(self, payload, timeout):
        self.payloads.append(payload)
        return 200, {"content": [{"type": "text", "text": json.dumps(self.obj)}],
                     "usage": {"input_tokens": 1, "output_tokens": 1}}


def no_key(payload, timeout):
    raise NoKey("no key")


class TrustTextTests(unittest.TestCase):
    def test_sentence_uses_given_numbers_and_verdict(self):
        t = Fake({"sentence": "The crowd matched sales only a little."})
        s = tt.trust_sentence("ask_real_people", "intent spearman = 0.21", "below 0.4 means ask",
                              False, True, llm=LLM(transport=t))
        self.assertEqual(s, "The crowd matched sales only a little.")
        p = t.payloads[0]
        text = p["system"] + json.dumps(p["messages"])
        self.assertIn("0.21", text)
        self.assertIn("ask_real_people", text)
        self.assertEqual(p["model"], "claude-sonnet-5-5")

    def test_sentence_fallback_keeps_verdict_meaning(self):
        for v in tt.VERDICTS:
            s = tt.trust_sentence(v, "m", "r", True, False, llm=LLM(transport=no_key))
            self.assertEqual(s, tt._FALLBACK[v])

    def test_bad_verdict_rejected(self):
        with self.assertRaises(ValueError):
            tt.trust_sentence("maybe", "m", "r", True, False, llm=LLM(transport=Fake({})))

    def test_question_only_for_ask_real_people(self):
        t = Fake({"question": "What made you choose this store?"})
        llm = LLM(transport=t)
        for v in ("trust", "verify"):
            self.assertIsNone(tt.real_survey_question(v, "ctx", llm=llm))
        self.assertEqual(t.payloads, [])
        self.assertEqual(tt.real_survey_question("ask_real_people", "A candle shop", llm=llm),
                         "What made you choose this store?")
        self.assertIsNone(tt.real_survey_question("ask_real_people", "x", llm=LLM(transport=no_key)))

    def test_prompts_have_no_revenue(self):
        t = Fake({"sentence": "ok", "question": "q"})
        llm = LLM(transport=t)
        tt.trust_sentence("verify", "intent spearman = 0.5", "0.4 to 0.7", False, True, llm=llm)
        tt.real_survey_question("ask_real_people", "A candle shop", llm=llm)
        for p in t.payloads:
            self.assertNotIn("revenue", (p["system"] + json.dumps(p["messages"])).lower().replace(
                "never mention revenue", ""))

    def test_question_fallback_without_model(self):
        from agent.llm import NoKey
        class NoKeyLLM:
            def call(self, *a, **k):
                raise NoKey("no key")
        q = tt.real_survey_question("ask_real_people", "Gap", llm=NoKeyLLM(), fallback="Have you bought from X?")
        self.assertEqual(q, "Have you bought from X?")
        self.assertIsNone(tt.real_survey_question("verify", "Gap", llm=NoKeyLLM(), fallback="x"))

    def test_store_card_exact(self):
        c = tt.store_card("Moonwick", "Sells candles.",
                          {"say_mean": 6.1, "intent_mean": 4.2, "aware_share": 0.1}, "verify")
        self.assertEqual(c["label"], "FICTIONAL DEMO STORE")
        self.assertEqual(c["note"], "No answer key for this store; trust level comes from the brand test.")
        self.assertEqual(c["verdict"], "verify")
        self.assertEqual(set(c), {"name", "description", "label", "say_mean", "intent_mean",
                                  "aware_share", "verdict", "note"})


if __name__ == "__main__":
    unittest.main()
