"""End-to-end test of the whole pipeline with no network and no Anthropic key.

MTA calls are stubbed with fixtures and the LLM uses a fake transport that answers each
prompt purpose with valid JSON. Standard library only.
"""
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent import audit, coach, grade, mta, run
from agent import llm as llm_mod
from agent.trace import validate_run

REAL_LLM = llm_mod.LLM
CFG = run.load_config()
DAYS = grade.DAYS

# MEASURED fixture shares by borough (each sums to 1.0). Brooklyn/Manhattan Friday is low (hybrid work).
MEASURED = {
    "Brooklyn": [0.205, 0.225, 0.230, 0.205, 0.135],
    "Manhattan": [0.205, 0.225, 0.230, 0.205, 0.135],
    "Queens": [0.200, 0.215, 0.215, 0.205, 0.165],
    "Bronx": [0.200, 0.210, 0.210, 0.195, 0.185],
}


def make_panels(panel_dir, skip=()):
    """12 panel files. SYNTHETIC shares are flat ~20% everywhere (the panel can't see the Friday dip)."""
    rng = random.Random(7)
    for i, st in enumerate(CFG["stations"]):
        if st["id"] in skip:
            continue
        counts = {d: 40 + rng.randint(-2, 2) for d in DAYS}
        counts["None"] = 12
        # incomes: two stations are rich (so an income rule matches < 3 training stations)
        income = 160000 if st["id"] in ("477", "41") else 70000 + 1000 * i
        panel = {"station_id": st["id"], "panel_id": f"fp-{st['id']}", "source_link": f"https://example.test/p/{st['id']}",
                 "recorded_at": "2026-11-14T11:00:00-05:00", "n": 200, "counts": counts,
                 "demographics": {"wfh_share_pct": (35.0 if st["borough"] in ("Brooklyn", "Manhattan") else 15.0) + i % 3, "median_income_local": income,
                                  "bachelors_pct": 30.0 + i, "nested": {"x": 1}, "ignored_field": 5},
                 "fit_score": None, "raw": {}}
        (Path(panel_dir) / f"{st['id']}.json").write_text(json.dumps(panel))


def fake_fetch_daily(ids, window):
    return {i: {"2026-10-05": 1000, "2026-10-06": 1000} for i in ids}


def fake_audit(ids, window, daily):
    return {"exclude_dates": [], "findings": [
        {"station_id": "all", "finding": "Checked Columbus Day 2026-10-12: not low, kept.", "action": "Kept"}]}


def fake_fetch_measured(ids, window, exclude_dates=()):
    out = {}
    for st in CFG["stations"]:
        if st["id"] in ids:
            out[st["id"]] = {"shares": dict(zip(DAYS, MEASURED[st["borough"]])),
                             "totals": {d: 1000 for d in DAYS}, "day_counts": {d: 4 for d in DAYS},
                             "lat": 40.7, "lon": -73.9, "name": st["name"], "borough": st["borough"],
                             "query_url": "https://data.ny.gov/resource/5wq4-mkjj.json?fixture=1"}
    return out


