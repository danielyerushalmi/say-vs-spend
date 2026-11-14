import os
import threading
import unittest
from unittest import mock

from agent.llm import LLM, LLMError, NoKey, StopSwitch, extract_json
from agent.standin import NOTE, standin_panel


def ok(text, tin=10, tout=5):
    return 200, {"content": [{"type": "text", "text": text}],
                 "usage": {"input_tokens": tin, "output_tokens": tout}}


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.payloads = []
        self._lock = threading.Lock()

    def __call__(self, payload, timeout):
        with self._lock:
            self.payloads.append(payload)
            return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


class FakeTrace:
    def __init__(self):
        self.steps = []

    def step(self, agent, model, step, detail=""):
        self.steps.append((agent, model, step, detail))


class LLMTests(unittest.TestCase):
    def make(self, *responses, **kw):
        t = FakeTransport(*responses)
        return LLM(transport=t, sleep=lambda s: None, **kw), t

    def test_counts_tokens_and_cost(self):
        llm, _ = self.make(ok("hi", 1_000_000, 1_000_000))
        self.assertEqual(llm.call("claude-haiku-5-5", "s", "u"), "hi")
        self.assertEqual((llm.calls, llm.input_tokens, llm.output_tokens), (1, 1_000_000, 1_000_000))
        self.assertGreater(llm.cost_usd_estimate(), 0)

    def test_stop_switch(self):
        llm, t = self.make(ok("x"), max_calls=2)
        llm.call("claude-haiku-5-5", "s", "u")
        llm.call("claude-haiku-5-5", "s", "u")
        with self.assertRaises(StopSwitch):
            llm.call("claude-haiku-5-5", "s", "u")
        self.assertEqual(len(t.payloads), 2)

    def test_parallel_calls_counted_safely(self):
        llm, _ = self.make(ok("x"), max_calls=100, max_parallel=3)
        ts = [threading.Thread(target=llm.call, args=("claude-haiku-5-5", "s", "u"))
              for _ in range(40)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(llm.calls, 40)
        self.assertEqual(llm.input_tokens, 400)

    def test_no_key_raises(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(NoKey):
                LLM().call("claude-haiku-5-5", "s", "u")

    def test_retry_once_on_429_then_success(self):
        llm, t = self.make((429, {}), ok("fine"))
        self.assertEqual(llm.call("claude-haiku-5-5", "s", "u"), "fine")
        self.assertEqual(len(t.payloads), 2)

    def test_second_5xx_raises(self):
        llm, _ = self.make((500, {"error": {"message": "boom"}}))
        with self.assertRaises(LLMError):
            llm.call("claude-haiku-5-5", "s", "u")

    def test_400_not_retried(self):
        llm, t = self.make((400, {}))
        with self.assertRaises(LLMError):
            llm.call("claude-haiku-5-5", "s", "u")
        self.assertEqual(len(t.payloads), 1)

    def test_json_extraction_from_prose(self):
        llm, _ = self.make(ok('Sure! {"a": {"b": "}"}} done'))
        self.assertEqual(llm.call("m", "s", "u", json_mode=True), {"a": {"b": "}"}})

    def test_json_repair_retry(self):
        llm, t = self.make(ok("not json"), ok('{"a": 1}'))
        self.assertEqual(llm.call("m", "s", "u", json_mode=True), {"a": 1})
        self.assertEqual(len(t.payloads), 2)

    def test_json_repair_fails(self):
        llm, _ = self.make(ok("nope"))
        with self.assertRaises(LLMError):
            llm.call("m", "s", "u", json_mode=True)

    def test_trace_records_model_and_tokens_only(self):
        tr = FakeTrace()
        llm, _ = self.make(ok("x"), trace=tr)
        llm.call("claude-haiku-5-5", "SECRET SYSTEM", "u", purpose="p")
        self.assertEqual(tr.steps[0][:3], ("llm", "claude-haiku-5-5", "p"))
        self.assertNotIn("SECRET", repr(tr.steps))

    def test_extract_json_none(self):
        with self.assertRaises(ValueError):
            extract_json("no braces")


class StandinTests(unittest.TestCase):
    def test_counts_and_label(self):
        reply = ('{"personas": [{"who": "nurse", "days": ["Mon", "Tue", "Funday"]},'
                 '{"who": "retired", "days": []}, "junk"]}')
        llm = LLM(transport=FakeTransport(ok(reply)))
        out = standin_panel({"name": "Kings Hwy", "borough": "Brooklyn"}, "q?", n=5, llm=llm)
        self.assertEqual(out["counts"], {"Mon": 1, "Tue": 1, "Wed": 0, "Thu": 0, "Fri": 0, "None": 1})
        self.assertEqual(out["note"], NOTE)
        self.assertEqual(out["panel_id"], "claude-standin")


if __name__ == "__main__":
    unittest.main()
