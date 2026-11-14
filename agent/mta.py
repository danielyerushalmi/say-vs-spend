"""MTA answer-key puller.

Pulls real subway entries (the "answer key") from the public MTA Subway Hourly
Ridership dataset on data.ny.gov (no API key needed) using server-side SoQL
grouping, and caches each raw response on disk keyed by a hash of the URL.

Public functions:
    fetch_measured(station_ids, window, exclude_dates=[]) -> per-station shares
    fetch_daily(station_ids, window)                      -> per-station daily totals

Everything here is MEASURED data. All arithmetic is done in code.
"""
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_URL = "https://data.ny.gov/resource/5wq4-mkjj.json"
CACHE_DIR = Path(__file__).resolve().parent / "data" / "mta"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
TIMEOUT_S = 60
RETRIES = 2  # retries after the first attempt


def _http_get(url):
    """GET a URL and return the decoded JSON. Timeout 60 s, 2 retries."""
    last_err = None
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as err:
            last_err = err
            if attempt < RETRIES:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"MTA request failed after {RETRIES + 1} tries: {last_err}")


def _cached_get(url, cache_dir=None):
    """Return JSON for url, reading/writing the on-disk cache (keyed by URL hash)."""
    cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
    path = cache_dir / (hashlib.sha256(url.encode("utf-8")).hexdigest()[:24] + ".json")
    if path.exists():
        return json.loads(path.read_text())
    data = _http_get(url)
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)
    return data


def _in_list(station_ids):
    return ",".join("'" + str(s).replace("'", "") + "'" for s in station_ids)


def _daily_url(station_ids, window, exclude_dates=()):
    """Build the SoQL URL: entries per station per calendar day, inside the hour window."""
    where = [
        f"station_complex_id IN ({_in_list(station_ids)})",
        f"transit_timestamp >= '{window['start']}'",
        f"transit_timestamp < '{window['end']}'",
        f"date_extract_hh(transit_timestamp) >= {int(window['hour_from'])}",
        f"date_extract_hh(transit_timestamp) < {int(window['hour_to'])}",
    ]
    for d in sorted(set(exclude_dates)):
        nxt = (date.fromisoformat(d) + timedelta(days=1)).isoformat()
        where.append(f"NOT (transit_timestamp >= '{d}T00:00:00' AND transit_timestamp < '{nxt}T00:00:00')")
    params = {
        "$select": "station_complex_id,station_complex,borough,"
                   "date_trunc_ymd(transit_timestamp) as day,sum(ridership) as r",
        "$where": " AND ".join(where),
        "$group": "station_complex_id,station_complex,borough,day",
        "$limit": "50000",
    }
    return BASE_URL + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def _coords_url(station_ids, window):
    """Station lat/lon. Limited to the first day of the window: an unbounded
    group-by over the whole dataset times out."""
    first = window["start"][:10]
    nxt = (date.fromisoformat(first) + timedelta(days=1)).isoformat()
    params = {
        "$select": "station_complex_id,max(latitude) as lat,max(longitude) as lon",
        "$where": f"station_complex_id IN ({_in_list(station_ids)}) "
                  f"AND transit_timestamp >= '{first}T00:00:00' AND transit_timestamp < '{nxt}T00:00:00'",
        "$group": "station_complex_id",
        "$limit": "1000",
    }
    return BASE_URL + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def _rows_to_daily(rows):
    """Turn raw rows into {station_id: {"YYYY-MM-DD": int}} plus {station_id: (name, borough)}."""
    daily, meta = {}, {}
    for row in rows:
        sid = str(row["station_complex_id"])
        day = row["day"][:10]
        daily.setdefault(sid, {})[day] = daily.get(sid, {}).get(day, 0) + int(round(float(row["r"])))
        meta[sid] = (row.get("station_complex", ""), row.get("borough", ""))
    return daily, meta


def fetch_daily(station_ids, window, cache_dir=None):
    """Entries between hour_from and hour_to for each station and each day.

    Returns {station_id: {"2026-10-05": 12345, ...}} (all days, incl. weekends).
    Days with no rows at all are simply absent (the auditor reports them as missing).
    """
    rows = _cached_get(_daily_url(station_ids, window), cache_dir)
    daily, _ = _rows_to_daily(rows)
    return {str(s): daily.get(str(s), {}) for s in station_ids}


def _weekday_name(day_iso):
    """'2026-10-05' -> 'Mon'; weekends return None."""
    idx = date.fromisoformat(day_iso).weekday()
    return DAYS[idx] if idx < 5 else None


def compute_shares(daily_for_station):
    """From {date: entries} compute Mon-Fri totals, day counts and shares.

    Shares use the MEAN entries per day of each weekday, so dropping one
    holiday Monday does not make Monday look smaller just because it has
    fewer days. Shares sum to 1.0.
    """
    totals = {d: 0 for d in DAYS}
    counts = {d: 0 for d in DAYS}
    for day, n in daily_for_station.items():
        wd = _weekday_name(day)
        if wd:
            totals[wd] += n
            counts[wd] += 1
    means = {d: (totals[d] / counts[d] if counts[d] else 0.0) for d in DAYS}
    grand = sum(means.values())
    shares = {d: (means[d] / grand if grand else 0.0) for d in DAYS}
    return shares, totals, counts


def fetch_measured(station_ids, window, exclude_dates=(), cache_dir=None):
    """Real Mon-Fri morning-entry shares per station (MEASURED).

    exclude_dates are removed inside the SoQL query itself (and the URL shows it).
    Returns {station_id: {"shares", "totals", "day_counts", "lat", "lon",
                          "name", "borough", "query_url"}}.
    """
    exclude_dates = list(exclude_dates)
    url = _daily_url(station_ids, window, exclude_dates)
    daily, meta = _rows_to_daily(_cached_get(url, cache_dir))
    coords = {str(r["station_complex_id"]): r for r in _cached_get(_coords_url(station_ids, window), cache_dir)}
    out = {}
    for sid in map(str, station_ids):
        if sid not in daily:
            raise RuntimeError(f"No MTA rows for station {sid} in the window")
        shares, totals, counts = compute_shares(daily[sid])
        c = coords.get(sid, {})
        out[sid] = {
            "shares": shares, "totals": totals, "day_counts": counts,
            "lat": float(c["lat"]) if c.get("lat") else None,
            "lon": float(c["lon"]) if c.get("lon") else None,
            "name": meta[sid][0], "borough": meta[sid][1], "query_url": url,
        }
    return out
