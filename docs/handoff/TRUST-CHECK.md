# "Should I trust my AI focus group?": how to wire it into the page (for Daniel)

Engine: `say/trust_check.py` (commit de24c47, 10 tests, 240 total pass). Jayden approved the feature at ~1:19 PM ET.
A store owner types what they sell and what they want to learn. The page answers:
how far to trust an AI shopper crowd for THAT kind of question, why (our evidence), one question to
ask real people instead, and a 3-step check with 12+ real people.

Who does what (on purpose):
- Claude (1 Sonnet call, through the same `LLM_CLIENT`, so it counts toward the 20-call cap):
  sorts the question into buy / like / aware / other and drafts the real-people question.
  It never sees a number, the revenue or the verdict.
- Code: picks the evidence line, copies its numbers from the run file, and sets the level with the
  same cutoffs as the pre-registered rule. "Could be chance" never earns trust. Kinds we didn't test
  ("other", e.g. price) always get "Ask real people" with no number.
- With no key it still works: code keywords + a code-template question (labeled "code template").

## 1. Server: `frontend/server.py` (tested in a scratch copy of main 1a1cdee + de24c47)

Add after the `agent.llm` import block:
```python
try:  # 'Should I trust my AI focus group?' engine (say/trust_check.py)
    from say import trust_check  # type: ignore
except Exception:  # noqa: BLE001
    trust_check = None
```
Add at the top of `do_POST`:
```python
        if self.path.split("?")[0] == "/api/trust-check":
            if trust_check is None:
                return self._json(503, {"error": "trust check not available"})
            try:
                n = min(int(self.headers.get("Content-Length", "0")), 8_000)
                data = json.loads(self.rfile.read(n) or b"{}")
                run = load_run(data.get("run_path") or "runs/say_latest.json")
                return self._json(200, trust_check.check(str(data.get("store", "")), str(data.get("question", "")),
                                                         run, llm=LLM_CLIENT))
            except (ValueError, FileNotFoundError) as e:
                return self._json(400, {"error": str(e)})
```
Tested with no key on port 3083:
- POST `{"store":"Hand-made soy candles","question":"Do people like my website design?"}` gave 200:
  kind `like`, "Ask real people", "...matched real revenue at 0.77, and that could be chance...".
- An empty store gave 400. `/api/chat` behaved the same as before.

## 2. Request and response

POST `/api/trust-check` with `{"store": "...", "question": "...", "run_path": "runs/say_latest.json"}` (inputs capped at 300 chars).

Response fields to show:
| field | show as |
|---|---|
| `level_text` | the big answer: "Trust it" / "Double-check it" / "Ask real people" |
| `why` | one sentence under it (numbers rounded; from the run file) |
| `evidence.label` | tag: "SYNTHETIC vs MEASURED" (+ ", EXPLORATORY" for non-buy kinds); `evidence` is null for untested kinds |
| `real_question` + `question_source` | "Ask real people this:" + tag AI-GENERATED if `question_source` starts with "model", else CODE TEMPLATE |
| `check_steps` (3) | numbered list |
| `limits` (3) | small print |
| `note` | "Nothing was sent or bought. A human decides." |

## 3. Suggested UI (your call)
A box on the desk (or a 4th tab, "Check my crowd"): two inputs ("What do you sell?", "What do you
want to ask an AI crowd?"), one button, then the fields above. Good demo inputs:
- "Hand-made soy candles" / "Will people buy my new pumpkin scent?" -> buy line, 0.03, Ask real people
- "Vintage sneakers" / "What price should I charge?" -> untested kind, Ask real people, no number
