import json
import os
import re
import tempfile
import unittest

from agent import trace
from agent.trace import Trace, new_run, validate_run

SHARES = {"Mon": 0.2, "Tue": 0.2, "Wed": 0.2, "Thu": 0.2, "Fri": 0.2}


def full_run():
    run = new_run("Which mornings?", "flashpoint", "recorded")
    run["stations"].append({
        "id": "41", "name": "7 Av", "borough": "Brooklyn", "lat": 40.0, "lon": -73.0, "split": "exam",
        "synthetic_shares": SHARES, "measured_shares": SHARES, "gap_before_pp": 1.0,
        "gap_after_pp": 0.5, "gap_dumbfix_pp": 0.8, "predicted_error_band_pp": [0.2, 1.1],
        "fit_score": None, "sources": {"synthetic": "p1", "measured": "https://example.org/q"}})
    run["rules"].append({"id": "r1", "text": "t", "status": "kept", "reason": "r",
                         "stations_holding": 3, "beats_dumb_fix": True})
    run["trust_card"] = {"place": "p", "station_id": "41", "verdict": "verify",
                         "draft_question": "q", "note": "n"}
    return run


class TestTrace(unittest.TestCase):
    def test_step_format(self):
        tr = Trace(run_dir="unused")
        tr.step("coach", "claude-opus-5-5", "Proposed 4 rules", "detail")
        e = tr.steps[0]
        self.assertEqual(set(e), {"t", "agent", "model", "step", "detail"})
        self.assertRegex(e["t"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}-05:00$")
        self.assertEqual(tr.step("a", "m", "s")["detail"], "")

    def test_new_run_has_all_keys_and_validates(self):
        run = new_run("q", "claude_standin", "live")
        self.assertEqual(set(run), set(trace.TOP_LEVEL))
        self.assertEqual(validate_run(run), [])
        self.assertRegex(run["run_id"], r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}$")

    def test_write_creates_folder_and_valid_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = os.path.join(tmp, "nested", "runs")
            tr = Trace(run_dir=run_dir)
            tr.step("planner", "m", "step")
            run = full_run()
            run["trace"] = tr.steps
            path = tr.write(run)
            self.assertEqual(os.path.basename(path), run["run_id"] + ".json")
            for name in (run["run_id"] + ".json", "latest.json"):
                with open(os.path.join(run_dir, name), encoding="utf-8") as f:
                    loaded = json.load(f)
                self.assertEqual(validate_run(loaded), [])
                self.assertEqual(loaded["run_id"], run["run_id"])
            self.assertEqual([n for n in os.listdir(run_dir) if n.startswith(".tmp")], [])

    def test_write_failure_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tr = Trace(run_dir=tmp)
            run = full_run()
            run["cost"] = {"calls": object()}  # not JSON serializable
            with self.assertRaises(TypeError):
                tr.write(run)
            self.assertEqual(os.listdir(tmp), [])


class TestValidate(unittest.TestCase):
    def test_full_run_valid(self):
        self.assertEqual(validate_run(full_run()), [])

    def test_missing_key(self):
        run = full_run()
        del run["audit"]
        self.assertTrue(any("audit" in e for e in validate_run(run)))

    def test_bad_split(self):
        run = full_run()
        run["stations"][0]["split"] = "test"
        self.assertTrue(any("split" in e for e in validate_run(run)))

    def test_bad_verdict(self):
        run = full_run()
        run["trust_card"]["verdict"] = "maybe"
        self.assertTrue(any("verdict" in e for e in validate_run(run)))

    def test_null_verdict_ok(self):
        run = full_run()
        run["trust_card"]["verdict"] = None
        self.assertEqual(validate_run(run), [])

    def test_bad_rule_status(self):
        run = full_run()
        run["rules"][0]["status"] = "maybe"
        self.assertTrue(any("status" in e for e in validate_run(run)))

    def test_bad_mode_and_panel_source(self):
        run = full_run()
        run["mode"] = "demo"
        run["panel_source"] = "gpt"
        errs = validate_run(run)
        self.assertTrue(any("mode" in e for e in errs))
        self.assertTrue(any("panel_source" in e for e in errs))

    def test_bad_band_and_shares(self):
        run = full_run()
        run["stations"][0]["predicted_error_band_pp"] = [1]
        run["stations"][0]["synthetic_shares"] = {"Mon": 1}
        errs = validate_run(run)
        self.assertTrue(any("band" in e for e in errs))
        self.assertTrue(any("synthetic_shares" in e for e in errs))

    def test_not_a_dict(self):
        self.assertEqual(validate_run([]), ["run is not a dict"])


if __name__ == "__main__":
    unittest.main()
