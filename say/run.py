"""Say vs. Spend: the one command that turns a Flashpoint export into the run file.

Run it from the repo root, in the terminal where ANTHROPIC_API_KEY is set:

    python3 -m say.run --export say/panels/main_export.csv --panel-id <id> --recorded-at <iso>
        [--followup say/panels/followup.json] [--store say/panels/store_run.json]
        [--no-llm] [--run-dir frontend/runs] [--max-calls 30]

Stages (each one prints a trace line; the page file say_latest.json is rewritten after
stages 3 to 7, and say_progress.json after stages 1 and 2):
  1 load brands   2 import CSV   3 compare   4 detective (LLM)   5 trust card (LLM)
  6 store card    7 cost, validate, write

The verdict, all numbers and all ranks come from code. The model only phrases text and
never sees revenue. The API key is read by agent/llm.py from the environment and is never
printed or stored here. Mode is "recorded" unless --live is passed.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from agent.llm import LLM, MODELS, NoKey
from . import compare, detective, flashpoint_import, runfile, trust_text

MIN_BRANDS = 6
NOTE = "Stopped for a human. Nothing was bought."
FLASHPOINT_COST_NOTE = ("Anthropic model calls only (ESTIMATE from list prices). Flashpoint synthetic panels: "
                        "the tool showed no charge (UNVERIFIED). No real respondents were bought.")
DRAFT_NOTE = "Drafted by the agent. Stopped for a human. Nothing was bought."
KEY_HELP = ("ANTHROPIC_API_KEY is not set in this terminal.\n"
            "Run this in your own terminal (the key stays hidden), then run the command again:\n"
            "    read -s ANTHROPIC_API_KEY && export ANTHROPIC_API_KEY\n"
            "Or add --no-llm to run without the model (template text, still a valid run).")
ET = timezone(timedelta(hours=-5))


class Abort(Exception):
    """A clear, human-readable reason to stop. Printed without a traceback."""


class Tracer:
    """Collects trace steps in the run-file shape, prints them, and serves as the LLM trace hook."""

    def __init__(self, echo: bool = True):
        self.steps: list[dict] = []
        self.echo = echo

    def step(self, agent: str, model: str, step: str, detail: str = "") -> dict:
        entry = {"t": datetime.now(ET).replace(microsecond=0).isoformat(), "agent": agent,
                 "model": model, "step": step, "detail": detail}
        self.steps.append(entry)
        if self.echo:
            print(f"[{agent}] {step}" + (f" - {detail}" if detail else ""), flush=True)
        return entry


class _NoKeyTransport:
    """Transport for --no-llm: any call raises NoKey, so every model step falls back to template text."""

    def __call__(self, payload, timeout):
        raise NoKey("model calls are switched off (--no-llm)")


# ---------- helpers ----------

def _read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _public_path(path: str) -> str:
    """Path safe to put in the public run file: relative to the repo, else the bare file name."""
    full = os.path.realpath(path)
    root = os.path.realpath(_REPO_ROOT)
    if full.startswith(root + os.sep):
        return os.path.relpath(full, root)
    return os.path.basename(full)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load_all_brand_files(brands_dir: str) -> list[dict]:
    """Every say/brands/*.json (pass or not). Raises Abort if the folder has none."""
    out = []
    for path in sorted(glob.glob(os.path.join(brands_dir, "*.json"))):
        b = _read_json(path)
        if isinstance(b, dict) and b.get("id") and b.get("name"):
            out.append(b)
    if not out:
        raise Abort(f"No brand files found in {brands_dir}.")
    return out


def _save_progress(run_dir: str, stage: str, tracer: Tracer) -> None:
    os.makedirs(run_dir, exist_ok=True)
    text = json.dumps({"stage": stage, "trace": tracer.steps}, indent=2, ensure_ascii=False)
    runfile._atomic_write(os.path.join(run_dir, "say_progress.json"), text)


def _cost(llm: Optional[LLM]) -> dict:
    if llm is None:
        return {"calls": 0, "estimate_usd": 0.0, "note": "ESTIMATE", "flashpoint_note": FLASHPOINT_COST_NOTE}
    return {"calls": llm.calls, "estimate_usd": llm.cost_usd_estimate(), "note": "ESTIMATE",
            "flashpoint_note": FLASHPOINT_COST_NOTE}


def _save_run(run: dict, tracer: Tracer, llm: Optional[LLM], run_dir: str) -> str:
    run["trace"] = tracer.steps
    run["cost"] = _cost(llm)
    return runfile.write_run(run, run_dir)


def _answers_from_followup(data) -> tuple[list[str], dict[str, list[str]]]:
    """Read the follow-up file. Returns (answers with no brand, {brand_id: answers}).
    Accepts a list of strings, a list of dicts (brand_id + answer/text/response), a dict of
    {brand_id: [answers]}, or {"responses"|"answers": [...]}."""
    ungrouped: list[str] = []
    grouped: dict[str, list[str]] = {}
    if isinstance(data, dict):
        for key in ("responses", "answers"):
            if isinstance(data.get(key), list):
                return _answers_from_followup(data[key])
        for k, v in data.items():
            if isinstance(v, list):
                grouped.setdefault(k, []).extend(str(x) for x in v if str(x).strip())
        return ungrouped, grouped
    for item in data if isinstance(data, list) else []:
        if isinstance(item, str):
            if item.strip():
                ungrouped.append(item)
        elif isinstance(item, dict):
            text = next((item[k] for k in ("answer", "text", "response", "reason") if item.get(k)), None)
            if text is None or not str(text).strip():
                continue
            if item.get("brand_id"):
                grouped.setdefault(item["brand_id"], []).append(str(text))
            else:
                ungrouped.append(str(text))
    return ungrouped, grouped


def _join_lines(lines: list[str]) -> str:
    bare = [l[len(detective.PREFIX):] if l.startswith(detective.PREFIX) else l for l in lines]
    return detective.PREFIX + " ".join(bare)


def _store_stats(store: dict) -> dict:
    """Store stats either given directly or computed from per-respondent rows."""
    if all(store.get(k) is not None for k in ("say_mean", "intent_mean", "aware_share")):
        return {k: store[k] for k in ("say_mean", "intent_mean", "aware_share")}
    rows = [{**r, "brand_id": "store"} for r in store.get("responses", []) if isinstance(r, dict)]
    s = compare.brand_stats(rows).get("store", {})
    return {k: (round(s[k], 4) if s.get(k) is not None else None)
            for k in ("say_mean", "intent_mean", "aware_share")} if s else {}


# ---------- the pipeline ----------

def run_pipeline(args, tracer: Tracer, llm: Optional[LLM]) -> str:
    panels_dir = os.path.dirname(os.path.abspath(args.export))
    panel_out = args.panel_out or os.path.relpath(os.path.join(panels_dir, "main_run.json"))
    question_out = os.path.join(panels_dir, "followup_question.txt")

    # Stage 1: brands
    all_brands = load_all_brand_files(args.brands_dir)
    passing = [b for b in all_brands if b.get("pass") is True]
    for b in all_brands:
        if b.get("pass") is not True:
            why = str(b.get("fail_reason") or "no reason recorded").strip()
            tracer.step("brands", "code", f"dropped {b['id']}", why[:300])
    tracer.step("brands", "code", "loaded brands",
                f"{len(passing)} passed of {len(all_brands)}: {', '.join(b['id'] for b in passing) or 'none'}")
    _save_progress(args.run_dir, "1 brands", tracer)

    # Stage 2: import the Flashpoint CSV (all brand files, so columns of dropped brands still match)
    if not os.path.isfile(args.export):
        raise Abort(f"Export file not found: {args.export}")
    importer_brands = [{"id": b["id"], "name": b["name"], "aliases": b.get("aliases", [])} for b in all_brands]
    meta = {"panel_id": args.panel_id, "recorded_at": args.recorded_at, "source_link": args.source_link,
            "persona_model_note": args.persona_model_note, "order": args.order}
    try:
        panel = flashpoint_import.import_export(args.export, importer_brands, meta)
    except (OSError, ValueError) as e:
        raise Abort(f"Could not read the export: {e}")
    report = flashpoint_import.summarize_import(panel)
    print(report, flush=True)
    unmatched = panel["_import"]["unmatched_columns"]
    if unmatched:
        tracer.step("importer", "code", "stopped: unmatched columns", f"{len(unmatched)} column(s)")
        raise Abort(f"{len(unmatched)} column(s) in the export could not be matched (listed above). "
                    "Fix the brand files or column names, then run again. Nothing was written to the page.")
    if args.expect_n is not None and panel.get("n_personas") != args.expect_n:
        tracer.step("importer", "code", "stopped: wrong persona count", f"{panel.get('n_personas')} != {args.expect_n}")
        raise Abort(f"Export has {panel.get('n_personas')} personas, expected exactly {args.expect_n}.")
    stats = compare.brand_stats(panel["responses"])
    usable = [b for b in passing
              if compare._is_number(b.get("revenue_usd"))
              and all((stats.get(b["id"]) or {}).get(k) is not None
                      for k in ("say_mean", "intent_mean", "aware_share"))]
    if len(usable) < MIN_BRANDS:
        tracer.step("importer", "code", "stopped: too few usable brands", f"{len(usable)} < {MIN_BRANDS}")
        raise Abort(f"Only {len(usable)} usable brands (need at least {MIN_BRANDS}): a brand needs "
                    "pass=true, a revenue number, and say, intent and aware answers in the export.")
    _write_text(panel_out, json.dumps({k: v for k, v in panel.items()}, indent=2, ensure_ascii=False))
    tracer.step("importer", "code", "imported Flashpoint export",
                f"{panel['n_personas']} personas, {len(usable)} usable brands, saved {_public_path(panel_out)}")
    _save_progress(args.run_dir, "2 import", tracer)

    # Stage 3: compare + build the run (never "live" unless --live)
    mode = "live" if args.live else "recorded"
    run = runfile.build_run(passing, {k: v for k, v in panel.items() if k != "_import"},
                            tracer.steps, _cost(llm), mode)
    tracer.steps[:] = run["trace"]  # build_run added its own comparer step
    if len(run["brands"]) < MIN_BRANDS:
        raise Abort(f"Only {len(run['brands'])} brands made it into the comparison (need {MIN_BRANDS}).")
    if tracer.echo:
        print(f"[comparer] {tracer.steps[-1]['detail']}", flush=True)
    path = _save_run(run, tracer, llm, args.run_dir)
    by_id = {b["id"]: b for b in passing}

    # Stage 4: detective
    asked = None
    if run["top_gaps"]:
        asked = detective.draft_followup(run["top_gaps"], passing, llm)
    if asked:
        for g in run["top_gaps"]:
            if g["brand_id"] in asked["brand_ids"]:
                g["followup_question"] = asked["question"]
        _write_text(question_out, asked["question"] + "\n")
        tracer.step("detective", "llm" if llm and not args.no_llm else "code", "drafted follow-up question",
                    f"for a human to send through Flashpoint; saved {_public_path(question_out)}")
    else:
        tracer.step("detective", "code", "no model-drafted follow-up in this pass",
                    ("model off; the follow-up WHY survey was run separately by the follow-up agent "
                     "(see followup_loop)") if args.followup_trace else "model off, no key, call cap hit, or no gaps")
    if args.followup:
        try:
            ungrouped, grouped = _answers_from_followup(_read_json(args.followup))
        except (OSError, ValueError) as e:
            tracer.step("detective", "code", "could not read follow-up answers", str(e)[:200])
            ungrouped, grouped = [], {}
        summarized = 0
        gap_names = ", ".join(by_id[g["brand_id"]]["name"] for g in run["top_gaps"])
        for g in run["top_gaps"]:
            answers = grouped.get(g["brand_id"]) or ungrouped
            brand = by_id[g["brand_id"]] if g["brand_id"] in grouped else {"name": gap_names}
            res = detective.summarize_reasons(answers, brand, llm)
            if res["lines"]:
                g["why_summary"] = _join_lines(res["lines"])
                g["raw_link"] = args.followup
                summarized += 1
        tracer.step("detective", "llm" if llm and not args.no_llm else "code", "summarized follow-up answers",
                    f"{summarized} of {len(run['top_gaps'])} gaps got a summary; raw answers in {_public_path(args.followup)}")
    _save_run(run, tracer, llm, args.run_dir)

    # Stage 5: trust card (verdict stays as code set it)
    tc = run["trust_card"]
    verdict = tc["verdict"]
    chance = run["agreement"]["intent"]["could_be_chance"]
    tc["reason"] = trust_text.trust_sentence(verdict, tc["metric"], tc["rule"], run["crowd_beat_fame"],
                                             chance, llm)
    tc["note"] = NOTE
    if verdict == "ask_real_people" and run["top_gaps"]:
        # The single biggest gap decides the question (no paid real-respondent tool is ever called).
        g = max(run["top_gaps"], key=lambda x: abs(x.get("places_off") or 0))
        b = by_id[g["brand_id"]]
        context = (f"{b['name']} ({b.get('description') or ''}). The AI crowd ranked it "
                   f"#{g.get('crowd_rank')} on {g.get('question')}, but it is #{g.get('revenue_rank')} "
                   f"by actual yearly sales among {run['agreement']['n_brands']} brands.")
        fallback = f"In the past 12 months, have you bought anything from {b['name']}'s website?"
        tc["draft_question"] = trust_text.real_survey_question(verdict, context, llm, fallback=fallback)
        tc["draft_question_source"] = ("code template (no model call)" if tc["draft_question"] == fallback
                                       else f"model ({MODELS['hard']}), AI-generated")
        tc["draft_question_brand"] = g["brand_id"]
        if tc["draft_question"]:
            # Honest note: "agent" only when a model actually wrote the question.
            tc["note"] = (DRAFT_NOTE if tc["draft_question"] != fallback
                          else "Drafted by our code from the biggest miss. Stopped for a human. Nothing was bought.")
    tracer.step("trust", "llm" if llm and not args.no_llm else "code", "trust card filled",
                f"verdict {verdict} set by code")
    _save_run(run, tracer, llm, args.run_dir)

    # Stage 6: optional store block
    if args.store:
        try:
            store = _read_json(args.store)
            stats6 = _store_stats(store)
            if not store.get("name") or not stats6 or any(v is None for v in stats6.values()):
                raise ValueError("store file needs a name and say/intent/aware answers")
            run["store"] = trust_text.store_card(store["name"], store.get("description"), stats6, verdict)
            tracer.step("store", "code", "store card added", f"{store['name']} (FICTIONAL DEMO STORE)")
        except (OSError, ValueError) as e:
            tracer.step("store", "code", "store card skipped", str(e)[:200])
        _save_run(run, tracer, llm, args.run_dir)

    # Stage 6b: repeat run (second independent panel, same brands) and independent Wikipedia fame
    if args.repeat_export:
        try:
            from say import repeat
            run["repeat_run"] = repeat.repeat_block(run, args.repeat_export, args.brands_dir,
                                                    panel_id=args.repeat_panel_id, recorded_at=args.repeat_recorded_at)
            tracer.step("repeat", "code", "repeat run compared",
                        f"panel {args.repeat_panel_id}: {run['repeat_run'].get('n_personas')} personas")
        except Exception as e:  # optional extra: never sinks the main run
            tracer.step("repeat", "code", "repeat run skipped", str(e)[:200])
    if args.followup_trace:
        try:
            steps = _read_json(args.followup_trace)
            last = steps[-1] if steps else {}
            run["followup_loop"] = {
                "label": "SYNTHETIC",
                "what": "Agent loop: biggest gaps -> follow-up WHY question -> new small synthetic Flashpoint panel -> raw answers.",
                "survey_id": last.get("survey_id"), "panel_id": last.get("panel_id"),
                "run_id": last.get("run_id"), "n_personas": last.get("n"),
                "raw_answers": args.followup, "trace": steps,
                "question_source": ("WHY question text written by Claude (the building agent) for the follow-up "
                                    "survey; AI-generated. Answers are SYNTHETIC personas, verbatim."),
                "note": "Synthetic personas only. Nothing was bought; no real respondents.",
            }
            tracer.step("detective", "code", "follow-up loop attached",
                        f"{len(steps)} steps, panel {last.get('panel_id')}, n={last.get('n')}")
        except (OSError, ValueError, AttributeError, IndexError) as e:
            tracer.step("detective", "code", "follow-up loop skipped", str(e)[:200])
    if args.wiki_fame:
        try:
            from say.fame import wiki
            run["fame_wiki"] = wiki.fame_block(run, args.wiki_fame)
            run["fame_wiki"]["caveats"] = [
                "Counts views of the exact article title only (not redirects), so each is a floor, not a total.",
                "Revolve has no English Wikipedia article, so this line uses 5 brands.",
                "BARK uses the 'BarkBox' article (the company's old name 'Bark & Co.' redirects there).",
                "EXPLORATORY: added at 12:24 ET after the main result was seen."]
            tracer.step("fame", "code", "Wikipedia fame compared", args.wiki_fame)
        except Exception as e:
            tracer.step("fame", "code", "Wikipedia fame skipped", str(e)[:200])
    run["agreement"]["label"] = "SYNTHETIC crowd ranking vs MEASURED revenue ranking (Spearman)"
    if run.get("agreement_buyers"):
        run["agreement_buyers"]["label"] = "SYNTHETIC (buyers only, EXPLORATORY) vs MEASURED revenue"
    for g in run.get("top_gaps", []):
        g.setdefault("labels", {"crowd_rank": "SYNTHETIC", "revenue_rank": "MEASURED"})
        if args.followup and not g.get("raw_link"):
            g["raw_link"] = args.followup
    run["trust_card"]["metric_label"] = "SYNTHETIC crowd vs MEASURED revenue"
    if args.extras:
        try:
            from say import extras
            all_ids = [b["id"] for b in all_brands]
            main_ids = [b["id"] for b in run["brands"]]
            resp = panel["responses"]
            ex = {"label": "EXPLORATORY (not pre-registered)"}
            ex["sensitivity"] = extras.sensitivity_view(run, resp, args.brands_dir)
            ex["order_effect"] = extras.order_effect(args.export, all_ids)
            ex["compression"] = extras.compression(resp, brand_ids=main_ids)
            if args.repeat_export:
                rep_panel = flashpoint_import.import_export(args.repeat_export, importer_brands, {})
                rev = {b["id"]: b["revenue_usd"] for b in run["brands"]}
                ex["crowd_vs_crowd"] = extras.crowd_vs_crowd(resp, rep_panel["responses"], main_ids, rev)
            run["extras"] = ex
            tracer.step("extras", "code", "exploratory checks added",
                        "sensitivity (8 brands), order effect, compression, crowd vs crowd")
        except Exception as e:
            tracer.step("extras", "code", "exploratory checks skipped", str(e)[:200])
    _save_run(run, tracer, llm, args.run_dir)

    # Stage 7: cost, validate, write
    tracer.step("run", "code", "run file written",
                f"{llm.calls if llm else 0} model calls, about ${_cost(llm)['estimate_usd']} (ESTIMATE)")
    path = _save_run(run, tracer, llm, args.run_dir)
    print("\n" + runfile.headline_text(run))
    print(f"\nWrote {path} and {os.path.join(args.run_dir, 'say_latest.json')}")
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python3 -m say.run",
                                description="Flashpoint export -> compared, checked Say vs. Spend run file.")
    p.add_argument("--export", required=True, help="the Flashpoint raw CSV export")
    p.add_argument("--panel-id", required=True)
    p.add_argument("--recorded-at", required=True, help="ISO time the panel was run, e.g. 2026-11-14T12:55:00-05:00")
    p.add_argument("--followup", help="JSON of the crowd's WHY answers (optional)")
    p.add_argument("--store", help="JSON of the fictional demo store's answers (optional)")
    p.add_argument("--no-llm", action="store_true", help="no model calls; template text only")
    p.add_argument("--run-dir", default="frontend/runs")
    p.add_argument("--max-calls", type=int, default=30, help="hard cap on model calls")
    p.add_argument("--brands-dir", default="say/brands")
    p.add_argument("--panel-out", help="where to save the normalized panel (default: main_run.json next to the export)")
    p.add_argument("--source-link")
    p.add_argument("--persona-model-note")
    p.add_argument("--order", default="shuffled", choices=["shuffled", "fixed"])
    p.add_argument("--expect-n", type=int, help="abort unless the export has exactly this many personas")
    p.add_argument("--repeat-export", help="second independent panel's CSV (shown as repeat_run)")
    p.add_argument("--repeat-panel-id")
    p.add_argument("--repeat-recorded-at")
    p.add_argument("--extras", action="store_true", help="add EXPLORATORY checks (sensitivity, order, compression, crowd vs crowd)")
    p.add_argument("--followup-trace", help="say/panels/followup_trace.json from the follow-up panel loop")
    p.add_argument("--wiki-fame", help="say/fame/wikipedia_pageviews.json (independent fame line)")
    p.add_argument("--live", action="store_true", help='mark the run mode "live" (default is "recorded")')
    return p


def main(argv: Optional[list[str]] = None, transport=None) -> int:
    """transport: tests inject a fake model transport; real runs leave it None."""
    args = build_parser().parse_args(argv)
    try:
        datetime.fromisoformat(args.recorded_at)
    except ValueError:
        print("ERROR: --recorded-at must be an ISO time like 2026-11-14T12:55:00-05:00", file=sys.stderr)
        return 2
    if not args.no_llm and transport is None and not os.environ.get("ANTHROPIC_API_KEY"):
        print(KEY_HELP, file=sys.stderr)
        return 2
    tracer = Tracer()
    llm = LLM(max_calls=args.max_calls, trace=tracer,
              transport=_NoKeyTransport() if args.no_llm else transport)
    if args.no_llm:
        llm.max_calls = 0  # belt and braces: no call can be made; steps fall back to template text
    try:
        run_pipeline(args, tracer, llm)
    except Abort as e:
        print(f"\nSTOPPED: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"\nSTOPPED: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
