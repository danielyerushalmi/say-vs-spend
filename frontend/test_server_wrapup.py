"""Tests for frontend/server.py and api/index.py request handling. Standard library only.

No key and no internet needed: ANTHROPIC_API_KEY is removed before anything runs, and the
servers under test listen on 127.0.0.1 only. Run from the repo root with either:

    python3 frontend/test_server_wrapup.py
    python3 -m unittest discover -s frontend -p 'test_*.py'
"""
import http.client
import json
import os
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer

os.environ.pop("ANTHROPIC_API_KEY", None)  # never call the real API from a test

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "api"))

import server as S  # noqa: E402
import index as V  # noqa: E402  (api/index.py, the Vercel entry)

BAD_BODIES = [b"[]", b"null", b'"hello"', b"42", b"true", b"{not json"]


def _start(handler_cls):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _post(srv, path, raw: bytes, length=None):
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    try:
        c.putrequest("POST", path)
        c.putheader("Content-Type", "application/json")
        c.putheader("Content-Length", str(len(raw) if length is None else length))
        c.endheaders()
        c.send(raw)
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"null")
    finally:
        c.close()


class ParseBody(unittest.TestCase):
    def test_object_ok(self):
        self.assertEqual(S.parse_body(b'{"store": "candles"}', "predict"), {"store": "candles"})
        self.assertEqual(S.parse_body(b"", "predict"), {})

    def test_missing_or_null_fields_allowed(self):
        self.assertEqual(S.parse_body(b'{"run_path": null}', "chat"), {"run_path": None})

    def test_non_object_bodies_rejected(self):
        for raw in BAD_BODIES:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                S.parse_body(raw, "chat")

    def test_field_types(self):
        cases = [("predict", {"store": 5}), ("trust-check", {"question": ["x"]}), ("trust-check", {"run_path": {}}),
                 ("grade-site", {"url": 1}), ("chat", {"messages": "hi"}), ("chat", {"messages": {}}),
                 ("chat", {"run_path": 3})]
        for route, body in cases:
            with self.subTest(route=route, body=body), self.assertRaises(ValueError):
                S.parse_body(json.dumps(body).encode(), route)

    def test_body_length_clamped(self):
        self.assertEqual(S.body_length("-5", 100), 0)
        self.assertEqual(S.body_length("500", 100), 100)
        self.assertEqual(S.body_length(None, 100), 0)
        with self.assertRaises(ValueError):
            S.body_length("abc", 100)


class _Routes:
    """Shared HTTP checks; subclasses set srv and a path builder."""
    srv = None

    def path(self, route):
        raise NotImplementedError

    def test_bad_bodies_give_400_json(self):
        for route in ("chat", "trust-check", "predict", "grade-site"):
            for raw in BAD_BODIES:
                with self.subTest(route=route, raw=raw):
                    status, j = _post(self.srv, self.path(route), raw)
                    self.assertEqual(status, 400)
                    self.assertIsInstance(j, dict)
                    self.assertIn("error", j)

    def test_wrong_field_types_give_400(self):
        for route, body in [("predict", {"store": 5}), ("trust-check", {"store": "a", "question": 7}),
                            ("grade-site", {"url": ["x"]}), ("chat", {"messages": "hi"}), ("chat", {"messages": 5})]:
            with self.subTest(route=route, body=body):
                status, j = _post(self.srv, self.path(route), json.dumps(body).encode())
                self.assertEqual(status, 400)
                self.assertIn("error", j)

    def test_bad_content_length_gives_400(self):
        status, _ = _post(self.srv, self.path("predict"), b"{}", length="abc")
        self.assertEqual(status, 400)

    def test_valid_predict_still_works_without_key(self):
        if S.crowd_predict is None:
            self.skipTest("say/predict.py not importable")
        status, j = _post(self.srv, self.path("predict"), json.dumps({"store": "Hand-made soy candles"}).encode())
        self.assertEqual(status, 200)
        self.assertIn("predicted_website_score", j)
        self.assertIn("EXPLORATORY", j.get("note", ""))

    def test_valid_chat_without_key_is_503_not_crash(self):
        if not S.HAVE_WRAPPER:
            self.skipTest("agent/llm.py not importable")
        body = {"messages": [{"role": "user", "content": "hi"}], "run_path": "runs/say_latest.json"}
        status, j = _post(self.srv, self.path("chat"), json.dumps(body).encode())
        self.assertEqual(status, 503)
        self.assertIn("error", j)


class LocalServer(_Routes, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _start(S.Handler)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def path(self, route):
        return "/api/" + route


class VercelEntry(_Routes, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _start(V.handler)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def path(self, route):
        return "/api/index?route=" + route  # the vercel.json rewrite target


@unittest.skipUnless(S.HAVE_WRAPPER, "agent/llm.py not importable")
class ModelCallLimits(unittest.TestCase):
    def test_page_client_is_fast_and_capped(self):
        self.assertLessEqual(S.LLM_CLIENT.timeout, 12)
        self.assertGreaterEqual(S.LLM_CLIENT.timeout, 5)
        self.assertEqual(S.LLM_CLIENT.max_calls, S.MAX_CALLS)
        self.assertIs(S.LLM_CLIENT._sleep, S._no_retry)

    def test_busy_api_is_not_retried(self):
        calls = []

        def transport(payload, timeout):
            calls.append(timeout)
            return 529, {"error": {"message": "overloaded"}}

        llm = S.LLM(max_calls=5, timeout=S.LLM_TIMEOUT, transport=transport, sleep=S._no_retry)
        with self.assertRaises(S.LLMError):
            llm.call("m", "sys", "user")
        self.assertEqual(calls, [S.LLM_TIMEOUT])  # one attempt, with the short timeout
        self.assertEqual(llm.calls, 1)

    def test_call_cap_still_applies(self):
        llm = S.LLM(max_calls=1, timeout=S.LLM_TIMEOUT, transport=lambda p, t: (200, {"content": [{"type": "text", "text": "ok"}]}),
                    sleep=S._no_retry)
        self.assertEqual(llm.call("m", "s", "u"), "ok")
        with self.assertRaises(S.StopSwitch):
            llm.call("m", "s", "u")


if __name__ == "__main__":
    unittest.main()
