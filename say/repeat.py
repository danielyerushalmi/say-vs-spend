"""Repeat-panel block for the run file's `repeat_run` field. Standard library only.

A second, independent synthetic panel answers the same questions. We rank the same brands
the same way as the main run and report how much the two crowds agree with each other.
All numbers come from compare.py (code, never an LLM). Label: SYNTHETIC.

CLI: python3 -m say.repeat --run frontend/runs/say_latest.json --export say/panels/main_export.csv --out <path>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Optional

from . import compare, flashpoint_import

NOTE = "Two panels of 200 different AI personas from the same persona model (gpt-5.4-mini); same questions (main panel also had a 4th question)."
CROWD_FIELDS = ("say_mean", "intent_mean", "aware_share")


def _r(v, digits: int = 4):
    return None if v is None else round(v, digits)


def _rk(v: float):
    return int(v) if float(v).is_integer() else round(v, 2)


def _round_agreement(a: dict) -> dict:
    return {k: (_r(a.get(k)) if k in ("spearman", "wobble_low", "wobble_high", "avg_places_off", "p_exact") else a.get(k))
            for k in ("spearman", "wobble_low", "wobble_high", "could_be_chance", "avg_places_off", "p_exact")}


def _brand_files(brands_dir: str) -> dict:
    out = {}
    for path in sorted(glob.glob(os.path.join(brands_dir, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                b = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(b, dict) and b.get("id"):
            out[b["id"]] = b
    return out


def repeat_block(main_run: dict, repeat_export_csv: str, brands_dir: str = "say/brands",
                 panel_id: Optional[str] = None, recorded_at: Optional[str] = None,
                 n_boot: int = 2000, seed: int = compare.DEFAULT_SEED) -> dict:
    main_brands = main_run["brands"]
    files = _brand_files(brands_dir) if brands_dir and os.path.isdir(brands_dir) else {}
    # Only the main run's brand set; brand files (if found) add aliases for CSV matching.
    matcher_brands = [{**files.get(b["id"], {}), "id": b["id"], "name": b.get("name") or files.get(b["id"], {}).get("name") or b["id"]}
                      for b in main_brands]
    panel = flashpoint_import.import_export(
        repeat_export_csv, matcher_brands, {"panel_id": panel_id, "recorded_at": recorded_at})
    stats = compare.brand_stats(panel["responses"])

    rows, left_out = [], []
    for b in main_brands:
        s = stats.get(b["id"], {})
        if any(s.get(k) is None for k in CROWD_FIELDS) or not compare._is_number(b.get("revenue_usd")) \
                or not compare._is_number(b.get("intent_mean")):
            left_out.append(b["id"])
            continue
        rows.append({"id": b["id"], "revenue_usd": b["revenue_usd"],
                     **{k: s[k] for k in CROWD_FIELDS},
                     "main_say": b.get("say_mean"), "main_intent": b["intent_mean"],
                     "main_fame": b.get("aware_share")})

    ranks_rep = {}
    for q, field in compare.QUESTION_FIELD.items():
        ranks_rep[q] = compare.ranks([r[field] for r in rows]) if rows else []
        for r, v in zip(rows, ranks_rep[q]):
            r[f"rank_{q}"] = v
    # Main-panel ranks over the SAME (common) brands, so a left-out brand cannot distort the comparison.
    main_ranks = {}
    for q, key in (("say", "main_say"), ("intent", "main_intent"), ("fame", "main_fame")):
        vals = [r[key] for r in rows]
        main_ranks[q] = compare.ranks(vals) if rows and all(compare._is_number(v) for v in vals) else None

    agree = {q: compare.agreement(rows, q, n_boot=n_boot, seed=seed) for q in compare.QUESTIONS}
    verdict = compare.trust_verdict(agree["intent"]["spearman"], agree["intent"]["wobble_low"],
                                    agree["intent"]["wobble_high"])

    def between(q):
        if main_ranks[q] is None:
            return None
        return _r(compare.spearman(main_ranks[q], ranks_rep[q]))

    moves = []
    if main_ranks["intent"] is not None:
        for r, mr in zip(rows, main_ranks["intent"]):
            moves.append({"id": r["id"], "rank_intent_main": _rk(mr), "rank_intent_repeat": _rk(r["rank_intent"]),
                          "move": _rk(abs(mr - r["rank_intent"]))})
        moves.sort(key=lambda m: (-m["move"], m["id"]))

    out = {
        "panel_id": panel.get("panel_id"),
        "recorded_at": recorded_at,
        "n_personas": panel.get("n_personas"),
        "label": "SYNTHETIC",
        "brands": [{"id": r["id"], "say_mean": _r(r["say_mean"]), "intent_mean": _r(r["intent_mean"]),
                    "aware_share": _r(r["aware_share"]), "rank_say": _rk(r["rank_say"]),
                    "rank_intent": _rk(r["rank_intent"]), "rank_fame": _rk(r["rank_fame"])} for r in rows],
        "agreement": {q: _round_agreement(agree[q]) for q in compare.QUESTIONS},
        "verdict_if_main": verdict,
        "stability": {
            "intent_rank_spearman_between_panels": between("intent"),
            "say_rank_spearman_between_panels": between("say"),
            "fame_rank_spearman_between_panels": between("fame"),
            "max_rank_move": max((m["move"] for m in moves), default=None),
            "moves": moves,
            "note": NOTE,
        },
        "brands_left_out": left_out,
    }
    return out


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Build the repeat_run block from a second panel export.")
    ap.add_argument("--run", required=True, help="main run file (JSON)")
    ap.add_argument("--export", required=True, help="repeat panel Flashpoint CSV")
    ap.add_argument("--out", required=True, help="where to write the block (JSON)")
    ap.add_argument("--brands-dir", default="say/brands")
    ap.add_argument("--panel-id", default=None)
    ap.add_argument("--recorded-at", default=None)
    a = ap.parse_args(argv)
    with open(a.run, encoding="utf-8") as f:
        run = json.load(f)
    block = repeat_block(run, a.export, a.brands_dir, a.panel_id, a.recorded_at)
    text = json.dumps(block, indent=2, ensure_ascii=False)
    print(text)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
