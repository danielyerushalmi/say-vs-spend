"""Tests for say.flashpoint_import. Run: python3 -m unittest say.tests.test_flashpoint_import"""
import os
import tempfile
import unittest

from say import flashpoint_import as fi

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "..", "fixtures", "FAKE_TEST_DATA_export.csv")
BRANDS = [
    {"id": "figs", "name": "Figs"},
    {"id": "allbirds", "name": "Allbirds"},
    {"id": "1800flowers", "name": "1-800-Flowers", "aliases": ["flowers"]},
    {"id": "casper", "name": "Casper"},
]
QMAP = {"Q1": "say", "Q2": "intent", "Q3": "aware"}


def write_csv(text):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "export.csv")
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def rec(panel, pid, bid):
    for r in panel["responses"]:
        if r["persona_id"] == pid and r["brand_id"] == bid:
            return r
    return None


class ValueParsing(unittest.TestCase):
    def test_scale(self):
        for raw, want in [("7", 7), (" 7 ", 7), ("7 - Good", 7), ("10 (Extremely likely)", 10),
                          ("7.0", 7), ("Extremely likely (10)", 10)]:
            self.assertEqual(fi.parse_scale(raw), (want, None), raw)

    def test_scale_rejects(self):
        self.assertEqual(fi.parse_scale("11")[0], None)
        self.assertEqual(fi.parse_scale("0")[1], "out of range")
        self.assertEqual(fi.parse_scale("7.5")[1], "unparseable")
        self.assertEqual(fi.parse_scale("very good")[1], "unparseable")

    def test_blank_is_not_a_problem(self):
        for raw in ["", "  ", None, "N/A"]:
            self.assertEqual(fi.parse_scale(raw), (None, None))
            self.assertEqual(fi.parse_bool(raw), (None, None))

    def test_bool(self):
        for raw in ["Yes", "yes", "Y", "true", "1", "Yes, I have heard of it"]:
            self.assertEqual(fi.parse_bool(raw), (True, None), raw)
        for raw in ["No", "n", "FALSE", "0", "No, never heard of it"]:
            self.assertEqual(fi.parse_bool(raw), (False, None), raw)
        self.assertEqual(fi.parse_bool("not sure"), (None, "unparseable"))


class HeaderSplitting(unittest.TestCase):
    def test_variants(self):
        for h in ["Q1__figs", "Q1_figs", "Q1 - figs", "Q1[figs]", "Q1: figs", "Q1.figs", "Q1 figs"]:
            self.assertEqual(fi.split_header(h), ("Q1", "figs"), h)

    def test_hyphenated_brand(self):
        self.assertEqual(fi.split_header("Q1 - 1-800-Flowers"), ("Q1", "1-800-Flowers"))
        self.assertEqual(fi.split_header("Q2__1_800_flowers"), ("Q2", "1_800_flowers"))

    def test_question_text(self):
        self.assertEqual(fi.split_header("How good is this brand's website? - Figs"),
                         ("How good is this brand's website?", "Figs"))

    def test_not_looped(self):
        self.assertIsNone(fi.split_header("duration_sec"))
        self.assertIsNone(fi.split_header("panel_respondent_id"))


class AliasMatching(unittest.TestCase):
    def setUp(self):
        self.m = fi.build_brand_matcher(BRANDS)

    def test_exact_and_punctuation(self):
        self.assertEqual(self.m("FIGS")[0], "figs")
        self.assertEqual(self.m("1-800-Flowers")[0], "1800flowers")
        self.assertEqual(self.m("1_800_flowers")[0], "1800flowers")

    def test_alias_and_containment(self):
        self.assertEqual(self.m("flowers")[0], "1800flowers")
        self.assertEqual(self.m("Allbirds Inc")[0], "allbirds")

    def test_no_match(self):
        self.assertIsNone(self.m("brand_a")[0])

    def test_alias_argument_and_loop_key_map(self):
        m = fi.build_brand_matcher(BRANDS, aliases={"casper": ["sleep co"]}, loop_key_map={"brand_a": "figs"})
        self.assertEqual(m("Sleep Co")[0], "casper")
        self.assertEqual(m("brand_a")[0], "figs")

    def test_ambiguous_not_guessed(self):
        brands = [{"id": "a", "name": "Sun Shoes"}, {"id": "b", "name": "Sun Socks"}]
        self.assertIsNone(fi.build_brand_matcher(brands)("sun")[0])


