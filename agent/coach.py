"""Prompts and validation for the Coach, verdict explainer, Predictor and Trust card.

The model only writes conditions, directions and plain-English phrasing.
All sizes, verdicts and measured numbers come from code (grade.py).
"""
import json

from agent.llm import LLM, MODELS, LLMError, NoKey, StopSwitch

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
OPS = {"==", "!=", ">", "<", ">=", "<="}
NUMERIC_OPS = {">", "<", ">=", "<="}
FORBIDDEN_FEATURES = {"tier"}  # computed from the answer key: using it would leak the answers
TRUST_NOTE = "Stopped for a human. Nothing was bought."
VERDICTS = {"trust", "verify", "ask_real_people"}

PLAIN = ("Write for a high-school student. Plain English, short sentences, no jargon, "
         "no statistics words. If you must use a term, explain it in the same sentence.")

_llm = None


def set_llm(llm):
    """Let the orchestrator share one LLM (one call counter, one stop switch)."""
    global _llm
    _llm = llm


def _get_llm(llm):
    global _llm
    if llm is not None:
        return llm
    if _llm is None:
        _llm = LLM()
    return _llm


def clean_features(features):
    """Copy of `features` without forbidden keys (never show 'tier' to the model)."""
    return {k: v for k, v in (features or {}).items() if k not in FORBIDDEN_FEATURES}


# ---------------------------------------------------------------- rules
def _norm_direction(v):
    """Turn 'up'/'down'/'none' or a number into a direction in {-1.0, 0.0, 1.0}."""
    if isinstance(v, bool):
        raise ValueError("direction must not be a boolean")
    if isinstance(v, (int, float)):
        return 1.0 if v > 0 else -1.0 if v < 0 else 0.0
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("up", "higher", "more", "+", "increase"):
            return 1.0
        if s in ("down", "lower", "less", "-", "decrease"):
            return -1.0
        if s in ("none", "same", "0", "flat", ""):
            return 0.0
    raise ValueError(f"bad direction {v!r}")


def validate_rule(raw, allowed_features):
    """Return a clean Rule dict, or raise ValueError with the reason."""
    if not isinstance(raw, dict):
        raise ValueError("rule is not an object")
    rid, text = raw.get("id"), raw.get("text")
    if not isinstance(rid, str) or not rid.strip():
        raise ValueError("missing id")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("missing plain-English text")
    when = raw.get("when")
    if when is not None:
        if not isinstance(when, dict):
            raise ValueError("'when' must be an object or null")
        feat, op, val = when.get("feature"), when.get("op"), when.get("value")
        if feat in FORBIDDEN_FEATURES:
            raise ValueError(f"feature '{feat}' is forbidden (it leaks the answer key)")
        if feat not in allowed_features:
            raise ValueError(f"unknown feature {feat!r}")
        if op not in OPS:
            raise ValueError(f"bad operator {op!r}")
        if "value" not in when or val is None or isinstance(val, (dict, list)):
            raise ValueError("missing or non-scalar value")
        if op in NUMERIC_OPS and (isinstance(val, bool) or not isinstance(val, (int, float))):
            raise ValueError(f"operator {op} needs a number")
        when = {"feature": feat, "op": op, "value": val}
    adj = raw.get("adjust")
    if not isinstance(adj, dict) or set(adj) != set(DAYS):
        raise ValueError("adjust must give a direction for each of Mon..Fri")
    adjust = {d: _norm_direction(adj[d]) for d in DAYS}
    if all(v == 0.0 for v in adjust.values()):
        raise ValueError("adjust moves no day")
    # Directions only: grade.fit_adjust (code) replaces these with fitted sizes.
    return {"id": rid.strip(), "text": text.strip(), "when": when, "adjust": adjust}


