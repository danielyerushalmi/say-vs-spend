"""Local, measured neighborhood features per station from the US Census Bureau.

Free public APIs. The ACS needs a free key, read ONLY from the CENSUS_API_KEY environment
variable and added at request time; it never appears in cache file names, saved URLs or logs:
  1. Census Geocoder: station lat/lon -> census tract.
  2. ACS 5-year (try 2023, fall back to 2022): tract-level work-from-home share,
     median household income, bachelor's-or-higher share, transit share.

Method (also written into each result's "method"): the single census tract that
contains the station point. Tracts are small (~4,000 people), so this is a
"the block around the station" number, not a borough average. Where several
tracts are used, medians are combined as a household-weighted mean of tract
medians (an approximation: a true combined median needs the full distribution).

Standard library only. Run: python3 -m agent.features
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "data" / "census"
OUT_FILE = CACHE_DIR / "stations_features.json"
GEOCODER_URL = ("https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
                "?x={lon}&y={lat}&benchmark=Public_AR_Current&vintage=Current_Current&format=json")
ACS_URL = "https://api.census.gov/data/{year}/acs/acs5"
ACS_YEARS = (2023, 2022)
TIMEOUT_S = 30
RETRIES = 2

# ACS variables
WORKERS, WFH, TRANSIT = "B08301_001E", "B08301_021E", "B08301_010E"
INCOME, HOUSEHOLDS = "B19013_001E", "B11001_001E"
POP25 = "B15003_001E"
BACHELORS_PLUS = ("B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E")
VARIABLES = (WORKERS, WFH, TRANSIT, INCOME, HOUSEHOLDS, POP25) + BACHELORS_PLUS


def _with_key(url):
    """Add the Census key for the actual request only (saved/printed URLs stay keyless)."""
    key = os.environ.get("CENSUS_API_KEY")
    if key and url.startswith("https://api.census.gov/"):
        return url + "&key=" + urllib.parse.quote(key, safe="")
    return url


def _http_get(url):
    last = None
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(_with_key(url), headers={"User-Agent": "hack-the-unreachable/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = type(exc).__name__ + (f" {exc.code}" if hasattr(exc, "code") else "")  # never echo the keyed URL
            if attempt < RETRIES:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {RETRIES + 1} tries: {url} ({last})")


def _cached_json(url, cache_dir=CACHE_DIR, http=None):
    """Return parsed JSON for url, cached on disk by URL hash."""
    path = Path(cache_dir) / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")
    if path.exists():
        return json.loads(path.read_text())
    data = json.loads((http or _http_get)(url))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def clean_number(value):
    """Census value -> float, or None if missing. Negative sentinels
    (-666666666, -999999999, ...) and blanks mean 'no data'."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number < 0 else number


def geocode_tract(lat, lon, cache_dir=CACHE_DIR, http=None):
    """Tract containing the point -> {"state","county","tract","geoid"}; None if outside any tract."""
    url = GEOCODER_URL.format(lat=lat, lon=lon)
    data = _cached_json(url, cache_dir, http)
    tracts = data.get("result", {}).get("geographies", {}).get("Census Tracts", [])
    if not tracts:
        return None, url
    t = tracts[0]
    return {"state": t["STATE"], "county": t["COUNTY"], "tract": t["TRACT"], "geoid": t["GEOID"]}, url


def acs_url(year, tract):
    params = {"get": ",".join(VARIABLES), "for": f"tract:{tract['tract']}",
              "in": f"state:{tract['state']} county:{tract['county']}"}
    return ACS_URL.format(year=year) + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote, safe=":,")


def parse_acs_row(header_and_row):
    """[[header...],[row...]] -> {variable: float|None}."""
    header, row = header_and_row[0], header_and_row[1]
    raw = dict(zip(header, row))
    return {v: clean_number(raw.get(v)) for v in VARIABLES}


def tract_measures(acs):
    """Raw ACS numbers for one tract -> percentages (None when a part is missing)."""
    def pct(num, den):
        return None if num is None or not den else 100.0 * num / den
    parts = [acs.get(v) for v in BACHELORS_PLUS]
    bach = None if any(p is None for p in parts) else sum(parts)
    return {
        "wfh_share_pct": pct(acs.get(WFH), acs.get(WORKERS)),
        "transit_share_pct": pct(acs.get(TRANSIT), acs.get(WORKERS)),
        "bachelors_pct": pct(bach, acs.get(POP25)),
        "median_income_local": acs.get(INCOME),
        "households": acs.get(HOUSEHOLDS),
        "workers": acs.get(WORKERS),
        "pop25": acs.get(POP25),
    }


