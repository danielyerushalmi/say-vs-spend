"""The math core of Say vs. Spend. Pure functions, standard library only.

Every number shown to a judge is computed here, in code (never by an LLM).

Conventions
- Rank 1 = best (highest value). Tied values share the average of the ranks they span.
- Spearman = Pearson correlation of the two rank lists (the version that handles ties).
- The three crowd measures are compared against revenue: "say" (say_mean), "intent"
  (intent_mean) and "fame" (aware_share, the share of the panel that has heard of the brand).
"""
from __future__ import annotations

import math
import random
from typing import Iterable, Optional, Sequence

QUESTIONS = ("say", "intent", "fame")
# Which brand field feeds each question's crowd ranking.
QUESTION_FIELD = {"say": "say_mean", "intent": "intent_mean", "fame": "aware_share"}
SCALE_MIN, SCALE_MAX = 1, 10
MIN_BRANDS = 3  # below this a rank correlation is meaningless
DEFAULT_SEED = 20261114
NICHE_MAX = 0.30          # a brand is "niche" when buy_share is strictly under this
MIN_BUYER_RESPONDENTS = 10  # buyers-only view: fewer "buy = yes" respondents than this -> brand left out

# PRE-REGISTERED 2026-11-14 11:47 (decisions.md), before any panel result existed.
TRUST_MIN = 0.7
VERIFY_MIN = 0.4
TRUST_RULE_TEXT = (
    "Pre-registered 2026-11-14 11:47; amended 12:10 after the panel ran but BEFORE any result was "
    "computed or seen: the label comes from the LOW end of the 90% wobble range (5th percentile of a "
    "bootstrap over brands) of the Spearman rank agreement between the crowd's intent ranking and "
    "the revenue ranking. Low end 0.7 or higher = trust it; 0.4 to under 0.7 = double-check it; "
    "under 0.4 = ask real people."
)


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isnan(v)


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def brand_stats(responses: Iterable[dict]) -> dict[str, dict]:
    """Per-brand averages from raw per-respondent rows.

    Each row: {"brand_id", "say": 1-10, "intent": 1-10, "aware": bool, ...}.
    A missing value (absent, null, wrong type, or outside 1-10 for ratings) is skipped for
    THAT question only; the row still counts for the other questions.
    Optional "buy" (bool, "is this a kind of product you buy?") gives buy_share / n_buy.
    Returns {brand_id: {say_mean, intent_mean, aware_share, n_say, n_intent, n_aware,
    buy_share, n_buy}}; a mean (or buy_share) is None when the brand has no usable answers for that question.
    """
    say: dict[str, list[float]] = {}
    intent: dict[str, list[float]] = {}
    aware: dict[str, list[bool]] = {}
    buy: dict[str, list[bool]] = {}
    for row in responses:
        bid = row.get("brand_id")
        if not bid:
            continue
        say.setdefault(bid, [])
        intent.setdefault(bid, [])
        aware.setdefault(bid, [])
        buy.setdefault(bid, [])
        for key, bucket in (("say", say), ("intent", intent)):
            v = row.get(key)
            if _is_number(v) and SCALE_MIN <= v <= SCALE_MAX:
                bucket[bid].append(float(v))
        a = row.get("aware")
        if isinstance(a, bool):
            aware[bid].append(a)
        b = row.get("buy")
        if isinstance(b, bool):
            buy[bid].append(b)
    out: dict[str, dict] = {}
    for bid in say:
        out[bid] = {
            "say_mean": _mean(say[bid]),
            "intent_mean": _mean(intent[bid]),
            "aware_share": (sum(aware[bid]) / len(aware[bid])) if aware[bid] else None,
            "n_say": len(say[bid]),
            "n_intent": len(intent[bid]),
            "n_aware": len(aware[bid]),
            "buy_share": (sum(buy[bid]) / len(buy[bid])) if buy[bid] else None,
            "n_buy": len(buy[bid]),
        }
    return out


def ranks(values: Sequence[float], higher_is_better: bool = True) -> list[float]:
    """Average ranks (rank 1 = best). Tied values share the mean of the ranks they occupy."""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i], reverse=higher_is_better)
    result = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1  # positions i..j are ranks i+1..j+1
        for k in range(i, j + 1):
            result[order[k]] = avg
        i = j + 1
    return result


def spearman(x_ranks: Sequence[float], y_ranks: Sequence[float]) -> Optional[float]:
    """Pearson correlation of two rank lists. None if fewer than 3 items, unequal lengths,
    or either list has zero variance (everything tied)."""
    n = len(x_ranks)
    if n < MIN_BRANDS or n != len(y_ranks):
        return None
    mx, my = sum(x_ranks) / n, sum(y_ranks) / n
    sxx = sum((a - mx) ** 2 for a in x_ranks)
    syy = sum((b - my) ** 2 for b in y_ranks)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((a - mx) * (b - my) for a, b in zip(x_ranks, y_ranks))
    return max(-1.0, min(1.0, sxy / math.sqrt(sxx * syy)))


