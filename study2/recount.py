"""Independent recount of Study 2's main numbers with scipy/numpy (different code from analyze.py).

Reads the raw crowd answers and brands.json directly, recomputes brand means, the three Spearman
scores, the partial Spearman (via residuals of ranks), and the leave-one-out fits (numpy lstsq).
Run: python3 -m study2.recount
"""
import json
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

DATA = Path(__file__).parent / "data"


def resid(y, x):
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ beta


def main():
    brands = {b["cik"]: b for b in json.loads((DATA / "brands.json").read_text())["brands"]}
    rows = json.loads((DATA / "crowd_main.json").read_text())["rows"]
    buy, heard = {}, {}
    for r in rows:
        buy.setdefault(r["cik"], []).append(r["buy"])
        heard.setdefault(r["cik"], []).append(r["heard"])
    ciks = sorted(buy)
    intent = np.array([np.mean(buy[c]) for c in ciks])
    hrd = np.array([np.mean(heard[c]) for c in ciks])
    rev = np.array([brands[c]["revenue_usd"] for c in ciks], dtype=float)
    views = np.array([brands[c]["views"] for c in ciks], dtype=float)

    ri, rr, rv = rankdata(intent), rankdata(rev), rankdata(views)
    partial = np.corrcoef(resid(ri, rv), resid(rr, rv))[0, 1]

    lr, lv = np.log(rev), np.log(views)
    def loo(cols):
        X = np.column_stack([np.ones(len(lr))] + cols)
        preds = []
        for i in range(len(lr)):
            m = np.arange(len(lr)) != i
            beta, *_ = np.linalg.lstsq(X[m], lr[m], rcond=None)
            preds.append(X[i] @ beta)
        return spearmanr(preds, lr).statistic

    out = {"n_brands": len(ciks), "n_answers": len(rows),
           "intent_vs_revenue": spearmanr(intent, rev).statistic,
           "intent_vs_fame": spearmanr(intent, views).statistic,
           "fame_vs_revenue": spearmanr(views, rev).statistic,
           "heard_vs_revenue": spearmanr(hrd, rev).statistic,
           "partial_intent_revenue_given_fame": partial,
           "loo_correction_A": loo([intent, lv]), "loo_fame_only": loo([lv])}
    print(json.dumps({k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v) for k, v in out.items()}, indent=1))


if __name__ == "__main__":
    main()
