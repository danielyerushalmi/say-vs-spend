"""Crowd Coach orchestrator.

Runs the whole pipeline in order and rewrites frontend/runs/latest.json after every stage,
so the demo page can show progress:

    answer key (MTA) -> auditor -> panels (Flashpoint, or a labeled Claude stand-in)
    -> coach rounds (rules) -> skeptic (code) -> predict -> exam (once) -> trust card

Usage (from the repo root):
    python3 -m agent.run                       # Flashpoint panel files required
    python3 -m agent.run --allow-standin       # fill missing panels with Claude stand-ins (labeled)
    python3 -m agent.run --no-llm              # code-only dry run: dumb fix only, no coach (Turnstile Truth mode)

All arithmetic happens in agent/grade.py. Models only write rules (conditions + direction),
plain-English explanations, predicted bands (ESTIMATE) and the trust card.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent import audit, grade, mta
from agent.trace import Trace, new_run, validate_run

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "agent" / "config" / "stations.json"
PREREG = json.loads((ROOT / "agent" / "config" / "preregistration.json").read_text())
PANEL_DIRS = [ROOT / "data" / "panels", ROOT / "flashpoint" / "panels"]
ET = timezone(timedelta(hours=-5))
MAX_COACH_ROUNDS = 2
DAYS = grade.DAYS


def load_config() -> dict:
    return json.loads(CONFIG.read_text())


def find_panel(station_id: str, panel_dir: Path | None) -> dict | None:
    """Return Daniel's Flashpoint panel file for a station, or None if it is not there yet."""
    dirs = [panel_dir] if panel_dir else PANEL_DIRS
    for d in dirs:
        p = d / f"{station_id}.json"
        if p.exists():
            return json.loads(p.read_text())
    return None


def numeric_features(demographics: dict | None) -> dict:
    """Keep only flat numeric demographic fields as rule features (nested data is skipped)."""
    allowed = set(PREREG["allowed_rule_features"])  # fixed before any panel result existed
    out = {}
    for k, v in (demographics or {}).items():
        if k in allowed and isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = v
    return out


def census_features() -> dict:
    """Tract-level Census ACS traits per station (agent/features.py output), or {} if not built yet."""
    path = ROOT / "agent" / "data" / "census" / "stations_features.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {sid: numeric_features(v) for sid, v in data.items() if isinstance(v, dict)}


def trust_verdict(expected_error_pp: float) -> str:
    """Pre-registered cutoffs decide the label, not a model."""
    cut = PREREG["trust_cutoffs_pp"]
    if expected_error_pp < cut["trust_it_below"]:
        return "trust"
    if expected_error_pp > cut["ask_real_people_above"]:
        return "ask_real_people"
    return "verify"


def _r2(v):
    """Round floats to 2 decimals for display; leave bools and None alone."""
    return round(v, 2) if isinstance(v, float) else v


def pct(shares: dict | None) -> dict | None:
    return None if shares is None else {d: round(shares[d], 4) for d in DAYS}


def station_rows(stations: list[dict]) -> list[dict]:
    """Shape station records for the run file (docs/FRONTEND.md data contract)."""
    rows = []
    for s in stations:
        rows.append({
            "id": s["id"], "name": s["name"], "borough": s["borough"],
            "lat": s.get("lat"), "lon": s.get("lon"), "split": s["split"],
            "synthetic_shares": pct(s.get("synthetic")),
            "measured_shares": pct(s.get("measured")),
            "gap_before_pp": s.get("gap_before_pp"),
            "gap_after_pp": s.get("gap_after_pp"),
            "gap_dumbfix_pp": s.get("gap_dumbfix_pp"),
            "predicted_error_band_pp": s.get("predicted_error_band_pp"),
            "fit_score": s.get("fit_score"),
            "noise_pp": s.get("noise_pp"),  # ESTIMATE: 90th-percentile chance wobble of this panel
            "sources": s.get("sources", {}),
        })
    return rows


