"""Tiny Anthropic Messages API client built on urllib (standard library only).

Safety rules:
* The API key is read ONLY from the ANTHROPIC_API_KEY environment variable,
  at call time, and is never stored on the object, logged, or traced.
* A hard call cap (StopSwitch) protects the spend limit.
* Tests inject a fake `transport`, so they never touch the network.
"""
import http.client
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

MODELS = {"bulk": "claude-haiku-5-5", "hard": "claude-sonnet-5-5", "coach": "claude-opus-5-5"}

# ESTIMATE, check current pricing: USD per million tokens (input, output).
# These are placeholders from memory, not verified against Anthropic's price page.
PRICES_USD_PER_MTOK = {
    "claude-haiku-5-5": (1.0, 5.0),
    "claude-sonnet-5-5": (3.0, 15.0),
    "claude-opus-5-5": (5.0, 25.0),
}


class StopSwitch(Exception):
    """Raised when max_calls is reached. The run must stop spending."""


class NoKey(Exception):
    """Raised when ANTHROPIC_API_KEY is not set. Callers fall back."""


class LLMError(Exception):
    """Any other failure talking to the API (after retries)."""


def extract_json(text):
    """Return the first balanced {...} block in `text` parsed as a dict.

    Raises ValueError if there is none or it does not parse.
    """
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError("no JSON object found in model output")


def _http_transport(payload, timeout):
    """Default transport: POST to the API. Returns (status, body_dict)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise NoKey("ANTHROPIC_API_KEY is not set")
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-api-key": key, "anthropic-version": API_VERSION,
                 "content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            try:
                body = json.loads(resp.read().decode("utf-8"))
            except (ValueError, http.client.IncompleteRead) as e:
                raise LLMError(f"bad response body: {type(e).__name__}") from None
            if not isinstance(body, dict):
                raise LLMError("bad response body: not a JSON object")
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return e.code, body
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # Do not include request details (headers) in the message.
        raise LLMError(f"network error: {type(e).__name__}") from None


class LLM:
    """Thread-safe client. `transport(payload, timeout) -> (status, body)` is injectable."""

    def __init__(self, max_calls=60, max_parallel=8, timeout=120,
                 transport=None, trace=None, sleep=time.sleep, backoff=2.0):
        self.max_calls = max_calls
        self.timeout = timeout
        self.trace = trace
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._by_model = {}  # model -> [input_tokens, output_tokens]
        self._lock = threading.Lock()
        self._sem = threading.Semaphore(max_parallel)
        self._transport = transport or _http_transport
        self._sleep = sleep
        self._backoff = backoff

    # -- accounting ---------------------------------------------------
    def _reserve_call(self):
        with self._lock:
            if self.calls >= self.max_calls:
                raise StopSwitch(f"max_calls={self.max_calls} reached")
            self.calls += 1

    def _record(self, model, purpose, usage):
        tin = int(usage.get("input_tokens", 0) or 0)
        tout = int(usage.get("output_tokens", 0) or 0)
        with self._lock:
            self.input_tokens += tin
            self.output_tokens += tout
            m = self._by_model.setdefault(model, [0, 0])
            m[0] += tin
            m[1] += tout
        if self.trace is not None:
            self.trace.step("llm", model, purpose or "call", f"tokens in={tin} out={tout}")

    def cost_usd_estimate(self):
        """ESTIMATE in USD from the price table above."""
        with self._lock:
            items = list(self._by_model.items())
        total = 0.0
        for model, (tin, tout) in items:
            pin, pout = PRICES_USD_PER_MTOK.get(model, (0.0, 0.0))
            total += tin / 1e6 * pin + tout / 1e6 * pout
        return round(total, 6)

    # -- calls --------------------------------------------------------
    def _request(self, model, system, messages, max_tokens, purpose):
        payload = {"model": model, "max_tokens": max_tokens, "system": system,
                   "messages": messages}
        for attempt in range(2):  # one retry on 429 / 5xx
            self._reserve_call()
            with self._sem:
                status, body = self._transport(payload, self.timeout)
            if status == 200:
                self._record(model, purpose, body.get("usage", {}))
                return "".join(b.get("text", "") for b in body.get("content", [])
                               if b.get("type") == "text")
            if (status == 429 or status >= 500) and attempt == 0:
                self._sleep(self._backoff)
                continue
            msg = body.get("error", {}).get("message", "") if isinstance(body, dict) else ""
            raise LLMError(f"API status {status}: {msg}"[:300])
        raise LLMError("unreachable")

    def call(self, model, system, user, max_tokens=1500, json_mode=False, purpose=""):
        """Return text, or a dict when json_mode=True (one repair retry on bad JSON)."""
        if not json_mode:
            return self._request(model, system, [{"role": "user", "content": user}],
                                 max_tokens, purpose)
        system = system + "\n\nReply with a single JSON object only. No prose, no code fences."
        messages = [{"role": "user", "content": user}]
        text = self._request(model, system, messages, max_tokens, purpose)
        try:
            return extract_json(text)
        except ValueError:
            pass
        messages = messages + [
            {"role": "assistant", "content": text or "(empty)"},
            {"role": "user", "content": "That was not valid JSON. Reply again with ONLY the "
                                        "corrected JSON object, nothing else."}]
        text = self._request(model, system, messages, max_tokens, (purpose or "call") + ":repair")
        try:
            return extract_json(text)
        except ValueError as e:
            raise LLMError("model did not return valid JSON after one repair retry") from e
