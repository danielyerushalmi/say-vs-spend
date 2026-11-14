"""Build, check and write the Say vs. Spend run file (shape: docs/SAY-VS-SPEND.md).

Input panel file (say/panels/main_run.json), the normalized shape the Flashpoint export is
converted into. One row per persona x brand; any value may be missing and is then skipped:

    {"panel_id": "...", "source_link": "...", "recorded_at": "2026-11-14T12:55:00-05:00",
     "n_personas": 200, "persona_model_note": "...", "order": "shuffled" | "fixed",
     "responses": [{"persona_id": "P-001", "brand_id": "figs", "say": 1-10, "intent": 1-10,
                    "aware": true | false, "age_group": "optional", "income_group": "optional"}]}

Input brand files (say/brands/<id>.json): id, name, description, pass, revenue_usd,
fiscal_year, filing_url, online_note, label. Only pass == true is used.

CLI:  python3 -m say.runfile --panel say/panels/main_run.json --brands-dir say/brands --run-dir frontend/runs
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import compare

ET = timezone(timedelta(hours=-5))  # New York in November (EST), as in the contract
MODES = {"recorded", "live", "sample"}
VERDICTS = {"trust", "verify", "ask_real_people"}
VERDICT_WORDS = {"trust": "Trust it", "verify": "Double-check it", "ask_real_people": "Ask real people"}

QUESTIONS_BLOCK = {
    # Exact wording of Flashpoint survey 46608e7a-d27b-4419-ac80-33e08abbb39c (as built 2026-11-14).
    "say": {"text": "How good do you think this brand's website is? (1 to 10)", "scale": "1-10"},
    "intent": {"text": "How likely are you to buy from this website in the next 12 months? (1 to 10)", "scale": "1-10"},
    "aware": {"text": "Before today, had you heard of this brand?", "scale": "yes/no"},
}
BUY_QUESTION = {"text": "Is this a kind of product you buy?", "scale": "yes/no"}
BUY_LIMIT = ("Buyers-only agreement uses only personas who said they buy this kind of product; "
             "it is a secondary view, not the trust label.")
LIMITS = [
    "Revenue is total yearly revenue (worldwide, incl. any wholesale), not US website-only sales.",
    "Both crowd answers are things the AI shoppers SAY; only revenue is real spending.",
    "Fame ranking comes from the same panel (share who have heard of each brand).",
    "Revenue = number of customers x spend per customer (plus any non-US sales): it measures business size, "
    "not how many people buy. Fiscal years end in different months.",
    "Only one number was pre-registered: the crowd's intent ranking vs revenue. Every other agreement "
    "number (say, fame, Wikipedia, buyers-only, repeat panel, sensitivity) is EXPLORATORY.",
    "With 6 brands, 'Trust it' needs a near-perfect ranking; small samples make every range wide.",
]
HEADLINE = "Did the AI crowd understand shoppers, or just pick the famous brands?"
TOP_LEVEL = ["run_id", "mode", "recorded_at", "panel_source", "questions", "limits", "panel", "brands",
             "agreement", "crowd_beat_fame", "headline", "top_gaps", "trust_card", "store", "splits",
             "repeat_run", "cost", "trace"]
BRAND_KEYS = ["id", "name", "description", "revenue_usd", "fiscal_year", "online_note", "filing_url",
              "say_mean", "intent_mean", "aware_share", "rank_say", "rank_intent", "rank_fame",
              "rank_fame_source", "rank_revenue", "fame_guess", "labels"]
OPTIONAL_BRAND_KEYS = ["buy_share", "niche"]  # present only when the export has BUY answers
AGREEMENT_KEYS = ["spearman", "wobble_low", "wobble_high", "could_be_chance", "avg_places_off", "p_exact"]


# ---------- loading ----------

def load_brands(brands_dir: str) -> list[dict]:
    """Read every say/brands/<id>.json and keep only pass == true."""
    out = []
    for path in sorted(glob.glob(os.path.join(brands_dir, "*.json"))):
        with open(path, encoding="utf-8") as f:
            b = json.load(f)
        if b.get("pass") is True:
            out.append(b)
    return out


def load_panel(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def panel_problems(panel: dict) -> list[str]:
    """Shape problems in a panel file (empty list = usable)."""
    errs = [f"panel missing '{k}'" for k in ("panel_id", "source_link", "recorded_at", "n_personas",
                                              "persona_model_note", "order", "responses") if k not in panel]
    if panel.get("order") not in (None, "shuffled", "fixed"):
        errs.append("panel.order must be 'shuffled' or 'fixed'")
    for i, r in enumerate(panel.get("responses", [])):
        if not r.get("brand_id") or not r.get("persona_id"):
            errs.append(f"responses[{i}] needs persona_id and brand_id")
    return errs


# ---------- building ----------

def _now() -> datetime:
    return datetime.now(ET).replace(microsecond=0)


def _r(v: Optional[float], digits: int = 4) -> Optional[float]:
    return None if v is None else round(v, digits)


def _rk(v: float):
    """Whole-number ranks print as ints (3), tied ranks keep the half (2.5)."""
    return int(v) if float(v).is_integer() else v


def _round_agreement(a: dict) -> dict:
    return {k: (a[k] if k == "could_be_chance" else _r(a[k])) for k in AGREEMENT_KEYS}


def _run_id(recorded_at: str, mode: str) -> str:
    stamp = datetime.fromisoformat(recorded_at).strftime("%Y-%m-%dT%H-%M")
    return f"say-sample-{stamp}" if mode == "sample" else f"say-{stamp}"


def _why_trust(verdict: str, rho: Optional[float], downgraded: bool, low, high) -> str:
    if rho is None:
        return "Too few brands (or no spread in the answers) to measure agreement, so ask real people."
    base = f"On intent, the crowd's brand order matched the revenue order with Spearman {rho:.2f}"
    if downgraded:
        return (f"{base}, but the label uses the cautious low end of the 90% wobble range ({low:.2f} to "
                f"{high:.2f}), so it is {VERDICT_WORDS[verdict]}.")
    if low is not None:
        return f"{base} (90% wobble range {low:.2f} to {high:.2f}) = {VERDICT_WORDS[verdict]}."
    return f"{base} = {VERDICT_WORDS[verdict]}."


def _personas(responses: list, brand_ids: set, label: str) -> list:
    """Per-shopper answers for the page. Answers ONLY (no IP hash / user agent / city columns)."""
    by: dict = {}
    for r in responses:
        bid, pid = r.get("brand_id"), r.get("persona_id")
        if bid not in brand_ids or pid in (None, ""):
            continue
        by.setdefault(str(pid), {})[bid] = {k: r.get(k) for k in ("say", "intent", "aware", "buy")}
    return [{"n": pid, "label": label, "answers": ans} for pid, ans in sorted(by.items())]


def build_run(brands: list[dict], panel: dict, trace_steps: list[dict], cost: Optional[dict], mode: str,
              n_boot: int = 2000, seed: int = compare.DEFAULT_SEED) -> dict:
    """Assemble the run file dict from brand files, a normalized panel and a trace.

    Brands that fail (pass != true), have no revenue, or lack any of say / intent / aware
    in the panel are left out and named in the trace. All arithmetic is in compare.py.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {sorted(MODES)}")
    responses = panel.get("responses", [])
    stats = compare.brand_stats(responses)
    rows: list[dict] = []
    dropped: list[str] = []
    for b in brands:
        if b.get("pass") is not True:
            continue
        s = stats.get(b["id"], {})
        if (not compare._is_number(b.get("revenue_usd"))
                or any(s.get(k) is None for k in ("say_mean", "intent_mean", "aware_share"))):
            dropped.append(b["id"])
            continue
        rows.append({**b, **{k: s[k] for k in ("say_mean", "intent_mean", "aware_share")}})
    rows.sort(key=lambda r: -r["revenue_usd"])

    for q, field in compare.QUESTION_FIELD.items():
        rk = compare.ranks([r[field] for r in rows])
        for r, v in zip(rows, rk):
            r[f"rank_{q}"] = v
    for r, v in zip(rows, compare.ranks([r["revenue_usd"] for r in rows])):
        r["rank_revenue"] = v

    agree = {q: compare.agreement(rows, q, n_boot=n_boot, seed=seed) for q in compare.QUESTIONS}
    verdict = compare.trust_verdict(agree["intent"]["spearman"], agree["intent"]["wobble_low"],
                                    agree["intent"]["wobble_high"])
    beat = compare.crowd_beat_fame(agree["intent"]["spearman"], agree["fame"]["spearman"])
    has_buy = any(stats.get(r["id"], {}).get("buy_share") is not None for r in rows)
    agree_buyers = None
    if has_buy:
        ab = compare.buyers_only_agreement(rows, responses, n_boot=n_boot, seed=seed)
        agree_buyers = {"intent": _round_agreement(ab), "n_brands": ab["n_brands"],
                        "min_yes_respondents": compare.MIN_BUYER_RESPONDENTS}
    fake = "FAKE TEST DATA"
    crowd_label = fake if mode == "sample" else "SYNTHETIC"
    labels = {"revenue": fake if mode == "sample" else "MEASURED",
              "say": crowd_label, "intent": crowd_label, "aware": crowd_label}
    if has_buy:
        labels["buy"] = crowd_label

    out_brands = []
    for r in rows:
        bs = stats.get(r["id"], {}).get("buy_share")
        out_brands.append({
            "id": r["id"], "name": r.get("name"), "description": r.get("description"),
            "revenue_usd": r["revenue_usd"], "fiscal_year": r.get("fiscal_year"),
            "online_note": r.get("online_note"), "filing_url": r.get("filing_url"),
            "say_mean": _r(r["say_mean"]), "intent_mean": _r(r["intent_mean"]),
            "aware_share": _r(r["aware_share"]),
            "rank_say": _rk(r["rank_say"]), "rank_intent": _rk(r["rank_intent"]), "rank_fame": _rk(r["rank_fame"]),
            "rank_fame_source": "aware_share", "rank_revenue": _rk(r["rank_revenue"]),
            "fame_guess": r.get("fame_guess"), "labels": dict(labels),
            **({"buy_share": _r(bs), "niche": compare.is_niche(bs)} if has_buy else {}),
        })

    gaps = [{"brand_id": g["brand_id"], "question": g["question"], "crowd_rank": _rk(g["crowd_rank"]),
             "revenue_rank": _rk(g["revenue_rank"]), "why_summary": None, "raw_link": None}
            for g in compare.top_gaps(rows, "intent", k=3)]

    rho = agree["intent"]["spearman"]
    metric = "intent spearman = n/a" if rho is None else f"intent spearman = {rho:.2f}"
    revenue_by_brand = {r["id"]: r["revenue_usd"] for r in rows}
    recorded_at = panel.get("recorded_at") or _now().isoformat()
    steps = list(trace_steps or [])
    steps.append({"t": _now().isoformat(), "agent": "comparer", "model": "code",
                  "step": "compared crowd ranks with revenue ranks",
                  "detail": f"{len(rows)} brands used; left out: {', '.join(dropped) or 'none'}; "
                            f"bootstrap n={n_boot}, seed={seed}"})
    return {
        "run_id": _run_id(recorded_at, mode),
        "mode": mode,
        "recorded_at": recorded_at,
        "panel_source": "flashpoint",
        "questions": {**json.loads(json.dumps(QUESTIONS_BLOCK)), **({"buy": dict(BUY_QUESTION)} if has_buy else {})},
        "limits": list(LIMITS) + ([BUY_LIMIT] if has_buy else []),
        "panel": {k: panel.get(k) for k in ("panel_id", "source_link", "n_personas",
                                            "persona_model_note", "order")},
        "brands": out_brands,
        "agreement": {**{q: _round_agreement(agree[q]) for q in compare.QUESTIONS}, "n_brands": len(rows)},
        **({"agreement_buyers": agree_buyers} if has_buy else {"agreement_buyers": None}),
        "crowd_beat_fame": beat,
        "headline": HEADLINE,
        "top_gaps": gaps,
        "trust_card": {
            "verdict": verdict["verdict"], "metric": metric, "rule": verdict["rule"],
            "reason": _why_trust(verdict["verdict"], rho, verdict["downgraded"],
                                 agree["intent"]["wobble_low"], agree["intent"]["wobble_high"]),
            "draft_question": None, "note": "Stopped for a human. Nothing was bought.",
        },
        "store": None,
        "splits": [{**s, "agreement": {q: (_round_agreement(a) if a else None) for q, a in s["agreement"].items()}}
                   for s in compare.splits(responses, revenue_by_brand, seed=seed)],
        "repeat_run": None,
        "personas": _personas(responses, {b["id"] for b in out_brands}, crowd_label),
        "cost": cost or {"calls": 0, "estimate_usd": 0.0},
        "trace": steps,
    }


