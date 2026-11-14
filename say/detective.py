"""Detective step of Say vs. Spend: ask the crowd WHY, then summarize the answers.

The model only phrases things. All numbers come from code. Neither function ever
sends revenue, revenue rank or company size to the model (the crowd must not learn
the answer key). Both return None (or an empty result) if there is no key or the
call cap is hit, so the pipeline keeps going.
"""
from __future__ import annotations

from agent.llm import LLM, MODELS, LLMError, NoKey, StopSwitch

PREFIX = "AI-generated: "
MAX_BRANDS = 3
MAX_ANSWERS = 200

_FOLLOWUP_SYSTEM = (
    "You write ONE short, neutral survey question for a crowd of shoppers. It asks WHY they "
    "rated the named brands the way they did. Use plain English a high-school student "
    "understands. Do not lead or hint at a right answer. Do not mention revenue, sales, "
    "size, rankings, money made, or that a gap exists. Mention only what the shoppers "
    "themselves rated (website quality and how likely they are to buy). Reply as JSON: "
    '{"question": "<one question>"}'
)

_SUMMARY_SYSTEM = (
    "You summarize survey answers about one brand. Write 2 to 4 short plain-English lines. "
    "Each line is one theme that actually appears in the answers. Use ONLY what the answers "
    "say. Invent no quotes, facts, or numbers. Do not do any arithmetic or count answers; "
    "if you want to show size, use words like 'several' only when clearly true. Reply as "
    'JSON: {"lines": ["...", "..."]}'
)


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def _safe_brand(b: dict) -> dict:
    """Only name and description. Never revenue or ranks."""
    return {"id": b.get("id"), "name": _clean(b.get("name")),
            "description": _clean(b.get("description"))}


def draft_followup(top_gaps, brands, llm: LLM | None = None):
    """Return {"question": str, "brand_ids": [...]} or None if it cannot be drafted."""
    by_id = {b.get("id"): b for b in brands or []}
    ids = []
    for g in top_gaps or []:
        bid = g.get("brand_id")
        if bid in by_id and bid not in ids:
            ids.append(bid)
        if len(ids) == MAX_BRANDS:
            break
    if not ids:
        return None
    shown = [_safe_brand(by_id[i]) for i in ids]
    user = ("Brands (name and description only):\n"
            + "\n".join(f"- {b['name']}: {b['description']}" for b in shown)
            + "\n\nWrite one question asking why shoppers rated these brands' websites and "
              "their likelihood to buy as they did.")
    try:
        out = (llm or LLM()).call(MODELS["hard"], _FOLLOWUP_SYSTEM, user, max_tokens=300,
                                  json_mode=True, purpose="detective:followup")
    except (NoKey, StopSwitch, LLMError):
        return None
    q = _clean(out.get("question")) if isinstance(out, dict) else ""
    if not q:
        return None
    return {"question": q, "brand_ids": ids}


def summarize_reasons(raw_answers, brand, llm: LLM | None = None):
    """Return {"lines": [...], "n_answers": int}. Lines are empty if no summary was possible."""
    answers = [_clean(a) for a in (raw_answers or []) if _clean(a)]
    result = {"lines": [], "n_answers": len(answers)}
    if not answers:
        return result
    b = _safe_brand(brand if isinstance(brand, dict) else {"name": brand})
    user = (f"Brand: {b['name']}\n\nAnswers (one per line):\n"
            + "\n".join(f"- {a}" for a in answers[:MAX_ANSWERS]))
    try:
        out = (llm or LLM()).call(MODELS["hard"], _SUMMARY_SYSTEM, user, max_tokens=500,
                                  json_mode=True, purpose="detective:summary")
    except (NoKey, StopSwitch, LLMError):
        return result
    raw = out.get("lines") if isinstance(out, dict) else None
    lines = [_clean(x) for x in raw if _clean(x)] if isinstance(raw, list) else []
    result["lines"] = [PREFIX + (l[len(PREFIX):] if l.startswith(PREFIX) else l)
                       for l in lines[:4]]
    return result
