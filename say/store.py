"""Try your store: rate ONE fictional store with the same Flashpoint panel, then place it
next to the brands. Standard library only. This module never calls Flashpoint or any network.

The store is NEVER a real business. It must carry the label "FICTIONAL DEMO STORE".
Its trust level is the brand test's verdict; there is no answer key (no revenue) for it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Iterable, Optional

from say import compare, runfile, trust_text

DEFAULT_STORE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "demo_store.json")
PLACEMENT_LABEL = "SYNTHETIC"
PLACEMENT_CAVEAT = (
    "Placement is where the AI crowd would put this store among the brands. It is SYNTHETIC "
    "(AI-generated opinions), not sales, and says nothing about real revenue. "
    + trust_text.STORE_NOTE
)
_FIELDS = (("say", "say_mean"), ("intent", "intent_mean"), ("fame", "aware_share"))


def load_store(path: str = DEFAULT_STORE_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return check_store(json.load(f))


def check_store(store: dict) -> dict:
    """Refuse a store that is not clearly the fictional demo store."""
    if not isinstance(store, dict):
        raise ValueError("store must be a JSON object")
    if store.get("label") != trust_text.STORE_LABEL:
        raise ValueError(f"store label must be exactly {trust_text.STORE_LABEL!r}; refusing to use it")
    for k in ("id", "name", "description"):
        if not isinstance(store.get(k), str) or not store[k].strip():
            raise ValueError(f"store is missing '{k}'")
    return store


def flashpoint_brief(store: dict) -> str:
    """The exact brief Claude sends to Flashpoint's tool_survey. Text only."""
    check_store(store)
    q = runfile.QUESTIONS_BLOCK
    return (
        "Create a DRAFT survey with ONE looped item. Do not publish it, do not recruit anyone, "
        "and take no paid steps. Draft only.\n"
        f"Loop key (use exactly this id as the item key): {store['id']}\n"
        # The FICTIONAL label is for our screen only; telling respondents would bias their answers.
        f"Item shown to each respondent: {store['name']} - {store['description']}\n"
        "Ask exactly these three questions about the item, in this order:\n"
        f"1. SAY: {q['say']['text']} (scale 1-10, 1 = worst, 10 = best)\n"
        f"2. INTENT: {q['intent']['text']} (scale 1-10, 1 = not at all likely, 10 = extremely likely)\n"
        f"3. AWARE: {q['aware']['text']} (Yes / No)\n"
        "Use the same wording and scales as the existing brand survey. Do not add other questions. "
        "Reply with the draft survey link or id only; do not publish, recruit, or pay."
    )


def store_stats(panel_responses: Iterable[dict], store_id: str) -> dict:
    """Averages for the store from raw per-respondent rows (code arithmetic)."""
    rows = [r for r in panel_responses if r.get("brand_id") == store_id]
    s = compare.brand_stats(rows).get(store_id)
    if s is None:
        return {"say_mean": None, "intent_mean": None, "aware_share": None, "n": 0}
    return {"say_mean": s["say_mean"], "intent_mean": s["intent_mean"],
            "aware_share": s["aware_share"], "n": len({r.get("persona_id") for r in rows}) or len(rows)}


def placement(stats: dict, brand_rows: list[dict]) -> dict:
    """Where the store would sit among the brands on each ladder (1 = best, ties share the
    average place). Brands missing a value are left out of that ladder."""
    out: dict = {"label": PLACEMENT_LABEL, "caveat": PLACEMENT_CAVEAT}
    for name, field in _FIELDS:
        v = stats.get(field)
        if not compare._is_number(v):
            out[name] = None
            continue
        others = [(b.get("name") or b.get("id"), b[field]) for b in brand_rows
                  if compare._is_number(b.get(field))]
        vals = [x[1] for x in others] + [float(v)]
        rank = compare.ranks(vals)[-1]
        out[name] = {"rank": rank, "of": len(vals),
                     "tied_with": [n for n, x in others if x == v],
                     "metric": field, "value": v}
    return out


def build_store_block(store: dict, stats: dict, verdict: str, brand_rows: Optional[list[dict]] = None) -> dict:
    check_store(store)
    if verdict not in trust_text.VERDICTS:
        raise ValueError(f"unknown verdict: {verdict!r}")
    block = trust_text.store_card(store["name"], store["description"], stats, verdict)
    block["n"] = stats.get("n")
    block["placement"] = placement(stats, brand_rows or [])
    return block


def add_to_run(run: dict, store: dict, panel: dict) -> dict:
    stats = store_stats(panel.get("responses", []), store["id"])
    if not stats["n"]:
        raise ValueError(f"no responses found for store id {store['id']!r} in the export")
    new = dict(run)
    new["store"] = build_store_block(store, stats, run["trust_card"]["verdict"], run["brands"])
    errs = runfile.validate_run(new)
    if errs:
        raise ValueError("run file invalid after adding store: " + "; ".join(errs))
    return new


def main(argv: Optional[list[str]] = None) -> int:
    from say import flashpoint_import as fi
    ap = argparse.ArgumentParser(prog="python3 -m say.store")
    ap.add_argument("--store", default=DEFAULT_STORE_PATH)
    ap.add_argument("--brief", action="store_true", help="print the Flashpoint brief")
    ap.add_argument("--export", help="Flashpoint CSV export containing the store's answers")
    ap.add_argument("--run", help="existing run file to add the store block to")
    ap.add_argument("--question-map", default="Q1=say,Q2=intent,Q3=aware",
                    help="export question ids, default Q1=say,Q2=intent,Q3=aware")
    a = ap.parse_args(argv)
    try:
        store = load_store(a.store)
        if a.brief:
            print(flashpoint_brief(store))
            return 0
        if not (a.export and a.run):
            ap.error("give --brief, or both --export and --run")
        with open(a.run, encoding="utf-8") as f:
            run = json.load(f)
        panel = fi.import_export(a.export, [{"id": store["id"], "name": store["name"]}],
                                 loop_key_map={store["name"]: store["id"]},
                                 question_map=fi._parse_pairs(a.question_map.split(","), "--question-map"))
        new = add_to_run(run, store, panel)
        runfile._atomic_write(a.run, json.dumps(new, indent=2, ensure_ascii=False))
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(f"Added store block to {a.run}: {json.dumps(new['store']['placement']['intent'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