class Pipeline:
    def __init__(self, args):
        self.args = args
        self.cfg = load_config()
        self.trace = Trace(run_dir=str(args.run_dir))
        self.stations = [dict(s) for s in self.cfg["stations"]]
        self.llm = None
        self.panel_source = "flashpoint"
        self.run = None

    # ---- helpers -------------------------------------------------------
    def step(self, agent, model, text, detail=""):
        print(f"[{agent}] {text}" + (f" — {detail}" if detail else ""), flush=True)
        self.trace.step(agent, model, text, detail)

    def save(self):
        """Rewrite the run file so the page can show progress."""
        self.run["stations"] = station_rows(self.stations)
        self.run["trace"] = self.trace.steps
        if self.llm is not None:
            self.run["cost"] = {"calls": self.llm.calls, "estimate_usd": round(self.llm.cost_usd_estimate(), 4)}
        errors = validate_run(self.run)
        if errors:
            raise RuntimeError("Run file failed validation: " + "; ".join(errors))
        self.trace.write(self.run)

    def train(self):
        return [s for s in self.stations if s["split"] == "train"]

    def exam_set(self):
        return [s for s in self.stations if s["split"] == "exam"]

    # ---- stages --------------------------------------------------------
    def plan(self):
        n_exam = len(self.exam_set())
        self.step("planner", "code", f"Loaded {len(self.stations)} stations; {n_exam} locked as the exam",
                  self.cfg.get("exam_draw", ""))

    def answer_key(self):
        ids = [s["id"] for s in self.stations]
        window = self.cfg["window"]
        daily = mta.fetch_daily(ids, window)
        result = audit.audit(ids, window, daily)
        self.run["audit"] = result["findings"]
        for f in result["findings"]:
            self.step("auditor", "code", f["finding"], f["action"])
        if not result["findings"]:
            self.step("auditor", "code", "No data problems found in the answer key")
        measured = mta.fetch_measured(ids, window, exclude_dates=result["exclude_dates"])
        for s in self.stations:
            m = measured.get(s["id"])
            if m is None:
                raise RuntimeError(f"No MTA data for station {s['id']} {s['name']}")
            s["measured"] = m["shares"]
            s["lat"], s["lon"] = m.get("lat"), m.get("lon")
            s.setdefault("sources", {})["measured"] = m["query_url"]
        self.step("workers", "code", f"Pulled MEASURED Mon-Fri morning shares for {len(measured)} stations",
                  "MTA Subway Hourly Ridership, data.ny.gov 5wq4-mkjj")
        self.save()

    def panels(self):
        missing = []
        for s in self.stations:
            p = find_panel(s["id"], self.args.panel_dir)
            if p is None:
                missing.append(s)
                continue
            s["synthetic"] = grade.normalize(p["counts"])
            s["counts"] = p["counts"]
            s["features"] = {"borough": s["borough"], **numeric_features(p.get("demographics"))}
            s["fit_score"] = p.get("fit_score")
            s.setdefault("sources", {})["synthetic"] = p.get("source_link") or p.get("panel_id", "")
        if missing and not self.args.allow_standin:
            names = ", ".join(f"{s['id']} {s['name']}" for s in missing)
            raise SystemExit(f"Missing Flashpoint panels for: {names}. Re-run with --allow-standin to use labeled Claude stand-ins.")
        if missing:
            # Honest labeling: one stand-in panel makes the whole run a stand-in run.
            self.panel_source = "claude_standin"
            self.run["panel_source"] = "claude_standin"
            from agent.standin import standin_panel
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda st: standin_panel(st, self.cfg["question"]), missing))
            for s, p in zip(missing, results):
                s["synthetic"] = grade.normalize(p["counts"])
                s["counts"] = p["counts"]
                s["features"] = {"borough": s["borough"]}
                s.setdefault("sources", {})["synthetic"] = p.get("note", "Claude stand-in, not Flashpoint, not census-grounded")
            self.step("workers", "claude-haiku-5-5", f"Built {len(missing)} Claude stand-in panels",
                      "Claude stand-in, not Flashpoint, not census-grounded")
        census = census_features()
        with_census = 0
        for s in self.stations:
            local = census.get(s["id"]) or {}
            if local:
                s["features"].update(local)  # MEASURED tract numbers override county-level context
                with_census += 1
        self.step("workers", "code", f"Loaded SYNTHETIC shares for {len(self.stations)} stations", self.panel_source)
        self.step("workers", "code",
                  f"Rule traits: Census tract data for {with_census} of {len(self.stations)} stations"
                  if with_census else "Rule traits: borough + Flashpoint county-level numbers only (no Census tract data)",
                  "MEASURED, US Census ACS 5-year" if with_census else "")
        for s in self.stations:
            s["gap_before_pp"] = round(grade.gap_pp(s["synthetic"], s["measured"]), 2)
            noise = grade.noise_pp(s["counts"])
            s["noise_pp"] = None if noise is None else round(noise, 2)
        self.save()

    def coach_and_skeptic(self) -> list[dict]:
        """Up to two coach rounds. Returns kept rules (refit on all training stations)."""
        train = self.train()
        rules_out, kept, verdicts = [], [], []
        if self.llm is None:
            self.step("coach", "none", "Skipped: --no-llm run (Turnstile Truth mode, dumb fix only)")
            return []
        from agent import coach
        for round_no in range(1, MAX_COACH_ROUNDS + 1):
            proposed = coach.coach_rules(train, round_no, verdicts)
            self.step("coach", "claude-opus-5-5", f"Round {round_no}: proposed {len(proposed)} rules")
            verdicts = []
            for rule in proposed:
                ev = grade.evaluate_rule(rule, train)
                try:
                    reason = coach.explain_verdict(rule, ev)
                except Exception:  # explanation is cosmetic; the code's own reason is the fallback
                    reason = ev["reason"]
                rec = {
                    "id": f"r{round_no}-{rule['id']}", "text": rule["text"],
                    "status": "kept" if ev["keep"] else "thrown_out", "reason": reason,
                    "stations_holding": ev["stations_improved"], "beats_dumb_fix": ev["beats_dumb_fix"],
                }
                rules_out.append(rec)
                verdicts.append({"rule": rule, "evaluation": ev})
                if ev["keep"]:
                    kept.append(rule)
                self.step("skeptic", "code", f"{rec['status'].upper()}: {rule['text']}", ev["reason"])
            self.run["rules"] = rules_out
            self.save()
            if kept:
                break
        return grade.refit_rules(kept, train)  # sizes fit on ALL training stations; exam never used

    def predict(self, kept):
        if self.llm is None:
            return
        from agent import coach
        bands = coach.predict_bands({s["id"]: s.get("features", {}) for s in self.exam_set()},
                                    kept, self.train())
        for s in self.exam_set():
            if s["id"] in bands:
                s["predicted_error_band_pp"] = bands[s["id"]]
        self.step("predictor", "claude-sonnet-5-5", "Wrote expected error bands for exam stations BEFORE the exam",
                  "ESTIMATE")
        self.save()

    def final_exam(self, kept):
        dumb = grade.dumb_fix(self.train())
        result = grade.exam(self.exam_set(), kept, dumb)
        summary, fields = grade.summarize_exam(result)
        for s in self.exam_set():
            s.update({k: _r2(v) for k, v in fields[s["id"]].items()})
        self.run["summary"] = {k: _r2(v) for k, v in summary.items()}
        hits, total = grade.band_hits(self.exam_set())
        self.run["summary"]["band_hits"], self.run["summary"]["band_total"] = hits, total
        if result["gap_before"] is None:
            raise RuntimeError("No exam station had both synthetic and measured shares")
        verdict = "helped" if result["helped"] else "did NOT help"
        vs_dumb = "beat" if result["gap_after"] < result["gap_dumb"] else "did NOT beat"
        self.step("exam", "code",
                  f"Exam (once): gap {result['gap_before']:.2f} -> {result['gap_after']:.2f} pp; "
                  f"dumb fix {result['gap_dumb']:.2f} pp; coaching {verdict} and {vs_dumb} the dumb fix",
                  "SYNTHETIC vs MEASURED")
        self.save()
        return result

    def trust(self, kept, result):
        if self.llm is None:
            return
        from agent import coach
        sid = self.cfg.get("trust_card_station", self.exam_set()[0]["id"])
        station = next(s for s in self.stations if s["id"] == sid)
        # Expected error at a new station = measured exam error after kept rules (code, not model).
        verdict = trust_verdict(self.run["summary"]["exam_gap_after_pp"])
        self.step("trust", "code", f"Label set by pre-registered cutoffs: {verdict}",
                  f"exam error {self.run['summary']['exam_gap_after_pp']} pp")
        card = coach.trust_card(station, kept, self.run["summary"], verdict=verdict)
        card["verdict"] = verdict  # belt and braces: code's label always wins
        if verdict != "ask_real_people":
            card["draft_question"] = None
        card["note"] = "Stopped for a human. Nothing was bought."
        # What the frontend's "Ask your neighborhood" card replays: the question, the crowd's raw
        # answer (SYNTHETIC) and the answer after kept rules (SYNTHETIC, corrected by code).
        card["question"] = self.cfg["question"]
        card["answer_shares"] = pct(station.get("synthetic"))
        card["corrected"] = pct(grade.apply_rules(station["synthetic"], station.get("features", {}), kept))
        self.run["trust_card"] = card
        self.step("trust", "claude-sonnet-5-5", f"Trust card for {card.get('place', station['name'])}: {card['verdict']}")
        self.save()

    def go(self):
        mode = "live" if self.args.live else "recorded"
        self.run = new_run(self.cfg["question"], self.panel_source, mode)
        if not self.args.no_llm:
            from agent.llm import LLM
            from agent import coach
            self.llm = LLM(max_calls=self.args.max_calls, trace=self.trace)
            coach.set_llm(self.llm)  # one shared client: one call counter, one stop switch
        self.plan()
        self.answer_key()
        self.panels()
        kept = self.coach_and_skeptic()
        self.predict(kept)
        result = self.final_exam(kept)
        self.trust(kept, result)
        self.step("done", "code", f"Run {self.run['run_id']} complete")
        self.save()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the Crowd Coach pipeline.")
    ap.add_argument("--allow-standin", action="store_true", help="fill missing panels with labeled Claude stand-ins")
    ap.add_argument("--no-llm", action="store_true", help="code-only run, no model calls")
    ap.add_argument("--live", action="store_true", help="label this run LIVE (only for a run happening in front of judges)")
    ap.add_argument("--panel-dir", type=Path, default=None, help="folder of <station_id>.json panel files")
    ap.add_argument("--run-dir", type=Path, default=ROOT / "frontend" / "runs",
                    help="where run files go (use a scratch folder for tests)")
    ap.add_argument("--max-calls", type=int, default=60, help="stop switch: maximum model calls")
    args = ap.parse_args(argv)
    try:
        Pipeline(args).go()
    except KeyboardInterrupt:
        sys.exit("Stopped by user.")


if __name__ == "__main__":
    main()
