"""Hardening tests for say.flashpoint_import on awkward-but-realistic CSV exports.

All data here is FAKE, built inline. Run: python3 -m unittest say.tests.test_hardening_import
"""
import os
import tempfile
import unittest

from say import flashpoint_import as fi

BRANDS = [
    {"id": "figs", "name": "Figs"},
    {"id": "allbirds", "name": "Allbirds"},
    {"id": "casper", "name": "Casper"},
]
LOOPED = ["SAY__figs", "SAY__allbirds", "SAY__casper",
          "INTENT__figs", "INTENT__allbirds", "INTENT__casper",
          "AWARE__figs", "AWARE__allbirds", "AWARE__casper",
          "BUY__figs", "BUY__allbirds", "BUY__casper"]
HEADER = "panel_respondent_id," + ",".join(LOOPED)


def write_raw(data: bytes) -> str:
    d = tempfile.mkdtemp()
    p = os.path.join(d, "FAKE_export.csv")
    with open(p, "wb") as f:
        f.write(data)
    return p


def write_csv(text: str, bom: bool = False, crlf: bool = False) -> str:
    if crlf:
        text = text.replace("\n", "\r\n")
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    return write_raw(data)


def rec(panel, pid, bid):
    for r in panel["responses"]:
        if r["persona_id"] == pid and r["brand_id"] == bid:
            return r
    return None


def ids(panel):
    return sorted({r["persona_id"] for r in panel["responses"]})


ROW1 = "FAKE-01,7,5,3,9,6,2,1,1,2,1,2,1"
ROW2 = "FAKE-02,8,6,4,10,7,1,1,2,2,2,1,1"


class Bom(unittest.TestCase):
    def test_bom_on_id_column(self):
        p = write_csv(f"{HEADER}\n{ROW1}\n{ROW2}\n", bom=True)
        panel = fi.import_export(p, BRANDS)
        info = panel["_import"]
        self.assertEqual(info["id_column"], "panel_respondent_id")
        self.assertEqual(panel["n_personas"], 2)
        self.assertEqual(ids(panel), ["FAKE-01", "FAKE-02"])
        self.assertFalse(any(pid.startswith("ROW-") for pid in ids(panel)))
        self.assertEqual(info["ignored_admin_columns"], [])
        self.assertEqual(info["unmatched_columns"], [])
        self.assertEqual(rec(panel, "FAKE-01", "figs")["say"], 7)

    def test_bom_with_crlf(self):
        p = write_csv(f"{HEADER}\n{ROW1}\n{ROW2}\n", bom=True, crlf=True)
        panel = fi.import_export(p, BRANDS)
        self.assertEqual(panel["n_personas"], 2)
        self.assertEqual(rec(panel, "FAKE-02", "casper")["buy"], True)
        self.assertEqual(panel["_import"]["unparseable_values"], [])

    def test_bom_on_admin_first_column(self):
        p = write_csv(f"Status,{HEADER}\nComplete,{ROW1}\n", bom=True)
        panel = fi.import_export(p, BRANDS)
        self.assertEqual(panel["_import"]["ignored_admin_columns"], ["Status"])
        self.assertEqual(panel["_import"]["id_column"], "panel_respondent_id")
        self.assertEqual(panel["n_personas"], 1)

    def test_bom_on_looped_first_column(self):
        # No id column; the first looped column carries the BOM and must still map to say/figs.
        p = write_csv("SAY__figs,SAY__allbirds,SAY__casper\n7,5,3\n", bom=True)
        panel = fi.import_export(p, BRANDS)
        self.assertIn("figs/say", panel["_import"]["columns_used"])
        self.assertEqual(panel["_import"]["unmatched_columns"], [])
        self.assertEqual(panel["responses"][0]["say"], 7)


class RepeatedHeaderRow(unittest.TestCase):
    def test_repeated_header_is_skipped_and_not_counted(self):
        p = write_csv(f"{HEADER}\n{HEADER}\n{ROW1}\n{ROW2}\n")
        panel = fi.import_export(p, BRANDS)
        info = panel["_import"]
        self.assertTrue(info["label_row_skipped"])
        self.assertEqual(panel["n_personas"], 2)
        self.assertEqual(ids(panel), ["FAKE-01", "FAKE-02"])
        self.assertIsNone(rec(panel, "panel_respondent_id", "figs"))
        self.assertEqual(info["unparseable_values"], [])

    def test_repeated_header_with_bom_and_admin_columns(self):
        h = "panel_respondent_id,Status,duration_sec," + ",".join(LOOPED)
        p = write_csv(f"{h}\n{h}\nFAKE-01,Complete,100,7,5,3,9,6,2,1,1,2,1,2,1\n", bom=True)
        panel = fi.import_export(p, BRANDS)
        self.assertEqual(panel["n_personas"], 1)
        self.assertEqual(ids(panel), ["FAKE-01"])
        self.assertEqual(panel["_import"]["unparseable_values"], [])

    def test_first_real_persona_is_not_mistaken_for_a_header(self):
        p = write_csv(f"{HEADER}\n{ROW1}\n{ROW2}\n")
        panel = fi.import_export(p, BRANDS)
        self.assertFalse(panel["_import"]["label_row_skipped"])
        self.assertEqual(panel["n_personas"], 2)
        self.assertEqual(rec(panel, "FAKE-01", "figs")["intent"], 9)