def parse_rules(data, allowed_features, max_rules=6):
    """Validate model output. Returns (rules, dropped) where dropped = [{"id","reason"}]."""
    raw = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return [], [{"id": "?", "reason": "model output has no 'rules' list"}]
    rules, dropped, seen = [], [], set()
    for i, r in enumerate(raw):
        rid = r.get("id") if isinstance(r, dict) and isinstance(r.get("id"), str) else f"#{i + 1}"
        try:
            rule = validate_rule(r, allowed_features)
            if rule["id"] in seen:
                raise ValueError("duplicate id")
            if len(rules) >= max_rules:
                raise ValueError("more than the allowed number of rules")
            seen.add(rule["id"])
            rules.append(rule)
        except ValueError as e:
            dropped.append({"id": rid, "reason": str(e)})
    return rules, dropped


COACH_SYSTEM = (
    "You are the Coach for an AI survey panel. The panel (SYNTHETIC) guesses which weekday "
    "mornings (6-10 AM) people ride the subway from a station. Real turnstile counts "
    "(MEASURED) are the answer key. You see training stations only: synthetic share, measured "
    "share, and station features. Find patterns where the panel is wrong in a way a station "
    "feature explains.\n"
    "Propose 3 to 6 rules. Each rule: a condition on ONE listed feature (or null for all "
    "stations) and which weekdays should go up or down. You give direction only. Code fits "
    "the size, so never write numbers for how much.\n"
    "Use only the feature names listed. Never invent features. Do not use anything about "
    "'tier'.\n" + PLAIN + "\n"
    'Return JSON: {"rules": [{"id": "r1", "text": "one plain sentence", '
    '"when": {"feature": "borough", "op": "==", "value": "Brooklyn"} or null, '
    '"adjust": {"Mon": "up|down|none", "Tue": "...", "Wed": "...", "Thu": "...", "Fri": "..."}}]}'
)


def _station_view(s):
    return {"id": s.get("id"), "name": s.get("name"),
            "features": clean_features(s.get("features")),
            "synthetic": s.get("synthetic"), "measured": s.get("measured")}


def coach_rules(train_stations, round_no, previous_verdicts, llm=None, dropped=None):
    """Ask Opus (fallback Sonnet) for rules. Invalid rules are dropped; reasons are appended
    to `dropped` if a list is passed. Round 2+ also sees round-1 verdicts so it can revise."""
    llm = _get_llm(llm)
    view = [_station_view(s) for s in train_stations]
    allowed = {k for s in view for k in s["features"]}
    user = (f"Round {round_no}.\nAllowed features: {sorted(allowed)}\n"
            f"Training stations (shares are fractions per weekday):\n{json.dumps(view)}\n")
    if previous_verdicts:
        user += ("\nCode already tested your earlier rules. Verdicts:\n"
                 f"{json.dumps(previous_verdicts)}\nKeep what worked, change or replace what "
                 "failed, and say in each rule's text what you changed.\n")
    last_err = None
    for model in (MODELS["coach"], MODELS["hard"]):
        try:
            data = llm.call(model, COACH_SYSTEM, user, max_tokens=2500, json_mode=True,
                            purpose=f"coach_round_{round_no}")
        except (StopSwitch, NoKey):
            raise
        except LLMError as e:
            last_err = e
            continue
        rules, bad = parse_rules(data, allowed)
        if dropped is not None:
            dropped.extend(bad)
        return rules
    raise LLMError(f"coach failed on both models: {last_err}")


# ---------------------------------------------------------------- explain
EXPLAIN_SYSTEM = ("You explain a test result in ONE sentence. Use only the numbers given; "
                  "never calculate or add numbers. " + PLAIN)


def explain_verdict(rule, evaluation, llm=None):
    """One plain sentence. Falls back to the code's own reason if the model is unavailable."""
    fallback = str(evaluation.get("reason", ""))
    user = (f"Rule: {rule.get('text')}\nTest result (from code): {json.dumps(evaluation)}\n"
            "Say whether the rule was kept and why, in one sentence.")
    try:
        text = _get_llm(llm).call(MODELS["hard"], EXPLAIN_SYSTEM, user, max_tokens=150,
                                  purpose="explain_verdict")
    except (NoKey, LLMError):
        return fallback
    text = text.strip().replace("\n", " ")
    return text or fallback


