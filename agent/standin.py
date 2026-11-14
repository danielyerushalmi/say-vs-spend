"""Fallback survey panel written by Claude when no Flashpoint panel file exists."""
from agent.llm import LLM, MODELS

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
NOTE = "Claude stand-in, not Flashpoint, not census-grounded"

SYSTEM = (
    "You role-play commuters for a survey. Invent short, realistic personas who live near "
    "the given NYC subway station. Each persona answers the survey question honestly for "
    "their own life (job, school, shifts, remote days). Vary the people; do not make "
    "everyone ride every day. Keep each persona under 12 words."
)


def standin_panel(station, question, n=40, llm=None):
    """Return {"counts", "panel_id", "source_link", "note"}; counts include a "None" key."""
    llm = llm or LLM()
    user = (
        f"Station: {station.get('name')} ({station.get('borough')}).\n"
        f"Survey question: {question}\n"
        f"Make {n} personas. Return JSON: "
        '{"personas": [{"who": "short description", "days": ["Mon", "Wed"]}]}. '
        'Use only Mon, Tue, Wed, Thu, Fri in "days". Use an empty list if they ride none.'
    )
    data = llm.call(MODELS["bulk"], SYSTEM, user, max_tokens=4000, json_mode=True,
                    purpose="standin_panel")
    counts = {d: 0 for d in DAYS}
    counts["None"] = 0
    for p in (data.get("personas") or [])[:n]:
        if not isinstance(p, dict) or not isinstance(p.get("days"), list):
            continue  # skip malformed persona
        days = {d for d in p["days"] if d in DAYS}
        if not days:
            counts["None"] += 1
        for d in days:
            counts[d] += 1
    return {"counts": counts, "panel_id": "claude-standin", "source_link": "", "note": NOTE}
