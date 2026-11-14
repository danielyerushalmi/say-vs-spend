import os
import tempfile
import unittest

from say import repeat


def main_run():
    # Main-panel intent ranking: a > b > c > d (by intent_mean).
    def b(i, rev, say, intent, aw):
        return {"id": i, "name": i.upper(), "revenue_usd": rev, "say_mean": say,
                "intent_mean": intent, "aware_share": aw}
    return {"brands": [b("a", 400, 8, 8, 0.9), b("b", 300, 7, 7, 0.8),
                       b("c", 200, 6, 6, 0.7), b("d", 100, 5, 5, 0.6)]}


def write_csv(rows_by_brand, n=4, drop=()):
    """rows_by_brand: {brand: (say, intent, aware_bool)} same for every persona."""
    cols = []
    for q in ("SAY", "INTENT", "AWARE"):
        for bid in rows_by_brand:
            if bid not in drop:
                cols.append(f"{q}__{bid}")
    lines = ["pid," + ",".join(cols), "pid," + ",".join(cols)]  # repeated header row
    for i in range(n):
        vals = []
        for qi in range(3):
            for bid, v in rows_by_brand.items():
                if bid in drop:
                    continue
                vals.append(("Yes" if v[2] else "No") if qi == 2 else str(v[qi]))
        lines.append(f"P{i}," + ",".join(vals))
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
    f.write("\n".join(lines) + "\n")
    f.close()
    return f.name


class RepeatTests(unittest.TestCase):
    def run_block(self, data, **kw):
        path = write_csv(data, **kw)
        self.addCleanup(os.remove, path)
        return repeat.repeat_block(main_run(), path, brands_dir="no/such/dir", n_boot=50, **kw and {})

    def test_same_order_gives_perfect_stability(self):
        blk = self.run_block({"a": (9, 9, True), "b": (7, 7, True), "c": (5, 5, False), "d": (3, 3, False),
                              "extra": (10, 10, True)})
        st = blk["stability"]
        self.assertEqual(st["intent_rank_spearman_between_panels"], 1.0)
        self.assertEqual(st["max_rank_move"], 0)
        self.assertEqual(blk["label"], "SYNTHETIC")
        self.assertEqual(blk["n_personas"], 4)
        self.assertEqual([b["id"] for b in blk["brands"]], ["a", "b", "c", "d"])  # 'extra' ignored
        self.assertEqual(blk["agreement"]["intent"]["spearman"], 1.0)
        self.assertIn("verdict", blk["verdict_if_main"])
        self.assertEqual(blk["stability"]["note"], repeat.NOTE)

    def test_swap_moves(self):
        # repeat intent ranks: b > a > c > d  -> a and b each move 1 place
        blk = self.run_block({"a": (9, 6, True), "b": (7, 9, True), "c": (5, 5, True), "d": (3, 3, True)})
        moves = {m["id"]: m for m in blk["stability"]["moves"]}
        self.assertEqual(moves["a"]["rank_intent_main"], 1)
        self.assertEqual(moves["a"]["rank_intent_repeat"], 2)
        self.assertEqual(moves["a"]["move"], 1)
        self.assertEqual(moves["c"]["move"], 0)
        self.assertEqual(blk["stability"]["max_rank_move"], 1)
        # Spearman of [1,2,3,4] vs [2,1,3,4] = 0.8
        self.assertAlmostEqual(blk["stability"]["intent_rank_spearman_between_panels"], 0.8, places=4)

    def test_fully_reversed(self):
        blk = self.run_block({"a": (1, 1, False), "b": (2, 2, False), "c": (3, 3, True), "d": (4, 4, True)})
        self.assertEqual(blk["stability"]["intent_rank_spearman_between_panels"], -1.0)
        self.assertEqual(blk["stability"]["max_rank_move"], 3)
        self.assertEqual(blk["stability"]["moves"][0]["move"], 3)

    def test_missing_brand_left_out_and_ranks_on_common_set(self):
        blk = self.run_block({"a": (9, 9, True), "b": (7, 7, True), "c": (5, 5, True), "d": (3, 3, True)}, drop=("d",))
        self.assertEqual(blk["brands_left_out"], ["d"])
        self.assertEqual([b["id"] for b in blk["brands"]], ["a", "b", "c"])
        self.assertEqual(blk["stability"]["max_rank_move"], 0)

    def test_keys_present(self):
        blk = self.run_block({"a": (9, 9, True), "b": (7, 7, True), "c": (5, 5, True), "d": (3, 3, True)})
        for k in ("panel_id", "recorded_at", "n_personas", "label", "brands", "agreement",
                  "verdict_if_main", "stability"):
            self.assertIn(k, blk)
        for q in ("say", "intent", "fame"):
            for k in ("spearman", "wobble_low", "wobble_high", "could_be_chance", "avg_places_off"):
                self.assertIn(k, blk["agreement"][q])
        for k in ("rank_say", "rank_intent", "rank_fame", "say_mean", "intent_mean", "aware_share", "id"):
            self.assertIn(k, blk["brands"][0])
        for k in ("intent_rank_spearman_between_panels", "say_rank_spearman_between_panels",
                  "fame_rank_spearman_between_panels", "max_rank_move", "moves", "note"):
            self.assertIn(k, blk["stability"])


if __name__ == "__main__":
    unittest.main()
