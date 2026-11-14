"""Offline evidence report for Say vs. Spend.

Reads the run file (frontend/runs/say_latest.json) plus, when present, the
follow-up WHY answers, the independent recount, the team decision log and the
git history, and writes ONE static HTML page: inline CSS and inline SVG, no
JavaScript, no CDN, no network. It works from a USB stick and prints cleanly.

Every number on the page is read from those files (or computed from them, e.g.
a rank from pageviews); nothing is typed in by hand.

    python3 -m say.report                       # real run -> docs/report/index.html
    python3 -m say.report --run some_run.json --out /tmp/x.html --no-git
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
from datetime import datetime
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

DEFAULT_RUN = os.path.join(REPO, "frontend", "runs", "say_latest.json")
DEFAULT_OUT = os.path.join(REPO, "docs", "report", "index.html")
DEFAULT_FOLLOWUP = os.path.join(HERE, "panels", "followup.json")
DEFAULT_RECOUNT = os.path.join(HERE, "audit", "RECOUNT.md")
DEFAULT_WIKI = os.path.join(HERE, "fame", "wikipedia_pageviews.json")
# The team's decision log lives one folder above the repo (not published).
DEFAULT_DECISIONS = os.path.join(os.path.dirname(REPO), "decisions.md")

# The Say vs. Spend idea was adopted at 11:42 ET; earlier history is a different idea.
TIMELINE_SINCE = "11:40"

# Okabe-Ito colour-blind-safe palette, one colour per brand slot.
BRAND_COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000", "#999999"]

VERDICT_TEXT = {
    "trust_it": "TRUST IT",
    "double_check": "DOUBLE-CHECK IT",
    "ask_real_people": "ASK REAL PEOPLE",
}

NOT_ADVICE = ("This page tests whether AI survey answers match real spending. "
              "It is not investment advice and says nothing about any company's stock.")


# ---------------------------------------------------------------- helpers

def esc(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


_PATH_RE = re.compile(r"(/Users|/home|/private|C:\\Users)[^\s'\",;)]*")


def scrub(text) -> str:
    """Remove local absolute paths (they leak usernames) from text bound for a public page."""
    if text is None:
        return ""
    s = str(text)

    def repl(m):
        p = m.group(0)
        marker = "hackathon-project/"
        if marker in p:
            return p.split(marker, 1)[1]
        return "<local path>"

    return _PATH_RE.sub(repl, s)


def num(x, digits=2) -> str:
    if x is None:
        return "n/a"
    s = f"{x:.{digits}f}"
    return s.replace("-", "\u2212")


def money(x) -> str:
    if x is None:
        return "n/a"
    if x >= 1e9:
        return f"${x / 1e9:.2f}B"
    return f"${x / 1e6:.0f}M"


def pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def hhmm(iso: Optional[str]) -> str:
    if not iso:
        return ""
    m = re.search(r"T(\d\d:\d\d)", iso)
    return m.group(1) if m else iso


def minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def tag(label: str) -> str:
    cls = {
        "MEASURED": "t-meas", "SYNTHETIC": "t-syn", "AI-GENERATED": "t-ai",
        "ESTIMATE": "t-est", "COMPUTED": "t-comp", "AGENT DRAFT": "t-ai", "UNVERIFIED": "t-est",
    }.get(label.upper(), "t-comp")
    return f'<span class="tag {cls}">{esc(label)}</span>'


def read_json(path: Optional[str]):
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_text(path: Optional[str]) -> Optional[str]:
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def ranks_desc(values: dict) -> dict:
    """1 = biggest. Ignores None. Average rank for ties."""
    items = [(k, v) for k, v in values.items() if v is not None]
    items.sort(key=lambda kv: -kv[1])
    out, i = {}, 0
    while i < len(items):
        j = i
        while j + 1 < len(items) and items[j + 1][1] == items[i][1]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[items[k][0]] = r
        i = j + 1
    return out


# ---------------------------------------------------------------- inputs

def git_log(repo: str) -> list[dict]:
    try:
        out = subprocess.run(
            ["git", "-C", repo, "log", "--format=%h|%ad|%s", "--date=format:%Y-%m-%d|%H:%M"],
            capture_output=True, text=True, timeout=10, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            rows.append({"hash": parts[0], "date": parts[1], "time": parts[2], "subject": parts[3]})
    return rows


_DEC_RE = re.compile(r"^-\s*(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})(?:\s*ET)?\s*[\u2014-]+\s*(.+)$")


def parse_decisions(text: Optional[str]) -> list[dict]:
    if not text:
        return []
    out = []
    for line in text.splitlines():
        m = _DEC_RE.match(line.strip())
        if m:
            t = m.group(2).zfill(5)
            out.append({"date": m.group(1), "time": t, "text": m.group(3).strip()})
    return out


def parse_recount(text: Optional[str]) -> Optional[dict]:
    if not text:
        return None
    yes = len(re.findall(r"\|\s*YES\s*\|", text))
    no = len(re.findall(r"\|\s*NO\s*\|", text))
    mism = re.search(r"Mismatches:\s*([^\n]+)", text)
    persona = re.search(r"persona answers mismatching CSV \(of (\d+)\)\s*\|\s*(\d+)", text)
    not_checked = re.search(r"Not checked:\s*([^\n]+)", text)
    return {
        "checks_yes": yes, "checks_no": no,
        "mismatches": mism.group(1).strip() if mism else None,
        "persona_cells": persona.group(1) if persona else None,
        "persona_bad": persona.group(2) if persona else None,
        "not_checked": not_checked.group(1).strip() if not_checked else None,
    }


def classify(text: str) -> str:
    t = text.lower()
    if re.search(r"pre-registered|amended|trust rule|frozen|locks?\b|stays at|inclusion rule", t):
        return "rule"
    if re.search(r"first real run|honest timing|statistics? .*computed", t):
        return "result"
    return "other"


# ---------------------------------------------------------------- sections

def section(title: str, body: str, sub: str = "", sid: str = "") -> str:
    sub_html = f'<p class="sub">{sub}</p>' if sub else ""
    ida = f' id="{esc(sid)}"' if sid else ""
    return f'<section{ida}><h2>{esc(title)}</h2>{sub_html}{body}</section>'


def verdict_card(run: dict) -> str:
    tc = run.get("trust_card") or {}
    ag = (run.get("agreement") or {}).get("intent") or {}
    v = tc.get("verdict") or ""
    vt = VERDICT_TEXT.get(v, v.upper().replace("_", " "))
    cls = {"trust_it": "v-trust", "double_check": "v-check"}.get(v, "v-ask")
    dq = tc.get("draft_question")
    dq_html = ""
    if dq:
        dq_src = tc.get("draft_question_source") or ""
        by_model = "model" in dq_src.lower()
        who = "drafted by the model" if by_model else "drafted by our code template"
        dq_html = (f'<div class="draft"><div class="lab">Next question to ask real people, {who} '
                   f'{tag("AI-GENERATED" if by_model else "CODE TEMPLATE")}'
                   + (f' <span class="src">({esc(dq_src)})</span>' if dq_src else "")
                   + f'</div><p class="q">\u201c{esc(dq)}\u201d</p></div>')
    note = tc.get("note") or ""
    return f"""
