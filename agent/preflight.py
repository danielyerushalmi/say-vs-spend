"""Preflight: run this the moment the keys are set, before the real pipeline run.

    python3 -m agent.preflight

Checks, without ever printing a key:
  1. ANTHROPIC_API_KEY is set, and which of our three model ids answer (one tiny call each).
  2. CENSUS_API_KEY is set (optional; without it rule traits fall back to borough + county numbers).
  3. How many Flashpoint panel files are on disk (12:30 go/no-go: 6+ = Crowd Coach).
  4. The unit tests pass.
Then it prints the exact next commands.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_IDS = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]


def check_models() -> dict:
    from agent.llm import LLM, LLMError, NoKey
    llm = LLM(max_calls=len(MODEL_IDS) * 2, timeout=60)
    status = {}
    for model in MODEL_IDS:
        try:
            llm.call(model, "Reply with the single word OK.", "Say OK.", max_tokens=5, purpose="preflight")
            status[model] = "OK"
        except NoKey:
            return {m: "no key" for m in MODEL_IDS}
        except (LLMError, Exception) as exc:  # report the error type only; never echo request details
            status[model] = f"FAILED ({type(exc).__name__}: {str(exc)[:80]})"
    status["_calls"] = llm.calls
    status["_cost_estimate_usd"] = round(llm.cost_usd_estimate(), 5)
    return status


def main() -> int:
    ok = True
    print("1. Anthropic key:", "set" if os.environ.get("ANTHROPIC_API_KEY") else "NOT SET")
    if os.environ.get("ANTHROPIC_API_KEY"):
        for model, result in check_models().items():
            print(f"   {model}: {result}")
            if isinstance(result, str) and result != "OK" and not model.startswith("_"):
                ok = False
    else:
        ok = False
    census = bool(os.environ.get("CENSUS_API_KEY"))
    print("2. Census key:", "set" if census else "not set (optional: traits fall back to borough + county)")
    panels = sorted(p.stem for p in (ROOT / "data" / "panels").glob("*.json"))
    print(f"3. Flashpoint panel files: {len(panels)} of 12 {panels}")
    print("   12:30 rule: 6+ = Crowd Coach; 1-5 = Turnstile Truth; 0 = labeled Claude stand-ins")
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "agent/tests"],
                           cwd=ROOT, capture_output=True, text=True)
    last = (tests.stderr.strip().splitlines() or ["?"])[-1]
    print("4. Unit tests:", last)
    ok = ok and tests.returncode == 0
    print("\nNext commands:")
    if census:
        print("   python3 -m agent.features            # tract traits for all 12 stations")
    flag = "" if len(panels) == 12 else "  --allow-standin   # fills missing panels with LABELED Claude stand-ins"
    print(f"   python3 -m agent.run{flag}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
