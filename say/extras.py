"""Extra statistics views for Say vs. Spend. Pure functions, standard library only.

Four blocks, each a dict with "label" and a plain-English "summary"; numbers rounded to 4 dp.

- sensitivity_view: the same agreement numbers on 8 brands (the 6 pre-registered ones plus the
  2 that passed a recheck AFTER the 6-brand results were seen). Display only, never the verdict.
- order_effect: does the position a brand was shown in (1..12) move its SAY / INTENT score?
- compression: how squeezed the AI crowd's 1-10 answers are. Describes the AI only.
- crowd_vs_crowd: do two independent AI crowds agree with each other more than with revenue?

All numbers come from code (compare.py math), never from an LLM.
"""
from __future__ import annotations

import csv
import itertools
import math
import random
from typing import Optional, Sequence

from . import compare, flashpoint_import, repeat

SENSITIVITY_LABEL = ("SENSITIVITY CHECK - 2 brands added after the 6-brand results were seen; "
                     "not the pre-registered result.")
SYNTHETIC = "SYNTHETIC"
RATING_KINDS = ("say", "intent")
_PREFIX = {"say": "SAY", "intent": "INTENT"}
MAX_EXACT_PERM_N = 8  # 8! = 40320 orderings: exact permutation test stays fast


# ----------------------------------------------------------------------------- small helpers

def _r(v, digits: int = 4):
    return None if v is None else round(float(v), digits)


def _rk(v):
    return None if v is None else (int(v) if float(v).is_integer() else round(float(v), 2))


def _round_agreement(a: dict) -> dict:
    return {k: (_r(v) if k in ("spearman", "wobble_low", "wobble_high", "avg_places_off", "p_exact") else v)
            for k, v in a.items()}


