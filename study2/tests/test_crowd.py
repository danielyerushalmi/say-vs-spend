import unittest
from study2 import crowd


def brands(n):
    return [{"key": f"b{i:02d}", "name": f"B{i}", "cik": str(i), "sic_label": "RETAIL"} for i in range(n)]


class Crowd(unittest.TestCase):
    def test_personas_fixed(self):
        self.assertEqual(crowd.personas(), crowd.personas())
        self.assertEqual(len(crowd.personas()), 200)

    def test_plan_each_brand_once_per_persona(self):
        bs, ps = brands(80), crowd.personas(3)
        jobs = crowd.plan(bs, ps, 1)
        self.assertEqual(len(jobs), 6)  # 80 brands -> 2 batches of 40
        for p in ps:
            got = [b["key"] for q, batch in jobs if q is p for b in batch]
            self.assertEqual(sorted(got), sorted(b["key"] for b in bs))

    def test_plan_balanced_batches(self):
        jobs = crowd.plan(brands(61), crowd.personas(1), 1)
        self.assertEqual(sorted(len(b) for _, b in jobs), [30, 31])

    def test_valid(self):
        b = brands(2)
        ok = {"answers": {"b00": {"heard": 3, "buy": 1}, "b01": {"heard": 10, "buy": 7}}}
        self.assertIsNotNone(crowd.valid(ok, b))
        self.assertIsNone(crowd.valid({"answers": {"b00": {"heard": 3, "buy": 1}}}, b))
        bad = {"answers": {"b00": {"heard": 0, "buy": 1}, "b01": {"heard": 10, "buy": 7}}}
        self.assertIsNone(crowd.valid(bad, b))
        self.assertIsNone(crowd.valid({"answers": {"b00": {"heard": 3.5, "buy": 1}, "b01": {"heard": 1, "buy": 1}}}, b))


if __name__ == "__main__":
    unittest.main()