class QuotedCommasInAdminColumns(unittest.TestCase):
    def test_quoted_values_do_not_shift_columns(self):
        h = 'panel_respondent_id,Status,"Device, browser",Notes,' + ",".join(LOOPED)
        rows = [
            'FAKE-01,"Complete, verified","iPhone, Safari","He said ""hi"", then left",' + ROW1.split(",", 1)[1],
            'FAKE-02,"Partial, 50%","Mac, Chrome","multi\nline, note",' + ROW2.split(",", 1)[1],
        ]
        p = write_csv(h + "\n" + "\n".join(rows) + "\n")
        panel = fi.import_export(p, BRANDS)
        info = panel["_import"]
        self.assertEqual(info["ignored_admin_columns"], ["Status", "Device, browser", "Notes"])
        self.assertEqual(info["unmatched_columns"], [])
        self.assertEqual(info["unparseable_values"], [])
        self.assertEqual(panel["n_personas"], 2)
        r1 = rec(panel, "FAKE-01", "figs")
        self.assertEqual((r1["say"], r1["intent"], r1["aware"], r1["buy"]), (7, 9, True, True))
        r2 = rec(panel, "FAKE-02", "casper")
        self.assertEqual((r2["say"], r2["intent"], r2["aware"], r2["buy"]), (4, 1, False, True))


class TenVersusOne(unittest.TestCase):
    def test_scale_values(self):
        self.assertEqual(fi.parse_scale("10"), (10, None))
        self.assertEqual(fi.parse_scale("1"), (1, None))
        self.assertEqual(fi.parse_scale(" 10 "), (10, None))
        self.assertEqual(fi.parse_scale("10 - Extremely likely"), (10, None))
        self.assertEqual(fi.parse_scale("1 - Not at all likely"), (1, None))
        self.assertEqual(fi.parse_scale("10.0"), (10, None))
        self.assertEqual(fi.parse_scale("Extremely likely (10)"), (10, None))
        self.assertEqual(fi.parse_scale("100")[1], "out of range")

    def test_bool_code_10_is_not_yes(self):
        self.assertNotEqual(fi.parse_bool("10")[0], True)
        self.assertNotEqual(fi.parse_bool("12")[0], True)
        self.assertNotEqual(fi.parse_bool("21")[0], False)

    def test_in_a_file(self):
        p = write_csv(f"{HEADER}\nFAKE-01,10,1,10,1,10,1,1,1,1,1,1,1\nFAKE-02,1,10,1,10,1,10,2,2,2,2,2,2\n")
        panel = fi.import_export(p, BRANDS)
        a, b = rec(panel, "FAKE-01", "figs"), rec(panel, "FAKE-01", "allbirds")
        self.assertEqual((a["say"], a["intent"]), (10, 1))
        self.assertEqual((b["say"], b["intent"]), (1, 10))
        c2 = rec(panel, "FAKE-02", "casper")
        self.assertEqual((c2["say"], c2["intent"]), (1, 10))
        self.assertEqual(panel["_import"]["unparseable_values"], [])

    def test_ten_in_a_yes_no_column_is_reported_not_guessed(self):
        p = write_csv(f"{HEADER}\nFAKE-01,7,5,3,9,6,2,10,1,1,1,1,1\n")
        panel = fi.import_export(p, BRANDS)
        self.assertIsNone(rec(panel, "FAKE-01", "figs")["aware"])
        bad = panel["_import"]["unparseable_values"]
        self.assertEqual([(b["column"], b["value"]) for b in bad], [("AWARE__figs", "10")])


class AwareBuyCodes(unittest.TestCase):
    def test_parse_codes(self):
        self.assertEqual(fi.parse_bool("1"), (True, None))
        self.assertEqual(fi.parse_bool("2"), (False, None))
        self.assertEqual(fi.parse_bool(" 1 "), (True, None))
        self.assertEqual(fi.parse_bool(" 2 "), (False, None))
        self.assertEqual(fi.parse_bool("Yes"), (True, None))
        self.assertEqual(fi.parse_bool("No"), (False, None))

    def test_codes_in_file(self):
        p = write_csv(f"{HEADER}\n{ROW1}\n{ROW2}\n")
        panel = fi.import_export(p, BRANDS)
        # ROW1 AWARE = 1,1,2 ; BUY = 1,2,1
        got = [(rec(panel, "FAKE-01", b)["aware"], rec(panel, "FAKE-01", b)["buy"]) for b in ("figs", "allbirds", "casper")]
        self.assertEqual(got, [(True, True), (True, False), (False, True)])
        # ROW2 AWARE = 1,2,2 ; BUY = 2,1,1
        got = [(rec(panel, "FAKE-02", b)["aware"], rec(panel, "FAKE-02", b)["buy"]) for b in ("figs", "allbirds", "casper")]
        self.assertEqual(got, [(True, False), (False, True), (False, True)])
        kinds = {q: d["kind"] for q, d in panel["_import"]["question_kinds"].items()}
        self.assertEqual(kinds, {"SAY": "say", "INTENT": "intent", "AWARE": "aware", "BUY": "buy"})