class FullImport(unittest.TestCase):
    def setUp(self):
        self.panel = fi.import_export(FIXTURE, BRANDS, {"panel_id": "fake", "recorded_at": "x"}, question_map=QMAP)
        self.info = self.panel["_import"]

    def test_shape(self):
        p = self.panel
        for k in ["panel_id", "source_link", "recorded_at", "n_personas", "persona_model_note", "order", "responses"]:
            self.assertIn(k, p)
        self.assertEqual(p["n_personas"], 5)
        self.assertEqual(p["order"], "shuffled")
        self.assertEqual(self.info["id_column"], "panel_respondent_id")

    def test_values_and_label_formats(self):
        self.assertEqual(rec(self.panel, "FAKE-001", "figs"), {"persona_id": "FAKE-001", "brand_id": "figs", "say": 7, "intent": 6, "aware": True, "buy": None})
        r = rec(self.panel, "FAKE-002", "allbirds")
        self.assertEqual((r["say"], r["intent"], r["aware"]), (10, 10, True))
        self.assertEqual(rec(self.panel, "FAKE-002", "figs")["intent"], 8)

    def test_blanks_skipped(self):
        # FAKE-002 casper and FAKE-003 flowers are entirely blank: no record at all.
        self.assertIsNone(rec(self.panel, "FAKE-002", "casper"))
        self.assertIsNone(rec(self.panel, "FAKE-003", "1800flowers"))
        # FAKE-005 figs intent blank but others present: record kept, intent None.
        r = rec(self.panel, "FAKE-005", "figs")
        self.assertIsNone(r["intent"])
        self.assertEqual(r["say"], 9)

    def test_bad_values_reported_not_dropped_silently(self):
        self.assertIsNone(rec(self.panel, "FAKE-004", "figs")["say"])      # 11 out of range
        self.assertIsNone(rec(self.panel, "FAKE-004", "allbirds")["intent"])  # 0 out of range
        probs = {(u["persona_id"], u["column"]): u["problem"] for u in self.info["unparseable_values"]}
        self.assertEqual(probs[("FAKE-004", "Q1__figs")], "out of range")
        self.assertEqual(probs[("FAKE-004", "Q2__allbirds")], "out of range")
        self.assertEqual(probs[("FAKE-005", "Q3__casper")], "unparseable")
        self.assertTrue(rec(self.panel, "FAKE-004", "figs")["aware"])      # "true"
        self.assertFalse(rec(self.panel, "FAKE-004", "1800flowers")["aware"])  # "0"

    def test_admin_column_ignored_not_unmatched(self):
        # Non-looped admin columns never block a run; they are listed as ignored.
        self.assertEqual([u["column"] for u in self.info["unmatched_columns"]], [])
        self.assertEqual(self.info["ignored_admin_columns"], ["duration_sec"])

    def test_repeated_header_row_skipped(self):
        import csv, tempfile
        src = list(csv.reader(open(FIXTURE, encoding="utf-8")))
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(src[0]); w.writerow(src[0]); w.writerows(src[1:])
        panel = fi.import_export(f.name, BRANDS, question_map=QMAP)
        self.assertTrue(panel["_import"]["label_row_skipped"])
        self.assertEqual(panel["n_personas"], self.panel["n_personas"])

    def test_summary_text(self):
        text = fi.summarize_import(self.panel)
        self.assertIn("5 personas", text)
        self.assertIn("duration_sec", text)
        self.assertIn("figs", text)
        counts = fi.count_table(self.panel)
        self.assertEqual(counts["casper"]["say"], 4)  # 001, 003, 004, 005; 002 blank


