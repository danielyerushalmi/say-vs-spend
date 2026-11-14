# Agent pipeline contract (read before writing any code in agent/)

Python 3.14, **standard library only** (no pip installs). Run from the repo root: `python3 -m agent.run`.
Public repo: no keys, tokens or personal info in any file. The Anthropic key is read from `ANTHROPIC_API_KEY` only.
All arithmetic happens in code, never in a model. Every number carries a label: `SYNTHETIC`, `MEASURED` or `ESTIMATE`.

## Files and owners

| File | Owner | Purpose |
|---|---|---|
| `agent/config/stations.json` | done | 12 stations, question, date window, locked train/exam split |
| `agent/mta.py` | builder A | MTA answer-key puller with file cache |
| `agent/audit.py` | builder A | Auditor: data checks on the answer key, re-pull if needed |
| `agent/grade.py` | builder B | All math: shares, gaps, rules engine, dumb fix, leave-one-out, exam |
| `agent/llm.py` | builder C | Tiny Anthropic Messages API client (urllib), call counter, cost, stop switch |
| `agent/coach.py` | builder C | Coach, Skeptic-explainer, Predictor, Trust card prompts |
| `agent/standin.py` | builder C | Fallback panel made by Claude when no Flashpoint file exists |
| `agent/trace.py` | builder B | Trace log + run-file writer |
| `agent/run.py` | integrator (lead) | Orchestrator |
| `agent/tests/test_*.py` | each builder, own module | `python3 -m unittest discover agent/tests` |

## Shared types (plain dicts)

```
DAYS = ["Mon","Tue","Wed","Thu","Fri"]
Shares = {"Mon": float, ..., "Fri": float}   # fractions, sum to 1.0 (±1e-9)
```

Station record (built by run.py, passed around):
```
{"id": "41", "name": "...", "borough": "...", "split": "train"|"exam",
 "lat": float|None, "lon": float|None,
 "features": {"borough": "Brooklyn", ...numbers from Flashpoint demographics if any...},
 "synthetic": Shares|None, "measured": Shares|None,
 "sources": {"synthetic": str, "measured": str}}
```
`tier` in stations.json was computed FROM the answer key. It must NEVER be a rule feature (that would leak the answers).

## mta.py

```
fetch_measured(station_ids: list[str], window: dict, exclude_dates: list[str] = []) -> dict[str, dict]
  returns {station_id: {"shares": Shares, "totals": {"Mon": int,...}, "day_counts": {"Mon": int,...},
                        "lat": float, "lon": float, "name": str, "borough": str, "query_url": str}}
fetch_daily(station_ids, window) -> dict[str, dict[str, int]]   # {station_id: {"2026-10-05": entries_6_to_10, ...}} for the auditor
```
One grouped SoQL request to `https://data.ny.gov/resource/5wq4-mkjj.json` (no key). Window hours: `hour_from <= hh < hour_to`.
Cache raw responses under `agent/data/mta/` keyed by a hash of the query; reuse the cache when present. Timeout 60 s, 2 retries.
`query_url` is the full clickable request URL (that is the source link shown to judges).

## audit.py

```
audit(station_ids, window, daily: dict) -> {"exclude_dates": [...], "findings": [{"station_id": str|"all", "finding": str, "action": str}]}
```
Code checks: federal/NY holidays inside the window (Columbus Day 2026-10-12 is in it), missing days, unequal count of each weekday,
days far below the station's median for that weekday (e.g. < 60%). Report ONLY real catches backed by the numbers; if Oct 12 is not low, say it
was checked and kept. Never invent a finding.

## grade.py

```
normalize(counts: dict) -> Shares                      # from panel counts (ignore "None")
gap_pp(a: Shares, b: Shares) -> float                  # mean absolute difference over 5 days, in percentage points
Rule = {"id": str, "text": str, "when": {"feature": str, "op": "==|!=|>|<|>=|<=", "value": any} | None,
        "adjust": {"Mon": float_pp, ..., "Fri": float_pp}}   # adds pp to synthetic shares, then clip at 0 and renormalize
apply_rules(synth: Shares, features: dict, rules: list[Rule]) -> Shares
dumb_fix(train: list[station]) -> Rule                 # adjust = mean (measured - synthetic) per day over train, when=None
evaluate_rule(rule, train) -> {"stations_matching": int, "stations_improved": int, "loo_gap": float, "loo_gap_dumb": float,
                               "beats_dumb_fix": bool, "keep": bool, "reason": str}
   # The coach writes the CONDITION ("when") and the direction; code fits the size:
   #   fit_adjust(rule, stations) = per-day mean (measured - synthetic) over stations matching "when" (all stations if when=None).
   # Leave-one-out (LOO): for each training station i, fit the rule's adjust on the other training stations, apply to i
   #   (only changes i if i matches), and record gap at i. Same for the dumb fix. loo_gap / loo_gap_dumb = mean over i.
   # stations_improved = training stations where the LOO gap with the rule < gap with no correction.
   # keep = stations_matching >= 3 AND stations_improved >= 3 AND loo_gap < loo_gap_dumb. reason = plain sentence with those numbers.
   # The final kept rules are refit on ALL training stations before the exam. Exam stations are never used for fitting.
exam(exam_stations, kept_rules, dumb_rule) -> {"per_station": [...], "gap_before": float, "gap_after": float, "gap_dumb": float, "helped": bool}
```
Exam runs ONCE per run; it must refuse a second call in the same process (raise).

## llm.py

```
class LLM: __init__(max_calls=60, max_parallel=8, timeout=120); call(model, system, user, max_tokens=1500, json_mode=False) -> str | dict
   .calls, .input_tokens, .output_tokens, .cost_usd_estimate()   # price table in one dict, labeled ESTIMATE
   raises StopSwitch when max_calls reached. If ANTHROPIC_API_KEY is missing: raise NoKey (callers fall back).
MODELS = {"bulk": "claude-haiku-5-5", "hard": "claude-sonnet-5-5", "coach": "claude-opus-5-5"}
```
POST https://api.anthropic.com/v1/messages, headers x-api-key, anthropic-version: 2023-06-01. json_mode = ask for JSON only, then parse
the first {...} block; one repair retry on bad JSON. Never log the key.

## coach.py

```
coach_rules(train_stations, round_no, previous_verdicts) -> list[Rule]   # Opus, falls back to Sonnet on error
explain_verdict(rule, evaluation) -> str                                 # Sonnet, one plain sentence; numbers come from evaluation only
predict_bands(exam_station_features, kept_rules, train_evidence) -> {station_id: [low_pp, high_pp]}
trust_card(station, kept_rules, evaluation_summary) -> {"place","station_id","verdict":"trust|verify|ask_real_people","draft_question","note"}
```
Models see numbers produced by code; they never compute new ones (except the predicted band, which is labeled ESTIMATE).

## standin.py

```
standin_panel(station, question, n=40) -> {"counts": {...}, "panel_id": "claude-standin", "source_link": "", "note": "Claude stand-in, not Flashpoint, not census-grounded"}
```

## Panel input (from Daniel, Flashpoint)

`data/panels/<station_id>.json` = `{"station_id","panel_id","source_link","recorded_at","n","counts":{"Mon".."Fri","None"},"demographics":{...},"fit_score":null,"raw":{...}}`

## trace.py

```
Trace(run_dir="frontend/runs"): .step(agent, model, step, detail="") ; .write(run_dict)  # writes frontend/runs/<run_id>.json and latest.json atomically
```
Run file shape: `docs/FRONTEND.md` → "Data contract". Follow it exactly.