class BlankCells(unittest.TestCase):
    def test_blank_cells_are_none_and_not_reported(self):
        p = write_csv(f"{HEADER}\n"
                      "FAKE-01,,5,3,9,,2,1,,2,1,2,\n"     # figs: say blank; allbirds: intent+aware blank
                      "FAKE-02,N/A, ,-,,,,,,,,,\n"        # everything blank-ish
                      ",,,,,,,,,,,,\n")                    # fully blank row
        panel = fi.import_export(p, BRANDS)
        info = panel["_import"]
        self.assertEqual(info["unparseable_values"], [])
        f = rec(panel, "FAKE-01", "figs")
        self.assertEqual((f["say"], f["intent"], f["aware"], f["buy"]), (None, 9, True, True))
        a = rec(panel, "FAKE-01", "allbirds")
        self.assertEqual((a["say"], a["intent"], a["aware"], a["buy"]), (5, None, None, False))
        c3 = rec(panel, "FAKE-01", "casper")
        self.assertEqual((c3["say"], c3["intent"], c3["aware"], c3["buy"]), (3, 2, False, None))
        # A persona with no answers at all has no brand rows.
        self.assertIsNone(rec(panel, "FAKE-02", "figs"))
        # The fully blank line is not a persona.
        self.assertFalse(any(pid.startswith("ROW-") for pid in ids(panel)))
        self.assertNotIn(None, [r["persona_id"] for r in panel["responses"]])
        self.assertEqual(panel["n_personas"], 2)

    def test_short_row_is_tolerated(self):
        p = write_csv(f"{HEADER}\nFAKE-01,7,5\n")
        panel = fi.import_export(p, BRANDS)
        self.assertEqual(rec(panel, "FAKE-01", "figs")["say"], 7)
        self.assertEqual(rec(panel, "FAKE-01", "allbirds")["say"], 5)
        self.assertIsNone(rec(panel, "FAKE-01", "casper"))

    def test_blank_persona_id_is_reported(self):
        p = write_csv(f"{HEADER}\n,7,5,3,9,6,2,1,1,2,1,2,1\n")
        panel = fi.import_export(p, BRANDS)
        self.assertEqual(ids(panel), ["ROW-1"])
        probs = [u["problem"] for u in panel["_import"]["unparseable_values"]]
        self.assertTrue(any("no persona id" in x for x in probs))


class UnknownBrandLoopKey(unittest.TestCase):
    def test_unknown_brand_is_reported_unmatched(self):
        h = HEADER + ",SAY__warbyparker,INTENT__warbyparker"
        p = write_csv(f"{h}\nFAKE-01,7,5,3,9,6,2,1,1,2,1,2,1,8,8\n")
        panel = fi.import_export(p, BRANDS)
        info = panel["_import"]
        un = {u["column"]: u["reason"] for u in info["unmatched_columns"]}
        self.assertEqual(un, {"SAY__warbyparker": "loop key matches no brand",
                              "INTENT__warbyparker": "loop key matches no brand"})
        self.assertNotIn("warbyparker", info["brand_ids"])
        self.assertFalse(any("warbyparker" in v for v in info["columns_used"].values()))
        self.assertEqual({r["brand_id"] for r in panel["responses"]}, {"figs", "allbirds", "casper"})
        self.assertNotIn("SAY__warbyparker", info["ignored_admin_columns"])
        self.assertIn("Unmatched columns (2)", fi.summarize_import(panel))


class AdminColumnsIgnored(unittest.TestCase):
    def test_admin_columns_listed_and_never_read(self):
        admin = ["Status", "duration_sec", "Device", "Recorded Date", "Quality score", "IP_Address", "UserLanguage"]
        h = "panel_respondent_id," + ",".join(admin) + "," + ",".join(LOOPED)
        vals = ["Complete", "10", "1", "2026-11-14", "2", "203.0.113.5", "EN"]
        p = write_csv(f"{h}\nFAKE-01,{','.join(vals)},{ROW1.split(',', 1)[1]}\n")
        panel = fi.import_export(p, BRANDS)
        info = panel["_import"]
        self.assertEqual(info["ignored_admin_columns"], admin)
        self.assertEqual(info["unmatched_columns"], [])
        self.assertEqual(info["unparseable_values"], [])
        self.assertEqual(sorted(info["question_kinds"]), ["AWARE", "BUY", "INTENT", "SAY"])
        self.assertTrue(all(col in LOOPED for col in info["columns_used"].values()))
        self.assertEqual(rec(panel, "FAKE-01", "figs")["say"], 7)
        self.assertEqual(panel["n_personas"], 1)


if __name__ == "__main__":
    unittest.main()
