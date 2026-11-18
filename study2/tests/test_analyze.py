import math, random, unittest
from study2 import analyze as A


class Analyze(unittest.TestCase):
    def test_ols_recovers_exact_line(self):
        xs = [[x, x * x % 7] for x in range(10)]
        y = [2 + 3 * a - 0.5 * b for a, b in xs]
        beta = A._ols_fit(xs, y)
        for got, want in zip(beta, [2, 3, -0.5]):
            self.assertAlmostEqual(got, want, places=8)

    def test_loo_exact_fit_predicts_exactly(self):
        xs = [[float(x)] for x in range(8)]
        y = [1 + 2 * x[0] for x in xs]
        for p, t in zip(A.loo_predictions(xs, y), y):
            self.assertAlmostEqual(p, t, places=8)

    def test_partial_zero_when_x_is_z(self):
        z = [3, 1, 4, 1.5, 5, 9, 2.6]
        y = [2, 7, 1, 8, 2.8, 1.8, 2.9]
        self.assertIsNone(A.partial_rho(z, y, z))  # rxz = 1 -> undefined

    def test_fame_driven_crowd(self):
        rng = random.Random(0)
        n = 60
        views = [math.exp(rng.gauss(12, 1.5)) for _ in range(n)]
        revenue = [math.exp(rng.gauss(20, 1.5)) for _ in range(n)]  # unrelated to fame
        intent = [math.log(v) + rng.gauss(0, 0.3) for v in views]  # crowd follows fame only
        r = A.score(intent, revenue, views)
        self.assertEqual(r["H1"]["verdict"], "PASS")
        self.assertTrue(r["H2"]["verdict"].startswith("PASS"))
        self.assertEqual(r["H3"]["verdict"], "FAIL")

    def test_revenue_aware_crowd(self):
        rng = random.Random(1)
        n = 60
        views = [math.exp(rng.gauss(12, 1.5)) for _ in range(n)]
        revenue = [math.exp(rng.gauss(20, 1.5)) for _ in range(n)]
        intent = [math.log(r) + rng.gauss(0, 0.2) for r in revenue]  # crowd knows spending
        r = A.score(intent, revenue, views)
        self.assertEqual(r["H1"]["verdict"], "FAIL")
        self.assertTrue(r["H2"]["verdict"].startswith("FAIL"))

    def test_brand_means(self):
        rows = [{"cik": "1", "buy": 2, "heard": 4}, {"cik": "1", "buy": 4, "heard": 6}]
        self.assertEqual(A.brand_means(rows), {"1": {"buy": 3, "heard": 5}})


if __name__ == "__main__":
    unittest.main()
