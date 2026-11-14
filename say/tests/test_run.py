import contextlib
import io
import json
import os
import tempfile
import unittest

from agent.llm import NoKey
from say import run as say_run
from say import runfile

IDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf"]
REVENUES = [900_123_457, 800_234_568, 700_345_679, 600_456_781, 500_567_893, 400_678_913, 300_789_127]


def ok(obj):
    return 200, {"content": [{"type": "text", "text": json.dumps(obj)}],
                 "usage": {"input_tokens": 10, "output_tokens": 5}}


class FakeTransport:
    def __init__(self):
        self.payloads = []

    def __call__(self, payload, timeout):
        self.payloads.append(payload)
        return ok({"question": "Why did you rate these websites that way?",
                   "sentence": "The AI crowd ordered brands much like real sales did.",
                   "lines": ["Shoppers liked easy checkout.", "Prices felt fair."]})

    def prompts(self):
        return "\n".join(p["system"] + json.dumps(p["messages"]) for p in self.payloads)


def dead(payload, timeout):
    raise NoKey("no key")


class RunTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = self._tmp.name
        self.brands_dir = os.path.join(self.d, "brands")
        self.panels = os.path.join(self.d, "panels")
        self.run_dir = os.path.join(self.d, "runs")
        os.makedirs(self.brands_dir)
        os.makedirs(self.panels)
        self.write_brands(IDS)
        self.export = os.path.join(self.panels, "main_export.csv")
        self.write_export(IDS)

    def write_brands(self, ids, failing=()):
        for i, bid in enumerate(ids):
            b = {"id": bid, "name": bid.title(), "description": f"Sells {bid} things online.",
                 "pass": bid not in failing, "revenue_usd": REVENUES[i % len(REVENUES)],
                 "fiscal_year": "FY2025", "online_note": "online", "filing_url": "https://example.test/x",
                 "label": "MEASURED"}
            if bid in failing:
                b["fail_reason"] = "UNVERIFIED online share"
            with open(os.path.join(self.brands_dir, bid + ".json"), "w") as f:
                json.dump(b, f)

    def write_export(self, ids, extra_cols=None):
        cols = ["panel_respondent_id"] + [f"{k}__{b}" for k in ("SAY", "INTENT", "AWARE") for b in ids]
        cols += extra_cols or []
        lines = [",".join(cols)]
        for n in range(1, 13):
            row = [f"P{n}"]
            for kind in ("SAY", "INTENT", "AWARE"):
                for i, _ in enumerate(ids):
                    base = 9 - i  # alpha rated highest
                    v = max(1, min(10, base + (n % 3) - 1))
                    row.append(("1" if i + n % 4 < 6 else "2") if kind == "AWARE" else str(v))
            row += ["x"] * len(extra_cols or [])
            lines.append(",".join(row))
        with open(self.export, "w") as f:
            f.write("\n".join(lines) + "\n")

    def go(self, *extra, transport=None):
        argv = ["--export", self.export, "--panel-id", "test-panel", "--recorded-at",
                "2026-11-14T12:55:00-05:00", "--run-dir", self.run_dir, "--brands-dir", self.brands_dir,
                *extra]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = say_run.main(argv, transport=transport)
        return code, out.getvalue(), err.getvalue()

    def latest(self):
        with open(os.path.join(self.run_dir, "say_latest.json")) as f:
            return json.load(f)

    def test_expect_n_mismatch_aborts(self):
        code, out, err = self.go("--no-llm", "--expect-n", "999")
        self.assertEqual(code, 2)
        self.assertIn("expected exactly 999", err + out)

    def test_full_path_writes_valid_run(self):
        t = FakeTransport()
        code, out, err = self.go(transport=t)
        self.assertEqual(code, 0, err)
        run = self.latest()
        self.assertEqual(runfile.validate_run(run), [])
        self.assertEqual(run["mode"], "recorded")
        self.assertEqual(len(run["brands"]), 7)
        self.assertEqual(run["trust_card"]["note"], "Stopped for a human. Nothing was bought.")
        self.assertEqual(run["trust_card"]["reason"], "The AI crowd ordered brands much like real sales did.")
        self.assertGreaterEqual(run["cost"]["calls"], 2)
        self.assertGreater(run["cost"]["estimate_usd"], 0)
        self.assertTrue(os.path.exists(os.path.join(self.panels, "main_run.json")))
        with open(os.path.join(self.panels, "followup_question.txt")) as f:
            self.assertIn("Why did you rate", f.read())
        self.assertIn("Why did you rate", run["top_gaps"][0]["followup_question"])
        self.assertTrue(os.path.exists(os.path.join(self.run_dir, "say_progress.json")))

    def test_aware_codes_one_yes_two_no(self):
        self.go("--no-llm")
        run = self.latest()
        shares = {b["id"]: b["aware_share"] for b in run["brands"]}
        self.assertEqual(shares["alpha"], 1.0)  # every alpha answer is code 1 = Yes
        self.assertEqual(shares["golf"], 0.0)   # every golf answer is code 2 = No

    def test_no_llm_path_is_valid_and_makes_no_calls(self):
        t = FakeTransport()
        code, out, err = self.go("--no-llm", transport=t)
        self.assertEqual(code, 0, err)
        self.assertEqual(t.payloads, [])
        run = self.latest()
        self.assertEqual(runfile.validate_run(run), [])
        self.assertEqual(run["cost"]["calls"], 0)
        self.assertTrue(run["trust_card"]["reason"])
        self.assertFalse(os.path.exists(os.path.join(self.panels, "followup_question.txt")))

    def test_missing_key_gives_clear_message(self):
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            code, out, err = self.go()
        finally:
            if old is not None:
                os.environ["ANTHROPIC_API_KEY"] = old
        self.assertEqual(code, 2)
        self.assertIn("read -s ANTHROPIC_API_KEY", err)
        self.assertFalse(os.path.exists(os.path.join(self.run_dir, "say_latest.json")))

    def test_fewer_than_six_brands_aborts(self):
        self.write_brands(IDS, failing=("echo", "foxtrot"))  # 5 pass; CSV still has all 7
        code, out, err = self.go("--no-llm")
        self.assertEqual(code, 2)
        self.assertIn("Only 5 usable brands", err)
        self.assertFalse(os.path.exists(os.path.join(self.run_dir, "say_latest.json")))

    def test_dropped_brands_named_in_trace(self):
        self.write_brands(IDS, failing=("golf",))
        code, out, err = self.go("--no-llm")
        self.assertEqual(code, 0, err)
        trace = json.dumps(self.latest()["trace"])
        self.assertIn("dropped golf", trace)
        self.assertIn("UNVERIFIED online share", trace)

    def test_unmatched_columns_abort(self):
        self.write_export(IDS, extra_cols=["SAY__mystery_brand"])
        code, out, err = self.go("--no-llm")
        self.assertEqual(code, 2)
        self.assertIn("could not be matched", err)
        self.assertFalse(os.path.exists(os.path.join(self.run_dir, "say_latest.json")))

    def test_mode_never_live_by_default(self):
        self.go("--no-llm")
        self.assertEqual(self.latest()["mode"], "recorded")
        self.go("--no-llm", "--live")
        self.assertEqual(self.latest()["mode"], "live")

    def test_prompts_never_contain_revenue(self):
        t = FakeTransport()
        fu = os.path.join(self.d, "followup.json")
        with open(fu, "w") as f:
            json.dump(["Checkout was easy.", "Liked the photos."], f)
        code, out, err = self.go("--followup", fu, "--max-calls", "30", transport=t)
        self.assertEqual(code, 0, err)
        self.assertGreater(len(t.payloads), 3)
        prompts = t.prompts()
        for rev in REVENUES:
            self.assertNotIn(str(rev), prompts)
            self.assertNotIn(f"{rev:,}", prompts)
        self.assertNotIn("revenue_usd", prompts)
        run = self.latest()
        self.assertTrue(run["top_gaps"][0]["why_summary"].startswith("AI-generated: "))
        self.assertEqual(run["top_gaps"][0]["raw_link"], fu)

    def test_max_calls_stop_switch(self):
        t = FakeTransport()
        code, out, err = self.go("--max-calls", "1", transport=t)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(t.payloads), 1)
        self.assertEqual(runfile.validate_run(self.latest()), [])

    def test_store_block(self):
        sp = os.path.join(self.d, "store.json")
        with open(sp, "w") as f:
            json.dump({"name": "Demo Mugs", "description": "Fictional mug shop.",
                       "responses": [{"say": 6, "intent": 5, "aware": True}, {"say": 8, "intent": 7, "aware": False}]}, f)
        code, out, err = self.go("--no-llm", "--store", sp)
        self.assertEqual(code, 0, err)
        store = self.latest()["store"]
        self.assertEqual(store["label"], "FICTIONAL DEMO STORE")
        self.assertEqual(store["say_mean"], 7.0)
        self.assertEqual(store["aware_share"], 0.5)
        self.assertEqual(store["verdict"], self.latest()["trust_card"]["verdict"])

    def test_key_never_in_output(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-test-SECRET123"
        try:
            code, out, err = self.go("--no-llm")
        finally:
            del os.environ["ANTHROPIC_API_KEY"]
        self.assertNotIn("SECRET123", out + err + json.dumps(self.latest()))


if __name__ == "__main__":
    unittest.main()