<div class="verdict {cls}">
  <div class="v-top">
    <div>
      <div class="lab">Verdict, set by code from a rule written before any result was computed</div>
      <div class="v-word">{esc(vt)}</div>
      <p class="v-reason">{esc(tc.get("reason"))}</p>
    </div>
    <div class="v-metric">
      <div class="big">{num(ag.get("spearman"))}</div>
      <div class="small">crowd \u201clikely to buy\u201d rank vs real revenue rank (Spearman)</div>
      <div class="small">90% wobble range: <b>{num(ag.get("wobble_low"))}</b> to {num(ag.get("wobble_high"))}</div>
      <div>{tag("SYNTHETIC")} vs {tag("MEASURED")}</div>
    </div>
  </div>
  <div class="rule"><div class="lab">The rule, exact text from the run file</div>
    <blockquote>{esc(tc.get("rule"))}</blockquote></div>
  {dq_html}
  <p class="stop">{esc(note)}</p>
</div>"""


def stat_tiles(run: dict) -> str:
    tiles = []
    ag = (run.get("agreement") or {}).get("intent") or {}
    chance = " · <b>could be chance</b>"
    tiles.append(("AI crowd vs money", num(ag.get("spearman")),
                  "intent rank vs revenue rank" + (chance if ag.get("could_be_chance") else ""),
                  [tag("SYNTHETIC"), tag("MEASURED")]))
    rr = run.get("repeat_run") or {}
    st = rr.get("stability") or {}
    if st.get("intent_rank_spearman_between_panels") is not None:
        tiles.append(("AI crowd A vs AI crowd B", num(st["intent_rank_spearman_between_panels"]),
                      f"two panels of {esc(rr.get('n_personas'))} different AI shoppers (same model), intent ranks",
                      [tag("SYNTHETIC"), tag("SYNTHETIC")]))
    fw = run.get("fame_wiki") or {}
    fa = fw.get("agreement") or {}
    if fa.get("spearman") is not None:
        tiles.append(("Wikipedia views vs money", num(fa["spearman"]),
                      f"{esc(fa.get('n_brands'))} brands, 365-day pageviews"
                      + (chance if fa.get("could_be_chance") else ""),
                      [tag("MEASURED"), tag("MEASURED"), tag("EXPLORATORY")]))
    out = []
    for title, big, small, tags in tiles:
        out.append(f'<div class="tile"><div class="lab">{esc(title)}</div><div class="big">{big}</div>'
                   f'<div class="small">{small}</div><div>{"".join(tags)}</div></div>')
    return f'<div class="tiles">{"".join(out)}</div>'


def slope_chart(run: dict, wiki_file: Optional[dict]) -> str:
    brands = run.get("brands") or []
    if not brands:
        return ""
    names = {b["id"]: b.get("name", b["id"]) for b in brands}
    color = {b["id"]: BRAND_COLORS[i % len(BRAND_COLORS)] for i, b in enumerate(brands)}
    cols = [("AI crowd A", "\u201clikely to buy\u201d", "SYNTHETIC", {b["id"]: b.get("rank_intent") for b in brands})]
    rr = run.get("repeat_run") or {}
    if rr.get("brands"):
        cols.append(("AI crowd B", "repeat, new 200", "SYNTHETIC",
                     {b["id"]: b.get("rank_intent") for b in rr["brands"]}))
    cols.append(("Real revenue", "SEC filings", "MEASURED", {b["id"]: b.get("rank_revenue") for b in brands}))
    fw = run.get("fame_wiki") or {}
    if fw.get("views"):
        wr = ranks_desc({k: v for k, v in fw["views"].items() if k in names})
        cols.append(("Wikipedia views", "last 365 days", "MEASURED", wr))

    # rho between neighbouring columns, all read from the run file
    gaps = []
    for a, b in zip(cols, cols[1:]):
        pair = (a[0], b[0])
        val, note = None, ""
        if pair == ("AI crowd A", "AI crowd B"):
            val = (rr.get("stability") or {}).get("intent_rank_spearman_between_panels")
        elif pair == ("AI crowd B", "Real revenue"):
            val = ((rr.get("agreement") or {}).get("intent") or {}).get("spearman")
        elif pair == ("AI crowd A", "Real revenue"):
            val = ((run.get("agreement") or {}).get("intent") or {}).get("spearman")
        elif pair == ("Real revenue", "Wikipedia views"):
            val = (fw.get("agreement") or {}).get("spearman")
            note = f" ({(fw.get('agreement') or {}).get('n_brands')} brands)"
        gaps.append(None if val is None else f"\u03c1 = {num(val)}{note}")

    n = len(brands)
    W, top, row = 760, 92, 46
    H = top + row * (n - 1) + 74
    left, right = 160, W - 150
    xs = [left + (right - left) * i / max(1, len(cols) - 1) for i in range(len(cols))]

    def y(r):
        return top + (r - 1) * row

    parts = [f'<svg class="slope" viewBox="0 0 {W} {H}" role="img" '
             f'aria-labelledby="slope-t slope-d"><title id="slope-t">Rank of each brand in four lists</title>'
             f'<desc id="slope-d">Lines join each brand\u2019s rank (1 = top) across the AI crowds, real revenue and Wikipedia views.</desc>']
    for i, (title, sub, label, _) in enumerate(cols):
        x = xs[i]
        parts.append(f'<text class="ch" x="{x:.0f}" y="24" text-anchor="middle">{esc(title)}</text>')
        parts.append(f'<text class="cs" x="{x:.0f}" y="42" text-anchor="middle">{esc(sub)}</text>')
        lcls = "meas" if label == "MEASURED" else "syn"
        parts.append(f'<text class="cl {lcls}" x="{x:.0f}" y="60" text-anchor="middle">{esc(label)}</text>')
        parts.append(f'<line class="axis" x1="{x:.0f}" y1="{top - 14}" x2="{x:.0f}" y2="{y(n) + 14}"/>')
    for i, g in enumerate(gaps):
        if g:
            parts.append(f'<text class="rho" x="{(xs[i] + xs[i + 1]) / 2:.0f}" y="{H - 8}" '
                         f'text-anchor="middle">{esc(g)}</text>')
    missing_end = []
    for b in brands:
        bid = b["id"]
        pts = [(xs[i], cols[i][3].get(bid)) for i in range(len(cols))]
        c = color[bid]
        segs = [(p, q) for p, q in zip(pts, pts[1:]) if p[1] is not None and q[1] is not None]
        for (x1, r1), (x2, r2) in segs:
            parts.append(f'<line x1="{x1:.0f}" y1="{y(r1):.0f}" x2="{x2:.0f}" y2="{y(r2):.0f}" '
                         f'stroke="{c}" stroke-width="3" stroke-linecap="round"/>')
        for x, r in pts:
            if r is not None:
                parts.append(f'<circle cx="{x:.0f}" cy="{y(r):.0f}" r="6" fill="{c}" class="dot"/>')
                parts.append(f'<text class="rv" x="{x:.0f}" y="{y(r) - 10:.0f}" text-anchor="middle">{num(r, 0) if float(r).is_integer() else num(r, 1)}</text>')
        if pts[0][1] is not None:
            parts.append(f'<text class="bl" x="{xs[0] - 12:.0f}" y="{y(pts[0][1]) + 5:.0f}" text-anchor="end" fill="{c}">{esc(names[bid])}</text>')
        if pts[-1][1] is not None:
            parts.append(f'<text class="bl" x="{pts[-1][0] + 12:.0f}" y="{y(pts[-1][1]) + 5:.0f}" fill="{c}">{esc(names[bid])}</text>')
        else:
            missing_end.append((bid, c))
    for k, (bid, c) in enumerate(missing_end):
        parts.append(f'<text class="cs" x="{xs[-1]:.0f}" y="{y(n) + 30 + 16 * k:.0f}" text-anchor="middle" '
                     f'fill="{c}">{esc(names[bid])}: no figure</text>')
    parts.append("</svg>")
    wiki_note = ""
    if fw.get("views"):
        missing = [names[k] for k, v in fw["views"].items() if v is None and k in names]
        if missing:
            why = ""
            if wiki_file:
                notes = {k: (v or {}).get("status") for k, v in (wiki_file.get("brands") or {}).items()}
                why = "; ".join(f"{names[k]}: {str(notes.get(k)).replace('_', ' ')}"
                                for k in fw["views"] if fw["views"][k] is None and notes.get(k))
            dash = (": " + esc(why)) if why else ""
            wiki_note = (f' Wikipedia ranks are computed here from the MEASURED pageview counts, among the brands that have one '
                         f'(left out{dash or ": " + esc(", ".join(missing))}).')
    caption = ("Read it left to right. The two AI crowds draw almost the same lines, so they agree with each other. "
               "Then the lines cross on the way to real revenue: the crowds\u2019 order is not the money order. "
               "Wikipedia views run nearly flat into revenue." + wiki_note)
    return f'<div class="chart scroll">{"".join(parts)}</div><p class="cap">{caption}</p>'


def agree_bars(run: dict) -> str:
    rows = []
    rr = run.get("repeat_run") or {}
    st = rr.get("stability") or {}
    if st.get("intent_rank_spearman_between_panels") is not None:
        rows.append(("Crowd A \u2194 Crowd B", "each other", st["intent_rank_spearman_between_panels"], ["SYNTHETIC", "SYNTHETIC"]))
    ia = ((run.get("agreement") or {}).get("intent") or {}).get("spearman")
    if ia is not None:
        rows.append(("Crowd A \u2194 revenue", "money", ia, ["SYNTHETIC", "MEASURED"]))
    ib = ((rr.get("agreement") or {}).get("intent") or {}).get("spearman")
    if ib is not None:
        rows.append(("Crowd B \u2194 revenue", "money", ib, ["SYNTHETIC", "MEASURED"]))
    wf = ((run.get("fame_wiki") or {}).get("agreement") or {}).get("spearman")
    if wf is not None:
        rows.append(("Wikipedia views \u2194 revenue", "money", wf, ["MEASURED", "MEASURED"]))
    if not rows:
        return '<p class="muted">No repeat crowd in this run file.</p>'
    out = []
    for label, kind, v, tags in rows:
        # bar from 0 on a -1..1 track; percentages of the track width
        zero = 50.0
        x = 50.0 + 50.0 * max(-1.0, min(1.0, v))
        lo, hi = min(zero, x), max(zero, x)
        cls = "b-each" if kind == "each other" else ("b-wiki" if label.startswith("Wiki") else "b-money")
        out.append(
            f'<div class="arow"><div class="alab">{esc(label)}<div>{"".join(tag(t) for t in tags)}</div></div>'
            f'<div class="atrack"><div class="azero"></div><div class="abar {cls}" style="left:{lo:.1f}%;width:{hi - lo:.1f}%"></div></div>'
            f'<div class="aval">{num(v)}</div></div>')
    axis = ('<div class="arow axisrow"><div></div><div class="aticks"><span>\u22121</span><span>0</span><span>+1</span></div><div></div></div>')
    return f'<div class="agree">{"".join(out)}{axis}</div>'


def wobble_chart(run: dict) -> str:
    rows = []
    ag = run.get("agreement") or {}
    rr = run.get("repeat_run") or {}
    rag = rr.get("agreement") or {}
    labels = {"intent": "\u201clikely to buy\u201d", "say": "\u201cwebsite is good\u201d", "fame": "\u201cheard of it\u201d"}
    for k in ("intent", "say", "fame"):
        if ag.get(k):
            rows.append((f"Crowd A {labels[k]}", ag[k], k == "intent", "SYNTHETIC vs MEASURED"))
    ab = (run.get("agreement_buyers") or {}).get("intent")
    if ab:
        rows.append(("Crowd A \u201clikely to buy\u201d, buyers only", ab, False, "SYNTHETIC vs MEASURED"))
    for k in ("intent", "say", "fame"):
        if rag.get(k):
            rows.append((f"Crowd B {labels[k]}", rag[k], False, "SYNTHETIC vs MEASURED"))
    fw = (run.get("fame_wiki") or {}).get("agreement")
    if fw:
        rows.append((f"Wikipedia views ({fw.get('n_brands')} brands)", fw, False, "MEASURED vs MEASURED"))
    out = []
    for label, a, is_test, kind in rows:
        lo, hi, pt = a.get("wobble_low"), a.get("wobble_high"), a.get("spearman")
        if pt is None:
            continue

        def p(v):
            return 50.0 + 50.0 * max(-1.0, min(1.0, v))
        rng = ""
        if lo is not None and hi is not None:
            rng = (f'<div class="wr" style="left:{p(lo):.1f}%;width:{p(hi) - p(lo):.1f}%"></div>'
                   f'<div class="wlo" style="left:{p(lo):.1f}%" title="low end"></div>')
        chance = " \u00b7 could be chance" if a.get("could_be_chance") else ""
        out.append(
            f'<div class="wrow{" wtest" if is_test else ""}"><div class="wlab">{esc(label)}'
            f'{"<b class=testmark> THE TEST</b>" if is_test else ""}<div class="wk">{esc(kind)}</div></div>'
            f'<div class="wtrack"><div class="z z1"></div><div class="z z2"></div><div class="z z3"></div>'
            f'<div class="azero"></div>{rng}<div class="wpt" style="left:{p(pt):.1f}%"></div></div>'
            f'<div class="wval">{num(pt)}<div class="wk">{num(lo)} to {num(hi)}{chance}</div></div></div>')
    legend = ('<div class="wleg"><span class="sw z1"></span>under 0.4: ask real people '
              '<span class="sw z2"></span>0.4 to 0.7: double-check '
              '<span class="sw z3"></span>0.7+: trust it</div>')
    axis = ('<div class="wrow axisrow"><div></div><div class="aticks"><span>\u22121</span><span>0</span>'
            '<span>+1</span></div><div></div></div>')
    return (f'{legend}<div class="wobble">{"".join(out)}{axis}</div>'
            '<p class="cap">Dot = the number. Bar = the 90% wobble range from re-drawing the brands '
            '(bootstrap). The verdict reads the <b>left end</b> of the bar against the shaded bands, so a '
            'single lucky number cannot earn \u201ctrust it\u201d. Only the first row is the pre-registered trust test; '
            'the rest are context.</p>')


def brand_table(run: dict) -> str:
    rows = []
    for b in sorted(run.get("brands") or [], key=lambda b: b.get("rank_revenue") or 99):
        link = b.get("filing_url")
        rev = money(b.get("revenue_usd"))
        rev_html = f'<a href="{esc(link)}">{rev}</a>' if link and link.startswith("https://") else rev
        niche = " \u00b7 niche" if b.get("niche") else ""
        rows.append(
            f'<tr><td><b>{esc(b.get("name"))}</b><div class="muted">{esc(b.get("description"))}</div></td>'
            f'<td class="n">{rev_html}<div class="muted">{esc(b.get("fiscal_year"))}</div></td>'
            f'<td class="n">#{num(b.get("rank_revenue"), 0)}</td>'
            f'<td class="n">{num(b.get("intent_mean"))}<div class="muted">#{num(b.get("rank_intent"), 0)}</div></td>'
            f'<td class="n">{num(b.get("say_mean"))}<div class="muted">#{num(b.get("rank_say"), 0)}</div></td>'
            f'<td class="n">{pct(b.get("aware_share"))}</td>'
            f'<td class="n">{pct(b.get("buy_share"))}{niche}</td></tr>')
    head = (f'<tr><th>Brand</th><th class="n">Revenue {tag("MEASURED")}</th><th class="n">Rank</th>'
            f'<th class="n">Likely to buy, 1\u201310 {tag("SYNTHETIC")}</th><th class="n">Website good, 1\u201310 {tag("SYNTHETIC")}</th>'
            f'<th class="n">Heard of it {tag("SYNTHETIC")}</th><th class="n">Buys this kind {tag("SYNTHETIC")}</th></tr>')
    return (f'<div class="scroll"><table><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'
            '<p class="cap">Revenue links go to the company\u2019s SEC filing named in the brand file. '
            'Crowd numbers are averages over the AI personas; \u201cniche\u201d = under 30% say they buy this kind of product.</p>')


def why_quotes(run: dict, followup: Optional[dict]) -> str:
    if not followup:
        return '<p class="muted">No follow-up answers file found.</p>'
    names = {b["id"]: b.get("name", b["id"]) for b in run.get("brands") or []}
    gaps = run.get("top_gaps") or []
    order = [g["brand_id"] for g in gaps if g.get("brand_id") in followup] or list(followup)
    fl = run.get("followup_loop") or {}
    out = []
    for bid in order:
        answers = [a for a in followup.get(bid) or [] if isinstance(a, str) and a.strip()]
        if not answers:
            continue
        n = len(answers)
        picks = sorted({0, n // 2, n - 1})
        gap = next((g for g in gaps if g.get("brand_id") == bid), None)
        gap_txt = (f'AI crowd ranked it #{num(gap.get("crowd_rank"), 0)}; real revenue ranks it '
                   f'#{num(gap.get("revenue_rank"), 0)}') if gap else ""
        qs = "".join(f'<blockquote class="quote">{esc(answers[i])}<footer>answer {i + 1} of {n}</footer></blockquote>'
                     for i in picks)
        out.append(f'<div class="why"><h3>{esc(names.get(bid, bid))}</h3><p class="muted">{esc(gap_txt)}</p>{qs}</div>')
    src = (f'Panel {esc(fl.get("panel_id"))}, {esc(fl.get("n_personas"))} new AI personas. '
           if fl.get("panel_id") else "")
    return (f'<p class="sub">{tag("SYNTHETIC")} {tag("AI-GENERATED")} Verbatim answers from AI personas, not real people. '
            f'{src}Picked by position (first, middle, last answer), not by content.</p>'
            f'<div class="whys">{"".join(out)}</div>')


def timeline(run: dict, commits: list[dict], decisions: list[dict]) -> str:
    day = (run.get("recorded_at") or "")[:10]
    since = minutes(TIMELINE_SINCE)
    cs = [c for c in commits if (not day or c["date"] == day) and minutes(c["time"]) >= since]
    ds = [d for d in decisions if (not day or d["date"] == day) and minutes(d["time"]) >= since]
    events = []
    for c in cs:
        events.append({"time": c["time"], "kind": classify(c["subject"]), "src": "commit",
                       "id": c["hash"], "text": c["subject"]})
    for d in ds:
        events.append({"time": d["time"], "kind": classify(d["text"]), "src": "decision", "id": "", "text": d["text"]})
    if not events:
        return '<p class="muted">No git history or decision log available where this page was built.</p>'
    events.sort(key=lambda e: (minutes(e["time"]), e["src"]))

    rule_c = [e for e in events if e["src"] == "commit" and e["kind"] == "rule"]
    result_c = [e for e in events if e["src"] == "commit" and re.search(r"first real run", e["text"], re.I)]
    claim = ""
    if rule_c and result_c:
        r0, res = rule_c[0], result_c[0]
        gap = minutes(res["time"]) - minutes(r0["time"])
        amend = [e for e in rule_c if minutes(e["time"]) < minutes(res["time"])]
        claim = (f'<div class="claim"><b>Rule first, result second.</b> The trust rule was committed at '
                 f'<code>{esc(r0["time"])}</code> ({esc(r0["id"])}); the first result was committed at '
                 f'<code>{esc(res["time"])}</code> ({esc(res["id"])}), {gap} minutes later. '
                 f'{len(amend)} rule commit(s) came before the first result. Source: git history of this repo.</div>')

    # SVG strip
    t0 = min(minutes(e["time"]) for e in events)
    t1 = max(minutes(e["time"]) for e in events)
    t1 = max(t1, t0 + 10)
    W, L, R = 760, 30, 730

    def x(t):
        return L + (R - L) * (minutes(t) - t0) / (t1 - t0)
    svg = [f'<svg class="tl" viewBox="0 0 {W} 96" role="img" aria-label="Timeline of rules and results">']
    svg.append(f'<line class="axis" x1="{L}" y1="48" x2="{R}" y2="48"/>')
    tick = (t0 // 10 + 1) * 10
    while tick <= t1:
        xx = L + (R - L) * (tick - t0) / (t1 - t0)
        svg.append(f'<line class="axis" x1="{xx:.0f}" y1="44" x2="{xx:.0f}" y2="52"/>'
                   f'<text class="cs" x="{xx:.0f}" y="92" text-anchor="middle">{tick // 60}:{tick % 60:02d}</text>')
        tick += 10
    for e in events:
        if e["src"] != "commit":
            continue
        cls = {"rule": "e-rule", "result": "e-res"}.get(e["kind"], "e-oth")
        yy = 30 if e["kind"] == "rule" else (66 if e["kind"] == "result" else 48)
        svg.append(f'<circle class="{cls}" cx="{x(e["time"]):.1f}" cy="{yy}" r="{7 if e["kind"] != "other" else 4}"/>')
    for e in events:
        if e["src"] == "decision" and e["kind"] == "rule":
            svg.append(f'<rect class="e-rule" x="{x(e["time"]) - 4:.1f}" y="10" width="8" height="8"/>')
    svg.append("</svg>")
    leg = ('<div class="wleg"><span class="sw e-rule"></span>rule written or locked '
           '<span class="sw e-res"></span>result computed <span class="sw e-oth"></span>other commit '
           '(squares = decision-log entries)</div>')

    items = []
    for e in events:
        kind = {"rule": "RULE", "result": "RESULT"}.get(e["kind"], "")
        badge = f'<span class="kb k-{e["kind"]}">{kind}</span>' if kind else ""
        src = (f'<code>{esc(e["id"])}</code> commit' if e["src"] == "commit" else "decision log")
        text = scrub(e["text"])
        if len(text) > 420:
            text = text[:417].rsplit(" ", 1)[0] + " \u2026"
        items.append(f'<li class="ev ev-{e["kind"]}"><span class="et">{esc(e["time"])}</span>'
                     f'<div>{badge} <span class="es">{src}</span><div>{esc(text)}</div></div></li>')
    return (f'{claim}{leg}<div class="chart scroll">{"".join(svg)}</div>'
            f'<details class="evs"><summary>All {len(events)} timestamped entries (commits + decision log, ET)</summary>'
            f'<ol class="events">{"".join(items)}</ol></details>'
            '<p class="cap">Times are Eastern. Decision-log text is quoted from the team log and shortened where long. '
            'The log itself records two honest caveats: the 12:10 amendment came after the panel ran (but before any '
            'statistic), and the Wikipedia line was added at 12:24, after the main result was seen.</p>')


def trace_list(run: dict) -> str:
    groups = []
    fl = run.get("followup_loop") or {}
    if fl.get("trace"):
        groups.append(("Agent loop: biggest gaps \u2192 WHY question \u2192 new synthetic panel \u2192 raw answers",
                       fl["trace"], fl.get("note")))
    if run.get("trace"):
        groups.append(("Pipeline run that wrote the run file", run["trace"], None))
    if not groups:
        return '<p class="muted">No trace in this run file.</p>'
    out = []
    for title, steps, note in groups:
        lis = []
        for s in steps:
            meta = " \u00b7 ".join(x for x in [s.get("agent"), s.get("tool") or s.get("model")] if x)
            lis.append(f'<li><span class="et">{esc(hhmm(s.get("t")))}</span><div><b>{esc(scrub(s.get("step")))}</b>'
                       f' <span class="es">{esc(meta)}</span><div class="muted">{esc(scrub(s.get("detail")))}</div></div></li>')
        nt = f'<p class="cap">{esc(note)}</p>' if note else ""
        out.append(f'<h3>{esc(title)}</h3><ol class="steps">{"".join(lis)}</ol>{nt}')
    return "".join(out)


def recount_box(rc: Optional[dict]) -> str:
    if not rc:
        return '<p class="muted">No recount file found.</p>'
    cells = ""
    if rc.get("persona_cells"):
        cells = f' All {esc(rc["persona_cells"])} single persona answers were compared; {esc(rc["persona_bad"])} differ.'
    nc = f'<p class="cap">Not checked by the recount: {esc(rc["not_checked"])}</p>' if rc.get("not_checked") else ""
    return (f'<div class="claim">A second script, written without reading the main code, recomputed the run file '
            f'from the raw CSV: <b>{rc["checks_yes"]}</b> checks matched, <b>{rc["checks_no"]}</b> did not.{cells} '
            f'Mismatches: {esc(rc.get("mismatches"))}. Source: <code>say/audit/RECOUNT.md</code>.</div>{nc}')


def limits_box(run: dict) -> str:
    lis = "".join(f"<li>{esc(scrub(x))}</li>" for x in run.get("limits") or [])
    panel = run.get("panel") or {}
    extra = []
    if panel.get("persona_model_note"):
        extra.append(f"<li>{esc(panel['persona_model_note'])}</li>")
    fw = run.get("fame_wiki") or {}
    if fw.get("note"):
        extra.append(f"<li>{esc(fw['note'])}</li>")
    n = (run.get("agreement") or {}).get("n_brands")
    if n:
        extra.append(f"<li>Only {esc(n)} brands, so every rank agreement is wide; the wobble bars show how wide.</li>")
    cost = run.get("cost") or {}
    cost_html = ""
    if cost:
        cost_html = (f'<p>{tag("ESTIMATE")} Model calls in the pipeline: {esc(cost.get("calls"))}, about '
                     f'${esc(cost.get("estimate_usd"))}. {esc(cost.get("flashpoint_note"))}</p>')
    return f'<ul class="limits">{lis}{"".join(extra)}</ul>{cost_html}<p class="muted">{esc(NOT_ADVICE)}</p>'


def legend() -> str:
    return (f'<div class="legend">{tag("MEASURED")} read from a public record (SEC filing, Wikimedia API) '
            f'{tag("SYNTHETIC")} answered by AI personas, not people {tag("AI-GENERATED")} text written by an AI model '
            f'{tag("ESTIMATE")} rough figure {tag("COMPUTED")} worked out by code from the labeled inputs</div>')


CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#5d5d58;--line:#d8d5cc;--card:#fff;--soft:#f1efe8;
--meas:#0b5c8f;--syn:#a8430a;--ai:#6b3d8f;--est:#7a6200;--comp:#3d5a3d;
--ask:#b3261e;--check:#8a6100;--trust:#1b6e3a;--z1:#f6dedb;--z2:#f7ecd0;--z3:#dcefe0;
--each:#6b6b6b;--money:#D55E00;--wiki:#009E73}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--muted:#a9a79f;--line:#3a3934;--card:#1f1f1c;
--soft:#26251f;--meas:#7cc2f0;--syn:#f0a170;--ai:#c7a3e6;--est:#e3c75a;--comp:#a6c9a6;--ask:#ff8a80;--check:#e8c167;
--trust:#7fd39a;--z1:#3d2422;--z2:#3a321c;--z3:#1f3626;--each:#b5b5b5}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:880px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:clamp(26px,5vw,38px);line-height:1.15;margin:6px 0 10px;letter-spacing:-.01em}
h2{font-size:22px;margin:0 0 4px}h3{font-size:17px;margin:18px 0 6px}
.kicker{font-weight:600;color:var(--muted);font-size:14px}
.meta{color:var(--muted);font-size:14px}.muted{color:var(--muted);font-size:14px}
.sub{color:var(--muted);margin:0 0 14px}.cap{color:var(--muted);font-size:14px;margin:10px 0 0}
section{margin:44px 0 0;padding-top:20px;border-top:1px solid var(--line)}
code{font:13px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--soft);padding:1px 5px;border-radius:4px}
a{color:var(--meas)}
.tag{display:inline-block;font:600 11px/1 ui-monospace,Menlo,monospace;padding:3px 6px;border-radius:4px;border:1px solid currentColor;margin:2px 4px 2px 0;vertical-align:middle;white-space:nowrap}
.t-meas{color:var(--meas)}.t-syn{color:var(--syn)}.t-ai{color:var(--ai)}.t-est{color:var(--est)}.t-comp{color:var(--comp)}
.legend{font-size:14px;color:var(--muted);margin:14px 0 0;line-height:2}
.verdict{background:var(--card);border:1px solid var(--line);border-left:8px solid var(--ask);border-radius:10px;padding:20px;margin:22px 0 0}
.v-trust{border-left-color:var(--trust)}.v-check{border-left-color:var(--check)}
.v-top{display:flex;gap:20px;flex-wrap:wrap;justify-content:space-between}
.v-word{font-size:clamp(30px,7vw,44px);font-weight:800;color:var(--ask);line-height:1.05;margin:4px 0}
.v-trust .v-word{color:var(--trust)}.v-check .v-word{color:var(--check)}
.v-reason{margin:6px 0 0;max-width:420px}
.v-metric{min-width:220px}.v-metric .big{font-size:44px;font-weight:800;line-height:1}
.lab{font-size:13px;font-weight:600;color:var(--muted)}
.small{font-size:14px;color:var(--muted)}
.rule blockquote{margin:6px 0 0;padding:10px 14px;background:var(--soft);border-radius:6px;font-size:15px}
.rule{margin-top:16px}.draft{margin-top:16px}.draft .q{font-size:18px;margin:4px 0 0}
.stop{margin:18px 0 0;font-weight:700;font-size:17px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:16px 0 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.tile .big{font-size:36px;font-weight:800;line-height:1.1;margin:4px 0}
.chart{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.scroll{overflow-x:auto}
svg{display:block;width:100%;height:auto}svg.slope{min-width:600px}svg.tl{min-width:520px}
svg text{fill:var(--fg)}.ch{font-weight:700;font-size:16px}.cs{font-size:13px;fill:var(--muted)}
.cl{font:700 11px ui-monospace,Menlo,monospace}.cl.meas{fill:var(--meas)}.cl.syn{fill:var(--syn)}
.rho{font-weight:700;font-size:15px}.rk{font-size:12px;fill:var(--muted)}
.bl{font-weight:700;font-size:14px}.rv{font-size:11px;fill:var(--muted)}
.axis{stroke:var(--line);stroke-width:2}.dot{stroke:var(--card);stroke-width:2}
.agree,.wobble{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.arow{display:grid;grid-template-columns:minmax(120px,32%) 1fr 64px;gap:10px;align-items:center;padding:8px 0}
.wrow{display:grid;grid-template-columns:minmax(120px,30%) 1fr 116px;gap:10px;align-items:center;padding:8px 0}
.arow+.arow,.wrow+.wrow{border-top:1px solid var(--soft)}
.alab,.wlab{font-size:14px;font-weight:600}.aval,.wval{font-weight:800;text-align:right;font-variant-numeric:tabular-nums}
.wval .wk{font-weight:400}
.atrack,.wtrack{position:relative;height:26px;background:var(--soft);border-radius:4px;overflow:hidden}
.azero{position:absolute;left:50%;top:0;bottom:0;width:2px;background:var(--muted);opacity:.6}
.abar{position:absolute;top:4px;bottom:4px;border-radius:3px}
.b-each{background:var(--each)}.b-money{background:var(--money)}.b-wiki{background:var(--wiki)}
.axisrow{border-top:0!important;padding-top:0}.aticks{display:flex;justify-content:space-between;font-size:12px;color:var(--muted)}
.z{position:absolute;top:0;bottom:0}.z1{left:0;width:70%;background:var(--z1)}.z2{left:70%;width:15%;background:var(--z2)}.z3{left:85%;width:15%;background:var(--z3)}
.wr{position:absolute;top:10px;height:6px;background:var(--fg);opacity:.55;border-radius:3px}
.wlo{position:absolute;top:4px;width:3px;height:18px;background:var(--fg);margin-left:-1px}
.wpt{position:absolute;top:6px;width:14px;height:14px;margin-left:-7px;border-radius:50%;background:var(--money);border:2px solid var(--card)}
.wk{font-size:12px;color:var(--muted);font-weight:400}
.wtest{background:linear-gradient(90deg,var(--soft),transparent);border-radius:6px}
.testmark{color:var(--ask);font-size:12px}
.wleg{font-size:13px;color:var(--muted);margin:0 0 8px;line-height:2}
.sw{display:inline-block;width:12px;height:12px;border-radius:2px;margin:0 4px 0 10px;vertical-align:-1px;border:1px solid var(--line)}
.sw.z1{background:var(--z1)}.sw.z2{background:var(--z2)}.sw.z3{background:var(--z3)}
.e-rule{fill:var(--meas);background:var(--meas)}.e-res{fill:var(--money);background:var(--money)}.e-oth{fill:var(--muted);background:var(--muted)}
table{width:100%;border-collapse:collapse;background:var(--card);font-size:14px;min-width:640px}
th,td{padding:9px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:13px;color:var(--muted);font-weight:600;vertical-align:bottom}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.whys{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.why{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:4px 14px 14px}
.quote{margin:10px 0 0;padding:8px 12px;border-left:3px solid var(--syn);background:var(--soft);font-size:14px;border-radius:0 6px 6px 0}
.quote footer{font-size:12px;color:var(--muted);margin-top:4px}
.claim{background:var(--card);border:1px solid var(--line);border-left:6px solid var(--meas);border-radius:8px;padding:12px 14px;margin:0 0 12px}
ol.steps,ol.events{list-style:none;padding:0;margin:8px 0 0;position:relative}
ol.steps li,ol.events li{display:grid;grid-template-columns:52px 1fr;gap:12px;padding:8px 0 8px;border-left:2px solid var(--line);margin-left:24px;padding-left:14px;position:relative}
ol.steps li::before,ol.events li::before{content:"";position:absolute;left:-7px;top:13px;width:12px;height:12px;border-radius:50%;background:var(--card);border:2px solid var(--muted)}
ol.events li.ev-rule::before{background:var(--meas);border-color:var(--meas)}ol.events li.ev-result::before{background:var(--money);border-color:var(--money)}
.et{font:600 13px ui-monospace,Menlo,monospace;color:var(--muted);padding-top:2px}
.es{font-size:12px;color:var(--muted)}
.kb{font:700 11px ui-monospace,Menlo,monospace;padding:2px 5px;border-radius:3px;color:#fff}.k-rule{background:var(--meas)}.k-result{background:var(--money)}
details.evs{margin-top:12px}details.evs summary{cursor:pointer;font-weight:600}
.limits li{margin:4px 0}
footer.foot{margin-top:48px;color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:14px}
@media (max-width:560px){.arow{grid-template-columns:1fr 56px}.wrow{grid-template-columns:1fr 100px}.alab,.wlab{grid-column:1/-1}.v-metric .big{font-size:36px}}
@media print{body{background:#fff;color:#000;font-size:12px}main{max-width:none;padding:0}
section,.verdict,.why,.tile,.chart,table,.claim{break-inside:avoid}
details.evs>*{display:block}details.evs summary{display:none}.scroll{overflow:visible}
svg.slope,svg.tl,table{min-width:0}a{color:#000}}
"""


