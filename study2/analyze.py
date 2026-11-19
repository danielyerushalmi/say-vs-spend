"""Study 2 scores and the pre-registered H1/H2/H3 verdicts (study2/PREREG.md).

Run: python3 -m study2.analyze [--crowd study2/data/crowd_main.json]
Pure standard library. Seed 20261117 for every bootstrap.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from say.compare import _percentile, ranks, spearman

SEED, N_BOOT = 20261117, 2000
DATA = Path(__file__).parent / "data"


def rho(x, y):
    return spearman(ranks(x), ranks(y))


def partial_rho(x, y, z):
    """Partial Spearman of x and y holding z fixed (rank all three, then partial correlation)."""
    rxy, rxz, ryz = rho(x, y), rho(x, z), rho(y, z)
    if None in (rxy, rxz, ryz):
        return None
    den = math.sqrt(max(0.0, (1 - rxz ** 2) * (1 - ryz ** 2)))
    return None if den == 0 else (rxy - rxz * ryz) / den


def _ols_fit(xs: list[list[float]], y: list[float]) -> list[float]:
    """Ordinary least squares with an intercept, solved by Gaussian elimination."""
    X = [[1.0] + r for r in xs]
    k = len(X[0])
    A = [[sum(X[i][a] * X[i][b] for i in range(len(X))) for b in range(k)] for a in range(k)]
    v = [sum(X[i][a] * y[i] for i in range(len(X))) for a in range(k)]
    for c in range(k):  # elimination with partial pivoting
        p = max(range(c, k), key=lambda r: abs(A[r][c]))
        A[c], A[p], v[c], v[p] = A[p], A[c], v[p], v[c]
        if abs(A[c][c]) < 1e-12:
            raise ValueError("singular fit")
        for r in range(k):
            if r != c:
                f = A[r][c] / A[c][c]
                A[r] = [a - f * b for a, b in zip(A[r], A[c])]
                v[r] -= f * v[c]
    return [v[i] / A[i][i] for i in range(k)]


def loo_predictions(features: list[list[float]], y: list[float]) -> list[float]:
    preds = []
    for i in range(len(y)):
        beta = _ols_fit(features[:i] + features[i + 1:], y[:i] + y[i + 1:])
        preds.append(beta[0] + sum(b * f for b, f in zip(beta[1:], features[i])))
    return preds


def boot(stat, n: int):
    """5th and 95th percentile of stat(sample_indices) over N_BOOT brand resamples."""
    rng = random.Random(SEED)
    vals = []
    for _ in range(N_BOOT):
        idx = [rng.randrange(n) for _ in range(n)]
        try:
            s = stat(idx)
        except (ValueError, ZeroDivisionError):
            s = None
        if s is not None:
            vals.append(s)
    vals.sort()
    return (_percentile(vals, 5), _percentile(vals, 95)) if vals else (None, None)


def brand_means(rows: list[dict]) -> dict[str, dict]:
    acc: dict[str, dict] = {}
    for r in rows:
        a = acc.setdefault(r["cik"], {"buy": [], "heard": []})
        a["buy"].append(r["buy"])
        a["heard"].append(r["heard"])
    return {k: {q: sum(v) / len(v) for q, v in a.items()} for k, a in acc.items()}


def score(intent: list[float], revenue: list[float], views: list[float], heard: list[float] | None = None) -> dict:
    n = len(intent)
    pick = lambda xs, idx: [xs[i] for i in idx]
    r_ir, r_if = rho(intent, revenue), rho(intent, views)

    # H1
    diff = r_if - r_ir
    d_lo, d_hi = boot(lambda idx: (lambda a, b: None if None in (a, b) else a - b)(
        rho(pick(intent, idx), pick(views, idx)), rho(pick(intent, idx), pick(revenue, idx))), n)
    h1 = diff >= 0.20 and d_lo is not None and d_lo > 0

    # H2
    pr = partial_rho(intent, revenue, views)
    p_lo, p_hi = boot(lambda idx: partial_rho(pick(intent, idx), pick(revenue, idx), pick(views, idx)), n)
    h2_adds = pr is not None and pr >= 0.30 and p_lo is not None and p_lo > 0

    # H3
    logrev, logv = [math.log(r) for r in revenue], [math.log(v) for v in views]
    pred_a = loo_predictions([[i, lv] for i, lv in zip(intent, logv)], logrev)
    pred_f = loo_predictions([[lv] for lv in logv], logrev)
    s_a, s_f = rho(pred_a, logrev), rho(pred_f, logrev)
    h3 = s_a - r_ir >= 0.15

    out = {
        "n_brands": n,
        "intent_vs_revenue": r_ir, "intent_vs_fame": r_if, "fame_vs_revenue": rho(views, revenue),
        "H1": {"diff": diff, "range90": [d_lo, d_hi], "verdict": "PASS" if h1 else "FAIL",
               "rule": "diff >= 0.20 and 5th percentile > 0"},
        "H2": {"partial": pr, "range90": [p_lo, p_hi],
               "verdict": "FAIL (crowd adds something)" if h2_adds else "PASS (crowd adds nothing)",
               "rule": "PASS if partial < 0.30 or range includes 0"},
        "H3": {"correction_A": s_a, "fame_only": s_f, "raw_intent": r_ir,
               "verdict": "PASS" if h3 else "FAIL", "rule": "correction_A - raw_intent >= 0.15",
               "fame_back_in": s_f is not None and s_a is not None and abs(s_a - s_f) <= 0.05},
    }
    if heard is not None:
        out["EXPLORATORY_heard_vs_revenue"] = rho(heard, revenue)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crowd", default=str(DATA / "crowd_main.json"))
    args = ap.parse_args()
    brands = {b["cik"]: b for b in json.loads((DATA / "brands.json").read_text())["brands"]}
    means = brand_means(json.loads(Path(args.crowd).read_text())["rows"])
    ciks = sorted(c for c in brands if c in means)
    res = score([means[c]["buy"] for c in ciks], [brands[c]["revenue_usd"] for c in ciks],
                [brands[c]["views"] for c in ciks], [means[c]["heard"] for c in ciks])
    sub = [c for c in ciks if brands[c]["sic"] == 5961]
    if len(sub) >= 5:
        res["EXPLORATORY_sic5961"] = {"n": len(sub), "intent_vs_revenue": rho(
            [means[c]["buy"] for c in sub], [brands[c]["revenue_usd"] for c in sub])}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