def exact_perm_p(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    """Exact two-sided permutation p-value for the Spearman of x and y.

    Shuffles y's ranks over every possible ordering (ties kept as average ranks) and counts how
    often |rho| is at least the observed |rho|. Only for 3..8 items (8! = 40320 orderings);
    None otherwise or when rho is undefined. With 6 brands the smallest possible p is 2/720.
    """
    n = len(x)
    if n < compare.MIN_BRANDS or n > MAX_EXACT_PERM_N or n != len(y):
        return None
    rx, ry = compare.ranks(x), compare.ranks(y)
    obs = compare.spearman(rx, ry)
    if obs is None:
        return None
    hits = total = 0
    for perm in itertools.permutations(ry):
        rho = compare.spearman(rx, perm)
        total += 1
        if rho is not None and abs(rho) >= abs(obs) - 1e-12:
            hits += 1
    return hits / total


def _ols_slope(n: float, sx: float, sy: float, sxx: float, sxy: float) -> Optional[float]:
    den = n * sxx - sx * sx
    return None if n < 2 or den == 0 else (n * sxy - sx * sy) / den


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    return compare._percentile(sorted_vals, q)


# ----------------------------------------------------------------------------- 1. sensitivity

def sensitivity_view(main_run: dict, panel_responses: Sequence[dict], brands_dir: str,
                     n_boot: int = 2000, seed: int = compare.DEFAULT_SEED) -> dict:
    """Agreement (say / intent / fame vs revenue) on the 6 main-run brands plus every brand file
    with "recheck_pass": true. Same math, seed and n_boot as the main run. Display only.

    panel_responses: the main panel's per-respondent rows (all 12 brands, from import_export).
    Brand means for ALL brands are recomputed from these rows; "reproduces_main" checks the
    6-brand numbers against the run file so a mismatch cannot hide.
    """
    main_brands = main_run["brands"]
    main_ids = [b["id"] for b in main_brands]
    files = repeat._brand_files(brands_dir)
    added = sorted(bid for bid, f in files.items()
                   if f.get("recheck_pass") is True and bid not in main_ids)
    revenue = {bid: f.get("revenue_usd") for bid, f in files.items()}
    revenue.update({b["id"]: b.get("revenue_usd") for b in main_brands})
    names = {bid: f.get("name") for bid, f in files.items()}
    names.update({b["id"]: b.get("name") for b in main_brands})

    stats = compare.brand_stats(panel_responses)
    rows, left_out = [], []
    for bid in main_ids + added:
        s = stats.get(bid) or {}
        if not compare._is_number(revenue.get(bid)) or any(s.get(f) is None for f in compare.QUESTION_FIELD.values()):
            left_out.append(bid)
            continue
        rows.append({"id": bid, "name": names.get(bid), "revenue_usd": revenue[bid],
                     **{f: s[f] for f in compare.QUESTION_FIELD.values()},
                     "added_after_results": bid in added})

    agree = {q: compare.agreement(rows, q, n_boot=n_boot, seed=seed) for q in compare.QUESTIONS}
    perm = {}
    for q, field in compare.QUESTION_FIELD.items():
        perm[q] = _r(exact_perm_p([r[field] for r in rows], [r["revenue_usd"] for r in rows]))
    verdict8 = compare.trust_verdict(agree["intent"]["spearman"], agree["intent"]["wobble_low"],
                                     agree["intent"]["wobble_high"])
    main_verdict = (main_run.get("trust_card") or {}).get("verdict")

    # Reproduce the 6-brand numbers from the same rows: guards against mixing up panels.
    six = [r for r in rows if not r["added_after_results"]]
    agree6 = {q: compare.agreement(six, q, n_boot=n_boot, seed=seed) for q in compare.QUESTIONS}
    diffs = {}
    for q in compare.QUESTIONS:
        for k in ("spearman", "wobble_low", "wobble_high"):
            ours, theirs = _r(agree6[q][k]), (main_run.get("agreement", {}).get(q) or {}).get(k)
            if theirs is None or ours is None or abs(ours - theirs) > 1e-4:
                diffs[f"{q}.{k}"] = {"recomputed": ours, "run_file": theirs}

    for q, field in compare.QUESTION_FIELD.items():
        for r, rk in zip(rows, compare.ranks([r[field] for r in rows])):
            r[f"rank_{q}"] = rk
    for r, rk in zip(rows, compare.ranks([r["revenue_usd"] for r in rows])):
        r["rank_revenue"] = rk

    i8, i6 = agree["intent"]["spearman"], agree6["intent"]["spearman"]
    change = verdict8["verdict"] != main_verdict
    summary = (f"With {len(rows)} brands instead of 6 (adding {', '.join(added) or 'none'}), intent-vs-revenue "
               f"agreement is {_r(i8)} (was {_r(i6)}; 90% range {_r(agree['intent']['wobble_low'])} to "
               f"{_r(agree['intent']['wobble_high'])}). The trust label "
               + ("WOULD change" if change else "would NOT change")
               + f" ({main_verdict} -> {verdict8['verdict']}). Display only: these brands were added after "
               "the results were seen.")
    return {
        "label": SENSITIVITY_LABEL,
        "summary": summary,
        "display_only": True,
        "brands": [r["id"] for r in rows],
        "added_brands": added,
        "n_brands": len(rows),
        "brands_left_out": left_out,
        "table": [{"id": r["id"], "added_after_results": r["added_after_results"],
                   "say_mean": _r(r["say_mean"]), "intent_mean": _r(r["intent_mean"]),
                   "aware_share": _r(r["aware_share"]), "rank_say": _rk(r["rank_say"]),
                   "rank_intent": _rk(r["rank_intent"]), "rank_fame": _rk(r["rank_fame"]),
                   "rank_revenue": _rk(r["rank_revenue"])} for r in rows],
        "agreement": {q: {**_round_agreement(agree[q]), "exact_perm_p": perm[q]} for q in compare.QUESTIONS},
        "crowd_beat_fame": compare.crowd_beat_fame(agree["intent"]["spearman"], agree["fame"]["spearman"]),
        "verdict_if_8": {"verdict": verdict8["verdict"], "downgraded": verdict8["downgraded"]},
        "main_verdict": main_verdict,
        "verdict_would_change": change,
        "reproduces_main": not diffs,
        "reproduce_mismatches": diffs,
        "n_boot": n_boot,
        "seed": seed,
    }


# ----------------------------------------------------------------------------- 2. order effect

def _read_order_rows(csv_path: str, brand_ids: Sequence[str]):
    """Yield (persona_id, {brand: position}, {kind: {brand: score}}) per real respondent row,
    plus a dict of skip counts. Skips the repeated header row Flashpoint puts first."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f"{csv_path} is empty")
    header = [h.strip() for h in rows[0]]
    order_cols = [i for i, h in enumerate(header) if h.lower().startswith("display order")]
    if not order_cols:
        raise ValueError("no 'Display Order' column in the export")
    oc = order_cols[0]
    id_idx = flashpoint_import._find_id_column(header, None)
    lower = {h.lower(): i for i, h in enumerate(header)}
    cols = {k: {b: lower.get(f"{_PREFIX[k]}__{b}".lower()) for b in brand_ids} for k in RATING_KINDS}
    skipped = {"header_rows": 0, "no_order": 0, "brand_not_in_order": 0, "duplicate_id": 0}
    seen, out = set(), []
    for n, row in enumerate(rows[1:], start=1):
        if not any(c.strip() for c in row):
            continue
        cell = row[oc].strip() if oc < len(row) else ""
        same = sum(1 for a, h in zip(row, header) if a.strip() == h)
        # Flashpoint repeats the header as the first data row (its order cell reads
        # "Display Order/Loop order: ..."), so match on most cells, not on every cell.
        if same * 2 >= len(header) or cell.lower().startswith("display order"):
            skipped["header_rows"] += 1
            continue
        tokens = [t.strip() for t in cell.split("|") if t.strip()]
        if not any(b in tokens for b in brand_ids):
            skipped["no_order"] += 1
            continue
        pid = row[id_idx].strip() if id_idx is not None and id_idx < len(row) and row[id_idx].strip() else f"ROW-{n}"
        if pid in seen:
            skipped["duplicate_id"] += 1
            continue
        seen.add(pid)
        pos = {}
        for b in brand_ids:
            if b in tokens:
                pos[b] = tokens.index(b) + 1
            else:
                skipped["brand_not_in_order"] += 1
        scores = {k: {} for k in RATING_KINDS}
        for k in RATING_KINDS:
            for b in brand_ids:
                c = cols[k][b]
                if c is None or c >= len(row) or b not in pos:
                    continue
                v, _ = flashpoint_import.parse_scale(row[c])
                if v is not None:
                    scores[k][b] = v
        out.append((pid, pos, scores))
    n_positions = max((max(p.values()) for _, p, _ in out if p), default=0)
    return out, skipped, n_positions


def _slope_block(persona_points: list[list[tuple[int, float]]], n_boot: int, seed: int):
    """Pooled least-squares slope of score on position, plus a 90% bootstrap range that
    resamples PERSONAS (all of a persona's answers stay together)."""
    suff = []
    for pts in persona_points:
        if pts:
            suff.append((len(pts), sum(x for x, _ in pts), sum(y for _, y in pts),
                         sum(x * x for x, _ in pts), sum(x * y for x, y in pts)))
    tot = [sum(s[i] for s in suff) for i in range(5)] if suff else [0] * 5
    slope = _ols_slope(*tot)
    if slope is None:
        return None, None, None
    rng = random.Random(seed)
    m = len(suff)
    est = []
    for _ in range(n_boot):
        acc = [0.0] * 5
        for _ in range(m):
            s = suff[rng.randrange(m)]
            for i in range(5):
                acc[i] += s[i]
        b = _ols_slope(*acc)
        if b is not None:
            est.append(b)
    est.sort()
    return slope, _percentile(est, 5), _percentile(est, 95)


def _balance_chi2(pos_lists: list[dict], brand_ids: Sequence[str], n_pos: int) -> Optional[float]:
    """Chi-square of the brand x position count table against an even spread (expected = row
    total x column total / grand total)."""
    counts = {b: [0] * n_pos for b in brand_ids}
    for pos in pos_lists:
        for b, p in pos.items():
            counts[b][p - 1] += 1
    tot = sum(sum(c) for c in counts.values())
    if not tot:
        return None
    row_t = {b: sum(counts[b]) for b in brand_ids}
    col_t = [sum(counts[b][j] for b in brand_ids) for j in range(n_pos)]
    return sum((counts[b][j] - row_t[b] * col_t[j] / tot) ** 2 / (row_t[b] * col_t[j] / tot)
               for b in brand_ids for j in range(n_pos) if row_t[b] and col_t[j])


def _balance_p_sim(pos_lists: list[dict], brand_ids: Sequence[str], n_pos: int, obs: float,
                   n_sim: int, seed: int) -> float:
    """Monte Carlo p: how often truly uniform shuffles give a chi-square at least this big.
    (The textbook chi-square p is wrong here: each persona sees each brand and each position
    exactly once, which makes cell counts about 12/11 more variable than the formula assumes.)"""
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_sim):
        sim = []
        for pos in pos_lists:
            bs = list(pos)
            sim.append(dict(zip(bs, rng.sample(range(1, n_pos + 1), len(bs)))))
        if _balance_chi2(sim, brand_ids, n_pos) >= obs - 1e-9:
            hits += 1
    return (hits + 1) / (n_sim + 1)


def _position_perm_p(persona_points: list[list[tuple[int, float]]], n_pos: int, n_perm: int, seed: int):
    """Randomization test for ANY position effect (not just a straight line).

    Statistic: between-position sum of squares of the scores, sum_p n_p * mean_p^2 (scores are
    brand-centered by the caller). Null: shuffle each persona's positions among its own answers,
    which is exactly how the survey randomized. Returns the share of shuffles at least as extreme.
    """
    def stat(points_iter):
        sums, ns = [0.0] * n_pos, [0] * n_pos
        for pts in points_iter:
            for p, v in pts:
                sums[p - 1] += v
                ns[p - 1] += 1
        return sum(s * s / n for s, n in zip(sums, ns) if n)

    obs = stat(persona_points)
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_perm):
        shuffled = []
        for pts in persona_points:
            pos = [p for p, _ in pts]
            rng.shuffle(pos)
            shuffled.append(list(zip(pos, (v for _, v in pts))))
        if stat(shuffled) >= obs - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def order_effect(csv_path: str, brand_ids: Sequence[str], n_boot: int = 2000,
                 seed: int = compare.DEFAULT_SEED, n_perm: int = 1000) -> dict:
    """Does the position a brand was shown in change its SAY and INTENT score?

    Reads the 'Display Order' column (pipe-delimited brand order each persona saw). For each
    question: mean score at each position, the least-squares slope of score on position (points
    per position later) with a 90% bootstrap range over personas, the same slope after removing
    each brand's own average ("brand-centered", less noisy), and mean score when shown first vs
    last. Order was randomized, so with no position bias the slope should be about 0.
    """
    brand_ids = list(brand_ids)
    data, skipped, n_pos = _read_order_rows(csv_path, brand_ids)
    # How evenly the shuffle spread each brand over the positions (randomization check).
    pos_counts = {b: [0] * n_pos for b in brand_ids}
    for _, pos, _ in data:
        for b, p in pos.items():
            pos_counts[b][p - 1] += 1

    out_q = {}
    for k in RATING_KINDS:
        by_pos = [[] for _ in range(n_pos)]
        brand_vals: dict[str, list[float]] = {}
        for _, pos, sc in data:
            for b, v in sc[k].items():
                by_pos[pos[b] - 1].append(v)
                brand_vals.setdefault(b, []).append(v)
        bmean = {b: sum(v) / len(v) for b, v in brand_vals.items()}
        raw_pts = [[(pos[b], v) for b, v in sc[k].items()] for _, pos, sc in data]
        cen_pts = [[(pos[b], v - bmean[b]) for b, v in sc[k].items()] for _, pos, sc in data]
        slope, lo, hi = _slope_block(raw_pts, n_boot, seed)
        cslope, clo, chi = _slope_block(cen_pts, n_boot, seed)
        means = [(sum(v) / len(v)) if v else None for v in by_pos]
        cen_by_pos = [[] for _ in range(n_pos)]
        for pts in cen_pts:
            for p, v in pts:
                cen_by_pos[p - 1].append(v)
        cen_means = [(sum(v) / len(v)) if v else None for v in cen_by_pos]
        any_p = _position_perm_p(cen_pts, n_pos, n_perm, seed) if n_pos and n_perm else None
        first, last = (means[0], means[-1]) if n_pos else (None, None)
        out_q[k] = {
            "mean_by_position": [_r(m) for m in means],
            "brand_centered_mean_by_position": [_r(m) for m in cen_means],
            "n_by_position": [len(v) for v in by_pos],
            "any_position_effect_p": _r(any_p),
            "slope_per_position": _r(slope),
            "slope_low": _r(lo), "slope_high": _r(hi),
            "could_be_chance": compare.could_be_chance(lo, hi),
            "drift_first_to_last": _r(slope * (n_pos - 1)) if slope is not None else None,
            "slope_brand_centered": _r(cslope),
            "slope_brand_centered_low": _r(clo), "slope_brand_centered_high": _r(chi),
            "brand_centered_could_be_chance": compare.could_be_chance(clo, chi),
            "mean_first": _r(first), "mean_last": _r(last),
            "first_minus_last": _r(first - last) if first is not None and last is not None else None,
        }

    def one(k):
        q = out_q[k]
        if q["slope_per_position"] is None:
            return f"{k.upper()}: not enough data."
        direction = "falls" if q["slope_per_position"] < 0 else "rises"
        verdict = ("no steady drift (could be chance)" if q["could_be_chance"] and q["brand_centered_could_be_chance"]
                   else "a steady drift: position bias in the AI crowd")
        anyp = q["any_position_effect_p"]
        extra = "" if anyp is None else f" Any-position test p = {anyp}."
        return (f"{k.upper()} {direction} {abs(q['slope_per_position'])} points per position later "
                f"(90% range {q['slope_low']} to {q['slope_high']}; brand-centered {q['slope_brand_centered']}, "
                f"{q['slope_brand_centered_low']} to {q['slope_brand_centered_high']}); "
                f"shown first {q['mean_first']} vs last {q['mean_last']}: {verdict}.{extra}")

    counts_flat = [c for b in brand_ids for c in pos_counts[b]]
    # Was the shuffle even? Chi-square of brand x position counts, p from simulated uniform shuffles.
    chi2 = chi_p = None
    if data and n_pos > 1 and len(brand_ids) > 1 and n_perm:
        pos_lists = [pos for _, pos, _ in data]
        chi2 = _balance_chi2(pos_lists, brand_ids, n_pos)
        if chi2 is not None:
            chi_p = _balance_p_sim(pos_lists, brand_ids, n_pos, chi2, n_perm, seed)
    return {
        "label": SYNTHETIC,
        "summary": " ".join(one(k) for k in RATING_KINDS),
        "n_personas": len(data),
        "n_positions": n_pos,
        "brands": brand_ids,
        "questions": out_q,
        "shuffle_check": {"min_times_a_brand_sat_at_a_position": min(counts_flat, default=None),
                          "max_times_a_brand_sat_at_a_position": max(counts_flat, default=None),
                          "expected_if_even": _r(len(data) / n_pos) if n_pos else None,
                          "chi_square": _r(chi2), "p_vs_uniform_shuffle": _r(chi_p),
                          "note": ("Uneven spread means raw position means mix in brand differences; "
                                   "the brand-centered numbers remove that.")},
        "rows_skipped": skipped,
        "n_boot": n_boot,
        "seed": seed,
        "note": "Bootstrap resamples personas, so one persona's 12 answers stay together.",
    }


