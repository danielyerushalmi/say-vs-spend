import unittest
from study2.build_brands import annual_revenue


def fact(start, end, val, filed="2026-02-01"):
    return {"start": start, "end": end, "val": val, "filed": filed, "accn": "x", "form": "10-K"}


class AnnualRevenue(unittest.TestCase):
    def wrap(self, concept, units):
        return {"facts": {"us-gaap": {concept: {"units": {"USD": units}}}}}

    def test_picks_latest_full_year(self):
        f = self.wrap("Revenues", [fact("2024-01-01", "2024-12-31", 1), fact("2025-01-01", "2025-12-31", 2),
                                   fact("2025-10-01", "2025-12-31", 99)])
        self.assertEqual(annual_revenue(f)["revenue_usd"], 2)

    def test_skips_quarter_and_out_of_window(self):
        f = self.wrap("Revenues", [fact("2025-10-01", "2025-12-31", 5), fact("2023-01-01", "2023-12-31", 7)])
        self.assertIsNone(annual_revenue(f))

    def test_concept_order(self):
        f = {"facts": {"us-gaap": {
            "Revenues": {"units": {"USD": [fact("2025-01-01", "2025-12-31", 10)]}},
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [fact("2025-01-01", "2025-12-31", 20)]}}}}}
        r = annual_revenue(f)
        self.assertEqual((r["revenue_usd"], r["concept"]), (20, "RevenueFromContractWithCustomerExcludingAssessedTax"))

    def test_53_week_year_ok(self):
        f = self.wrap("Revenues", [fact("2025-02-02", "2026-01-31", 3)])
        self.assertEqual(annual_revenue(f)["revenue_usd"], 3)


if __name__ == "__main__":
    unittest.main()