TWO = [{"id": "figs", "name": "Figs"}, {"id": "allbirds", "name": "Allbirds"}]


class HeaderVariantsEndToEnd(unittest.TestCase):
    def check(self, header, q=None):
        p = fi.import_export(write_csv(header + "\nR1,7,5,Yes\n"), TWO, {}, question_map=q)
        r = rec(p, "R1", "figs")
        return p, r

    def test_each_separator(self):
        for h in ["Q1_figs,Q2_figs,Q3_figs", "Q1 - Figs,Q2 - Figs,Q3 - Figs", "Q1[figs],Q2[figs],Q3[figs]"]:
            p, r = self.check("response_id," + h, QMAP)
            self.assertEqual((r["say"], r["intent"], r["aware"]), (7, 5, True), h)
            self.assertEqual(p["_import"]["unmatched_columns"], [])
            self.assertEqual(p["_import"]["id_column"], "response_id")

    def test_question_text_headers_detect_kinds(self):
        h = ("id,How good is this brand's website? - Figs,How likely are you to buy from this website "
             "in the next 12 months? - Figs,Have you heard of this brand? - Figs")
        p, r = self.check(h)
        self.assertEqual((r["say"], r["intent"], r["aware"]), (7, 5, True))
        self.assertEqual(p["_import"]["question_kinds"]["How likely are you to buy from this website in the next 12 months?"]["kind"], "intent")

    def test_second_row_question_text(self):
        text = ("respondent_id,Q1__figs,Q2__figs,Q3__figs\n"
                "Response ID,How good is the website of this brand?,How likely are you to buy in the next 12 months?,Have you heard of this brand?\n"
                "R1,7,5,Yes\n")
        p = fi.import_export(write_csv(text), TWO, {})
        self.assertEqual(p["n_personas"], 1)  # text row not counted as a persona
        r = rec(p, "R1", "figs")
        self.assertEqual((r["say"], r["intent"], r["aware"]), (7, 5, True))
        self.assertEqual(p["_import"]["question_kinds"]["Q2"]["source"], "question text keywords")

    def test_unmapped_question_is_reported(self):
        p = fi.import_export(write_csv("id,Q1__figs,Q9__figs\nR1,7,3\n"), TWO, {}, question_map={"Q1": "say"})
        self.assertEqual(rec(p, "R1", "figs")["say"], 7)
        cols = {u["column"]: u["reason"] for u in p["_import"]["unmatched_columns"]}
        self.assertIn("Q9__figs", cols)

    def test_unknown_brand_column_reported(self):
        p = fi.import_export(write_csv("id,Q1__figs,Q1__brand_z\nR1,7,4\n"), TWO, {}, question_map={"Q1": "say"})
        cols = {u["column"]: u["reason"] for u in p["_import"]["unmatched_columns"]}
        self.assertEqual(list(cols), ["Q1__brand_z"])

    def test_duplicate_persona_reported(self):
        p = fi.import_export(write_csv("id,Q1__figs\nR1,7\nR1,3\n"), TWO, {}, question_map={"Q1": "say"})
        self.assertEqual(p["n_personas"], 1)
        self.assertEqual(rec(p, "R1", "figs")["say"], 7)
        self.assertEqual(p["_import"]["duplicate_persona_ids_skipped"], ["R1"])

    def test_bad_question_map_value(self):
        with self.assertRaises(ValueError):
            fi.import_export(write_csv("id,Q1__figs\nR1,7\n"), TWO, {}, question_map={"Q1": "nope"})


