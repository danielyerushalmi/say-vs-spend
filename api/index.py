"""Vercel serverless entry for Crowd Check (Study 1: Say vs. Spend): /api/* -> this function (see vercel.json).

Reuses frontend/server.py (chat, trust check, predictor, website grader). The Anthropic key comes ONLY
from the ANTHROPIC_API_KEY environment variable set in the Vercel project settings; it is never in code.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "frontend"))
import server as S  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _route(self):
        u = urllib.parse.urlparse(self.path)
        r = urllib.parse.parse_qs(u.query).get("route", [""])[0] or u.path.rstrip("/").rsplit("/", 1)[-1]
        return r.strip("/")

    def _body(self, route):
        n = S.body_length(self.headers.get("Content-Length"), 64_000)
        return S.parse_body(self.rfile.read(n), route)  # same checks as frontend/server.py -> ValueError -> 400

    def do_GET(self):
        if self._route() == "health":
            return self._json(200, {"ok": True, "llm": bool(S.HAVE_WRAPPER and os.environ.get("ANTHROPIC_API_KEY")), "model": S.MODEL,
                                    "trust_check": S.trust_check is not None, "predict": S.crowd_predict is not None})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        route = self._route()
        try:
            data = self._body(route)
            if route == "chat":
                if not S.HAVE_WRAPPER:
                    return self._json(503, {"error": "Claude wrapper not available"})
                return self._json(200, {"reply": S.chat_reply(data.get("messages") or [], data.get("run_path") or "runs/say_latest.json")})
            if route == "trust-check":
                if S.trust_check is None:
                    return self._json(503, {"error": "trust check not available"})
                run = S.load_run(data.get("run_path") or "runs/say_latest.json")
                return self._json(200, S.trust_check.check(str(data.get("store", "")), str(data.get("question", "")), run, llm=S.LLM_CLIENT))
            if route == "predict":
                if S.crowd_predict is None:
                    return self._json(503, {"error": "predictor not available"})
                return self._json(200, S.crowd_predict.predict(str(data.get("store", "")), S.PRED_DATA, S.PRED_VAL, llm=S.LLM_CLIENT))
            if route == "grade-site":
                return self._json(200, S.grade_site(str(data.get("url", ""))[:500]))
            return self._json(404, {"error": "not found"})
        except urllib.error.HTTPError as e:
            msg = "That site refused automated visits" if e.code in (401, 403, 429) else "That site returned an error"
            return self._json(502, {"error": f"{msg} (HTTP {e.code}). Try another link, like your homepage."})
        except (ValueError, FileNotFoundError) as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            name = type(e).__name__
            if name == "NoKey":
                return self._json(503, {"error": "ANTHROPIC_API_KEY is not set"})
            if name == "StopSwitch":
                return self._json(503, {"error": "chat call limit reached for now"})
            return self._json(502, {"error": f"Something went wrong ({name}). Try again."})
