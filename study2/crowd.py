"""Study 2 do-it-yourself AI crowd (see study2/PREREG.md, "The AI crowd").

Builds 200 personas from a fixed grid, asks each one about every brand (heard of it 1-10,
likely to buy in the next 12 months 1-10), in batches of up to 40 brands per call.

Safety:
- Default is --dry-run: prints the prompt and a cost ESTIMATE, makes ZERO model calls.
- A real run needs --go AND the model written into PREREG.md's amendment section first.
- Hard call cap (--max-calls). The API key is read from the environment only.

Run:  python3 -m study2.crowd --pilot            (dry run of the pilot)
      python3 -m study2.crowd --pilot --go       (5 personas x 3 brands, real calls)
      python3 -m study2.crowd --run main --go    (full run)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
from pathlib import Path

from agent.llm import LLM

HERE = Path(__file__).parent
DATA = HERE / "data"
SEED_PERSONAS = 20261117
SHUFFLE_SEEDS = {"main": 20261117, "repeat": 20261118, "pilot": 1}
BATCH = 40
N_PERSONAS = 200

# Rough US adult shares (ESTIMATE: round numbers, not a Census table pull; stated as such).
AGE = [("18-29", 0.20), ("30-44", 0.26), ("45-64", 0.32), ("65+", 0.22)]
INCOME = [("under $35k", 0.25), ("$35k-$75k", 0.30), ("$75k-$150k", 0.29), ("over $150k", 0.16)]
REGION = [("Northeast", 0.17), ("Midwest", 0.21), ("South", 0.38), ("West", 0.24)]
ONLINE = [("rarely shop online", 0.20), ("shop online about once a month", 0.40),
          ("shop online every week", 0.40)]

# Anthropic first-party prices, USD per million tokens (input, output), from the claude-api
# skill's model table (cached 2026-11-03). Re-check the price page before a paid run.
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00)}

SYSTEM = ("You are role-playing one American adult shopper in a market-research survey. "
          "Answer as that person would, from what they would plausibly know and want. "
          "Do not look anything up and do not explain. Use whole numbers only.")


def _pick(rng: random.Random, options):
    r, acc = rng.random(), 0.0
    for label, w in options:
        acc += w
        if r < acc:
            return label
    return options[-1][0]


def personas(n: int = N_PERSONAS) -> list[dict]:
    rng = random.Random(SEED_PERSONAS)
    out = []
    for i in range(n):
        p = {"id": f"p{i:03d}", "age": _pick(rng, AGE), "income": _pick(rng, INCOME),
             "region": _pick(rng, REGION), "online": _pick(rng, ONLINE)}
        p["text"] = (f"You are {p['age']} years old, with household income {p['income']}, living in the "
                     f"{p['region']} of the US. You {p['online']}.")
        out.append(p)
    return out


def display_name(b: dict) -> str:
    """Everyday name: the English Wikipedia article title without a trailing '(...)'."""
    title = (b.get("wiki_title") or b["name"]).replace("_", " ")
    return re.sub(r"\s*\([^)]*\)$", "", title)


def brand_line(b: dict) -> str:
    label = (b.get("sic_label") or "retail").lower()
    return f'{b["key"]}: "{display_name(b)}" (a US company; industry: {label})'


def user_prompt(persona: dict, batch: list[dict]) -> str:
    lines = "\n".join(brand_line(b) for b in batch)
    keys = ", ".join(b["key"] for b in batch)
    return (f"{persona['text']}\n\nFor each company below, give two scores:\n"
            "- heard: how well you know this company, 1 = never heard of it, 10 = know it very well\n"
            "- buy: how likely you are to buy from this company in the next 12 months, "
            "1 = not at all likely, 10 = extremely likely\n\n"
            f"{lines}\n\n"
            'Reply as JSON: {"answers": {"<key>": {"heard": n, "buy": n}, ...}} '
            f"with exactly these keys: {keys}.")


def plan(brands: list[dict], people: list[dict], seed: int) -> list[tuple[dict, list[dict]]]:
    """Per persona: shuffle brands (seeded), split into batches of <= BATCH."""
    rng = random.Random(seed)
    jobs = []
    for p in people:
        order = brands[:]
        rng.shuffle(order)
        n_batches = -(-len(order) // BATCH)
        size = -(-len(order) // n_batches)
        for i in range(0, len(order), size):
            jobs.append((p, order[i:i + size]))
    return jobs


def valid(answer: dict, batch: list[dict]) -> dict | None:
    a = (answer or {}).get("answers")
    if not isinstance(a, dict) or set(a) != {b["key"] for b in batch}:
        return None
    for v in a.values():
        if not isinstance(v, dict):
            return None
        for q in ("heard", "buy"):
            if not (isinstance(v.get(q), int) and 1 <= v[q] <= 10):
                return None
    return a


def estimate(jobs, model: str) -> dict:
    tin = sum(len(SYSTEM + user_prompt(p, b)) / 3.5 for p, b in jobs)  # rough chars-per-token
    tout = sum(25 * len(b) + 30 for _, b in jobs)
    pin, pout = PRICES[model]
    return {"calls": len(jobs), "input_tokens_est": int(tin), "output_tokens_est": int(tout),
            "usd_est": round(tin / 1e6 * pin + tout / 1e6 * pout, 2),
            "note": "ESTIMATE without thinking tokens; the model thinks by default, so real cost may be 2-3x. Real tokens are saved after a run"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", choices=["main", "repeat"], default="main")
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--model", default="claude-haiku-5-5", choices=sorted(PRICES))
    ap.add_argument("--max-calls", type=int, default=450)
    ap.add_argument("--go", action="store_true", help="actually call the model (costs money)")
    args = ap.parse_args()

    brands = json.loads((DATA / "brands.json").read_text())["brands"]
    for i, b in enumerate(brands):
        b["key"] = f"b{i:02d}"
    people = personas()
    run = "pilot" if args.pilot else args.run
    if args.pilot:
        people, brands = people[:5], brands[:3]
    jobs = plan(brands, people, SHUFFLE_SEEDS[run])
    est = estimate(jobs, args.model)
    print(json.dumps({"run": run, "model": args.model, **est}, indent=1))
    print("--- example prompt ---\n" + user_prompt(*jobs[0]))
    if not args.go:
        print("\nDRY RUN: no model calls made.")
        return
    prereg = (HERE / "PREREG.md").read_text()
    if not args.pilot and args.model not in prereg.split("## Amendments", 1)[1]:
        raise SystemExit("STOP: write the model into PREREG.md amendments before a main/repeat run.")
    if len(jobs) > args.max_calls:  # the LLM helper also hard-stops at max_calls (repairs included)
        raise SystemExit(f"STOP: {len(jobs)} calls exceed the cap of {args.max_calls}.")

    llm = LLM(max_calls=args.max_calls, max_parallel=4)
    rows, failures = [], []
    for p, batch in jobs:
        try:
            ans = llm.call(args.model, SYSTEM, user_prompt(p, batch), max_tokens=8000,
                           json_mode=True, purpose=f"{run}:{p['id']}")
            a = valid(ans, batch)
        except Exception as e:  # keep going; every failure is logged, never silently dropped
            a, ans = None, {"error": str(e)[:200]}
        if a is None:
            failures.append({"persona": p["id"], "batch": [b["key"] for b in batch], "raw": ans})
            continue
        for b in batch:
            rows.append({"persona": p["id"], "cik": b["cik"], "brand": b["name"],
                         "heard": a[b["key"]]["heard"], "buy": a[b["key"]]["buy"]})
    out = {"run": run, "model": args.model, "recorded_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "label": "SYNTHETIC", "n_personas": len(people), "n_brands": len(brands),
           "calls": llm.calls, "input_tokens": llm.input_tokens, "output_tokens": llm.output_tokens,
           "usd_actual": round(llm.input_tokens / 1e6 * PRICES[args.model][0]
                               + llm.output_tokens / 1e6 * PRICES[args.model][1], 4),
           "failures": failures, "rows": rows}
    path = DATA / f"crowd_{run}.json"
    path.write_text(json.dumps(out, indent=1))
    print(f"saved {path}: {len(rows)} answers, {len(failures)} failed batches, ${out['usd_actual']}")


if __name__ == "__main__":
    main()