class Cli(unittest.TestCase):
    def test_cli_writes_and_refuses_overwrite(self):
        import json
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "figs.json"), "w") as f:
            json.dump({"id": "figs", "name": "Figs"}, f)
        with open(os.path.join(d, "all.json"), "w") as f:
            json.dump([{"id": "allbirds", "name": "Allbirds"}, {"id": "casper", "name": "Casper"}, {"id": "1800flowers", "name": "1-800-Flowers"}], f)
        out = os.path.join(d, "out", "panel.json")
        args = [FIXTURE, "--brands-dir", d, "--out", out, "--panel-id", "t", "--question-map", "Q1=say,Q2=intent,Q3=aware"]
        self.assertEqual(fi.main(args), 0)
        with open(out) as f:
            self.assertEqual(json.load(f)["panel_id"], "t")
        self.assertEqual(fi.main(args), 3)           # exists, no --force
        self.assertEqual(fi.main(args + ["--force"]), 0)


BUY_FIXTURE = os.path.join(HERE, "..", "fixtures", "FAKE_TEST_DATA_export_buy.csv")


class BuyColumn(unittest.TestCase):
    def test_buy_parsed_with_default_map_and_label_row_skipped(self):
        panel = fi.import_export(BUY_FIXTURE, BRANDS)
        self.assertEqual(panel["n_personas"], 20)  # label row not counted as a persona
        self.assertEqual(panel["_import"]["question_kinds"]["BUY"]["kind"], "buy")
        self.assertIs(rec(panel, "FAKE-B01", "figs")["buy"], True)
        self.assertIs(rec(panel, "FAKE-B20", "casper")["buy"], False)
        self.assertEqual(sum(1 for r in panel["responses"] if r["brand_id"] == "casper" and r["buy"] is True), 6)

    def test_buy_yes_no_words_and_codes(self):
        csv_text = "id,BUY__figs\nA,1\nB,2\nC,Yes\nD,No\nE,\nF,maybe\n"
        panel = fi.import_export(write_csv(csv_text), BRANDS)
        got = {pid: (rec(panel, pid, "figs") or {}).get("buy") for pid in "ABCDEF"}
        self.assertEqual(got, {"A": True, "B": False, "C": True, "D": False, "E": None, "F": None})
        self.assertEqual(len(panel["_import"]["unparseable_values"]), 1)

    def test_export_without_buy_columns_imports_as_before(self):
        panel = fi.import_export(FIXTURE, BRANDS, question_map=QMAP)
        self.assertTrue(all(r["buy"] is None for r in panel["responses"]))
        self.assertNotIn("buy", fi.count_table(panel)["figs"])

    def test_short_label_row_is_skipped(self):
        csv_text = "id,SAY__figs,BUY__figs\n,SAY label,BUY label\nA,5,1\n"
        panel = fi.import_export(write_csv(csv_text), BRANDS)
        self.assertEqual(panel["n_personas"], 1)
        self.assertTrue(panel["_import"]["label_row_skipped"])


if __name__ == "__main__":
    unittest.main()


class TestFlashpointSurveyFormat(unittest.TestCase):
    """Exact format our Flashpoint survey exports: LABEL__loopkey, AWARE codes 1=Yes / 2=No."""

    def test_say_intent_aware_columns_and_codes(self):
        import os
        import tempfile
        from say.flashpoint_import import import_export
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "export.csv")
            with open(path, "w") as f:
                f.write("panel_respondent_id,SAY__figs,INTENT__figs,AWARE__figs\nFAKE-1,7,3,1\nFAKE-2,9,5,2\n")
            p = import_export(path, [{"id": "figs", "name": "Figs"}], {"panel_id": "FAKE TEST DATA"})
        rows = {r["persona_id"]: r for r in p["responses"]}
        self.assertEqual((rows["FAKE-1"]["say"], rows["FAKE-1"]["intent"], rows["FAKE-1"]["aware"]), (7, 3, True))
        self.assertEqual(rows["FAKE-2"]["aware"], False)
