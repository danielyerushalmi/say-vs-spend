"""All the math: shares, gaps, correction rules, the dumb fix, leave-one-out, the exam.

Pure standard-library code. Shares are fractions that sum to 1; gaps and rule
adjustments are percentage points (pp). No model ever computes a number here.
"""
from __future__ import annotations

import copy
import operator
from typing import Any

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
OPS = {
    "==": operator.eq, "!=": operator.ne, ">": operator.gt,
    "<": operator.lt, ">=": operator.ge, "<=": operator.le,
}
MIN_MATCHING = 3   # a rule must match at least this many training stations
MIN_IMPROVED = 3   # ... and improve at least this many of them (leave-one-out)

_exam_used = False


def normalize(counts: dict) -> dict:
    """Turn panel counts into Mon-Fri shares summing to 1. Ignores "None" and unknown keys."""
    vals = {d: max(float(counts.get(d, 0) or 0), 0.0) for d in DAYS}
    total = sum(vals.values())
    if total <= 0:
        raise ValueError("no weekday counts to normalize")
    return {d: vals[d] / total for d in DAYS}


def gap_pp(a: dict, b: dict) -> float:
    """Mean absolute difference over Mon-Fri between two share dicts, in percentage points."""
    return sum(abs(a[d] - b[d]) for d in DAYS) / len(DAYS) * 100.0


def _matches(when: dict | None, features: dict) -> bool:
    """True if the rule's condition holds. No condition matches all; a missing feature never matches."""
    if when is None:
        return True
    op = when.get("op")
    if op not in OPS:
        raise ValueError(f"unknown op {op!r}; expected one of {sorted(OPS)}")
    feature = when.get("feature")
    if feature not in features or features[feature] is None:
        return False
    try:
        return bool(OPS[op](features[feature], when.get("value")))
    except TypeError:  # e.g. "Brooklyn" > 5
        return False


def _usable(st: dict) -> bool:
    return bool(st.get("synthetic")) and bool(st.get("measured"))


def _apply_adjust(synth: dict, adjust: dict) -> dict:
    """Add pp to each day, clip at 0, renormalize to sum 1."""
    raw = {d: max(synth[d] + adjust.get(d, 0.0) / 100.0, 0.0) for d in DAYS}
    total = sum(raw.values())
    if total <= 0:  # every day clipped to zero: refuse to invent a shape
        return dict(synth)
    return {d: raw[d] / total for d in DAYS}


def fit_adjust(rule: dict, stations: list[dict]) -> dict:
    """Per-day mean (measured - synthetic) in pp over stations matching the rule's "when".

    Stations lacking synthetic or measured shares are skipped. If nothing matches, all zeros.
    """
    rows = [s for s in stations if _usable(s) and _matches(rule.get("when"), s.get("features", {}))]
    if not rows:
        return {d: 0.0 for d in DAYS}
    fitted = {d: sum(s["measured"][d] - s["synthetic"][d] for s in rows) / len(rows) * 100.0 for d in DAYS}
    # The coach names which days move and which way (+/-, 0 = leave alone). Code only picks the size,
    # so a day the coach left alone, or a day whose data points the other way, gets no adjustment.
    # An empty adjust (the dumb fix) leaves every day free.
    directions = rule.get("adjust") or {}
    if directions:
        for d in DAYS:
            want = directions.get(d, 0.0)
            if want == 0 or (want > 0) != (fitted[d] > 0):
                fitted[d] = 0.0
    return fitted


def apply_rules(synth: dict, features: dict, rules: list[dict]) -> dict:
    """Apply each matching rule's adjust in order (add pp, clip at 0, renormalize each time)."""
    out = dict(synth)
    for rule in rules:
        if _matches(rule.get("when"), features):
            out = _apply_adjust(out, rule["adjust"])
    return out


def dumb_fix(train: list[dict]) -> dict:
    """The baseline rule: shift every day by the average training error. No condition."""
    rule = {"id": "dumb_fix", "text": "Shift every day by the average training error (no condition).",
            "when": None, "adjust": {}}
    rule["adjust"] = fit_adjust(rule, train)
    return rule


def _loo_gaps(rule: dict, train: list[dict]) -> list[tuple[float, float]]:
    """For each usable training station: (gap with no correction, gap with the LOO-fitted rule)."""
    rows = [s for s in train if _usable(s)]
    out = []
    for i, st in enumerate(rows):
        others = rows[:i] + rows[i + 1:]
        adjust = fit_adjust(rule, others)
        fitted = dict(rule, adjust=adjust)
        corrected = apply_rules(st["synthetic"], st.get("features", {}), [fitted])
        out.append((gap_pp(st["synthetic"], st["measured"]), gap_pp(corrected, st["measured"])))
    return out


def evaluate_rule(rule: dict, train: list[dict]) -> dict:
    """Skeptic test: leave-one-out gap of the rule vs the dumb fix on training stations only.

    Keep only if it matches >= 3 stations, improves >= 3, and has a lower LOO gap than the dumb fix.
    """
    rows = [s for s in train if _usable(s)]
    matching = sum(1 for s in rows if _matches(rule.get("when"), s.get("features", {})))
    if not rows:
        return {"stations_matching": 0, "stations_improved": 0, "loo_gap": 0.0, "loo_gap_dumb": 0.0,
                "beats_dumb_fix": False, "keep": False, "reason": "No usable training stations."}
    rule_pairs = _loo_gaps(rule, rows)
    dumb_pairs = _loo_gaps(dumb_fix_template(), rows)
    n = len(rows)
    loo_gap = sum(g for _, g in rule_pairs) / n
    loo_dumb = sum(g for _, g in dumb_pairs) / n
    improved = sum(1 for base, g in rule_pairs if g < base - 1e-12)
    beats = loo_gap < loo_dumb
    keep = matching >= MIN_MATCHING and improved >= MIN_IMPROVED and beats
    reason = (f"Matches {matching} training stations and improves {improved} of them in leave-one-out; "
              f"average gap {loo_gap:.2f} pp vs {loo_dumb:.2f} pp for the dumb fix, so it "
              + ("is kept." if keep else "is thrown out"
                 + _why_not(matching, improved, beats) + "."))
    return {"stations_matching": matching, "stations_improved": improved, "loo_gap": loo_gap,
            "loo_gap_dumb": loo_dumb, "beats_dumb_fix": beats, "keep": keep, "reason": reason}


