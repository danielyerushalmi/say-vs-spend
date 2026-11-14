"""Auditor: checks the MTA answer key for problems before we trust it.

Checks (all done in code, every finding quotes the real numbers):
  1. US federal holidays inside the window, and whether each was actually low.
  2. Missing weekdays (no data for a station on a weekday in the window).
  3. Unequal number of each weekday in the window.
  4. Outlier-low days: below 60% of that station's median for that weekday.
Returns the dates to exclude (only real outliers) and a list of findings.
"""
from datetime import date, timedelta
from statistics import median

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
LOW_FRACTION = 0.60  # a day under 60% of the station's weekday median is an outlier


def _nth_weekday(year, month, weekday, n):
    """n-th (1-based) given weekday (Mon=0) of a month; n=-1 means the last one."""
    if n > 0:
        d = date(year, month, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))
        return d
    d = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def federal_holidays(year):
    """US federal holidays for a year as {date: name}, computed by rule (not observed shifts)."""
    return {
        date(year, 1, 1): "New Year's Day",
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        _nth_weekday(year, 2, 0, 3): "Presidents' Day",
        _nth_weekday(year, 5, 0, -1): "Memorial Day",
        date(year, 6, 19): "Juneteenth",
        date(year, 7, 4): "Independence Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        _nth_weekday(year, 10, 0, 2): "Columbus Day / Indigenous Peoples' Day",
        date(year, 11, 11): "Veterans Day",
        _nth_weekday(year, 11, 3, 4): "Thanksgiving",
        date(year, 12, 25): "Christmas Day",
    }


def _window_dates(window):
    start = date.fromisoformat(window["start"][:10])
    end = date.fromisoformat(window["end"][:10])  # exclusive
    d = start
    while d < end:
        yield d
        d += timedelta(days=1)


def _fmt(d):
    return f"{DAYS[d.weekday()] if d.weekday() < 5 else ('Sat' if d.weekday() == 5 else 'Sun')} {d.strftime('%b')} {d.day}"


def audit(station_ids, window, daily):
    """Audit the answer key. See module docstring.

    daily = {station_id: {"YYYY-MM-DD": entries}} (from mta.fetch_daily).
    Returns {"exclude_dates": [...], "findings": [{"station_id", "finding", "action"}]}.
    """
    findings = []
    dates = list(_window_dates(window))
    weekdays = [d for d in dates if d.weekday() < 5]
    station_ids = [str(s) for s in station_ids]

    # Check 3: equal count of each weekday in the window.
    counts = {DAYS[i]: sum(1 for d in weekdays if d.weekday() == i) for i in range(5)}
    cstr = ", ".join(f"{k} {v}" for k, v in counts.items())
    if len(set(counts.values())) > 1:
        findings.append({"station_id": "all", "finding": f"Weekdays are not equally represented in the window ({cstr}).",
                         "action": "Shares use the mean per day so the imbalance does not bias them."})
    else:
        findings.append({"station_id": "all", "finding": f"Window has {counts['Mon']} of each weekday ({cstr}); checked, kept.",
                         "action": "None needed."})

    # Check 2: missing weekdays per station.
    for sid in station_ids:
        have = daily.get(sid, {})
        missing = [d for d in weekdays if d.isoformat() not in have]
        if missing:
            findings.append({"station_id": sid,
                             "finding": f"Missing {len(missing)} of {len(weekdays)} weekdays: " + ", ".join(_fmt(d) for d in missing) + ".",
                             "action": "Shares use only the days present."})
    if not any(f["finding"].startswith("Missing") for f in findings):
        findings.append({"station_id": "all", "finding": f"All {len(weekdays)} weekdays present at all {len(station_ids)} stations; checked, kept.",
                         "action": "None needed."})

    # Check 4: outlier-low days against the station's median for that weekday.
    low = {}  # date -> list of (sid, pct)
    for sid in station_ids:
        have = daily.get(sid, {})
        for i in range(5):
            vals = [have[d.isoformat()] for d in weekdays if d.weekday() == i and d.isoformat() in have]
            if len(vals) < 3:
                continue  # a median of fewer than 3 days is not meaningful
            med = median(vals)
            for d in weekdays:
                n = have.get(d.isoformat())
                if d.weekday() == i and n is not None and med > 0 and n < LOW_FRACTION * med:
                    low.setdefault(d, []).append((sid, n / med))

    # Check 1: holidays in the window (reported whether low or not).
    holidays = {}
    for y in {d.year for d in dates}:
        holidays.update({d: n for d, n in federal_holidays(y).items() if d in set(weekdays)})
    exclude = []
    for d, name in sorted(holidays.items()):
        hits = low.get(d, [])
        if hits:
            avg = sum(p for _, p in hits) / len(hits)
            findings.append({"station_id": "all",
                             "finding": f"{_fmt(d)} ({name}) entries were on average {avg:.0%} of the usual {DAYS[d.weekday()]} at {len(hits)} of {len(station_ids)} stations.",
                             "action": f"Excluded {d.isoformat()} and re-pulled."})
            exclude.append(d.isoformat())
        else:
            ratios = []
            for sid in station_ids:
                have = daily.get(sid, {})
                vals = [have[x.isoformat()] for x in weekdays if x.weekday() == d.weekday() and x.isoformat() in have]
                if d.isoformat() in have and len(vals) >= 3 and median(vals) > 0:
                    ratios.append(have[d.isoformat()] / median(vals))
            detail = (f"lowest station was {min(ratios):.0%} of its usual {DAYS[d.weekday()]}, none under {LOW_FRACTION:.0%}"
                      if ratios else "not enough data to compare")
            findings.append({"station_id": "all", "finding": f"{_fmt(d)} ({name}) checked: {detail}; kept.",
                             "action": "None needed."})

    # Non-holiday outliers.
    for d, hits in sorted(low.items()):
        if d in holidays:
            continue
        for sid, p in hits:
            findings.append({"station_id": sid, "finding": f"{_fmt(d)} entries were {p:.0%} of the usual {DAYS[d.weekday()]} at this station.",
                             "action": f"Excluded {d.isoformat()} for this run."})
        exclude.append(d.isoformat())
    return {"exclude_dates": sorted(set(exclude)), "findings": findings}
