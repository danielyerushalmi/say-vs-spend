"""Independent fame measure: English Wikipedia pageviews over the last 365 days.

Source: Wikimedia REST API, per-article pageviews (en.wikipedia, all-access, user, daily).
Standard library only. No keys, no personal info. Run: python3 -m say.fame.wiki --fetch
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from say import compare

USER_AGENT = "HackTheUnreachable student research project (no-reply)"
API = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
       "en.wikipedia/all-access/user/{title}/daily/{start}/{end}")
MIN_SLEEP = 1.6
RETRY_WAIT = 10
LABEL = "MEASURED (Wikipedia pageviews)"
SOURCE = ("Wikimedia REST API per-article pageviews, en.wikipedia, all-access, user, daily, "
          "summed over the 365 days ending yesterday")
JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wikipedia_pageviews.json")

# id -> (article title, status, note). Titles chosen from Wikipedia search / page-existence checks.
TITLES = {
    "figs": ("Figs_(company)", "ok", ""),
    "hims": ("Hims_&_Hers_Health", "ok", ""),
    "revolve": (None, "no_article", "No English Wikipedia article found (Revolve Group, Revolve (company), Revolve Clothing checked 2026-11-14: all missing). Views left null, not guessed."),
    "stitchfix": ("Stitch_Fix", "ok", ""),
    "thredup": ("ThredUp", "ok", ""),
    "lulus": (None, "no_article", "No English Wikipedia article found (Lulus, Lulus.com, Lulu's checked 2026-11-14: all missing). Views left null, not guessed."),
    "flowers": ("1-800-Flowers.com,_Inc.", "ok", ""),
    "bark": ("BarkBox", "uncertain_title", "Article is BarkBox (the product/brand of BARK, Inc.); there is no article titled BARK, Inc. Likely the right company, but the article may be about the BarkBox subscription rather than the whole company."),
    "realreal": ("The_RealReal", "ok", ""),
    "rtr": ("Rent_the_Runway", "ok", ""),
    "petmeds": ("PetMed_Express", "ok", ""),
    "carparts": (None, "no_article", "No English Wikipedia article found (CarParts.com, Carparts.com, CarParts checked 2026-11-14: all missing). Views left null, not guessed."),
}


def window(today: dt.date | None = None) -> tuple[str, str]:
    """365 days ending yesterday, as YYYYMMDD strings (inclusive)."""
    today = today or dt.date.today()
    end = today - dt.timedelta(days=1)
    start = end - dt.timedelta(days=364)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def build_url(title: str, start: str, end: str) -> str:
    return API.format(title=urllib.parse.quote(title, safe="()_,."), start=start, end=end)


def _get(url: str, opener=urllib.request.urlopen, sleep=time.sleep) -> tuple[int, dict | None]:
    """One GET with a single retry on 429. Returns (status, json or None)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in (0, 1):
        try:
            with opener(req, timeout=30) as r:
                return r.status if hasattr(r, "status") else 200, json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                sleep(RETRY_WAIT)
                continue
            return e.code, None
        except Exception:
            return 0, None
    return 429, None


def fetch(titles: dict, end_date: dt.date | None = None, opener=urllib.request.urlopen, sleep=time.sleep) -> dict:
    """titles: id -> article title. end_date = 'today' (window ends the day before)."""
    start, end = window(end_date)
    out: dict = {}
    stop = False
    first = True
    for bid, title in titles.items():
        url = build_url(title, start, end) if title else None
        rec = {"title": title, "url": url, "views_365d": None, "start": start, "end": end,
               "fetched_at": None, "status": "not_fetched", "note": ""}
        out[bid] = rec
        if not title:
            rec["status"], rec["note"] = "no_article", "No English Wikipedia article for this company."
            continue
        if stop:
            rec["note"] = "Skipped: an earlier request was rate-limited twice (HTTP 429); stopped."
            continue
        if not first:
            sleep(MIN_SLEEP)
        first = False
        code, data = _get(url, opener, sleep)
        rec["fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        if code == 200 and data is not None:
            rec["views_365d"] = sum(int(i.get("views", 0)) for i in data.get("items", []))
            rec["status"] = "ok"
            rec["n_days"] = len(data.get("items", []))
        elif code == 404:
            rec["status"], rec["note"] = "no_data", "HTTP 404: no pageview data for this title (article missing or no views)."
        elif code == 429:
            rec["status"], rec["note"] = "error_429", "HTTP 429 twice; stopped, not retried further."
            stop = True
        else:
            rec["status"], rec["note"] = f"error_{code}", f"HTTP error {code}."
    return out


def wiki_fame_agreement(brands: list, views: dict, n_boot: int = 2000, seed: int = compare.DEFAULT_SEED) -> dict:
    """Pageviews vs revenue, reusing say.compare. brands: dicts with id, revenue_usd.
    Brands whose views are null/missing are left out. Same keys as compare.agreement() + n_brands."""
    usable = [{"revenue_usd": b.get("revenue_usd"), "views": views.get(b["id"])} for b in brands]
    usable = [u for u in usable if compare._is_number(u["views"]) and compare._is_number(u["revenue_usd"])]
    # Same math as every other line (incl. exact p-value): feed views in as the "fame" field.
    rows = [{"aware_share": float(u["views"]), "revenue_usd": float(u["revenue_usd"])} for u in usable]
    out = compare.agreement(rows, "fame", n_boot=n_boot, seed=seed)
    out["n_brands"] = len(usable)
    return out


def fame_block(run: dict, json_path: str = JSON_PATH) -> dict:
    with open(json_path, encoding="utf-8") as f:
        saved = json.load(f)
    recs = saved.get("brands", {})
    brands = run["brands"]
    views = {b["id"]: (recs.get(b["id"]) or {}).get("views_365d") for b in brands}
    urls = {b["id"]: (recs.get(b["id"]) or {}).get("url") for b in brands}
    agr = wiki_fame_agreement(brands, views)
    # Compare on the SAME brands (those with a Wikipedia figure), not 6 vs 5.
    same = [b for b in brands if compare._is_number(views.get(b["id"]))]
    if len(same) == len(brands):
        intent = ((run.get("agreement") or {}).get("intent") or {}).get("spearman")
    else:
        intent = compare.agreement(same, "intent").get("spearman") if len(same) >= 3 else None
    agr["intent_same_brands_spearman"] = intent
    wiki_rho = agr.get("spearman")
    beat = bool(intent is not None and wiki_rho is not None and intent > wiki_rho)
    return {
        "label": "MEASURED (Wikipedia pageviews, last 365 days)",
        "source": "Wikimedia REST API per-article pageviews, en.wikipedia, all-access, user",
        "window": {"start": saved.get("start"), "end": saved.get("end")},
        "views": views, "urls": urls, "agreement": agr, "crowd_beat_wiki_fame": beat,
        "note": ("Added 12:24 as an independent fame line; the pre-registered fame test uses the "
                 "crowd's 'heard of it' share."),
    }


def run_fetch(path: str = JSON_PATH) -> dict:
    titles = {k: v[0] for k, v in TITLES.items()}
    res = fetch(titles)
    for k, (_, status, note) in TITLES.items():
        if status != "ok":
            res[k]["status"], res[k]["note"] = status, note
    any_rec = next(iter(res.values()))
    doc = {"label": LABEL, "source": SOURCE, "user_agent": USER_AGENT,
           "start": any_rec["start"], "end": any_rec["end"],
           "url_template": API, "brands": res}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    if ap.parse_args().fetch:
        d = run_fetch()
        for k, r in d["brands"].items():
            print(f"{k:10} {str(r['title']):28} {r['views_365d']} {r['status']}")