# ---------- checking ----------

def validate_run(run: dict) -> list[str]:
    """Check a run dict against the contract. Returns a list of error strings (empty = valid)."""
    errs: list[str] = []
    for k in TOP_LEVEL:
        if k not in run:
            errs.append(f"missing top-level key '{k}'")
    if errs:
        return errs
    if run["mode"] not in MODES:
        errs.append(f"mode '{run['mode']}' not in {sorted(MODES)}")
    if run["panel_source"] != "flashpoint":
        errs.append("panel_source must be 'flashpoint'")
    if "FAKE" in str(run["panel"].get("panel_id", "")).upper() and run["mode"] != "sample":
        errs.append("fake panel must have mode 'sample'")
    expected_q = dict(QUESTIONS_BLOCK)
    if "buy" in run["questions"]:
        expected_q["buy"] = BUY_QUESTION
    if run["questions"] != expected_q:
        errs.append("questions block does not match the contract texts")
    if not run["limits"] or not all(isinstance(x, str) and x for x in run["limits"]):
        errs.append("limits must be a non-empty list of strings")
    for k in ("panel_id", "source_link", "n_personas", "persona_model_note", "order"):
        if k not in run["panel"]:
            errs.append(f"panel missing '{k}'")
    n = len(run["brands"])
    if run["agreement"].get("n_brands") != n:
        errs.append("agreement.n_brands does not equal number of brands")
    ids = set()
    for i, b in enumerate(run["brands"]):
        for k in BRAND_KEYS:
            if k not in b:
                errs.append(f"brands[{i}] missing '{k}'")
        if b.get("id") in ids:
            errs.append(f"duplicate brand id {b.get('id')}")
        ids.add(b.get("id"))
        for k in ("rank_say", "rank_intent", "rank_fame", "rank_revenue"):
            v = b.get(k)
            if not compare._is_number(v) or not 1 <= v <= max(n, 1):
                errs.append(f"brands[{i}].{k} out of range")
        for k in ("say_mean", "intent_mean"):
            v = b.get(k)
            if not compare._is_number(v) or not compare.SCALE_MIN <= v <= compare.SCALE_MAX:
                errs.append(f"brands[{i}].{k} not in 1-10")
        v = b.get("aware_share")
        if not compare._is_number(v) or not 0 <= v <= 1:
            errs.append(f"brands[{i}].aware_share not in 0-1")
        want_labels = {"revenue", "say", "intent", "aware"} | ({"buy"} if "buy" in b.get("labels", {}) else set())
        if set(b.get("labels", {})) != want_labels:
            errs.append(f"brands[{i}].labels needs revenue, say, intent, aware (and buy only with BUY data)")
        if "buy_share" in b:
            v = b["buy_share"]
            if not compare._is_number(v) or not 0 <= v <= 1:
                errs.append(f"brands[{i}].buy_share not in 0-1")
            if b.get("niche") is not compare.is_niche(v):
                errs.append(f"brands[{i}].niche does not match buy_share (strictly under {compare.NICHE_MAX})")
        elif "niche" in b:
            errs.append(f"brands[{i}] has niche without buy_share")
    for q in compare.QUESTIONS:
        a = run["agreement"].get(q)
        if not isinstance(a, dict) or set(a) != set(AGREEMENT_KEYS):
            errs.append(f"agreement.{q} must have keys {AGREEMENT_KEYS}")
            continue
        rho = a["spearman"]
        if rho is not None and not -1 <= rho <= 1:
            errs.append(f"agreement.{q}.spearman out of range")
        if rho is not None and a["wobble_low"] is not None and a["wobble_low"] > a["wobble_high"]:
            errs.append(f"agreement.{q} wobble_low > wobble_high")
        if not isinstance(a["could_be_chance"], bool):
            errs.append(f"agreement.{q}.could_be_chance must be bool")
    ab = run.get("agreement_buyers")
    if ab is not None:
        a = ab.get("intent") if isinstance(ab, dict) else None
        if not isinstance(a, dict) or set(a) != set(AGREEMENT_KEYS):
            errs.append(f"agreement_buyers.intent must have keys {AGREEMENT_KEYS}")
        elif a["spearman"] is not None and not -1 <= a["spearman"] <= 1:
            errs.append("agreement_buyers.intent.spearman out of range")
        if not isinstance(ab.get("n_brands"), int) or ab["n_brands"] > n:
            errs.append("agreement_buyers.n_brands invalid")
        if ab.get("min_yes_respondents") != compare.MIN_BUYER_RESPONDENTS:
            errs.append("agreement_buyers.min_yes_respondents must be 10")
    if not isinstance(run["crowd_beat_fame"], bool):
        errs.append("crowd_beat_fame must be bool")
    for i, g in enumerate(run["top_gaps"]):
        for k in ("brand_id", "question", "crowd_rank", "revenue_rank", "why_summary", "raw_link"):
            if k not in g:
                errs.append(f"top_gaps[{i}] missing '{k}'")
        if g.get("brand_id") not in ids:
            errs.append(f"top_gaps[{i}] brand_id not in brands")
    tc = run["trust_card"]
    for k in ("verdict", "metric", "rule", "reason", "draft_question", "note"):
        if k not in tc:
            errs.append(f"trust_card missing '{k}'")
    if tc.get("verdict") not in VERDICTS:
        errs.append("trust_card.verdict invalid")
    elif tc["verdict"] == "trust" and not ((run["agreement"]["intent"].get("wobble_low") or -1) >= compare.TRUST_MIN):
        errs.append("trust_card.verdict is 'trust' but intent wobble_low is under the trust cutoff")
    for k in ("calls", "estimate_usd"):
        if k not in (run["cost"] or {}):
            errs.append(f"cost missing '{k}'")
    for i, t in enumerate(run["trace"]):
        for k in ("t", "agent", "model", "step", "detail"):
            if k not in t:
                errs.append(f"trace[{i}] missing '{k}'")
    return errs


