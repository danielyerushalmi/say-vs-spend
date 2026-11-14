"""Regression (code audit 12:50): a run WITH a model on the real export used to crash with
NameError (MODELS not imported) when the verdict is ask_real_people. Uses a fake transport."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

from say import run as R

HERE = os.path.dirname(os.path.abspath(__file__))
PANELS = os.path.join(HERE, "..", "panels")


def transport(payload, timeout):
    txt = json.dumps({"question": "Model question?", "sentence": "Model sentence.", "lines": ["AI-generated: x"]})
    return 200, {"content": [{"type": "text", "text": txt}], "usage": {"input_tokens": 1, "output_tokens": 1}}


@unittest.skipUnless(os.path.exists(os.path.join(PANELS, "q4_export.csv")), "real export not present")
class KeyPathTests(unittest.TestCase):
    def test_model_path_on_real_export_completes(self):
        d = tempfile.mkdtemp()
        try:
            shutil.copy(os.path.join(PANELS, "q4_export.csv"), d)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = R.main(["--export", os.path.join(d, "q4_export.csv"), "--panel-id", "p",
                               "--recorded-at", "2026-11-14T12:17:00-05:00", "--run-dir", os.path.join(d, "out"),
                               "--panel-out", os.path.join(d, "panel.json"), "--max-calls", "12"],
                              transport=transport)
            self.assertEqual(code, 0)
            run = json.load(open(os.path.join(d, "out", "say_latest.json")))
            self.assertEqual(run["trust_card"]["verdict"], "ask_real_people")
            self.assertEqual(run["trust_card"]["draft_question"], "Model question?")
            self.assertIn("AI-generated", run["trust_card"]["draft_question_source"])
            # 12:55 regression: the detective trace line saved an absolute path (with the username)
            dumped = json.dumps(run)
            self.assertNotIn(os.path.expanduser("~"), dumped)
            self.assertNotIn("/Users/", dumped)
            self.assertNotIn(os.path.realpath(d), dumped)
            self.assertNotIn(d, dumped)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
