"""Trace log and run-file writer. The run file shape is defined in docs/FRONTEND.md (Data contract)."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

ET = timezone(timedelta(hours=-5))  # New York in November (EST); the contract uses a -05:00 offset
MODES = {"recorded", "live", "sample"}
PANEL_SOURCES = {"flashpoint", "claude_standin"}
SPLITS = {"train", "exam"}
VERDICTS = {"trust", "verify", "ask_real_people"}
RULE_STATUSES = {"kept", "thrown_out"}
TOP_LEVEL = ["run_id", "mode", "recorded_at", "question", "panel_source", "stations", "rules",
             "audit", "summary", "trust_card", "cost", "trace"]
STATION_KEYS = ["id", "name", "borough", "lat", "lon", "split", "synthetic_shares", "measured_shares",
                "gap_before_pp", "gap_after_pp", "gap_dumbfix_pp", "predicted_error_band_pp",
                "fit_score", "sources"]
RULE_KEYS = ["id", "text", "status", "reason", "stations_holding", "beats_dumb_fix"]
SUMMARY_KEYS = ["exam_gap_before_pp", "exam_gap_after_pp", "exam_gap_dumbfix_pp", "coaching_helped"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def _now() -> datetime:
    return datetime.now(ET).replace(microsecond=0)


class Trace:
    """Collects agent steps and writes the run file."""

    def __init__(self, run_dir: str = "frontend/runs") -> None:
        self.run_dir = run_dir
        self.steps: list[dict] = []

    def step(self, agent: str, model: str, step: str, detail: str = "") -> dict:
        """Append one trace entry and return it."""
        entry = {"t": _now().isoformat(), "agent": agent, "model": model, "step": step, "detail": detail}
        self.steps.append(entry)
        return entry

    def write(self, run: dict) -> str:
        """Atomically write <run_dir>/<run_id>.json and latest.json. Returns the run file path."""
        os.makedirs(self.run_dir, exist_ok=True)
        text = json.dumps(run, indent=2, ensure_ascii=False)
        path = os.path.join(self.run_dir, f"{run['run_id']}.json")
        for target in (path, os.path.join(self.run_dir, "latest.json")):
            self._atomic_write(target, text)
        return path

    def _atomic_write(self, target: str, text: str) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.run_dir, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, target)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def new_run(question: str, panel_source: str, mode: str) -> dict:
    """Empty run dict with every top-level key from docs/FRONTEND.md present."""
    now = _now()
    return {
        "run_id": now.strftime("%Y-%m-%dT%H-%M"),
        "mode": mode,
        "recorded_at": now.isoformat(),
        "question": question,
        "panel_source": panel_source,
        "stations": [],
        "rules": [],
        "audit": [],
        "summary": {"exam_gap_before_pp": None, "exam_gap_after_pp": None,
                    "exam_gap_dumbfix_pp": None, "coaching_helped": False},
        "trust_card": None,
        "cost": {"calls": 0, "estimate_usd": 0.0},
        "trace": [],
    }


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _shares_ok(s) -> bool:
    return s is None or (isinstance(s, dict) and all(_num(s.get(d)) for d in DAYS))


def validate_run(run: dict) -> list[str]:
    """Return a list of problems (empty list means the run is valid)."""
    errs: list[str] = []
    if not isinstance(run, dict):
        return ["run is not a dict"]
    for k in TOP_LEVEL:
        if k not in run:
            errs.append(f"missing top-level key: {k}")
    if errs:
        return errs
    if not isinstance(run["run_id"], str) or not run["run_id"]:
        errs.append("run_id must be a non-empty string")
    if run["mode"] not in MODES:
        errs.append(f"mode must be one of {sorted(MODES)}, got {run['mode']!r}")
    if run["panel_source"] not in PANEL_SOURCES:
        errs.append(f"panel_source must be one of {sorted(PANEL_SOURCES)}, got {run['panel_source']!r}")
    for k in ("question", "recorded_at"):
        if not isinstance(run[k], str):
            errs.append(f"{k} must be a string")
    for k in ("stations", "rules", "audit", "trace"):
        if not isinstance(run[k], list):
            errs.append(f"{k} must be a list")
    if errs:
        return errs
    for i, st in enumerate(run["stations"]):
        for k in STATION_KEYS:
            if k not in st:
                errs.append(f"stations[{i}] missing {k}")
        if st.get("split") not in SPLITS:
            errs.append(f"stations[{i}].split must be train or exam, got {st.get('split')!r}")
        for k in ("synthetic_shares", "measured_shares"):
            if k in st and not _shares_ok(st[k]):
                errs.append(f"stations[{i}].{k} must have numeric Mon-Fri")
        for k in ("gap_before_pp", "gap_after_pp", "gap_dumbfix_pp"):
            if st.get(k) is not None and not _num(st[k]):
                errs.append(f"stations[{i}].{k} must be a number or null")
        band = st.get("predicted_error_band_pp")
        if band is not None and not (isinstance(band, list) and len(band) == 2 and all(_num(b) for b in band)):
            errs.append(f"stations[{i}].predicted_error_band_pp must be [low, high] or null")
    for i, r in enumerate(run["rules"]):
        for k in RULE_KEYS:
            if k not in r:
                errs.append(f"rules[{i}] missing {k}")
        if r.get("status") not in RULE_STATUSES:
            errs.append(f"rules[{i}].status must be kept or thrown_out, got {r.get('status')!r}")
    summary = run["summary"]
    if not isinstance(summary, dict):
        errs.append("summary must be a dict")
    else:
        for k in SUMMARY_KEYS:
            if k not in summary:
                errs.append(f"summary missing {k}")
        if "coaching_helped" in summary and not isinstance(summary["coaching_helped"], bool):
            errs.append("summary.coaching_helped must be a bool")
    tc = run["trust_card"]
    if tc is not None:
        if not isinstance(tc, dict):
            errs.append("trust_card must be a dict or null")
        elif tc.get("verdict") is not None and tc["verdict"] not in VERDICTS:
            errs.append(f"trust_card.verdict must be one of {sorted(VERDICTS)} or null, got {tc['verdict']!r}")
    cost = run["cost"]
    if not (isinstance(cost, dict) and isinstance(cost.get("calls"), int) and _num(cost.get("estimate_usd"))):
        errs.append("cost must have int calls and numeric estimate_usd")
    for i, t in enumerate(run["trace"]):
        for k in ("t", "agent", "model", "step", "detail"):
            if k not in t:
                errs.append(f"trace[{i}] missing {k}")
    return errs
