"""Real people check: score a hand-collected tally against the AI crowd and against revenue.

The students ask ~10-20 people at the venue, by hand, one yes/no question per brand
(script: docs/REAL-PEOPLE-KIT.md). They type the paper tally into a CSV with ONLY these columns:

    respondent_n,brand_id,bought_12m,age_band
    1,thredup,no,under 25
    1,hims,no,
    2,thredup,yes,25-44

- respondent_n: 1, 2, 3 ... (a counter, never a name)
- brand_id: an id from the run file's brands[] (e.g. thredup)
- bought_12m: yes / no
- age_band: optional, blank or one of "under 25", "25-44", "45+"
Lines starting with "#" are comments and are skipped.

No names, emails, phone numbers, handles or photos. Any extra column is refused, and a
column whose header or values look like a name / email / phone is refused with a PII error.

Output (JSON): {"label": "REAL (convenience sample)", "display_label": "REAL (n=__, convenience sample)",
"n_people", "brands": [...], "agreement_with_crowd", "agreement_with_revenue", "caveat", ...}.
Per brand: share who said yes and a 90% Wilson score interval (z = 1.6448536..., the exact
95th percentile of the standard normal). Rankings compared with Spearman from say.compare.

CLI:  python3 -m say.real_check --csv <file> --run frontend/runs/say_latest.json --out <json>
      python3 -m say.real_check --print-script --run frontend/runs/say_latest.json
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
from statistics import NormalDist
from typing import Optional

from . import compare

LABEL = "REAL (convenience sample)"
REQUIRED_COLUMNS = ("respondent_n", "brand_id", "bought_12m")
OPTIONAL_COLUMNS = ("age_band",)
ALLOWED_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
AGE_BANDS = ("under 25", "25-44", "45+")
YES, NO = "yes", "no"
CONFIDENCE = 0.90
Z90 = NormalDist().inv_cdf(1 - (1 - CONFIDENCE) / 2)  # 1.6448536269514722
BRAND_QUESTION_TEMPLATE = "Have you bought anything from {name}'s website in the past 12 months?"
CONSENT_LINE = "It's for a student hackathon project, anonymous, one question, takes 10 seconds, OK?"

CAVEAT = (
    "Tiny convenience sample: people who happened to be at a tech hackathon and agreed to answer. "
    "NOT representative of US shoppers. With this few people the intervals are wide and the "
    "rankings can flip with one answer. This shows the loop being closed (AI crowd -> real people), "
    "not a finding."
)

# Header words that suggest personal data. Matched against the lower-cased header split into words.
PII_HEADER_WORDS = {
    "name", "names", "firstname", "lastname", "fullname", "first", "last", "surname",
    "email", "mail", "e-mail", "phone", "mobile", "cell", "tel", "telephone", "contact",
    "address", "street", "zip", "instagram", "insta", "twitter", "handle", "linkedin",
    "snapchat", "tiktok", "username", "user", "photo", "picture", "pic", "selfie", "dob",
    "birthday", "birthdate", "school", "id_number", "ssn",
}
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
PHONE_RE = re.compile(r"(?:\+?\d[\s().-]*){7,}")


class RealCheckError(ValueError):
    """The CSV was refused. The message says why, in plain words."""


class PIIError(RealCheckError):
    """The CSV looks like it holds personal information. Delete that column (or file) and retry."""


# ----------------------------------------------------------------------------- math

def wilson_interval(yes: int, n: int, z: float = Z90) -> Optional[tuple[float, float]]:
    """Wilson score interval for a proportion yes/n. None when n == 0.

    low, high = (p + z^2/2n -/+ z*sqrt(p(1-p)/n + z^2/4n^2)) / (1 + z^2/n)
    Default z is the exact two-sided 90% value (1.6448536...).
    """
    if n <= 0:
        return None
    if yes < 0 or yes > n:
        raise ValueError("yes must be between 0 and n")
    p = yes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = p + z2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    low = max(0.0, (centre - margin) / denom)
    high = min(1.0, (centre + margin) / denom)
    return low, high


# ----------------------------------------------------------------------------- CSV checks

def _header_words(header: str) -> set[str]:
    h = header.strip().lower()
    words = set(re.split(r"[^a-z0-9-]+", h)) - {""}
    words.add(re.sub(r"[^a-z0-9]", "", h))  # "First Name" -> "firstname"
    return words


def check_header(fieldnames: list[str]) -> None:
    """Refuse PII-looking columns first (louder error), then any other unknown column."""
    cleaned = [f.strip() for f in fieldnames]
    pii = [f for f in cleaned if f.lower() not in ALLOWED_COLUMNS and _header_words(f) & PII_HEADER_WORDS]
    if pii:
        raise PIIError(
            f"Refused: column(s) {pii} look like personal information (name, email, phone, handle...). "
            "This kit records NO names, NO contact info, NO photos. Delete the column(s) and try again."
        )
    unknown = [f for f in cleaned if f.lower() not in ALLOWED_COLUMNS]
    if unknown:
        raise RealCheckError(f"Refused: unknown column(s) {unknown}. Allowed: {list(ALLOWED_COLUMNS)}.")
    missing = [c for c in REQUIRED_COLUMNS if c not in [f.lower() for f in cleaned]]
    if missing:
        raise RealCheckError(f"Refused: missing column(s) {missing}. Need: {list(REQUIRED_COLUMNS)}.")
    if len(set(f.lower() for f in cleaned)) != len(cleaned):
        raise RealCheckError("Refused: a column name appears twice.")


def _looks_like_pii_value(value: str) -> bool:
    return bool(EMAIL_RE.search(value) or PHONE_RE.search(value))


def parse_csv_text(text: str, brand_ids: set[str]) -> list[dict]:
    """Validate and parse the tally CSV. Returns rows {respondent_n:int, brand_id, bought:bool, age_band}.

    Raises PIIError for personal-looking columns or values, RealCheckError for anything else wrong.
    """
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise RealCheckError("Refused: the CSV is empty.")
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    check_header(reader.fieldnames or [])
    key = {f: f.strip().lower() for f in reader.fieldnames}
    rows: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for line_no, raw in enumerate(reader, start=2):
        if None in raw:
            raise RealCheckError(f"Refused: line {line_no} has more cells than columns.")
        r = {key[k]: (v or "").strip() for k, v in raw.items()}
        for col, val in r.items():
            if _looks_like_pii_value(val):
                raise PIIError(
                    f"Refused: line {line_no}, column '{col}' holds something that looks like an email "
                    "or phone number. Record only the answer code. Remove it and try again."
                )
        try:
            rn = int(r["respondent_n"])
        except ValueError:
            raise RealCheckError(
                f"Refused: line {line_no}: respondent_n must be a counter (1, 2, 3 ...), got '{r['respondent_n']}'."
            ) from None
        if rn < 1:
            raise RealCheckError(f"Refused: line {line_no}: respondent_n must be 1 or more.")
        bid = r["brand_id"].lower()
        if bid not in brand_ids:
            raise RealCheckError(
                f"Refused: line {line_no}: brand_id '{r['brand_id']}' is not in the run file. Use one of {sorted(brand_ids)}."
            )
        ans = r["bought_12m"].lower()
        if ans not in (YES, NO):
            raise RealCheckError(f"Refused: line {line_no}: bought_12m must be yes or no, got '{r['bought_12m']}'.")
        age = r.get("age_band", "").lower()
        if age and age not in AGE_BANDS:
            raise RealCheckError(
                f"Refused: line {line_no}: age_band must be blank or one of {list(AGE_BANDS)}, got '{r.get('age_band')}'."
            )
        if (rn, bid) in seen:
            raise RealCheckError(f"Refused: line {line_no}: respondent {rn} answered {bid} twice.")
        seen.add((rn, bid))
        rows.append({"respondent_n": rn, "brand_id": bid, "bought": ans == YES, "age_band": age or None})
    if not rows:
        raise RealCheckError("Refused: the CSV has a header but no answers.")
    return rows


# ----------------------------------------------------------------------------- scoring

def _question_for(brand: dict, run: dict) -> str:
    """The one uniform yes/no buying question, the same wording for every brand.

    The scoring counts yes/no buying answers only, so trust_card.draft_question (drafted text that may be
    subjective) is never used here. It is reported separately as draft_question and never scored.
    """
    return BRAND_QUESTION_TEMPLATE.format(name=brand.get("name", brand["id"]))


def _agreement(real: dict[str, float], other: dict[str, float], what: str) -> dict:
    """Spearman between the real share ranking and another ranking, over brands both have."""
    ids = sorted(set(real) & set(other))
    out = {"compared_to": what, "n_brands": len(ids), "spearman": None,
           "wobble_low": None, "wobble_high": None, "could_be_chance": True}
    if len(ids) < compare.MIN_BRANDS:
        out["note"] = f"Fewer than {compare.MIN_BRANDS} brands with real answers: no ranking comparison."
        return out
    xs = [real[i] for i in ids]
    ys = [other[i] for i in ids]
    rho = compare.spearman(compare.ranks(xs), compare.ranks(ys))
    out["spearman"] = None if rho is None else round(rho, 4)
    if rho is None:
        out["note"] = "Every brand tied on one side (e.g. nobody said yes to anything): no ranking comparison."
        return out
    wob = compare.bootstrap_wobble(list(zip(xs, ys)))
    if wob:
        out["wobble_low"], out["wobble_high"] = round(wob[0], 4), round(wob[1], 4)
        out["could_be_chance"] = compare.could_be_chance(*wob)
    return out


def score(rows: list[dict], run: dict) -> dict:
    """Per-brand real share + 90% Wilson interval; ranking agreement with crowd intent and revenue."""
    brands = run.get("brands") or []
    people = sorted({r["respondent_n"] for r in rows})
    n_people = len(people)
    out_brands = []
    real_share: dict[str, float] = {}
    for b in brands:
        bid = b["id"]
        answers = [r["bought"] for r in rows if r["brand_id"] == bid]
        n, yes = len(answers), sum(answers)
        share = yes / n if n else None
        ci = wilson_interval(yes, n)
        if share is not None:
            real_share[bid] = share
        out_brands.append({
            "id": bid,
            "name": b.get("name", bid),
            "question": _question_for(b, run),
            "n_asked": n,
            "n_yes": yes,
            "real_share": None if share is None else round(share, 4),
            "ci90_low": None if ci is None else round(ci[0], 4),
            "ci90_high": None if ci is None else round(ci[1], 4),
            "crowd_intent_mean": b.get("intent_mean"),
            "rank_intent": b.get("rank_intent"),
            "rank_revenue": b.get("rank_revenue"),
            "label": f"REAL (n={n}, convenience sample)",
        })
    # real rank among brands that got at least one answer (1 = most said yes; ties averaged)
    asked = [x for x in out_brands if x["real_share"] is not None]
    for x, rk in zip(asked, compare.ranks([real_share[x["id"]] for x in asked])):
        x["rank_real"] = rk
    for x in out_brands:
        x.setdefault("rank_real", None)

    crowd = {b["id"]: float(b["intent_mean"]) for b in brands if compare._is_number(b.get("intent_mean"))}
    revenue = {b["id"]: float(b["revenue_usd"]) for b in brands if compare._is_number(b.get("revenue_usd"))}

    ages = {band: 0 for band in AGE_BANDS}
    ages["not given"] = 0
    for p in people:
        bands = {r["age_band"] for r in rows if r["respondent_n"] == p and r["age_band"]}
        ages[bands.pop() if len(bands) == 1 else "not given"] += 1

    tc = run.get("trust_card") or {}
    focus = tc.get("draft_question_brand")
    return {
        "label": LABEL,
        "display_label": f"REAL (n={n_people}, convenience sample)",
        "n_people": n_people,
        "run_id": run.get("run_id"),
        "draft_question": tc.get("draft_question"),
        "draft_question_brand": focus,
        "draft_question_scored": False,  # reported only; every scored answer used the uniform question
        "confidence": CONFIDENCE,
        "interval_method": f"Wilson score interval, 90%, z = {Z90:.10f}",
        "brands": out_brands,
        "agreement_with_crowd": _agreement(real_share, crowd, "AI crowd intent ranking (intent_mean, SYNTHETIC)"),
        "agreement_with_revenue": _agreement(real_share, revenue, "revenue ranking (revenue_usd, MEASURED)"),
        "age_bands": ages,
        "caveat": CAVEAT,
    }


# ----------------------------------------------------------------------------- script printer

def script_text(run: dict) -> str:
    """The exact questions to ask today, read from the run file (never hard-coded)."""
    tc = run.get("trust_card") or {}
    q = tc.get("draft_question")
    lines = [f"Run: {run.get('run_id')}", f"Consent line: \"{CONSENT_LINE}\"", ""]
    if q:
        lines.append(f"DRAFTED FOLLOW-UP (trust_card.draft_question, brand {tc.get('draft_question_brand')}), "
                     "not scored, keep its answers out of the tally CSV:")
        lines.append(f"  {q}")
    else:
        lines.append("DRAFTED FOLLOW-UP: none in this run file (trust_card.draft_question is empty).")
    lines.append("")
    lines.append("SCORED: ask the same yes/no buying question for every brand (brand_id -> question).")
    lines.append("Only these answers go in the tally CSV:")
    for b in run.get("brands") or []:
        lines.append(f"  {b['id']:<10} {_question_for(b, run)}")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- CLI

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m say.real_check",
                                 description="Score a hand-collected real-people tally (no PII) against the AI crowd.")
    ap.add_argument("--run", required=True, help="run file, e.g. frontend/runs/say_latest.json")
    ap.add_argument("--csv", help="tally CSV: respondent_n,brand_id,bought_12m[,age_band]")
    ap.add_argument("--out", help="write the JSON block here (otherwise print it)")
    ap.add_argument("--print-script", action="store_true", help="print the exact questions from the run file and stop")
    a = ap.parse_args(argv)
    with open(a.run, encoding="utf-8") as f:
        run = json.load(f)
    if a.print_script:
        print(script_text(run))
        return 0
    if not a.csv:
        ap.error("--csv is required unless --print-script is used")
    with open(a.csv, encoding="utf-8-sig") as f:
        text = f.read()
    try:
        rows = parse_csv_text(text, {b["id"] for b in run.get("brands") or []})
    except RealCheckError as e:
        print(str(e), file=sys.stderr)
        return 2
    result = score(rows, run)
    blob = json.dumps(result, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(blob + "\n")
        print(f"Wrote {a.out}: {result['display_label']}")
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    sys.exit(main())
