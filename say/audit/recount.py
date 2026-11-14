"""Independent recount of frontend/runs/say_latest.json from the raw CSV.
Run from the hackathon-project folder: python3 say/audit/recount.py
Does not import or read anything in say/*.py."""
import csv, json, random, sys

RUN = "frontend/runs/say_latest.json"
CSV = "say/panels/q4_export.csv"
TOL = 0.001

run = json.load(open(RUN))
ids = [b["id"] for b in run["brands"]]
rows = list(csv.reader(open(CSV, newline="")))
hdr = rows[0]
data = [dict(zip(hdr, r)) for r in rows[1:]]
data = [r for r in data if r["Status"] == "COMPLETE"]  # drops the repeated header row (Status == 'Status')
n = len(data)

def col(p, b): return [int(r[f"{p}__{b}"]) for r in data]

def mean(x): return sum(x) / len(x)

def ranks_desc(vals):
    """average ranks, rank 1 = highest"""
    order = sorted(range(len(vals)), key=lambda i: -vals[i])
    rk = [0.0] * len(vals); i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]: j += 1
        for k in range(i, j + 1): rk[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return rk

def pearson(a, b):
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** .5; db = sum((y - mb) ** 2 for y in b) ** .5
    return num / (da * db) if da and db else float("nan")

def spearman(a, b): return pearson(ranks_desc(a), ranks_desc(b))

rc = {}
for b in ids:
    rc[b] = dict(say=mean(col("SAY", b)), intent=mean(col("INTENT", b)),
                 aware=mean([x == 1 for x in col("AWARE", b)]),
                 buy=mean([x == 1 for x in col("BUY", b)]))
rev_file = {b: json.load(open(f"say/brands/{b}.json"))["revenue_usd"] for b in ids}
rev_run = {b["id"]: b["revenue_usd"] for b in run["brands"]}
rev = [rev_file[b] for b in ids]
rk = {k: ranks_desc([rc[b][k] for b in ids]) for k in ("say", "intent", "aware")}
rk_rev = ranks_desc(rev)

table = []
def add(name, a, b, tol=TOL):
    ok = (a == b) if isinstance(a, (bool, str)) or tol is None else abs(a - b) <= tol
    table.append((name, a, b, ok))

add("n rows", run["panel"]["n_personas"], n, None)
add("n personas[]", len(run["personas"]), n, None)
for i, br in enumerate(run["brands"]):
    b = br["id"]
    add(f"{b} revenue (run vs brand file)", rev_run[b], rev_file[b], None)
    add(f"{b} revenue (brand file vs run)", br["revenue_usd"], rev_file[b], None)
    add(f"{b} say_mean", br["say_mean"], round(rc[b]["say"], 4))
    add(f"{b} intent_mean", br["intent_mean"], round(rc[b]["intent"], 4))
    add(f"{b} aware_share", br["aware_share"], round(rc[b]["aware"], 4))
    add(f"{b} buy_share", br["buy_share"], round(rc[b]["buy"], 4))
    add(f"{b} rank_say", br["rank_say"], rk["say"][i], None)
    add(f"{b} rank_intent", br["rank_intent"], rk["intent"][i], None)
    add(f"{b} rank_fame", br["rank_fame"], rk["aware"][i], None)
    add(f"{b} rank_revenue", br["rank_revenue"], rk_rev[i], None)
    add(f"{b} niche (buy<0.30)", br["niche"], rc[b]["buy"] < 0.30)
sp = {k: spearman([rc[b][k] for b in ids], rev) for k in ("say", "intent", "aware")}
for k, rk_ in (("say", "say"), ("intent", "intent"), ("aware", "fame")):
    add(f"spearman {rk_} vs revenue", run["agreement"][rk_]["spearman"], round(sp[k], 4))
    # also: Spearman recomputed from the run file's own rank columns
add("n_brands", run["agreement"]["n_brands"], len(ids), None)

# persona cross-check: every persona answer vs CSV by respondent ID
byid = {r["ID"]: r for r in data}
bad = 0; chk = 0
for p in run["personas"]:
    r = byid.get(p["n"])
    if r is None: bad += 1; continue
    for b in ids:
        a = p["answers"][b]; chk += 4
        if (a["say"], a["intent"], a["aware"], a["buy"]) != (int(r[f"SAY__{b}"]), int(r[f"INTENT__{b}"]), int(r[f"AWARE__{b}"]) == 1, int(r[f"BUY__{b}"]) == 1):
            bad += 1
add("persona answers mismatching CSV (of %d)" % chk, 0, bad, None)

# separate random bootstrap over brands, 2000 samples, seed 12345 (NOT the run's draw)
random.seed(12345)
def boot(key):
    out = []
    for _ in range(2000):
        s = [random.randrange(len(ids)) for _ in ids]
        a = [rc[ids[i]][key] for i in s]; r_ = [rev[i] for i in s]
        v = spearman(a, r_)
        if v == v: out.append(v)
    out.sort(); return out[int(.05 * len(out))], out[int(.95 * len(out)) - 1], len(out)
boots = {k: boot(k) for k in ("say", "intent", "aware")}

lines = ["| value | run file | recount | match? |", "|---|---|---|---|"]
for name, a, b, ok in table:
    lines.append(f"| {name} | {a} | {b} | {'YES' if ok else '**NO - MISMATCH**'} |")
lines += ["", "Bootstrap (own draw, 2000 resamples of brands, seed 12345; separate random draw, not expected to match exactly; NaN resamples dropped):", "",
          "| metric | run file 90% range | my 90% range | valid draws |", "|---|---|---|---|"]
for k, rk_ in (("say", "say"), ("intent", "intent"), ("aware", "fame")):
    g = run["agreement"][rk_]
    lines.append(f"| {rk_} | {g['wobble_low']} to {g['wobble_high']} | {boots[k][0]:.4f} to {boots[k][1]:.4f} | {boots[k][2]} |")
print("\n".join(lines))
print("\nMISMATCHES:", [t[0] for t in table if not t[3]] or "none")
