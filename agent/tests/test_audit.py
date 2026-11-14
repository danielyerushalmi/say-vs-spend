import unittest
from datetime import date, timedelta

from agent import audit

WINDOW = {"start": "2026-10-05T00:00:00", "end": "2026-10-31T00:00:00", "hour_from": 6, "hour_to": 10}


def make_daily(overrides=None, drop=()):
    """One station, 100 entries every weekday; overrides = {iso_date: value}."""
    out, d = {}, date(2026, 10, 5)
    while d < date(2026, 10, 31):
        iso = d.isoformat()
        if iso not in drop:
            out[iso] = (overrides or {}).get(iso, 100 if d.weekday() < 5 else 10)
        d += timedelta(days=1)
    return out


class AuditTests(unittest.TestCase):
    def test_columbus_day_is_2026_10_12(self):
        self.assertEqual(audit.federal_holidays(2026)[date(2026, 10, 12)].split()[0], "Columbus")
        self.assertEqual(audit.federal_holidays(2026)[date(2026, 11, 26)], "Thanksgiving")

    def test_low_holiday_is_excluded_with_numbers(self):
        daily = {"1": make_daily({"2026-10-12": 54}), "2": make_daily({"2026-10-12": 54})}
        res = audit.audit(["1", "2"], WINDOW, daily)
        self.assertEqual(res["exclude_dates"], ["2026-10-12"])
        text = " ".join(f["finding"] for f in res["findings"])
        self.assertIn("Mon Oct 12", text)
        self.assertIn("54%", text)
        self.assertIn("2 of 2", text)

    def test_normal_holiday_checked_and_kept(self):
        res = audit.audit(["1"], WINDOW, {"1": make_daily({"2026-10-12": 95})})
        self.assertEqual(res["exclude_dates"], [])
        self.assertTrue(any("checked" in f["finding"] and "kept" in f["finding"] and "Oct 12" in f["finding"]
                            for f in res["findings"]))

    def test_missing_day_reported(self):
        res = audit.audit(["1"], WINDOW, {"1": make_daily(drop=("2026-10-21",))})
        self.assertTrue(any("Missing 1 of 20" in f["finding"] and "Wed Oct 21" in f["finding"] for f in res["findings"]))

    def test_non_holiday_outlier_excluded(self):
        res = audit.audit(["1"], WINDOW, {"1": make_daily({"2026-10-21": 30})})
        self.assertEqual(res["exclude_dates"], ["2026-10-21"])

    def test_clean_data_has_no_exclusions_and_no_invented_problems(self):
        res = audit.audit(["1"], WINDOW, {"1": make_daily()})
        self.assertEqual(res["exclude_dates"], [])
        self.assertFalse(any(f["finding"].startswith("Missing") for f in res["findings"]))


if __name__ == "__main__":
    unittest.main()