# ---------- writing ----------

def _atomic_write(target: str, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_run(run: dict, run_dir: str = "frontend/runs") -> str:
    """Atomically write say_<run_id>.json and say_latest.json. Refuses an invalid run.
    Returns the path of the dated file."""
    errs = validate_run(run)
    if errs:
        raise ValueError("run file invalid: " + "; ".join(errs))
    os.makedirs(run_dir, exist_ok=True)
    text = json.dumps(run, indent=2, ensure_ascii=False)
    path = os.path.join(run_dir, f"say_{run['run_id']}.json")
    for target in (path, os.path.join(run_dir, "say_latest.json")):
        _atomic_write(target, text)
    return path


# ---------- CLI ----------

def headline_text(run: dict) -> str:
    a, tc = run["agreement"], run["trust_card"]
    banner = "*** FAKE TEST DATA, NOT A RESULT ***\n" if run["mode"] == "sample" else ""
    lines = [banner + f"Run {run['run_id']} ({run['mode']}), {a['n_brands']} brands, panel '{run['panel']['panel_id']}'"]
    for q in compare.QUESTIONS:
        x = a[q]
        if x["spearman"] is None:
            lines.append(f"  {q:6} spearman n/a")
            continue
        lines.append(f"  {q:6} spearman {x['spearman']:+.2f}  wobble {x['wobble_low']:+.2f} to "
                     f"{x['wobble_high']:+.2f}  could_be_chance={x['could_be_chance']}  avg places off {x['avg_places_off']:.2f}")
    lines.append(f"  crowd_beat_fame: {run['crowd_beat_fame']}")
    lines.append(f"  trust card: {VERDICT_WORDS[tc['verdict']]} ({tc['metric']})")
    lines.append(f"  {tc['reason']}")
    for g in run["top_gaps"]:
        lines.append(f"  gap: {g['brand_id']} crowd rank {g['crowd_rank']} vs revenue rank {g['revenue_rank']}")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Compare a normalized panel file with brand revenue and write the run file.")
    p.add_argument("--panel", required=True)
    p.add_argument("--brands-dir", default="say/brands")
    p.add_argument("--run-dir", default="frontend/runs")
    p.add_argument("--mode", choices=sorted(MODES), help="default: sample if the panel_id says FAKE, else recorded")
    p.add_argument("--brands-from-panel", action="store_true",
                   help="use the panel's 'fake_brands' list (test fixture only) instead of --brands-dir")
    args = p.parse_args(argv)
    panel = load_panel(args.panel)
    problems = panel_problems(panel)
    if problems:
        print("Panel file problems:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2
    brands = panel.get("fake_brands", []) if args.brands_from_panel else load_brands(args.brands_dir)
    brands = [b for b in brands if b.get("pass") is True]
    mode = args.mode or ("sample" if "FAKE" in str(panel["panel_id"]).upper() else "recorded")
    run = build_run(brands, panel, [], None, mode)
    path = write_run(run, args.run_dir)
    print(headline_text(run))
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