def dumb_fix_template() -> dict:
    """A condition-free rule used to fit the dumb fix inside leave-one-out."""
    return {"id": "dumb_fix", "text": "dumb fix", "when": None, "adjust": {}}


def _why_not(matching: int, improved: int, beats: bool) -> str:
    bits = []
    if matching < MIN_MATCHING:
        bits.append(f"matches fewer than {MIN_MATCHING} stations")
    if improved < MIN_IMPROVED:
        bits.append(f"improves fewer than {MIN_IMPROVED}")
    if not beats:
        bits.append("does not beat the dumb fix")
    return " (" + "; ".join(bits) + ")" if bits else ""


def refit_rules(rules: list[dict], train: list[dict]) -> list[dict]:
    """Copy the rules with adjust refit on ALL training stations (do this before the exam)."""
    return [dict(copy.deepcopy(r), adjust=fit_adjust(r, train)) for r in rules]


def exam(exam_stations: list[dict], kept_rules: list[dict], dumb_rule: dict) -> dict:
    """Score the locked exam stations once. Raises RuntimeError on a second call in this process.

    Returns per-station gaps (before, after kept rules, after dumb fix) and their means.
    Stations missing synthetic or measured shares are listed with None gaps and left out of the means.
    """
    global _exam_used
    if _exam_used:
        raise RuntimeError("exam() already ran in this process; the exam stations are locked")
    _exam_used = True
    per_station = []
    for st in exam_stations:
        if not _usable(st):
            per_station.append({"id": st.get("id"), "gap_before_pp": None,
                                "gap_after_pp": None, "gap_dumbfix_pp": None})
            continue
        feats = st.get("features", {})
        after = apply_rules(st["synthetic"], feats, kept_rules)
        dumb = apply_rules(st["synthetic"], feats, [dumb_rule])
        per_station.append({"id": st.get("id"),
                            "gap_before_pp": gap_pp(st["synthetic"], st["measured"]),
                            "gap_after_pp": gap_pp(after, st["measured"]),
                            "gap_dumbfix_pp": gap_pp(dumb, st["measured"])})
    scored = [p for p in per_station if p["gap_before_pp"] is not None]

    def mean(key: str) -> float | None:
        return sum(p[key] for p in scored) / len(scored) if scored else None

    before, after, dumb = mean("gap_before_pp"), mean("gap_after_pp"), mean("gap_dumbfix_pp")
    helped = bool(scored) and after < before
    return {"per_station": per_station, "gap_before": before, "gap_after": after,
            "gap_dumb": dumb, "helped": helped}


def _reset_exam_for_tests_only() -> None:
    """Re-arm the one-shot exam guard. Tests only; the real pipeline must never call this."""
    global _exam_used
    _exam_used = False


def summarize_exam(result: dict) -> tuple[dict, dict]:
    """Split an exam() result into (summary block, per-station fields) for the run file.

    summary: exam_gap_before_pp / exam_gap_after_pp / exam_gap_dumbfix_pp / coaching_helped.
    per-station: {station_id: {gap_before_pp, gap_after_pp, gap_dumbfix_pp}}.
    """
    summary = {"exam_gap_before_pp": result["gap_before"], "exam_gap_after_pp": result["gap_after"],
               "exam_gap_dumbfix_pp": result["gap_dumb"], "coaching_helped": result["helped"]}
    fields = {p["id"]: {k: p[k] for k in ("gap_before_pp", "gap_after_pp", "gap_dumbfix_pp")}
              for p in result["per_station"]}
    return summary, fields


def noise_pp(counts: dict, n_boot: int = 1000, seed: int = 0) -> float | None:
    """Chance wobble of a panel, in pp (ESTIMATE).

    Panel answers come as counts per day (multi-select), not per person, so we resample the
    day-selections themselves: draw the same number of selections from the panel's own shares,
    1,000 times, and take the 90th percentile of the gap between each redraw and the original.
    A gap smaller than this could be chance alone.
    """
    import random
    total = sum(int(counts.get(d, 0)) for d in DAYS)
    if total <= 0:
        return None
    shares = normalize(counts)
    rng = random.Random(seed)
    weights = [shares[d] for d in DAYS]
    gaps = []
    for _ in range(n_boot):
        draw = {d: 0 for d in DAYS}
        for d in rng.choices(DAYS, weights=weights, k=total):
            draw[d] += 1
        gaps.append(gap_pp(normalize(draw), shares))
    gaps.sort()
    return gaps[int(0.9 * (n_boot - 1))]


def band_hits(exam_rows: list[dict]) -> tuple[int, int]:
    """How many exam stations landed inside the error band the agent predicted BEFORE the exam.

    Each row needs "gap_after_pp" and "predicted_error_band_pp" = [low, high]. Rows without both are skipped.
    """
    scored = [r for r in exam_rows
              if r.get("gap_after_pp") is not None and r.get("predicted_error_band_pp")]
    hits = sum(1 for r in scored
               if r["predicted_error_band_pp"][0] <= r["gap_after_pp"] <= r["predicted_error_band_pp"][1])
    return hits, len(scored)