def spearman_from_values(crowd: Sequence[float], revenue: Sequence[float]) -> Optional[float]:
    """Convenience: rank both lists (higher = better) and return their Spearman."""
    return spearman(ranks(crowd), ranks(revenue))


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile (q in 0..100) of an already sorted list."""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q / 100
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def bootstrap_wobble(
    pairs: Sequence[tuple[float, float]], n_boot: int = 2000, seed: int = DEFAULT_SEED
) -> Optional[tuple[float, float]]:
    """How much the Spearman would wobble if we had drawn different brands.

    pairs = [(crowd_value, revenue), ...], one per brand. Resample the brands with
    replacement n_boot times, recompute Spearman each time (re-ranking inside the
    resample), skip degenerate resamples (zero variance), and return the 5th and 95th
    percentiles (the middle 90%). None if fewer than 3 brands or no valid resample.
    Same seed gives the same answer.
    """
    n = len(pairs)
    if n < MIN_BRANDS:
        return None
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(n_boot):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        rho = spearman_from_values([p[0] for p in sample], [p[1] for p in sample])
        if rho is not None:
            estimates.append(rho)
    if not estimates:
        return None
    estimates.sort()
    return _percentile(estimates, 5), _percentile(estimates, 95)


def could_be_chance(low: Optional[float], high: Optional[float]) -> bool:
    """True when the wobble range includes 0 (or could not be computed)."""
    if low is None or high is None:
        return True
    return low <= 0 <= high


def avg_places_off(rank_a: Sequence[float], rank_b: Sequence[float]) -> Optional[float]:
    """Mean absolute difference between two rank lists, in places. None if empty."""
    if not rank_a or len(rank_a) != len(rank_b):
        return None
    return sum(abs(a - b) for a, b in zip(rank_a, rank_b)) / len(rank_a)


EXACT_MAX_N = 8  # 8! = 40,320 orderings; above this p_exact is None


def exact_p(crowd_ranks: Sequence[float], rev_ranks: Sequence[float]) -> Optional[float]:
    """Exact two-sided permutation p-value for Spearman: the share of all n! orderings of the
    revenue ranks whose |rho| is at least the observed |rho|. None if n < 3 or n > EXACT_MAX_N."""
    import itertools
    n = len(crowd_ranks)
    if n < 3 or n > EXACT_MAX_N:
        return None
    obs = spearman(crowd_ranks, rev_ranks)
    if obs is None:
        return None
    hits = total = 0
    for perm in itertools.permutations(rev_ranks):
        r = spearman(crowd_ranks, list(perm))
        total += 1
        if r is not None and abs(r) >= abs(obs) - 1e-12:
            hits += 1
    return hits / total


def agreement(brands: Sequence[dict], question: str, n_boot: int = 2000, seed: int = DEFAULT_SEED) -> dict:
    """Agreement between one crowd measure and revenue.

    brands: dicts with "revenue_usd" and the field for `question` (say_mean / intent_mean /
    aware_share). Brands missing either value are left out of this question.
    Returns {spearman, wobble_low, wobble_high, could_be_chance, avg_places_off, p_exact}; the
    numbers are None when there are fewer than 3 usable brands. could_be_chance is True when the
    wobble range crosses 0 OR the exact permutation p-value is above 0.05 (red-team fix 12:45:
    the bootstrap alone is unreliable with 5-6 brands).
    """
    field = QUESTION_FIELD[question]
    usable = [b for b in brands if _is_number(b.get(field)) and _is_number(b.get("revenue_usd"))]
    crowd = [float(b[field]) for b in usable]
    rev = [float(b["revenue_usd"]) for b in usable]
    crowd_ranks, rev_ranks = ranks(crowd), ranks(rev)
    rho = spearman(crowd_ranks, rev_ranks)
    wob = bootstrap_wobble(list(zip(crowd, rev)), n_boot=n_boot, seed=seed) if rho is not None else None
    low, high = wob if wob else (None, None)
    p = exact_p(crowd_ranks, rev_ranks) if rho is not None else None
    chance = could_be_chance(low, high) or (p is not None and p > 0.05)
    return {
        "spearman": rho,
        "wobble_low": low,
        "wobble_high": high,
        "p_exact": p,
        "could_be_chance": chance,
        "avg_places_off": avg_places_off(crowd_ranks, rev_ranks) if rho is not None else None,
    }


def top_gaps(brands: Sequence[dict], question: str, k: int = 3) -> list[dict]:
    """The k brands where the crowd's rank is furthest from the revenue rank.

    brands: dicts with "id", "rank_<question>" and "rank_revenue" (rank_fame for fame).
    Sorted by |crowd_rank - revenue_rank| descending, ties broken by brand id.
    places_off is crowd_rank - revenue_rank (positive = crowd ranks the brand lower than
    its revenue does).
    """
    key = f"rank_{question}"
    rows = []
    for b in brands:
        c, r = b.get(key), b.get("rank_revenue")
        if _is_number(c) and _is_number(r):
            rows.append({"brand_id": b["id"], "question": question, "crowd_rank": c,
                         "revenue_rank": r, "places_off": c - r})
    rows.sort(key=lambda g: (-abs(g["places_off"]), g["brand_id"]))
    return rows[:k]


def _band(x: float) -> str:
    if x >= TRUST_MIN:
        return "trust"
    if x >= VERIFY_MIN:
        return "verify"
    return "ask_real_people"


def trust_verdict(
    intent_spearman: Optional[float], wobble_low: Optional[float], wobble_high: Optional[float]
) -> dict:
    """Apply the PRE-REGISTERED rule (amended 12:10, before any result). Returns
    {"verdict", "rule", "downgraded"}.

    The cutoffs are applied to wobble_low (the cautious end of the 90% range), not the point
    Spearman: >= 0.7 trust; 0.4 to < 0.7 verify; < 0.4 ask_real_people. No wobble_low ->
    ask_real_people. "downgraded" = the point Spearman alone would have earned a better label.
    """
    if wobble_low is None:
        return {"verdict": "ask_real_people", "rule": TRUST_RULE_TEXT, "downgraded": False}
    verdict = _band(wobble_low)
    order = ["ask_real_people", "verify", "trust"]
    downgraded = (intent_spearman is not None
                  and order.index(_band(intent_spearman)) > order.index(verdict))
    return {"verdict": verdict, "rule": TRUST_RULE_TEXT, "downgraded": downgraded}


def crowd_beat_fame(intent_spearman: Optional[float], fame_spearman: Optional[float]) -> bool:
    """True only if the intent Spearman is strictly greater than the fame Spearman."""
    if intent_spearman is None or fame_spearman is None:
        return False
    return intent_spearman > fame_spearman


def splits(
    responses: Sequence[dict], revenue_by_brand: dict[str, float],
    fields: Sequence[str] = ("age_group", "income_group"), n_boot: int = 1000, seed: int = DEFAULT_SEED,
) -> list[dict]:
    """Same agreement numbers, computed separately for each age / income group.

    Only groups that have data for at least 3 brands (with revenue) are kept. Each entry:
    {"by", "group", "n_responses", "n_brands", "agreement": {say, intent, fame}}.
    """
    out: list[dict] = []
    for field in fields:
        groups = sorted({str(r[field]) for r in responses if r.get(field) not in (None, "")})
        for g in groups:
            sub = [r for r in responses if str(r.get(field)) == g]
            stats = brand_stats(sub)
            rows = [{"id": bid, **s, "revenue_usd": revenue_by_brand.get(bid)} for bid, s in stats.items()]
            n_brands = sum(1 for r in rows if _is_number(r["intent_mean"]) and _is_number(r["revenue_usd"]))
            if n_brands < MIN_BRANDS:
                continue
            out.append({
                "by": field, "group": g, "n_responses": len(sub), "n_brands": n_brands,
                "agreement": {q: agreement(rows, q, n_boot=n_boot, seed=seed) for q in QUESTIONS},
            })
    return out


def is_niche(buy_share: Optional[float]) -> Optional[bool]:
    """True when fewer than NICHE_MAX (30%) of personas say they buy this kind of product.
    Exactly 0.30 is NOT niche. None when there is no BUY data."""
    if not _is_number(buy_share):
        return None
    return buy_share < NICHE_MAX


def buyers_intent_means(responses: Iterable[dict], min_yes: int = MIN_BUYER_RESPONDENTS) -> dict[str, Optional[float]]:
    """Per brand: mean intent using ONLY respondents with buy == True and a usable 1-10 intent.
    A brand with fewer than min_yes such respondents gets None."""
    vals: dict[str, list[float]] = {}
    for row in responses:
        bid = row.get("brand_id")
        if not bid:
            continue
        vals.setdefault(bid, [])
        v = row.get("intent")
        if row.get("buy") is True and _is_number(v) and SCALE_MIN <= v <= SCALE_MAX:
            vals[bid].append(float(v))
    return {bid: (_mean(v) if len(v) >= min_yes else None) for bid, v in vals.items()}


def buyers_only_agreement(brands: Sequence[dict], responses: Iterable[dict], min_yes: int = MIN_BUYER_RESPONDENTS,
                          n_boot: int = 2000, seed: int = DEFAULT_SEED) -> dict:
    """Intent-vs-revenue agreement using buyers-only intent means (same Spearman + bootstrap
    wobble as agreement()). brands: dicts with "id" and "revenue_usd". Brands under the cutoff
    are left out of the ladder. Returns agreement()'s keys plus "n_brands" (brands used)."""
    means = buyers_intent_means(responses, min_yes)
    rows = [{"intent_mean": means.get(b["id"]), "revenue_usd": b.get("revenue_usd")} for b in brands]
    usable = [r for r in rows if _is_number(r["intent_mean"]) and _is_number(r["revenue_usd"])]
    out = agreement(usable, "intent", n_boot=n_boot, seed=seed)
    out["n_brands"] = len(usable)
    return out
