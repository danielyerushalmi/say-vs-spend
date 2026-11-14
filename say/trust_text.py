"""Plain-English wording for the trust card. Code decides the verdict; the model only phrases.

The verdict is passed in and returned unchanged. If there is no key (or the call cap is
hit) every function falls back to fixed template text, so the pipeline never stops.
"""
from __future__ import annotations

from agent.llm import LLM, MODELS, LLMError, NoKey, StopSwitch

VERDICTS = ("trust", "verify", "ask_real_people")
STORE_LABEL = "FICTIONAL DEMO STORE"
STORE_NOTE = "No answer key for this store; trust level comes from the brand test."

_FALLBACK = {
    "trust": "The AI crowd ordered the brands almost like real sales did, so you can lean on it.",
    "verify": "The AI crowd matched real sales only partly, so double-check it before you act.",
    "ask_real_people": "The AI crowd did not match real sales well enough, so ask real people.",
}

_TRUST_SYSTEM = (
    "Write ONE plain sentence (under 35 words) for a high-school audience explaining how far "
    "to trust an AI shopper crowd. Use ONLY the numbers and facts given. Never compute, "
    "round, or add numbers. Never change or contradict the verdict. If told the crowd did "
    "not beat fame, or that the result could be chance, say so plainly. Reply as JSON: "
    '{"sentence": "..."}'
)

_QUESTION_SYSTEM = (
    "Write ONE short, neutral survey question (under 25 words) to ask REAL US online shoppers, "
    "aimed at the single biggest gap below between the AI crowd and real sales. Never mention sales figures, "
    "rankings or the AI crowd in the question. Plain English. No leading "
    "words. No numbers. Reply as JSON: " '{"question": "..."}'
)


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def _one(llm, system, user, key, purpose):
    try:
        out = (llm or LLM()).call(MODELS["hard"], system, user, max_tokens=250,
                                  json_mode=True, purpose=purpose)
    except (NoKey, StopSwitch, LLMError):
        return None
    return (_clean(out.get(key)) or None) if isinstance(out, dict) else None


def trust_sentence(verdict, metric_text, rule_text, crowd_beat_fame, could_be_chance,
                   llm: LLM | None = None) -> str:
    """One plain sentence. The verdict is decided by code and is not changed here."""
    if verdict not in VERDICTS:
        raise ValueError(f"unknown verdict: {verdict!r}")
    user = (f"Verdict (fixed, do not change): {verdict}\n"
            f"Result: {metric_text}\nRule used: {rule_text}\n"
            f"Crowd beat plain fame: {'yes' if crowd_beat_fame else 'no'}\n"
            f"Could be chance: {'yes' if could_be_chance else 'no'}")
    return _one(llm, _TRUST_SYSTEM, user, "sentence", "trust:sentence") or _FALLBACK[verdict]


def real_survey_question(verdict, brand_context, llm: LLM | None = None, fallback: str | None = None):
    """Only for 'ask_real_people'. Returns one question string (fallback text if no model), or None."""
    if verdict != "ask_real_people":
        return None
    user = f"Biggest gap: {_clean(brand_context)}"
    return _one(llm, _QUESTION_SYSTEM, user, "question", "trust:question") or fallback


def store_card(store_name, store_description, store_stats, verdict) -> dict:
    """The contract's store block. No model call; the label and note are fixed text."""
    stats = store_stats or {}
    return {
        "name": store_name,
        "description": store_description,
        "label": STORE_LABEL,
        "say_mean": stats.get("say_mean"),
        "intent_mean": stats.get("intent_mean"),
        "aware_share": stats.get("aware_share"),
        "verdict": verdict,
        "note": STORE_NOTE,
    }
