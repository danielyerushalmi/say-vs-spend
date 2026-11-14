import json
import unittest

from agent.llm import LLM, NoKey, StopSwitch
from say import detective


def ok(obj):
    return 200, {"content": [{"type": "text", "text": json.dumps(obj)}],
                 "usage": {"input_tokens": 1, "output_tokens": 1}}


class Fake:
    def __init__(self, obj):
        self.obj, self.payloads = obj, []

    def __call__(self, payload, timeout):
        self.payloads.append(payload)
        return ok(self.obj)


def no_key(payload, timeout):
    raise NoKey("no key")


BRANDS = [
    {"id": "figs", "name": "Figs", "description": "Sells scrubs.", "revenue_usd": 555123456},
    {"id": "away", "name": "Away", "description": "Sells luggage.", "revenue_usd": 777888999},
]
GAPS = [{"brand_id": "figs", "question": "intent", "crowd_rank": 2, "revenue_rank": 9},
        {"brand_id": "away", "question": "say", "crowd_rank": 1, "revenue_rank": 8}]


def prompt_text(t):
    p = t.payloads[0]
    return p["system"] + json.dumps(p["messages"])


class DetectiveTests(unittest.TestCase):
    def test_followup_returns_question_and_ids(self):
        t = Fake({"question": "What would stop you from buying?"})
        r = detective.draft_followup(GAPS, BRANDS, llm=LLM(transport=t))
        self.assertEqual(r, {"question": "What would stop you from buying?",
                             "brand_ids": ["figs", "away"]})
        self.assertEqual(t.payloads[0]["model"], "claude-sonnet-5-5")

    def test_followup_prompt_has_no_revenue(self):
        t = Fake({"question": "Why?"})
        detective.draft_followup(GAPS, BRANDS, llm=LLM(transport=t))
        text = prompt_text(t)
        for leak in ("555123456", "777888999", "revenue_usd", "revenue_rank", "crowd_rank"):
            self.assertNotIn(leak, text)
        self.assertIn("Figs", text)

    def test_followup_fallbacks(self):
        self.assertIsNone(detective.draft_followup(GAPS, BRANDS, llm=LLM(transport=no_key)))
        self.assertIsNone(detective.draft_followup([], BRANDS, llm=LLM(transport=Fake({}))))
        self.assertIsNone(detective.draft_followup(GAPS, BRANDS, llm=LLM(transport=Fake({"question": ""}))))
        stop = LLM(max_calls=0, transport=Fake({"question": "x"}))
        self.assertIsNone(detective.draft_followup(GAPS, BRANDS, llm=stop))

    def test_summary_prefix_and_count(self):
        t = Fake({"lines": ["Price feels high.", "AI-generated: Shipping is slow."]})
        r = detective.summarize_reasons(["too pricey", "slow shipping", ""], BRANDS[0],
                                        llm=LLM(transport=t))
        self.assertEqual(r["n_answers"], 2)
        self.assertEqual(r["lines"], ["AI-generated: Price feels high.",
                                      "AI-generated: Shipping is slow."])

    def test_summary_max_four_lines_and_no_revenue(self):
        t = Fake({"lines": [f"theme {i}" for i in range(7)]})
        r = detective.summarize_reasons(["a"], BRANDS[0], llm=LLM(transport=t))
        self.assertEqual(len(r["lines"]), 4)
        self.assertNotIn("555123456", prompt_text(t))

    def test_summary_fallbacks(self):
        r = detective.summarize_reasons(["a", "b"], BRANDS[0], llm=LLM(transport=no_key))
        self.assertEqual(r, {"lines": [], "n_answers": 2})
        self.assertEqual(detective.summarize_reasons([], BRANDS[0], llm=LLM(transport=no_key)),
                         {"lines": [], "n_answers": 0})


if __name__ == "__main__":
    unittest.main()