def build(run: dict, followup=None, recount_text=None, decisions_text=None, commits=None, wiki_file=None,
          run_path: str = "") -> str:
    commits = commits or []
    panel = run.get("panel") or {}
    title = run.get("headline") or "Say vs. Spend"
    n = panel.get("n_personas")
    nb = (run.get("agreement") or {}).get("n_brands")
    rr = run.get("repeat_run") or {}
    intro = (f'We asked {esc(n)} AI shoppers (Flashpoint synthetic personas) about {esc(nb)} online brands, '
             f'then checked their \u201chow likely are you to buy\u201d ranking against what the companies really sold '
             f'(SEC filings).' + (f' A second panel of {esc(rr.get("n_personas"))} different AI shoppers (same persona model) answered the same questions.'
                                  if rr.get("n_personas") else ""))
    meta = (f'Run <code>{esc(run.get("run_id"))}</code> \u00b7 recorded {esc(run.get("recorded_at"))} \u00b7 '
            f'panel <code>{esc(panel.get("panel_id"))}</code> \u00b7 source: {esc(run.get("panel_source"))}')
    body = [
        f'<div class="kicker">Say vs. Spend \u00b7 evidence report</div><h1>{esc(title)}</h1>',
        f'<p>{intro}</p><p class="meta">{meta}</p>',
        verdict_card(run),
        stat_tiles(run),
        legend(),
        section("Same shoppers, different order", slope_chart(run, wiki_file),
                "Each line is one brand. Rank 1 is the top of each list.", "ranks"),
        section("The AI crowds agree with each other, not with the money", agree_bars(run),
                "Spearman rank agreement: +1 = same order, 0 = no relation, \u22121 = reversed.", "agree"),
        section("How sure is each number?", wobble_chart(run),
                "Every agreement number in the run file, with its 90% wobble range.", "wobble"),
        section("The six brands", brand_table(run), "", "brands"),
        section("Why did the AI shoppers rank them that way?", why_quotes(run, followup),
                "", "why"),
        section("Rules came before results", timeline(run, commits, parse_decisions(decisions_text)),
                "Every rule change and result, in the order it happened.", "timeline"),
        section("What the agent did, step by step", trace_list(run),
                "Copied from the trace in the run file. Local file paths removed.", "trace"),
        section("Independent recount", recount_box(parse_recount(recount_text)), "", "recount"),
        section("Limits", limits_box(run), "", "limits"),
        f'<footer class="foot">Built by <code>say/report.py</code> from <code>{esc(scrub(run_path) or "run file")}</code>. '
        f'Static page: no JavaScript, no outside requests. '
        f'{esc(NOT_ADVICE)}</footer>',
    ]
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<meta name=\"color-scheme\" content=\"light dark\">"
            f"<title>Say vs. Spend: evidence report</title><style>{CSS}</style></head>"
            f"<body><main>{''.join(body)}</main></body></html>\n")


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m say.report", description="Write the offline evidence report.")
    p.add_argument("--run", default=DEFAULT_RUN)
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--followup", default=DEFAULT_FOLLOWUP)
    p.add_argument("--recount", default=DEFAULT_RECOUNT)
    p.add_argument("--decisions", default=DEFAULT_DECISIONS)
    p.add_argument("--wiki", default=DEFAULT_WIKI)
    p.add_argument("--no-git", action="store_true", help="skip git history (timeline uses the decision log only)")
    a = p.parse_args(argv)
    run = read_json(a.run)
    if not isinstance(run, dict):
        print(f"no run file at {a.run}")
        return 2
    page = build(run, followup=read_json(a.followup), recount_text=read_text(a.recount),
                 decisions_text=read_text(a.decisions), commits=[] if a.no_git else git_log(REPO),
                 wiki_file=read_json(a.wiki), run_path=os.path.relpath(a.run, REPO) if a.run.startswith(REPO) else os.path.basename(a.run))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {a.out} ({len(page):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