# ----------------------------------------------------------------------------- 3. compression

def _sd(values: Sequence[float]) -> Optional[float]:
    n = len(values)
    if n < 2:
        return None
    m = sum(values) / n
    return math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))


def compression(panel_responses: Sequence[dict], real_reference: Optional[dict] = None,
                brand_ids: Optional[Sequence[str]] = None) -> dict:
    """How squeezed the AI crowd's 1-10 answers are, per question (say, intent).

    Reports the share of answers that are 5, 6 or 7, the sample standard deviation (n-1) of all
    answers, the count of each value 1..10, the brand means and their spread (max - min), and
    the median standard error of a brand mean (spread / SE says whether the brand differences
    are bigger than the noise). Describes the AI's answers ONLY.

    real_reference: optional {"source": "<citation>", ...}; passed through untouched and only
    when it names a source. Without one, nothing here says anything about real humans.
    brand_ids: optional filter (e.g. the 6 brands in the main result).
    """
    if real_reference is not None and not (isinstance(real_reference, dict) and str(real_reference.get("source") or "").strip()):
        raise ValueError("real_reference must be a dict with a non-empty 'source'")
    keep = set(brand_ids) if brand_ids is not None else None
    rows = [r for r in panel_responses if keep is None or r.get("brand_id") in keep]
    out_q = {}
    for k in RATING_KINDS:
        vals, per_brand = [], {}
        for r in rows:
            v = r.get(k)
            if compare._is_number(v) and compare.SCALE_MIN <= v <= compare.SCALE_MAX:
                vals.append(float(v))
                per_brand.setdefault(r.get("brand_id"), []).append(float(v))
        counts = {str(i): sum(1 for v in vals if v == i) for i in range(1, 11)}
        bmeans = {b: sum(v) / len(v) for b, v in per_brand.items()}
        ses = sorted(_sd(v) / math.sqrt(len(v)) for v in per_brand.values() if len(v) >= 2)
        spread = (max(bmeans.values()) - min(bmeans.values())) if bmeans else None
        se_med = _percentile(ses, 50) if ses else None
        out_q[k] = {
            "n_answers": len(vals),
            "mean": _r(sum(vals) / len(vals)) if vals else None,
            "share_5_to_7": _r(sum(1 for v in vals if 5 <= v <= 7) / len(vals)) if vals else None,
            "sd": _r(_sd(vals)),
            "counts_1_to_10": counts,
            "brand_means": {b: _r(m) for b, m in sorted(bmeans.items(), key=lambda kv: -kv[1])},
            "brand_mean_spread": _r(spread),
            "n_brands": len(bmeans),
            "median_se_of_brand_mean": _r(se_med),
            "spread_in_se_units": _r(spread / se_med) if spread is not None and se_med else None,
        }

    def one(k):
        q = out_q[k]
        if not q["n_answers"]:
            return f"{k.upper()}: no answers."
        return (f"{k.upper()}: {round(100 * q['share_5_to_7'])}% of {q['n_answers']} AI answers are 5-7 "
                f"(SD {q['sd']}); the {q['n_brands']} brand means span {q['brand_mean_spread']} points "
                f"on a 1-10 scale (typical brand-mean noise +/- {q['median_se_of_brand_mean']}).")

    return {
        "label": SYNTHETIC,
        "summary": " ".join(one(k) for k in RATING_KINDS) + " Describes the AI crowd only; no claim about real people.",
        "questions": out_q,
        "real_reference": real_reference,
        "real_reference_note": (None if real_reference else
                                "No sourced data on how real people answer these questions, so no comparison is made."),
    }


