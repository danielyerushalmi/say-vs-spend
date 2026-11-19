"""Study 2 brand list, built by the rule in study2/PREREG.md (steps 2 to 8).

Input:  study2/data/sic.json (CIK -> SEC name, SIC, last annual filing, Wikidata item, article URL)
Output: study2/data/brands.json (kept brands) and study2/data/drops.json (every drop, with reason)

Free public sources only: data.sec.gov company facts, Wikimedia pageviews API.
Run: python3 -m study2.build_brands
"""
from __future__ import annotations

import datetime as dt
import json
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path

from say.fame import wiki

HERE = Path(__file__).parent
DATA = HERE / "data"
UA = "CrowdCheck-Study2 student research script"
# Wikimedia User-Agent policy asks for contact info; the public repo URL serves as that.
WIKI_UA = "CrowdCheck-Study2/1.0 (https://github.com/danielyerushalmi/say-vs-spend; student research)"
CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
]
FILED_FROM, FILED_TO = "2025-07-01", "2026-11-17"
END_FROM, END_TO = dt.date(2025, 1, 1), dt.date(2026, 10, 31)
MIN_REVENUE = 50_000_000
VIEW_START, VIEW_END = "20251101", "20261031"
SEED, MAX_N, MIN_N = 20261117, 80, 30


def annual_revenue(facts: dict) -> dict | None:
    """Latest 330-400 day USD revenue ending in the window, trying concepts in PREREG order."""
    gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    for concept in CONCEPTS:
        units = ((gaap.get(concept) or {}).get("units") or {}).get("USD") or []
        best = None
        for u in units:
            if not (u.get("start") and u.get("end")):
                continue
            s, e = dt.date.fromisoformat(u["start"]), dt.date.fromisoformat(u["end"])
            if not (330 <= (e - s).days <= 400 and END_FROM <= e <= END_TO):
                continue
            if best is None or (e, u.get("filed", "")) > (dt.date.fromisoformat(best["end"]), best.get("filed", "")):
                best = u
        if best:
            return {"revenue_usd": best["val"], "concept": concept, "period_start": best["start"],
                    "period_end": best["end"], "accession": best.get("accn"), "form": best.get("form")}
    return None


def get_json(url: str, ua: str = UA) -> tuple[int, dict | None]:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return 200, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def main() -> None:
    sic = json.loads((DATA / "sic.json").read_text())
    kept, drops = [], []

    def drop(cik, rec, step, reason):
        drops.append({"cik": cik, "name": rec.get("name"), "step": step, "reason": reason})

    for cik in sorted(sic):
        rec = sic[cik]
        try:
            code = int(rec.get("sic") or 0)
        except ValueError:
            code = 0
        if not 5200 <= code <= 5999:
            continue  # step 2: not retail trade (not logged one by one; count is in the summary)
        if not (rec.get("last_annual") and FILED_FROM <= rec["last_annual"] <= FILED_TO):
            drop(cik, rec, 3, f"last annual filing {rec.get('last_annual')} outside {FILED_FROM}..{FILED_TO}")
            continue
        time.sleep(0.2)
        status, facts = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        if status in (403, 429):
            raise SystemExit(f"STOP: SEC returned {status}. Not retrying (no bypass).")
        rev = annual_revenue(facts or {})
        if not rev:
            drop(cik, rec, 4, f"no qualifying annual USD revenue (HTTP {status})")
            continue
        if not (rev.get("form") or "").startswith("10-K"):
            drop(cik, rec, 3, f"annual report is a {rev.get('form')}, not a 10-K")
            continue
        if rev["revenue_usd"] < MIN_REVENUE:
            drop(cik, rec, 5, "revenue under $50M")
            continue
        kept.append({"cik": cik, "name": rec["name"], "sic": code, "sic_label": rec.get("sicDescription"),
                     "tickers": rec.get("tickers"), "wikidata": rec.get("wikidata"),
                     "article": rec.get("article"), **rev, "label": "MEASURED"})

    # Step 6: Wikipedia views over the fixed window.
    cache_path = DATA / "views_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    with_views = []
    for b in kept:
        title = urllib.parse.unquote(b["article"].rsplit("/wiki/", 1)[1])
        if title not in cache:
            time.sleep(2.0)  # polite: 1 request every 2 seconds
            status, data = get_json(wiki.build_url(title, VIEW_START, VIEW_END), WIKI_UA)
            if status == 429:
                cache_path.write_text(json.dumps(cache, indent=1))
                raise SystemExit("STOP: Wikimedia rate-limited (429). Not retrying.")
            cache[title] = {"status": status, "views": sum(int(i.get("views", 0)) for i in (data or {}).get("items", [])) if status == 200 else None}
            cache_path.write_text(json.dumps(cache, indent=1))
        status, views = cache[title]["status"], cache[title]["views"]
        if not views:
            drop(b["cik"], b, 6, f"no page views (HTTP {status})")
            continue
        b.update({"wiki_title": title, "views": views, "views_window": f"{VIEW_START}-{VIEW_END}"})
        with_views.append(b)

    # Step 7: one entry per Wikipedia article (keep larger revenue).
    by_article: dict[str, dict] = {}
    for b in with_views:
        cur = by_article.get(b["wiki_title"])
        if cur is None or b["revenue_usd"] > cur["revenue_usd"]:
            if cur is not None:
                drop(cur["cik"], cur, 7, f"shares article with CIK {b['cik']}, smaller revenue")
            by_article[b["wiki_title"]] = b
        else:
            drop(b["cik"], b, 7, f"shares article with CIK {cur['cik']}, smaller revenue")
    final = sorted(by_article.values(), key=lambda b: b["cik"])

    # Step 8: sample or stop.
    eligible = len(final)
    if eligible > MAX_N:
        chosen = set(x["cik"] for x in random.Random(SEED).sample(final, MAX_N))
        for b in final:
            if b["cik"] not in chosen:
                drop(b["cik"], b, 8, "not in the seeded random sample of 80")
        final = [b for b in final if b["cik"] in chosen]
    status = "ok" if len(final) >= MIN_N else "STOP: fewer than 30 brands"

    out = {"built_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "rule": "study2/PREREG.md steps 1-8", "eligible_before_sampling": eligible,
           "n": len(final), "status": status, "brands": final}
    (DATA / "brands.json").write_text(json.dumps(out, indent=1))
    (DATA / "drops.json").write_text(json.dumps(drops, indent=1))
    print(status, "eligible", eligible, "kept", len(final), "drops", len(drops))


if __name__ == "__main__":
    main()
