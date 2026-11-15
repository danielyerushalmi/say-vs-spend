"""Turn a Flashpoint survey export (wide CSV) into the normalized panel dict for Say vs. Spend.

Standard library only. Written BEFORE the real export existed, so column names are matched
loosely and every column or value we cannot read is reported, never silently dropped.

Wide format (one row per persona, one column per question x brand), e.g.

    panel_respondent_id, Q1__figs, Q1__allbirds, Q2__figs, ..., Q3__allbirds

Supported header shapes for a looped column (<QID> then a loop key that names the brand):
    Q1__figs      Q1_figs      Q1 - Figs      Q1[figs]      Q1: Figs      Q1.figs
    "How good is this brand's website? - Figs"   (question text instead of an id)
A second row holding the full question text (Qualtrics style) is detected and used to tell
which question is which.

Output (see import_export):
    {"panel_id", "source_link", "recorded_at", "n_personas", "persona_model_note", "order",
     "responses": [{"persona_id", "brand_id", "say", "intent", "aware"}],
     "_import": {...diagnostics: unmatched columns, unreadable values, mapping used...}}
Only the "_import" key is extra; consumers can ignore it.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from typing import Iterable, Optional

KINDS = ("say", "intent", "aware", "buy")
SCALE_MIN, SCALE_MAX = 1, 10

_BLANKS = {"", "na", "n/a", "none", "null", "nan", "-", "--", "—", "skipped", "no answer", "prefer not to say"}

# Keyword rules for deciding which question is which, from question text. First hit wins.
_KEYWORDS = (
    ("aware", ("heard", "aware", "familiar", "recogni")),
    ("buy", ("kind of product",)),
    ("intent", ("likely", "likelihood", "buy", "purchase")),
    ("say", ("website", "quality", "rate ", "rating")),
)

_ID_CANDIDATES = ("panel_respondent_id", "respondent_id", "response_id", "responseid", "persona_id", "id")


# ----------------------------------------------------------------------------- text helpers

def norm(text: str) -> str:
    """Lowercase and keep letters/digits only: '1-800-Flowers' -> '1800flowers'."""
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


def _is_blank(value: Optional[str]) -> bool:
    return value is None or str(value).strip().lower() in _BLANKS


def parse_scale(value: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    """Parse a 1-10 answer. Returns (int or None, problem or None). Blank -> (None, None)."""
    if _is_blank(value):
        return None, None
    s = str(value).strip()
    # A signed negative ("-3", "Rating: -3", Unicode minus) is out of range, never read as 3.
    # A dash between words or after a digit ("10 - Extremely likely", "1-800") is not a sign.
    if re.search(r"(?<![\w.])[-\u2212]\d", s):
        return None, "out of range"
    m = re.match(r"^\s*(\d+(?:\.0+)?)(?!\d|\.\d)", s)
    if m:
        number = int(float(m.group(1)))
    else:
        found = re.findall(r"(?<![\d.])(\d+)(?![\d.])", s)
        if len(found) != 1:
            return None, "unparseable"
        number = int(found[0])
    if not SCALE_MIN <= number <= SCALE_MAX:
        return None, "out of range"
    return number, None


def parse_bool(value: Optional[str]) -> tuple[Optional[bool], Optional[str]]:
    """Parse yes/no style answers. Returns (bool or None, problem or None)."""
    if _is_blank(value):
        return None, None
    s = str(value).strip().lower()
    # Flashpoint stores single-choice Yes/No as option codes: "1" = Yes, "2" = No (per its survey builder).
    if re.match(r"^(no\b|n$|false\b|0$|2$|never heard|not heard|have not|haven't|i have not|i haven't|unaware|not aware|not familiar)", s):
        return False, None
    if re.match(r"^(yes\b|y$|true\b|1$|heard|have heard|i have heard|i've heard|aware|familiar)", s):
        return True, None
    return None, "unparseable"


# ----------------------------------------------------------------------------- headers

_QID = r"[A-Za-z]{0,3}\d+[A-Za-z]?"


def split_header(header: str) -> Optional[tuple[str, str]]:
    """Split a header into (question key, loop key), or None if it is not a looped column."""
    h = header.strip()
    if not h:
        return None
    m = re.match(r"^(.+?)__+(.+)$", h)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(.+?)\s*\[\s*(.+?)\s*\]$", h)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(rf"^({_QID})\s*(?:[-–—:|.]|_)\s*(.+)$", h)
    if m:
        return m.group(1), m.group(2).strip()
    m = re.match(rf"^({_QID})\s+(.+)$", h)
    if m:
        return m.group(1), m.group(2).strip()
    # Question text then separator then brand: split on the last " - " (or ": ", " | ").
    m = re.match(r"^(.+)\s[-–—|]\s(.+)$", h)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None


def _brand_candidates(brand: dict, extra: Iterable[str] = ()) -> set[str]:
    cands = {norm(brand.get("id", "")), norm(brand.get("name", ""))}
    for a in list(brand.get("aliases") or []) + list(extra):
        cands.add(norm(a))
    cands.discard("")
    return cands


def build_brand_matcher(brands: list[dict], aliases: Optional[dict] = None, loop_key_map: Optional[dict] = None):
    """Return match(loop_key) -> (brand_id or None, note). Exact normalized match first, then
    containment (>= 4 chars) only if it points to exactly one brand."""
    aliases = aliases or {}
    cands = {b["id"]: _brand_candidates(b, _as_list(aliases.get(b["id"]))) for b in brands}
    explicit = {norm(k): v for k, v in (loop_key_map or {}).items()}

    def match(loop_key: str):
        k = norm(loop_key)
        if not k:
            return None, "empty loop key"
        if k in explicit:
            return explicit[k], None
        exact = [bid for bid, cs in cands.items() if k in cs]
        if len(exact) == 1:
            return exact[0], None
        if len(exact) > 1:
            return None, f"ambiguous: matches {sorted(exact)}"
        fuzzy = [bid for bid, cs in cands.items() if any(len(c) >= 4 and len(k) >= 4 and (c in k or k in c) for c in cs)]
        if len(fuzzy) == 1:
            return fuzzy[0], None
        if len(fuzzy) > 1:
            return None, f"ambiguous: could be {sorted(fuzzy)}"
        return None, "loop key matches no brand"

    return match


def _as_list(x) -> list:
    if x is None:
        return []
    return [x] if isinstance(x, str) else list(x)


def detect_kind(text: str) -> Optional[str]:
    t = text.lower()
    for kind, words in _KEYWORDS:
        if any(w in t for w in words):
            return kind
    return None


def _find_id_column(header: list[str], id_column: Optional[str]) -> Optional[int]:
    if id_column:
        for i, h in enumerate(header):
            if h.strip().lower() == id_column.strip().lower():
                return i
        raise ValueError(f"id column {id_column!r} not found in header")
    lower = [h.strip().lower() for h in header]
    for cand in _ID_CANDIDATES:
        if cand in lower:
            return lower.index(cand)
    for i, h in enumerate(lower):
        if re.search(r"(^|[^a-z])id($|[^a-z])", h) and split_header(header[i]) is None:
            return i
    return None


# ----------------------------------------------------------------------------- main import

def import_export(csv_path, brands: list[dict], meta: Optional[dict] = None, *,
                  question_map: Optional[dict] = None, aliases: Optional[dict] = None,
                  loop_key_map: Optional[dict] = None, id_column: Optional[str] = None) -> dict:
    """Read a Flashpoint wide-format CSV and return the normalized panel dict.

    brands: [{"id","name", optional "aliases"}]. meta: panel_id, source_link, recorded_at,
    persona_model_note, order. question_map: {"Q1":"say","Q2":"intent","Q3":"aware"}.
    aliases: {brand_id: [extra names]}. loop_key_map: {"brand_a": "figs"} for exact overrides.
    """
    meta = dict(meta or {})
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.reader(f)]
    if not rows:
        raise ValueError(f"{csv_path} is empty")
    header = [h.strip() for h in rows[0]]
    data = rows[1:]

    match_brand = build_brand_matcher(brands, aliases, loop_key_map)
    id_idx = _find_id_column(header, id_column)

    # Group looped columns by question key.
    groups: dict[str, list[tuple[int, str, str]]] = {}   # qkey -> [(col, brand_id, header)]
    unmatched: list[dict] = []
    ignored: list[str] = []
    for i, h in enumerate(header):
        if i == id_idx:
            continue
        parts = split_header(h)
        if parts is None:
            # Admin columns (Status, Device, Quality...) are not questions: listed, but never block a run.
            ignored.append(h)
            continue
        qkey, loop_key = parts
        bid, note = match_brand(loop_key)
        if bid is None:
            unmatched.append({"column": h, "reason": note})
            continue
        groups.setdefault(qkey, []).append((i, bid, h))

    # Optional second header row holding question text (or short labels).
    label_row_skipped = False
    texts: dict[str, list[str]] = {q: [q] for q in groups}
    if data and groups:
        cells = [(q, data[0][c].strip()) for q, cols in groups.items() for (c, _, _) in cols if c < len(data[0])]
        nonblank = [(q, t) for q, t in cells if t]
        same = [1 for cols in groups.values() for (c, _, h) in cols if c < len(data[0]) and data[0][c].strip() == h]
        if nonblank and len(same) * 2 >= len(nonblank):
            # Flashpoint repeats the header row as the first data row: skip it, it is not a persona.
            label_row_skipped = True
            data = data[1:]
            nonblank = []
        if nonblank and sum(1 for _, t in nonblank if len(t) >= 20 and detect_kind(t)) * 2 >= len(nonblank):
            for q, t in nonblank:
                texts[q].append(t)
            data = data[1:]
        elif nonblank and all(parse_scale(t)[0] is None and parse_bool(t)[0] is None for _, t in nonblank):
            # A label row (text where numbers / yes-no belong): skip it so it is not counted as a persona.
            label_row_skipped = True
            data = data[1:]

    # Decide the kind of each question key.
    # Our Flashpoint survey uses these stable labels (VERIFIED from its survey builder, 2026-11-14).
    defaults = {"SAY": "say", "INTENT": "intent", "AWARE": "aware", "BUY": "buy"}
    explicit = {norm(k): v for k, v in {**defaults, **(question_map or {})}.items()}
    for v in explicit.values():
        if v not in KINDS:
            raise ValueError(f"question_map values must be one of {KINDS}, got {v!r}")
    kind_of: dict[str, str] = {}
    kind_source: dict[str, str] = {}
    for q in groups:
        if norm(q) in explicit:
            kind_of[q], kind_source[q] = explicit[norm(q)], "explicit mapping"
            continue
        kind = detect_kind(" ".join(texts[q]))
        if kind:
            kind_of[q], kind_source[q] = kind, "question text keywords"
    for q, cols in groups.items():
        if q not in kind_of:
            for (_, _, h) in cols:
                unmatched.append({"column": h, "reason": f"question {q!r} could not be mapped to say/intent/aware/buy"})

    # Column index: (brand, kind) -> col; duplicates are reported.
    colmap: dict[tuple[str, str], int] = {}
    colname: dict[tuple[str, str], str] = {}
    for q, cols in groups.items():
        if q not in kind_of:
            continue
        for (c, bid, h) in cols:
            key = (bid, kind_of[q])
            if key in colmap:
                unmatched.append({"column": h, "reason": f"duplicate of {colname[key]!r} for {key}; first one used"})
                continue
            colmap[key] = c
            colname[key] = h

    # Walk the rows.
    responses: list[dict] = []
    unparseable: list[dict] = []
    duplicates: list[str] = []
    seen_ids: set[str] = set()
    persona_ids: list[str] = []
    brand_ids = [b["id"] for b in brands]
    for n, row in enumerate(data, start=1):
        if not any(c.strip() for c in row):
            continue
        pid = row[id_idx].strip() if id_idx is not None and id_idx < len(row) else ""
        if not pid:
            pid = f"ROW-{n}"
            unparseable.append({"row": n, "column": None, "value": None, "problem": "no persona id; used " + pid})
        if pid in seen_ids:
            duplicates.append(pid)
            continue
        seen_ids.add(pid)
        persona_ids.append(pid)
        for bid in brand_ids:
            rec = {"persona_id": pid, "brand_id": bid, "say": None, "intent": None, "aware": None, "buy": None}
            for kind in KINDS:
                c = colmap.get((bid, kind))
                if c is None or c >= len(row):
                    continue
                raw = row[c]
                if kind in ("aware", "buy"):
                    val, problem = parse_bool(raw)
                else:
                    val, problem = parse_scale(raw)
                if problem:
                    unparseable.append({"persona_id": pid, "column": colname[(bid, kind)], "value": raw, "problem": problem})
                rec[kind] = val
            if any(rec[k] is not None for k in KINDS):
                responses.append(rec)

    stem = os.path.splitext(os.path.basename(str(csv_path)))[0]
    return {
        "panel_id": meta.get("panel_id") or stem,
        "source_link": meta.get("source_link"),
        "recorded_at": meta.get("recorded_at"),
        "n_personas": len(persona_ids),
        "persona_model_note": meta.get("persona_model_note"),
        "order": meta.get("order", "shuffled"),
        "responses": responses,
        "_import": {
            "csv": str(csv_path),
            "id_column": header[id_idx] if id_idx is not None else None,
            "question_kinds": {q: {"kind": kind_of[q], "source": kind_source[q]} for q in kind_of},
            "brand_ids": brand_ids,
            "columns_used": {f"{b}/{k}": h for (b, k), h in colname.items()},
            "unmatched_columns": unmatched,
            "unparseable_values": unparseable,
            "duplicate_persona_ids_skipped": duplicates,
            "label_row_skipped": label_row_skipped,
            "ignored_admin_columns": ignored,
        },
    }


# ----------------------------------------------------------------------------- reporting

def _kinds_present(panel: dict) -> tuple:
    """KINDS, minus 'buy' when the export has no BUY answers (keeps old reports unchanged)."""
    has_buy = any(r.get("buy") is not None for r in panel["responses"])
    return KINDS if has_buy else tuple(k for k in KINDS if k != "buy")


def count_table(panel: dict) -> dict:
    """{brand_id: {"say": n, "intent": n, "aware": n}} = number of usable answers."""
    kinds = _kinds_present(panel)
    table = {b: {k: 0 for k in kinds} for b in panel.get("_import", {}).get("brand_ids", [])}
    for r in panel["responses"]:
        row = table.setdefault(r["brand_id"], {k: 0 for k in kinds})
        for k in kinds:
            if r.get(k) is not None:
                row[k] += 1
    return table


def summarize_import(panel: dict) -> str:
    """Plain-text report for a human to check before grading."""
    info = panel.get("_import", {})
    lines = [f"Panel {panel['panel_id']}: {panel['n_personas']} personas, {len(panel['responses'])} brand rows with data",
             f"Persona id column: {info.get('id_column')}"]
    for q, d in info.get("question_kinds", {}).items():
        lines.append(f"Question {q!r} -> {d['kind']} (by {d['source']})")
    has_buy = "buy" in _kinds_present(panel)
    lines += ["", f"{'brand':<24}{'say':>6}{'intent':>8}{'aware':>7}" + (f"{'buy':>6}" if has_buy else "") + "   (usable answers)"]
    for bid, c in count_table(panel).items():
        warn = "  <-- no data" if not any(c.values()) else ""
        lines.append(f"{bid:<24}{c['say']:>6}{c['intent']:>8}{c['aware']:>7}" + (f"{c['buy']:>6}" if has_buy else "") + warn)
    ig = info.get("ignored_admin_columns", [])
    lines += ["", f"Ignored admin columns ({len(ig)}): " + ", ".join(ig[:40])]
    un = info.get("unmatched_columns", [])
    lines += [f"Unmatched columns ({len(un)}):"] + [f"  {u['column']!r}: {u['reason']}" for u in un]
    bad = info.get("unparseable_values", [])
    lines += [f"Unreadable values ({len(bad)}):"]
    lines += [f"  {b.get('persona_id', 'row ' + str(b.get('row')))} {b.get('column')!r} = {b.get('value')!r}: {b['problem']}" for b in bad[:50]]
    if len(bad) > 50:
        lines.append(f"  ... and {len(bad) - 50} more")
    dups = info.get("duplicate_persona_ids_skipped", [])
    if dups:
        lines.append(f"Duplicate persona ids skipped ({len(dups)}): {dups[:10]}")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- CLI

def load_brands(path) -> list[dict]:
    """Load brands from a folder of .json files or one .json file. Each file may hold one brand
    dict, a list of brand dicts, or {"brands": [...]}. Only id and name (and aliases) are used."""
    files = [path] if os.path.isfile(path) else sorted(
        os.path.join(path, f) for f in os.listdir(path) if f.endswith(".json"))
    brands: list[dict] = []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            obj = json.load(f)
        items = obj.get("brands", obj) if isinstance(obj, dict) and "brands" in obj else obj
        for it in (items if isinstance(items, list) else [items]):
            if isinstance(it, dict) and it.get("id") and it.get("name"):
                brands.append({"id": it["id"], "name": it["name"], "aliases": it.get("aliases", [])})
    if not brands:
        raise ValueError(f"no brands (objects with id and name) found in {path}")
    return brands


def _parse_pairs(items: Optional[list[str]], what: str) -> dict:
    out = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError(f"{what} must look like KEY=VALUE, got {it!r}")
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m say.flashpoint_import",
                                 description="Normalize a Flashpoint wide CSV export and print a check report.")
    ap.add_argument("csv")
    ap.add_argument("--brands-dir", required=True, help="folder of brand .json files, or one .json file")
    ap.add_argument("--out", help="write the normalized panel JSON here (refuses to overwrite without --force)")
    ap.add_argument("--force", action="store_true", help="allow overwriting --out")
    ap.add_argument("--panel-id")
    ap.add_argument("--recorded-at")
    ap.add_argument("--source-link")
    ap.add_argument("--persona-model-note")
    ap.add_argument("--order", default="shuffled", choices=["shuffled", "fixed"])
    ap.add_argument("--question-map", help="e.g. Q1=say,Q2=intent,Q3=aware")
    ap.add_argument("--id-column")
    ap.add_argument("--alias", action="append", help="BRAND_ID=extra name (repeatable)")
    ap.add_argument("--loop-key", action="append", help="LOOPKEY=BRAND_ID exact override (repeatable)")
    a = ap.parse_args(argv)

    try:
        brands = load_brands(a.brands_dir)
        qmap = _parse_pairs(a.question_map.split(",") if a.question_map else None, "--question-map")
        aliases: dict = {}
        for k, v in _parse_pairs(a.alias, "--alias").items():
            aliases.setdefault(k, []).append(v)
        panel = import_export(
            a.csv, brands,
            {"panel_id": a.panel_id, "recorded_at": a.recorded_at, "source_link": a.source_link,
             "persona_model_note": a.persona_model_note, "order": a.order},
            question_map=qmap or None, aliases=aliases or None,
            loop_key_map=_parse_pairs(a.loop_key, "--loop-key") or None, id_column=a.id_column)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(summarize_import(panel))
    if a.out:
        if os.path.exists(a.out) and not a.force:
            print(f"\nNOT WRITTEN: {a.out} already exists (use --force to overwrite)", file=sys.stderr)
            return 3
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(panel, f, indent=2)
        print(f"\nWrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
