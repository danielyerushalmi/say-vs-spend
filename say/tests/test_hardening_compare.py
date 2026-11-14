"""Hardening tests for say.compare: property-style checks on seeded random inputs.

Standard library only. Every random input comes from a fixed seed, so a failure is reproducible.
Run: python3 -m unittest say.tests.test_hardening_compare
"""
import itertools
import math
import random
import unittest
from fractions import Fraction

from say import compare as c

SEED = 20261114


def brute_ranks(values, higher_is_better=True):
    """Average rank, computed the slow obvious way: 1 + (# strictly better) + (# tied others) / 2."""
    out = []
    for i, v in enumerate(values):
        if higher_is_better:
            better = sum(1 for w in values if w > v)
        else:
            better = sum(1 for w in values if w < v)
        tied_others = sum(1 for j, w in enumerate(values) if w == v and j != i)
        out.append(1 + better + tied_others / 2)
    return out


def _exact_sxy_parts(x, y):
    """Exact (Fraction) centred cross-product and sums of squares."""
    xs = [Fraction(v) for v in x]
    ys = [Fraction(v) for v in y]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    return sxy, sxx, syy


def brute_exact_p(crowd_ranks, rev_ranks):
    """Independent two-sided permutation p-value, in exact arithmetic.

    Permuting the revenue ranks leaves sxx and syy unchanged, so |rho_perm| >= |rho_obs|
    exactly when |sxy_perm| >= |sxy_obs|. Count over all n! orderings of the positions.
    """
    n = len(crowd_ranks)
    if n < 3 or n > c.EXACT_MAX_N:
        return None
    sxy_obs, sxx, syy = _exact_sxy_parts(crowd_ranks, rev_ranks)
    if sxx == 0 or syy == 0:
        return None
    hits = total = 0
    for idx in itertools.permutations(range(n)):
        perm = [rev_ranks[i] for i in idx]
        sxy, _, _ = _exact_sxy_parts(crowd_ranks, perm)
        total += 1
        if abs(sxy) >= abs(sxy_obs):
            hits += 1
    return hits / total