class FakeTransport:
    """Routes by the system prompt. Records every payload so tests can inspect them."""

    def __init__(self, round1_rules=None, round2_rules=None):
        self.payloads = []
        self.round1 = round1_rules if round1_rules is not None else self.good_rules()
        self.round2 = round2_rules

    @staticmethod
    def good_rules():
        return [
            {"id": "fri", "text": "High work-from-home areas (Brooklyn, Manhattan): fewer Friday riders.",
             "when": {"feature": "wfh_share_pct", "op": ">", "value": 30}, "adjust": {"Mon": "none", "Tue": "none", "Wed": "none", "Thu": "none", "Fri": "down"}},
            {"id": "rich", "text": "Very high local income: more Monday riders.",
             "when": {"feature": "median_income_local", "op": ">", "value": 150000},
             "adjust": {"Mon": "up", "Tue": "none", "Wed": "none", "Thu": "none", "Fri": "none"}},
        ]

    def __call__(self, payload, timeout):
        self.payloads.append(payload)
        system = payload["system"]
        user = payload["messages"][0]["content"]
        if "You are the Coach" in system:
            rules = self.round2 if (self.round2 is not None and "Round 2" in user) else self.round1
            body = {"rules": rules}
        elif "ONE sentence" in system:
            body = None
        elif "expected error" in system:
            body = {"bands": {s["id"]: [0.0, 12.0] for s in CFG["stations"] if s["split"] == "exam"}}
        elif "how far one small local user" in system:
            body = {"place": "A corner shop near Kings Hwy", "verdict": "ask_real_people",
                    "draft_question": "Which weekday mornings do you ride the subway?"}
        else:
            raise AssertionError("unrouted prompt: " + system[:80])
        text = "The rule was kept because it held at most stations." if body is None else json.dumps(body)
        return 200, {"content": [{"type": "text", "text": text}], "usage": {"input_tokens": 100, "output_tokens": 50}}