# ----------------------------------------------------------------------------- 4. crowd vs crowd

def crowd_vs_crowd(main_panel_responses: Sequence[dict], repeat_panel_responses: Sequence[dict],
                   brand_ids: Sequence[str], revenue_by_brand: dict, n_boot: int = 2000,
                   seed: int = compare.DEFAULT_SEED) -> dict:
    """Do two independent AI crowds agree with EACH OTHER more than either agrees with revenue?

    Per question (say, intent, fame): Spearman of main vs repeat brand means, of each crowd vs
    revenue, and gap = crowd-crowd minus the BETTER of the two crowd-revenue numbers (it must
    beat both). The gap's 90% range is a paired bootstrap over brands (all three numbers
    recomputed on the same resample). Exact permutation p-values are given for <= 8 brands.
    """
    sm, sr = compare.brand_stats(main_panel_responses), compare.brand_stats(repeat_panel_responses)
    out_q = {}
    used_by_q = {}
    for q, field in compare.QUESTION_FIELD.items():
        ids = [b for b in brand_ids
               if (sm.get(b) or {}).get(field) is not None and (sr.get(b) or {}).get(field) is not None
               and compare._is_number(revenue_by_brand.get(b))]
        used_by_q[q] = ids
        m = [sm[b][field] for b in ids]
        r = [sr[b][field] for b in ids]
        v = [float(revenue_by_brand[b]) for b in ids]
        cc = compare.spearman_from_values(m, r)
        mr = compare.spearman_from_values(m, v)
        rr = compare.spearman_from_values(r, v)
        gap = (cc - max(mr, rr)) if None not in (cc, mr, rr) else None
        lo = hi = None
        if gap is not None:
            rng = random.Random(seed)
            n = len(ids)
            est = []
            for _ in range(n_boot):
                idx = [rng.randrange(n) for _ in range(n)]
                a = compare.spearman_from_values([m[i] for i in idx], [r[i] for i in idx])
                b1 = compare.spearman_from_values([m[i] for i in idx], [v[i] for i in idx])
                b2 = compare.spearman_from_values([r[i] for i in idx], [v[i] for i in idx])
                if None not in (a, b1, b2):
                    est.append(a - max(b1, b2))
            if est:
                est.sort()
                lo, hi = _percentile(est, 5), _percentile(est, 95)
        wob = compare.bootstrap_wobble(list(zip(m, r)), n_boot=n_boot, seed=seed) if cc is not None else None
        out_q[q] = {
            "n_brands": len(ids),
            "crowd_vs_crowd": _r(cc),
            "crowd_vs_crowd_low": _r(wob[0]) if wob else None,
            "crowd_vs_crowd_high": _r(wob[1]) if wob else None,
            "crowd_vs_crowd_perm_p": _r(exact_perm_p(m, r)),
            "main_vs_revenue": _r(mr),
            "main_vs_revenue_perm_p": _r(exact_perm_p(m, v)),
            "repeat_vs_revenue": _r(rr),
            "repeat_vs_revenue_perm_p": _r(exact_perm_p(r, v)),
            "gap": _r(gap),
            "gap_low": _r(lo), "gap_high": _r(hi),
            "higher_than_both": gap is not None and gap > 0,
            "clearly_higher": lo is not None and lo > 0,
        }

    i = out_q["intent"]
    if i["gap"] is None:
        summary = "Not enough brands with data in both crowds to compare."
    else:
        summary = (f"On intent, the two AI crowds agree with each other at {i['crowd_vs_crowd']} but with real "
                   f"revenue at only {i['main_vs_revenue']} and {i['repeat_vs_revenue']} "
                   f"(gap {i['gap']}, 90% range {i['gap_low']} to {i['gap_high']}, {i['n_brands']} brands): "
                   + ("the AI crowd is consistent, but consistently measuring something other than spending."
                      if i["higher_than_both"] else "the crowds do not agree with each other more than with revenue.")
                   + f" Say: {out_q['say']['crowd_vs_crowd']} vs {out_q['say']['main_vs_revenue']}/{out_q['say']['repeat_vs_revenue']}."
                   + f" Fame: {out_q['fame']['crowd_vs_crowd']} vs {out_q['fame']['main_vs_revenue']}/{out_q['fame']['repeat_vs_revenue']}.")
    return {
        "label": SYNTHETIC,
        "summary": summary,
        "brands": list(brand_ids),
        "questions": out_q,
        "n_boot": n_boot,
        "seed": seed,
        "note": ("Both crowds come from the same persona generator, so their agreement shows the AI is "
                 "repeatable, not that it is right."),
    }