def rand_list(rng, n, lo=-20, hi=20, ties=True):
    if ties:
        return [rng.randint(lo // 4, hi // 4) for _ in range(n)]
    return rng.sample(range(lo, hi + 1), n)


class SpearmanProperties(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(SEED)

    def test_symmetric_and_bounded(self):
        for _ in range(300):
            n = self.rng.randint(3, 12)
            x = c.ranks(rand_list(self.rng, n, ties=self.rng.random() < 0.5))
            y = c.ranks(rand_list(self.rng, n, ties=self.rng.random() < 0.5))
            a, b = c.spearman(x, y), c.spearman(y, x)
            if a is None:
                self.assertIsNone(b)
                continue
            self.assertAlmostEqual(a, b, places=12)
            self.assertGreaterEqual(a, -1.0)
            self.assertLessEqual(a, 1.0)

    def test_identical_order_is_one_and_reversed_is_minus_one(self):
        for _ in range(200):
            n = self.rng.randint(3, 15)
            vals = rand_list(self.rng, n, ties=False)
            r = c.ranks(vals)
            self.assertAlmostEqual(c.spearman(r, r), 1.0, places=12)
            self.assertAlmostEqual(c.spearman(r, c.ranks(vals, higher_is_better=False)), -1.0, places=12)
            # Same order with ties on both sides is still a perfect +1.
            tied = rand_list(self.rng, n, ties=True)
            if len(set(tied)) > 1:
                self.assertAlmostEqual(c.spearman_from_values(tied, tied), 1.0, places=12)
                self.assertAlmostEqual(c.spearman_from_values(tied, [-v for v in tied]), -1.0, places=12)

    def test_invariant_to_monotone_transforms(self):
        increasing = [lambda v: 2 * v + 7, lambda v: v ** 3 + 5, lambda v: math.exp(v / 10), lambda v: v + 1e6]
        decreasing = [lambda v: -v, lambda v: 100 - v ** 3]
        for _ in range(200):
            n = self.rng.randint(3, 10)
            x = rand_list(self.rng, n, ties=self.rng.random() < 0.5)
            y = rand_list(self.rng, n, ties=self.rng.random() < 0.5)
            base = c.spearman_from_values(x, y)
            for f in increasing:
                got = c.spearman_from_values([f(v) for v in x], y)
                if base is None:
                    self.assertIsNone(got)
                else:
                    self.assertAlmostEqual(got, base, places=12)
            for f in decreasing:
                got = c.spearman_from_values([f(v) for v in x], y)
                if base is None:
                    self.assertIsNone(got)
                else:
                    self.assertAlmostEqual(got, -base, places=12)

    def test_none_cases(self):
        self.assertIsNone(c.spearman([1, 2], [1, 2]))            # n < 3
        self.assertIsNone(c.spearman([1, 2, 3], [1, 2]))         # unequal lengths
        self.assertIsNone(c.spearman([2, 2, 2], [1, 2, 3]))      # zero variance
        self.assertIsNone(c.spearman_from_values([5, 5, 5, 5], [1, 2, 3, 4]))


class RanksProperties(unittest.TestCase):
    def test_matches_brute_force_on_200_random_lists(self):
        rng = random.Random(SEED + 1)
        for _ in range(200):
            n = rng.randint(1, 9)
            if rng.random() < 0.5:
                vals = [rng.randint(0, 4) for _ in range(n)]           # many ties
            else:
                vals = [rng.choice([0.5, 1.25, 2.0, 3.75]) for _ in range(n)]
            for hib in (True, False):
                self.assertEqual(c.ranks(vals, higher_is_better=hib), brute_ranks(vals, hib), (vals, hib))

    def test_ties_get_average_rank(self):
        self.assertEqual(c.ranks([10, 20, 20, 5]), [3.0, 1.5, 1.5, 4.0])
        self.assertEqual(c.ranks([7, 7, 7]), [2.0, 2.0, 2.0])
        self.assertEqual(c.ranks([]), [])
        self.assertEqual(c.ranks([3]), [1.0])

    def test_rank_sum_is_constant(self):
        rng = random.Random(SEED + 2)
        for _ in range(100):
            n = rng.randint(1, 12)
            vals = [rng.randint(0, 3) for _ in range(n)]
            self.assertAlmostEqual(sum(c.ranks(vals)), n * (n + 1) / 2)


class ExactP(unittest.TestCase):
    def test_matches_brute_force_on_random_n4_to_7(self):
        rng = random.Random(SEED + 3)
        checked = 0
        for n in (4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 7, 7):
            for _ in range(2 if n < 7 else 1):
                crowd = c.ranks([rng.randint(1, 5) for _ in range(n)])
                rev = c.ranks([rng.randint(1, 9) for _ in range(n)])
                want = brute_exact_p(crowd, rev)
                got = c.exact_p(crowd, rev)
                if want is None:
                    self.assertIsNone(got, (crowd, rev))
                    continue
                checked += 1
                self.assertAlmostEqual(got, want, places=12, msg=(crowd, rev))
        self.assertGreaterEqual(checked, 15)

    def test_matches_brute_force_without_ties(self):
        rng = random.Random(SEED + 4)
        for n in (4, 5, 6, 7):
            vals = list(range(1, n + 1))
            rev = vals[:]
            rng.shuffle(rev)
            crowd = c.ranks(vals)
            revr = c.ranks(rev)
            self.assertAlmostEqual(c.exact_p(crowd, revr), brute_exact_p(crowd, revr), places=12)

    def test_rho_zero_gives_one(self):
        # sum d^2 = n(n^2-1)/6 -> rho exactly 0.
        cases = [([1, 2, 3, 4], [2, 4, 1, 3]),
                 ([1, 2, 3, 4, 5], [2, 5, 3, 1, 4])]
        for crowd, rev in cases:
            self.assertAlmostEqual(c.spearman(crowd, rev), 0.0, places=12)
            self.assertEqual(c.exact_p(crowd, rev), 1.0)

    def test_perfect_n6_is_2_over_720(self):
        r = [1, 2, 3, 4, 5, 6]
        self.assertAlmostEqual(c.exact_p(r, r), 2 / 720, places=15)
        self.assertAlmostEqual(c.exact_p(r, r[::-1]), 2 / 720, places=15)

    def test_out_of_range_n_is_none(self):
        self.assertIsNone(c.exact_p([1, 2], [1, 2]))
        nine = list(range(1, 10))
        self.assertIsNone(c.exact_p(nine, nine))
        self.assertIsNone(c.exact_p([2, 2, 2], [1, 2, 3]))   # zero variance

    def test_p_in_unit_interval(self):
        rng = random.Random(SEED + 5)
        for _ in range(10):
            n = rng.randint(3, 6)
            p = c.exact_p(c.ranks([rng.random() for _ in range(n)]), c.ranks([rng.random() for _ in range(n)]))
            self.assertGreater(p, 0.0)
            self.assertLessEqual(p, 1.0)


class TrustVerdict(unittest.TestCase):
    ORDER = ["ask_real_people", "verify", "trust"]

    def test_monotone_in_wobble_low(self):
        rng = random.Random(SEED + 6)
        grid = sorted([i / 200 for i in range(-200, 201)] + [rng.uniform(-1, 1) for _ in range(300)]
                      + [0.4, 0.7, math.nextafter(0.4, 0), math.nextafter(0.7, 0)])
        for point in (None, -0.5, 0.0, 0.5, 0.95):
            levels = [self.ORDER.index(c.trust_verdict(point, w, 1.0)["verdict"]) for w in grid]
            self.assertEqual(levels, sorted(levels), point)

    def test_never_trust_below_cutoff(self):
        rng = random.Random(SEED + 7)
        lows = [rng.uniform(-1, 0.6999) for _ in range(500)] + [0.6999, 0.69, -1.0, 0.0]
        for w in lows:
            for point in (1.0, 0.99, None):
                self.assertNotEqual(c.trust_verdict(point, w, 1.0)["verdict"], "trust", w)

    # Regression guard: a working-tree edit on 2026-11-14 briefly added
    # `wobble_low = round(wobble_low, 4)` to trust_verdict, which promoted 0.69996 to "trust"
    # against the pre-registered rule ("0.7 or higher"). If the page must show the same value
    # as the label, truncate for display (math.floor(x * 1e4) / 1e4); never round the input.
    def test_never_trust_just_below_cutoff(self):
        for w in (0.69996, 0.69999, math.nextafter(0.7, 0)):
            for point in (1.0, 0.99, None):
                self.assertNotEqual(c.trust_verdict(point, w, 1.0)["verdict"], "trust", w)

    def test_boundaries_and_none(self):
        self.assertEqual(c.trust_verdict(0.9, 0.7, 0.95)["verdict"], "trust")
        self.assertEqual(c.trust_verdict(0.9, 0.4, 0.95)["verdict"], "verify")
        self.assertEqual(c.trust_verdict(0.9, 0.39, 0.95)["verdict"], "ask_real_people")
        self.assertEqual(c.trust_verdict(0.9, None, None)["verdict"], "ask_real_people")
        self.assertEqual(c.trust_verdict(None, None, None)["verdict"], "ask_real_people")

    def test_downgraded_only_when_point_band_is_better(self):
        rng = random.Random(SEED + 8)
        for _ in range(300):
            low = rng.uniform(-1, 1)
            point = rng.uniform(-1, 1)
            out = c.trust_verdict(point, low, 1.0)
            better = self.ORDER.index(c._band(point)) > self.ORDER.index(out["verdict"])
            self.assertEqual(out["downgraded"], better)


class AgreementSmallN(unittest.TestCase):
    NUMBERS = ("spearman", "wobble_low", "wobble_high", "p_exact", "avg_places_off")

    def _brands(self, pairs):
        return [{"intent_mean": a, "say_mean": a, "aware_share": a, "revenue_usd": r} for a, r in pairs]

    def test_fewer_than_three_usable_brands_gives_none_numbers(self):
        for pairs in ([], [(5.0, 100.0)], [(5.0, 100.0), (6.0, 200.0)]):
            for q in c.QUESTIONS:
                out = c.agreement(self._brands(pairs), q, n_boot=50)
                for k in self.NUMBERS:
                    self.assertIsNone(out[k], (pairs, q, k))
                self.assertTrue(out["could_be_chance"])

    def test_unusable_rows_do_not_count_toward_n(self):
        brands = [
            {"intent_mean": 5.0, "revenue_usd": 100.0},
            {"intent_mean": 6.0, "revenue_usd": 200.0},
            {"intent_mean": None, "revenue_usd": 300.0},
            {"intent_mean": 7.0, "revenue_usd": None},
            {"intent_mean": float("nan"), "revenue_usd": 400.0},
            {"intent_mean": 8.0, "revenue_usd": True},       # bool is not a number
            {"revenue_usd": 500.0},
        ]
        out = c.agreement(brands, "intent", n_boot=50)
        for k in self.NUMBERS:
            self.assertIsNone(out[k], k)

    def test_all_tied_crowd_gives_none(self):
        out = c.agreement(self._brands([(5.0, 1.0), (5.0, 2.0), (5.0, 3.0), (5.0, 4.0)]), "intent", n_boot=50)
        for k in self.NUMBERS:
            self.assertIsNone(out[k], k)

    def test_p_exact_matches_exact_p_and_chance_rule(self):
        rng = random.Random(SEED + 9)
        for n in (3, 4, 5, 6):
            pairs = [(rng.randint(1, 10), rng.randint(1, 1000)) for _ in range(n)]
            out = c.agreement(self._brands(pairs), "intent", n_boot=100)
            if out["spearman"] is None:
                continue
            crowd = c.ranks([float(a) for a, _ in pairs])
            rev = c.ranks([float(r) for _, r in pairs])
            self.assertEqual(out["p_exact"], c.exact_p(crowd, rev))
            if out["p_exact"] > 0.05:
                self.assertTrue(out["could_be_chance"])

    def test_perfect_n5_is_not_chance_but_n4_is(self):
        five = c.agreement(self._brands([(i, i * 10) for i in range(1, 6)]), "intent", n_boot=200)
        self.assertAlmostEqual(five["p_exact"], 2 / 120)
        self.assertFalse(five["could_be_chance"])
        four = c.agreement(self._brands([(i, i * 10) for i in range(1, 5)]), "intent", n_boot=200)
        self.assertAlmostEqual(four["p_exact"], 2 / 24)
        self.assertTrue(four["could_be_chance"])   # p = 0.083 > 0.05


class BootstrapReproducible(unittest.TestCase):
    def test_same_seed_same_answer(self):
        rng = random.Random(SEED + 10)
        for _ in range(5):
            n = rng.randint(3, 8)
            pairs = [(rng.randint(1, 10), rng.randint(1, 100)) for _ in range(n)]
            a = c.bootstrap_wobble(pairs, n_boot=300, seed=42)
            b = c.bootstrap_wobble(pairs, n_boot=300, seed=42)
            self.assertEqual(a, b)
            if a is not None:
                low, high = a
                # Only the ordering of the two percentiles is guaranteed (NOT that the point
                # Spearman sits between them).
                self.assertLessEqual(low, high)
                self.assertGreaterEqual(low, -1.0)
                self.assertLessEqual(high, 1.0)

    def test_agreement_reproducible(self):
        brands = [{"intent_mean": v, "revenue_usd": r} for v, r in
                  [(7.1, 900), (6.2, 300), (5.5, 500), (4.9, 100), (6.8, 50), (3.3, 20)]]
        self.assertEqual(c.agreement(brands, "intent", n_boot=300, seed=7),
                         c.agreement(brands, "intent", n_boot=300, seed=7))

    def test_too_few_pairs(self):
        self.assertIsNone(c.bootstrap_wobble([(1, 2), (2, 3)], n_boot=50))


if __name__ == "__main__":
    unittest.main()