class PipelineBase(unittest.TestCase):
    def setUp(self):
        grade._reset_exam_for_tests_only()
        coach.set_llm(None)
        self._tmp = tempfile.TemporaryDirectory()
        self.panel_dir = Path(self._tmp.name) / "panels"
        self.run_dir = Path(self._tmp.name) / "runs"
        self.panel_dir.mkdir()
        self.transport = FakeTransport()
        patches = [
            mock.patch.object(mta, "fetch_daily", fake_fetch_daily),
            mock.patch.object(mta, "fetch_measured", fake_fetch_measured),
            mock.patch.object(audit, "audit", fake_audit),
            mock.patch.object(llm_mod, "LLM", lambda **kw: REAL_LLM(transport=self.transport, **kw)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(grade._reset_exam_for_tests_only)
        self.addCleanup(coach.set_llm, None)

    def go(self, *extra, panels=True):
        if panels:
            make_panels(self.panel_dir)
        run.main(["--panel-dir", str(self.panel_dir), "--run-dir", str(self.run_dir), *extra])
        return json.loads((self.run_dir / "latest.json").read_text())


class FullPipelineTest(PipelineBase):
    def test_full_run(self):
        r = self.go()
        self.assertEqual(validate_run(r), [])
        self.assertEqual(r["panel_source"], "flashpoint")
        self.assertEqual(len(r["stations"]), 12)
        self.assertTrue((self.run_dir / f"{r['run_id']}.json").exists())

        statuses = {x["status"] for x in r["rules"]}
        self.assertIn("kept", statuses)
        self.assertIn("thrown_out", statuses)
        by_id = {x["id"]: x for x in r["rules"]}
        self.assertEqual(by_id["r1-fri"]["status"], "kept")
        self.assertEqual(by_id["r1-rich"]["status"], "thrown_out")

        s = r["summary"]
        for k in ("exam_gap_before_pp", "exam_gap_after_pp", "exam_gap_dumbfix_pp"):
            self.assertIsInstance(s[k], float, k)
        self.assertEqual(s["band_total"], 4)
        self.assertIsInstance(s["band_hits"], int)
        self.assertLess(s["exam_gap_after_pp"], s["exam_gap_before_pp"])
        self.assertTrue(s["coaching_helped"])

        exam_rows = [x for x in r["stations"] if x["split"] == "exam"]
        self.assertEqual(len(exam_rows), 4)
        for x in exam_rows:
            self.assertEqual(x["predicted_error_band_pp"], [0.0, 12.0])
            self.assertIsNotNone(x["gap_after_pp"])
        for x in r["stations"]:
            if x["split"] == "train":
                self.assertIsNone(x["gap_after_pp"])
            self.assertIsNotNone(x["noise_pp"])

        tc = r["trust_card"]
        self.assertEqual(tc["verdict"], run.trust_verdict(s["exam_gap_after_pp"]))
        if tc["verdict"] != "ask_real_people":
            self.assertIsNone(tc["draft_question"])
        self.assertEqual(tc["note"], "Stopped for a human. Nothing was bought.")

        agents = {t["agent"] for t in r["trace"]}
        for a in ("planner", "auditor", "workers", "coach", "skeptic", "predictor", "exam", "trust", "done"):
            self.assertIn(a, agents)
        self.assertGreater(r["cost"]["calls"], 0)
        self.assertEqual(r["cost"]["calls"], len(self.transport.payloads))

    def test_exam_runs_once(self):
        self.go()
        with self.assertRaises(RuntimeError):
            grade.exam([], [], {"adjust": {}})

    def test_second_pipeline_run_in_same_process_refuses_exam(self):
        self.go()
        with self.assertRaises(RuntimeError):
            run.main(["--panel-dir", str(self.panel_dir), "--run-dir", str(self.run_dir)])

    def test_tier_never_reaches_model(self):
        self.go()
        for p in self.transport.payloads:
            self.assertNotIn('"tier"', p["messages"][0]["content"])

    def test_exam_stations_not_shown_to_coach(self):
        self.go()
        coach_users = [p["messages"][0]["content"] for p in self.transport.payloads if "You are the Coach" in p["system"]]
        self.assertTrue(coach_users)
        for u in coach_users:
            for st in CFG["stations"]:
                if st["split"] == "exam":
                    self.assertNotIn(f'"id": "{st["id"]}"', u)

    def test_round_two_when_round_one_has_no_keeper(self):
        noise = [FakeTransport.good_rules()[1]]
        self.transport = FakeTransport(round1_rules=noise, round2_rules=FakeTransport.good_rules())
        r = self.go()
        rounds = [x["id"].split("-")[0] for x in r["rules"]]
        self.assertIn("r1", rounds)
        self.assertIn("r2", rounds)
        self.assertEqual(validate_run(r), [])

    def test_no_kept_rules_still_completes(self):
        noise = [FakeTransport.good_rules()[1]]
        self.transport = FakeTransport(round1_rules=noise, round2_rules=noise)
        r = self.go()
        self.assertEqual(validate_run(r), [])
        self.assertFalse(any(x["status"] == "kept" for x in r["rules"]))
        self.assertIsNotNone(r["trust_card"])


class FallbackPathsTest(PipelineBase):
    def test_missing_panel_exits_without_standin(self):
        make_panels(self.panel_dir, skip=("41",))
        with self.assertRaises(SystemExit) as cm:
            run.main(["--panel-dir", str(self.panel_dir), "--run-dir", str(self.run_dir)])
        self.assertIn("Missing Flashpoint panels", str(cm.exception))
        self.assertIn("41", str(cm.exception))

    def test_no_llm_path(self):
        with mock.patch.object(llm_mod, "LLM", side_effect=AssertionError("LLM must not be built")):
            r = self.go("--no-llm")
        self.assertEqual(validate_run(r), [])
        self.assertEqual(r["rules"], [])
        self.assertIsNone(r["trust_card"])
        self.assertEqual(r["cost"]["calls"], 0)
        self.assertEqual(r["summary"]["band_total"], 0)
        self.assertIsInstance(r["summary"]["exam_gap_before_pp"], float)
        self.assertFalse(r["summary"]["coaching_helped"])
        self.assertTrue(any(t["agent"] == "coach" and "Skipped" in t["step"] for t in r["trace"]))


class TrustVerdictTest(unittest.TestCase):
    def test_cutoffs(self):
        cut = run.PREREG["trust_cutoffs_pp"]
        self.assertEqual(run.trust_verdict(cut["trust_it_below"] - 0.01), "trust")
        self.assertEqual(run.trust_verdict(cut["trust_it_below"]), "verify")
        self.assertEqual(run.trust_verdict(cut["ask_real_people_above"]), "verify")
        self.assertEqual(run.trust_verdict(cut["ask_real_people_above"] + 0.01), "ask_real_people")


if __name__ == "__main__":
    unittest.main()
