"""Regression tests for the four wrap-up fixes (outside review, Nov 2026). FAKE data only. No network."""
import json
import os
import unittest

from agent.llm import LLM, LLMError, NoKey
from say import flashpoint_import as fi
from say import predict as P
from say import real_check as rc
from say.tests import test_run as tr

# --------------------------------------------------------------------------- 1. real_check

SUBJECTIVE = "What do you like most about ThredUp's website?"
RUN = {
    "run_id": "FAKE-run",
    "trust_card": {"draft_question": SUBJECTIVE, "draft_question_brand": "thredup"},
    "brands": [{"id": "thredup", "name": "ThredUp"}, {"id": "bark", "name": "BARK"}],
}


class RealCheckUniformQuestionTests(unittest.TestCase):
    def test_every_scored_brand_uses_the_uniform_buying_question(self):
        rows = rc.parse_csv_text("respondent_n,brand_id,bought_12m\n1,thredup,yes\n1,bark,no\n",
                                 {"thredup", "bark"})
        out = rc.score(rows, RUN)
        for b in out["brands"]:
            self.assertEqual(b["question"], rc.BRAND_QUESTION_TEMPLATE.format(name=b["name"]))
            self.assertNotEqual(b["question"], SUBJECTIVE)
        # the drafted question is still reported, separately, and marked as not scored
        self.assertEqual(out["draft_question"], SUBJECTIVE)
        self.assertEqual(out["draft_question_brand"], "thredup")
        self.assertFalse(out["draft_question_scored"])

    def test_script_keeps_draft_separate_from_scored_questions(self):
        text = rc.script_text(RUN)
        self.assertIn(SUBJECTIVE, text)
        scored = text.split("SCORED", 1)[1]
        self.assertNotIn(SUBJECTIVE, scored)
        self.assertIn(rc.BRAND_QUESTION_TEMPLATE.format(name="ThredUp"), scored)


# --------------------------------------------------------------------------- 2. flashpoint_import

class NegativeScaleTests(unittest.TestCase):
    def test_signed_negative_is_rejected_not_read_as_positive(self):
        for raw in ("-3", " -3 ", "-3.0", "−3", "Rating: -3", "-10 - Not at all likely"):
            got = fi.parse_scale(raw)
            self.assertIsNone(got[0], raw)
            self.assertEqual(got[1], "out of range", raw)

    def test_dashes_that_are_not_signs_still_parse(self):
        self.assertEqual(fi.parse_scale("10 - Extremely likely"), (10, None))
        self.assertEqual(fi.parse_scale("Extremely likely - 9"), (9, None))
        self.assertEqual(fi.parse_scale("-"), (None, None))  # blank marker


# --------------------------------------------------------------------------- 3. run.py --panel-out

class PanelOutTests(unittest.TestCase):
    setUp = tr.RunTests.setUp
    write_brands = tr.RunTests.write_brands
    write_export = tr.RunTests.write_export
    go = tr.RunTests.go

    def _scratch(self):
        s = os.path.join(self.d, "scratch")
        os.makedirs(s)
        return s

    def test_panel_out_dir_gets_panel_and_question_nothing_beside_export(self):
        s = self._scratch()
        before = set(os.listdir(self.panels))
        code, out, err = self.go("--panel-out", s, transport=tr.FakeTransport())
        self.assertEqual(code, 0, err)
        self.assertEqual(set(os.listdir(self.panels)), before)  # nothing new beside the export
        self.assertTrue(os.path.isfile(os.path.join(s, "main_run.json")))
        with open(os.path.join(s, "followup_question.txt")) as f:
            self.assertIn("Why did you rate", f.read())

    def test_panel_out_folder_that_does_not_exist_yet(self):
        s = os.path.join(self.d, "new_scratch")  # same folder for --run-dir, like a real scratch rebuild
        before = set(os.listdir(self.panels))
        code, out, err = self.go("--panel-out", s, "--run-dir", s, transport=tr.FakeTransport())
        self.assertEqual(code, 0, err)
        self.assertEqual(set(os.listdir(self.panels)), before)
        self.assertTrue(os.path.isfile(os.path.join(s, "main_run.json")))
        self.assertTrue(os.path.isfile(os.path.join(s, "followup_question.txt")))

    def test_panel_out_file_puts_question_in_same_folder(self):
        s = self._scratch()
        before = set(os.listdir(self.panels))
        code, out, err = self.go("--panel-out", os.path.join(s, "panel.json"), transport=tr.FakeTransport())
        self.assertEqual(code, 0, err)
        self.assertEqual(set(os.listdir(self.panels)), before)
        self.assertTrue(os.path.isfile(os.path.join(s, "panel.json")))
        self.assertTrue(os.path.isfile(os.path.join(s, "followup_question.txt")))

    def test_default_still_writes_beside_export(self):
        code, out, err = self.go(transport=tr.FakeTransport())
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(os.path.join(self.panels, "main_run.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.panels, "followup_question.txt")))


# --------------------------------------------------------------------------- 4. predict fallback text

ROWS = [{"id": f"b{i}", "name": f"Brand {i}", "description": f"Sells thing {i}.",
         "say_mean": 6.0 + i * 0.1, "intent_mean": 3.0 + i * 0.2} for i in range(5)]
VAL = {"ok": True, "model_error": {"say_mean": 0.1, "intent_mean": 0.1},
       "model_beats_baseline": {"say_mean": True, "intent_mean": True}}
EXACT = "No usable model prediction returned; average used."


def _no_key(payload, timeout):
    raise NoKey("no key")


def _fails(payload, timeout):
    raise LLMError("network error: OSError")


def _bad(payload, timeout):
    return 200, {"content": [{"type": "text", "text": json.dumps({"say": "high", "intent": 99})}],
                 "usage": {"input_tokens": 1, "output_tokens": 1}}


class PredictFallbackTextTests(unittest.TestCase):
    def test_every_fallback_path_says_the_exact_text(self):
        for name, transport in (("no key", _no_key), ("failed call", _fails), ("bad response", _bad)):
            out = P.predict("Candles", {"brands": ROWS}, VAL, LLM(transport=transport))
            self.assertTrue(any(EXACT in w for w in out["why"]), (name, out["why"]))
            self.assertIn("code: average", out["method"]["website"], name)
            self.assertIn("code: average", out["method"]["buy"], name)


if __name__ == "__main__":
    unittest.main()
