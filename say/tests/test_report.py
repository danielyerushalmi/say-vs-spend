import contextlib
import io
import json
import os
import re
import tempfile
import unittest

from say import report
from say import run as say_run

HERE = os.path.dirname(os.path.abspath(__file__))
REAL_RUN = os.path.join(HERE, "..", "..", "frontend", "runs", "say_latest.json")

FAKE_IDS = ["fake-a", "fake-b", "fake-c", "fake-d", "fake-e", "fake-f"]
FAKE_REVENUES = [900_000_001, 700_000_003, 500_000_007, 300_000_011, 200_000_013, 100_000_017]

LEAKS = ("sk-ant", "X-Amz", "/Users/", "ANTHROPIC_API_KEY")


def make_fake_run(d):
    """Build a FAKE run file with the real pipeline (no model calls) from made-up numbers."""
    brands_dir = os.path.join(d, "brands")
    panels = os.path.join(d, "panels")
    runs = os.path.join(d, "runs")
    os.makedirs(brands_dir)
    os.makedirs(panels)
    for i, bid in enumerate(FAKE_IDS):
        with open(os.path.join(brands_dir, bid + ".json"), "w") as f:
            json.dump({"id": bid, "name": "FAKE " + bid, "description": "FAKE TEST DATA brand.", "pass": True,
                       "revenue_usd": FAKE_REVENUES[i], "fiscal_year": "FY2025", "online_note": "FAKE",
                       "filing_url": "https://example.invalid/fake", "label": "MEASURED"}, f)
    cols = ["panel_respondent_id"] + [f"{k}__{b}" for k in ("SAY", "INTENT", "AWARE") for b in FAKE_IDS]
    lines = [",".join(cols)]
    for n in range(1, 13):
        row = [f"FAKE{n}"]
        for kind in ("SAY", "INTENT", "AWARE"):
            for i, _ in enumerate(FAKE_IDS):
                v = max(1, min(10, 9 - i + (n % 3) - 1))
                row.append(("1" if i + n % 4 < 5 else "2") if kind == "AWARE" else str(v))
        lines.append(",".join(row))
    export = os.path.join(panels, "export.csv")
    with open(export, "w") as f:
        f.write("\n".join(lines) + "\n")
    argv = ["--export", export, "--panel-id", "test-fixture-panel", "--recorded-at", "2026-11-14T12:00:00-05:00",
            "--run-dir", runs, "--brands-dir", brands_dir, "--no-llm"]
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        code = say_run.main(argv)
    assert code == 0, code
    return os.path.join(runs, "say_latest.json")


class ReportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = self._tmp.name

    def gen(self, run_path, *extra):
        out = os.path.join(self.d, "out", "index.html")
        with contextlib.redirect_stdout(io.StringIO()):
            code = report.main(["--run", run_path, "--out", out, *extra])
        self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as f:
            return f.read()

    def assert_page_ok(self, page):
        self.assertTrue(page.startswith("<!doctype html>"))
        for label in ("MEASURED", "SYNTHETIC", "AI-GENERATED", "ESTIMATE", "not investment advice"):
            self.assertIn(label, page)
        for bad in LEAKS:
            self.assertNotIn(bad, page)
        # offline: no scripts, no outside stylesheets or images
        self.assertNotIn("<script", page.lower())
        self.assertIsNone(re.search(r'(src|href)="https?://(?!www\.sec\.gov|wikimedia\.org|example\.invalid)', page))

    def test_fake_fixture_run(self):
        run_path = make_fake_run(self.d)
        page = self.gen(run_path, "--no-git", "--followup", "none", "--recount", "none",
                        "--decisions", "none", "--wiki", "none")
        self.assert_page_ok(page)
        self.assertIn("FAKE fake-a", page)
        self.assertIn("Stopped for a human", page)
        with open(run_path) as f:
            run = json.load(f)
        self.assertIn(report.num(run["agreement"]["intent"]["spearman"]), page)

    @unittest.skipUnless(os.path.exists(REAL_RUN), "real run file not present")
    def test_real_run_file(self):
        page = self.gen(REAL_RUN, "--no-git")
        self.assert_page_ok(page)
        with open(REAL_RUN) as f:
            run = json.load(f)
        tc = run["trust_card"]
        self.assertIn(report.esc(tc["rule"]), page)
        self.assertIn(report.esc(tc["note"]), page)
        self.assertIn("Stopped for a human. Nothing was bought.", page)
        # 12:57 regression: a missing f-prefix printed the literal "{esc(dq)}" instead of the question
        # (checks the quoted question slot only: decisions.md, shown in the timeline, may mention the bug)
        self.assertNotIn("“{esc(", page)
        if tc.get("draft_question"):
            self.assertIn(report.esc(tc["draft_question"]), page)
            src = tc.get("draft_question_source") or ""
            self.assertIn("AI-GENERATED" if "model" in src.lower() else "CODE TEMPLATE", page)
        self.assertIn(report.VERDICT_TEXT.get(tc["verdict"], ""), page)
        for b in run["brands"]:
            self.assertIn(report.esc(b["name"]), page)
            self.assertIn(report.money(b["revenue_usd"]), page)
        fa = (run.get("fame_wiki") or {}).get("agreement") or {}
        if fa.get("could_be_chance"):
            wiki_tile = next(t for t in page.split('<div class="tile">') if "Wikipedia views vs money" in t)
            self.assertIn("could be chance", wiki_tile)
            self.assertIn("EXPLORATORY", wiki_tile)
        st = (run.get("repeat_run") or {}).get("stability") or {}
        if st:
            self.assertIn(report.num(st["intent_rank_spearman_between_panels"]), page)

    def test_scrub_removes_local_paths(self):
        s = report.scrub("saved /Users/someone/x/hackathon-project/say/panels/main_run.json and /Users/a/b.txt")
        self.assertNotIn("/Users/", s)
        self.assertIn("say/panels/main_run.json", s)

    def test_ranks_desc_ignores_missing_and_ties(self):
        self.assertEqual(report.ranks_desc({"a": 10, "b": None, "c": 30, "d": 10}), {"c": 1, "a": 2.5, "d": 2.5})

    def test_rule_vs_result_classifier(self):
        self.assertEqual(report.classify("Trust rule: cutoffs apply to the low end"), "rule")
        self.assertEqual(report.classify("First real run (Q4 panel)"), "result")
        self.assertEqual(report.classify("Add README"), "other")


if __name__ == "__main__":
    unittest.main()