def combine_tracts(measures):
    """Combine several tracts. Percentages are pooled from counts' weights
    (workers for WFH/transit, pop 25+ for bachelor's); income is the
    household-weighted mean of tract medians. Single tract passes straight through."""
    def weighted(key, weight_key):
        pairs = [(m[key], m[weight_key]) for m in measures if m.get(key) is not None and m.get(weight_key)]
        total = sum(w for _, w in pairs)
        return sum(v * w for v, w in pairs) / total if total else None
    return {
        "wfh_share_pct": weighted("wfh_share_pct", "workers"),
        "transit_share_pct": weighted("transit_share_pct", "workers"),
        "bachelors_pct": weighted("bachelors_pct", "pop25"),
        "median_income_local": weighted("median_income_local", "households"),
    }


def fetch_tract_acs(tract, cache_dir=CACHE_DIR, http=None):
    """Try each ACS year in turn; return (measures, year, url)."""
    errors = []
    for year in ACS_YEARS:
        url = acs_url(year, tract)
        try:
            acs = parse_acs_row(_cached_json(url, cache_dir, http))
        except (RuntimeError, ValueError, IndexError, KeyError) as exc:
            errors.append(f"{year}: {exc}")
            continue
        return tract_measures(acs), year, url
    raise RuntimeError("ACS failed for every year: " + "; ".join(errors))


def station_features(stations, cache_dir=CACHE_DIR, http=None):
    """stations: [{"id","lat","lon",...}] -> {station_id: features dict}.

    A station that fails (no tract, no ACS data) gets {"error": "..."} instead
    of numbers, so one bad station never hides the rest."""
    out = {}
    for st in stations:
        sid = str(st["id"])
        try:
            if st.get("lat") is None or st.get("lon") is None:
                raise RuntimeError("station has no lat/lon")
            tract, geo_url = geocode_tract(st["lat"], st["lon"], cache_dir, http)
            if tract is None:
                raise RuntimeError("point is not inside any census tract")
            measures, year, acs_link = fetch_tract_acs(tract, cache_dir, http)
            combined = combine_tracts([measures])
            out[sid] = {
                **{k: combined[k] for k in ("wfh_share_pct", "median_income_local", "bachelors_pct")},
                "transit_share_pct": combined["transit_share_pct"],
                "tracts": [tract["geoid"]],
                "acs_year": year,
                "method": (f"MEASURED: US Census ACS 5-year {year}, the one census tract containing the "
                           "station point (Census Geocoder). Percentages = tract counts / tract totals "
                           "(WFH and transit over workers 16+, bachelor's-or-higher over pop 25+). "
                           "Income = tract median household income; if several tracts were combined it "
                           "would be a household-weighted mean of tract medians (approximation)."),
                "source_urls": [geo_url, acs_link],
            }
        except RuntimeError as exc:
            out[sid] = {"error": str(exc)}
    return out


def _load_stations():
    """Stations from config plus lat/lon from the (cached) MTA coordinate query."""
    from agent import mta
    cfg = json.loads((Path(__file__).parent / "config" / "stations.json").read_text())
    ids = [s["id"] for s in cfg["stations"]]
    coords = mta._cached_get(mta._coords_url(ids, cfg["window"]))
    by_id = {str(r["station_complex_id"]): r for r in coords}
    return [{**s, "lat": float(by_id[s["id"]]["lat"]), "lon": float(by_id[s["id"]]["lon"])}
            for s in cfg["stations"] if s["id"] in by_id]


def _fmt(value, spec):
    return "n/a" if value is None else format(value, spec)


def main():
    stations = _load_stations()
    result = station_features(stations)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(result, indent=2))
    print(f"{'id':>4} {'station':<36} {'WFH%':>5} {'income':>8} {'BA+%':>5} {'transit%':>8}  tract")
    for st in stations:
        r = result[st["id"]]
        if "error" in r:
            print(f"{st['id']:>4} {st['name']:<36} ERROR {r['error']}")
            continue
        print(f"{st['id']:>4} {st['name'][:36]:<36} {_fmt(r['wfh_share_pct'], '5.1f')} "
              f"{_fmt(r['median_income_local'], '8,.0f')} {_fmt(r['bachelors_pct'], '5.1f')} "
              f"{_fmt(r['transit_share_pct'], '8.1f')}  {r['tracts'][0]} (ACS {r['acs_year']})")
    print(f"\nwrote {OUT_FILE}")


if __name__ == "__main__":
    main()
