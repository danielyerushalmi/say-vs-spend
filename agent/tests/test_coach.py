import json
import unittest

from agent import coach
from agent.llm import LLM, LLMError
from agent.tests.test_llm import FakeTransport, ok

UP = {"Mon": "up", "Tue": "none", "Wed": "none", "Thu": "none", "Fri": "down"}


def rule(**kw):
    r = {"id": "r1", "text": "Brooklyn rides more on Monday.",
         "when": {"feature": "borough", "op": "==", "value": "Brooklyn"}, "adjust": UP}
    r.update(kw)
    return r


STATIONS = [{"id": "41", "name": "7 Av", "features": {"borough": "Brooklyn", "tier": "high",
                                                        "median_income": 80000},
             "synthetic": {"Mon": .2}, "measured": {"Mon": .2}}]
ALLOWED = {"borough", "median_income"}


class RuleValidation(unittest.TestCase):
    def test_good_rule(self):
        r = coach.validate_rule(rule(), ALLOWED)
        self.assertEqual(r["adjust"]["Mon"], 1.0)
        self.assertEqual(r["adjust"]["Fri"], -1.0)

    def test_null_when_allowed(self):
        self.assertIsNone(coach.validate_rule(rule(when=None), ALLOWED)["when"])

    def test_rejects_bad_rules(self):
        bad = [
            rule(when={"feature": "tier", "op": "==", "value": "high"}),
            rule(when={"feature": "shoe_size", "op": "==", "value": 1}),
            rule(when={"feature": "borough", "op": "~", "value": "x"}),
            rule(when={"feature": "median_income", "op": ">", "value": "rich"}),
            rule(adjust={"Mon": "up"}),
            rule(adjust={d: "none" for d in coach.DAYS}),
            rule(adjust={**UP, "Mon": "sideways"}),
            rule(text=""),
            "not a dict",
        ]
        for b in bad:
            with self.assertRaises(ValueError, msg=repr(b)):
                coach.validate_rule(b, ALLOWED)

    def test_parse_rules_drops_with_reason(self):
        data = {"rules": [rule(), rule(id="r2", when={"feature": "tier", "op": "==", "value": "x"}),
                          rule()]}
        rules, dropped = coach.parse_rules(data, ALLOWED)
        self.assertEqual([r["id"] for r in rules], ["r1"])
        self.assertEqual(len(dropped), 2)
        self.assertIn("forbidden", dropped[0]["reason"])
        self.assertIn("duplicate", dropped[1]["reason"])

    def test_parse_rules_no_list(self):
        rules, dropped = coach.parse_rules({"oops": 1}, ALLOWED)
        self.assertEqual((rules, len(dropped)), ([], 1))


class CoachFlow(unittest.TestCase):
    def test_tier_never_sent_and_bad_rules_dropped(self):
        reply = json.dumps({"rules": [rule(), rule(id="r2", when={"feature": "tier",
                                                                   "op": "==", "value": "high"})]})
        t = FakeTransport(ok(reply))
        dropped = []
        rules = coach.coach_rules(STATIONS, 1, None, llm=LLM(transport=t), dropped=dropped)
        self.assertEqual(len(rules), 1)
        self.assertEqual(len(dropped), 1)
        sent = json.dumps(t.payloads[0]["messages"])
        self.assertNotIn("tier", sent)
        self.assertIn("claude-opus-5-5", t.payloads[0]["model"])

    def test_round2_includes_verdicts(self):
        t = FakeTransport(ok('{"rules": []}'))
        coach.coach_rules(STATIONS, 2, [{"id": "r1", "keep": False}], llm=LLM(transport=t))
        self.assertIn("Verdicts", t.payloads[0]["messages"][0]["content"])

    def test_falls_back_to_sonnet(self):
        t = FakeTransport((500, {}), (500, {}), ok(json.dumps({"rules": [rule()]})))
        rules = coach.coach_rules(STATIONS, 1, None, llm=LLM(transport=t, sleep=lambda s: None))
        self.assertEqual(len(rules), 1)
        self.assertEqual(t.payloads[-1]["model"], "claude-sonnet-5-5")

    def test_both_models_fail(self):
        t = FakeTransport((500, {}))
        with self.assertRaises(LLMError):
            coach.coach_rules(STATIONS, 1, None, llm=LLM(transport=t, sleep=lambda s: None))


class OtherFunctions(unittest.TestCase):
    def test_explain_uses_model_then_falls_back(self):
        ev = {"reason": "code reason"}
        self.assertEqual(coach.explain_verdict(rule(), ev, llm=LLM(transport=FakeTransport(
            ok("  It helped.\n")))), "It helped.")
        failing = LLM(transport=FakeTransport((400, {})))
        self.assertEqual(coach.explain_verdict(rule(), ev, llm=failing), "code reason")

    def test_predict_bands_validates(self):
        reply = '{"bands": {"a": [1, 3], "b": [5, 2], "c": "x"}}'
        out = coach.predict_bands({"a": {}, "b": {}, "c": {}, "d": {}}, [], {},
                                  llm=LLM(transport=FakeTransport(ok(reply))))
        self.assertEqual(out, {"a": [1.0, 3.0]})

    def test_trust_card_note_fixed(self):
        reply = ('{"place": "a corner shop near Kings Hwy", "verdict": "ask_real_people", '
                 '"draft_question": "Which weekday mornings do you ride?", "note": "I bought it"}')
        card = coach.trust_card({"id": "51", "name": "Kings Hwy", "borough": "Brooklyn"}, [], {},
                                llm=LLM(transport=FakeTransport(ok(reply))))
        self.assertEqual(card["note"], "Stopped for a human. Nothing was bought.")
        self.assertEqual(card["verdict"], "ask_real_people")
        self.assertTrue(card["draft_question"])
        self.assertEqual(card["station_id"], "51")

    def test_trust_card_bad_verdict_and_no_question_unless_asking(self):
        reply = '{"place": "x", "verdict": "buy_now", "draft_question": "q"}'
        card = coach.trust_card({"id": "1", "name": "N", "borough": "Queens"}, [], {},
                                llm=LLM(transport=FakeTransport(ok(reply))))
        self.assertEqual(card["verdict"], "verify")
        self.assertEqual(card["draft_question"], "")
        self.assertEqual(card["note"], coach.TRUST_NOTE)


if __name__ == "__main__":
    unittest.main()