# ---------------------------------------------------------------- predict
PREDICT_SYSTEM = (
    "You give a rough expected error for each exam station: how many percentage points the "
    "panel's weekday shares will differ from the real counts, on average. Base it on the "
    "training evidence and whether kept rules apply. It is an ESTIMATE, a guess, not a "
    'measurement. Return JSON: {"bands": {"<station_id>": [low, high]}} with 0 <= low <= high.'
)


def predict_bands(exam_station_features, kept_rules, train_evidence, llm=None):
    """{station_id: [low_pp, high_pp]} (ESTIMATE). Stations the model skips or botches get no entry."""
    feats = {sid: clean_features(f) for sid, f in exam_station_features.items()}
    evidence = [_station_view(s) for s in train_evidence]  # strips tier, counts, sources
    user = (f"Exam stations and features: {json.dumps(feats)}\n"
            f"Kept rules: {json.dumps(kept_rules)}\nTraining evidence: {json.dumps(evidence)}")
    data = _get_llm(llm).call(MODELS["hard"], PREDICT_SYSTEM, user, max_tokens=800,
                              json_mode=True, purpose="predict_bands")
    out = {}
    bands = data.get("bands") if isinstance(data, dict) else None
    for sid in feats:
        b = (bands or {}).get(sid)
        if (isinstance(b, list) and len(b) == 2
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in b)
                and 0 <= b[0] <= b[1]):
            out[sid] = [float(b[0]), float(b[1])]
    return out


# ---------------------------------------------------------------- trust card
TRUST_SYSTEM = (
    "You decide how far one small local user can trust the AI panel's answer for a station. "
    "Pick ONE verdict: 'trust' (rules were tested and held up), 'verify' (some support, check "
    "a little), or 'ask_real_people' (weak evidence, a human should ask). Name a realistic "
    "small user near the station, like 'a corner shop near Kings Hwy'. If the verdict is "
    "ask_real_people, write ONE short question a human can send to real people nearby; "
    "otherwise use an empty string. " + PLAIN + "\n"
    'Return JSON: {"place": "...", "verdict": "trust|verify|ask_real_people", '
    '"reason": "one plain sentence why, using only the numbers given", "draft_question": "..."}'
)


def trust_card(station, kept_rules, evaluation_summary, llm=None, verdict=None):
    """Always ends with the fixed note: nothing is sent or bought by code.

    If `verdict` is given (set by code from pre-registered cutoffs), the model must use it and only
    writes the place, the one-line reason and, for ask_real_people, the draft question.
    """
    fixed = (f"\nThe verdict is already decided by code: {verdict}. Use exactly this verdict."
             if verdict in VERDICTS else "")
    user = (f"Station: {station.get('name')} ({station.get('borough')}).\n"
            f"Kept rules: {json.dumps(kept_rules)}\nTest summary (from code): "
            f"{json.dumps(evaluation_summary)}{fixed}")
    data = _get_llm(llm).call(MODELS["hard"], TRUST_SYSTEM, user, max_tokens=400,
                              json_mode=True, purpose="trust_card")
    if verdict not in VERDICTS:
        verdict = data.get("verdict") if isinstance(data, dict) else None
    if verdict not in VERDICTS:
        verdict = "verify"  # safe default when the model gives nonsense
    place = data.get("place") if isinstance(data.get("place"), str) else ""
    question = data.get("draft_question") if isinstance(data.get("draft_question"), str) else ""
    reason = data.get("reason") if isinstance(data.get("reason"), str) else ""
    return {"place": place.strip() or f"a small business near {station.get('name')}",
            "station_id": station.get("id"), "verdict": verdict,
            "draft_question": question.strip() if verdict == "ask_real_people" else "",
            "reason": reason.strip(),
            "note": TRUST_NOTE}
