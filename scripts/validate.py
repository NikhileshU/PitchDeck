#!/usr/bin/env python3
"""validate.py — Tier-1 deterministic checks (14) over the deck.json IR.

No LLM, no network. Exit 0 = no error findings; exit 1 = at least one error.
Theme-dependent checks (contrast, min-type-size, overflow) run only when
--theme is given. `placeholder` sources become `unverified` findings.

NOTE on archetypes: spec §10 mandates archetype-conditional checks here
(answer-first, card-count), so the archetype names appear in the constants
below — and nowhere else in scripts/. Renderers never see them (invariant 6).
"""

import argparse, json, math, re, sys
from pathlib import Path

LAYOUTS = ("title", "section", "content", "hero")
ROLES = (None, "recommendation", "problem", "solution", "ask", "appendix")
TONES = ("info", "warn", "good")
CHARTS = ("bar", "hbar", "line", "pie")
BLOCK_TYPES = ("text", "bullets", "kpi", "chart", "table", "callout", "quote",
               "image", "columns", "divider")
SOURCED = ("chart", "table", "kpi")
CARD_LIMITS = {"startup-pitch": 15, "product-demo": 12, "idea-pitch": 10,
               "business-stakeholder": 20}
ANSWER_FIRST = ("business-stakeholder", "idea-pitch")

AUX = {"is", "are", "was", "were", "be", "been", "am", "has", "have", "had",
       "will", "would", "can", "could", "should", "must", "may", "might",
       "do", "does", "did", "cannot", "isn't", "aren't", "don't", "doesn't",
       "didn't", "won't", "can't", "needs", "need"}
_LEMMAS = ("grow drive increase decrease decline miss require deliver show prove "
           "win lose cost save exceed outperform convert hold lead trail expand "
           "shrink double halve accelerate stall drop climb slip surge jump plunge "
           "recover improve worsen widen narrow reach stay remain become make take "
           "give keep run move turn start stop end open close create build launch "
           "ship fund hire spend earn generate reduce boost lift push pull demand "
           "justify warrant unlock block enable threaten risk face own owe pay "
           "commit approve reject delay concentrate split depend rely mean signal "
           "suggest indicate confirm contradict undercut support strengthen weaken "
           "outpace lag total average beat cut hit fall rise sell buy bring catch "
           "choose draw find fly lay leave meet put say see send set stand stick "
           "tell think understand wear go come get write free clear close").split()
_IRREG = {"fell", "rose", "grew", "beat", "cut", "hit", "kept", "made", "took",
          "gave", "got", "ran", "went", "came", "wrote", "drove", "held", "led",
          "won", "lost", "spent", "paid", "built", "sank", "shrank", "broke",
          "fed", "met", "sold", "bought", "brought", "caught", "chose", "drew",
          "found", "flew", "laid", "left", "meant", "read", "said", "saw",
          "sent", "shot", "stood", "stuck", "told", "thought", "understood"}


def _verb_forms():
    forms = set(_IRREG)
    for w in _LEMMAS:
        forms |= {w, w + "s", w + "es", (w + "d") if w.endswith("e") else (w + "ed")}
        if w.endswith("y"):
            forms |= {w[:-1] + "ies", w[:-1] + "ied"}
    return forms


VERBS = _verb_forms()
_TEMPORAL = re.compile(
    r"^(q[1-4]|h[12]|fy ?\d{2,4}|\d{4}|w(ee)?k ?\d+|\d{1,2}[/.-]\d{1,2}([/.-]\d{2,4})?|"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*|"
    r"(mon|tue|wed|thu|fri|sat|sun)[a-z]*)$", re.I)


def F(check, severity, message, card=None, block=None):
    return {"check": check, "severity": severity, "card": card, "block": block,
            "message": message, "resolved": False}


def _iter_blocks(blocks, depth=0):
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        yield b, depth
        if b.get("type") == "columns":
            for col in b.get("children") or []:
                if isinstance(col, list):
                    yield from _iter_blocks(col, depth + 1)


def _cards(ir):
    return [c for c in ir.get("cards") or [] if isinstance(c, dict)]


def _content_cards(ir):
    return [c for c in _cards(ir) if c.get("layout") == "content"]


# ---- schema-valid ----------------------------------------------------------

def _check_block_schema(b, cid, depth, f):
    bid, t = b.get("id"), b.get("type")
    if not bid:
        f.append(F("schema-valid", "error", "block missing id", cid))
    if t not in BLOCK_TYPES:
        f.append(F("schema-valid", "error", f"unknown block type {t!r}", cid, bid))
        return
    req = {"text": ("text",), "bullets": ("items",), "kpi": ("value", "label"),
           "chart": ("chart", "data"), "table": ("headers", "rows"),
           "callout": ("tone", "text"), "quote": ("text",),
           "image": ("src", "alt"), "columns": ("children",), "divider": ()}
    for field in req[t]:
        if not b.get(field) and b.get(field) != 0:
            f.append(F("schema-valid", "error", f"{t} block missing {field!r}", cid, bid))
    if t == "callout" and b.get("tone") not in TONES:
        f.append(F("schema-valid", "error", f"callout tone {b.get('tone')!r} not in {TONES}", cid, bid))
    if t == "image" and b.get("fit") not in (None, "cover", "contain"):
        f.append(F("schema-valid", "error", f"image fit {b.get('fit')!r} invalid", cid, bid))
    if t == "columns":
        ch = b.get("children")
        if not isinstance(ch, list) or len(ch) not in (2, 3):
            f.append(F("schema-valid", "error", "columns needs 2 or 3 child arrays", cid, bid))
        elif depth > 0:
            f.append(F("schema-valid", "error", "columns may not nest inside columns", cid, bid))
    if t == "table" and isinstance(b.get("headers"), list) and isinstance(b.get("rows"), list):
        w = len(b["headers"])
        for i, row in enumerate(b["rows"]):
            if not isinstance(row, list) or len(row) != w:
                f.append(F("schema-valid", "error", f"table row {i} has {len(row) if isinstance(row, list) else '?'} cells for {w} headers", cid, bid))
    if t == "chart":
        if b.get("chart") not in CHARTS:
            f.append(F("schema-valid", "error", f"chart kind {b.get('chart')!r} not in {CHARTS}", cid, bid))
        d = b.get("data") or {}
        cats, series = d.get("categories"), d.get("series")
        if not cats or not isinstance(cats, list) or not series or not isinstance(series, list):
            f.append(F("schema-valid", "error", "chart data needs categories[] and series[]", cid, bid))
        else:
            for s in series:
                if not isinstance(s, dict) or len(s.get("values") or []) != len(cats):
                    f.append(F("schema-valid", "error", "series length mismatch with categories", cid, bid))
            if b.get("chart") == "pie":
                if len(series) != 1:
                    f.append(F("schema-valid", "error", "pie requires exactly one series", cid, bid))
                elif any(isinstance(v, (int, float)) and v < 0 for v in series[0].get("values") or []):
                    f.append(F("schema-valid", "error", "pie values must be non-negative", cid, bid))


def check_schema(ir):
    f = []
    if ir.get("schema") != "1.0":
        f.append(F("schema-valid", "error", f"schema must be \"1.0\", got {ir.get('schema')!r}"))
    meta = ir.get("meta") or {}
    if not meta.get("title"):
        f.append(F("schema-valid", "error", "meta.title missing"))
    if meta.get("archetype") not in CARD_LIMITS:
        f.append(F("schema-valid", "error", f"meta.archetype {meta.get('archetype')!r} unknown"))
    if meta.get("aspect") != "16:9":
        f.append(F("schema-valid", "error", "meta.aspect must be \"16:9\""))
    if not _cards(ir):
        f.append(F("schema-valid", "error", "deck has no cards"))
    ids = {}
    for c in _cards(ir):
        cid = c.get("id")
        if not cid:
            f.append(F("schema-valid", "error", "card missing id"))
        elif cid in ids:
            f.append(F("schema-valid", "error", f"duplicate id {cid!r}"))
        ids[cid] = True
        lay = c.get("layout")
        if lay not in LAYOUTS:
            f.append(F("schema-valid", "error", f"layout {lay!r} not in {LAYOUTS}", cid))
            continue
        if c.get("role") not in ROLES:
            f.append(F("schema-valid", "error", f"role {c.get('role')!r} invalid", cid))
        if c.get("subtitle") and lay not in ("title", "section"):
            f.append(F("schema-valid", "error", "subtitle only valid on title/section layouts", cid))
        blocks = c.get("blocks") or []
        one_media = (len(blocks) == 1 and blocks[0].get("type") in ("image", "kpi"))
        if not c.get("title") and not (lay == "hero" and one_media):
            f.append(F("schema-valid", "error", "card missing title", cid))
        for b, depth in _iter_blocks(blocks):
            bid = b.get("id")
            if bid:
                if bid in ids:
                    f.append(F("schema-valid", "error", f"duplicate id {bid!r}", cid))
                ids[bid] = True
            _check_block_schema(b, cid, depth, f)
    return f


# ---- content checks --------------------------------------------------------

def check_provenance(ir):
    f = []
    for c in _cards(ir):
        for b, _ in _iter_blocks(c.get("blocks")):
            if b.get("type") not in SOURCED:
                continue
            src = b.get("source")
            if src not in ("user", "derived", "placeholder"):
                f.append(F("data-provenance", "error",
                           f"{b['type']} block has no source (user|derived|placeholder)",
                           c.get("id"), b.get("id")))
            elif src == "placeholder":
                f.append(F("data-provenance", "unverified",
                           f"{b['type']} uses placeholder data", c.get("id"), b.get("id")))
    return f


def _is_claim(title):
    toks = re.findall(r"[a-z']+", str(title).lower())
    return any(t in AUX or t in VERBS or (t.endswith("ed") and len(t) > 4) for t in toks)


def check_title_claim(ir):
    return [F("title-is-claim", "error",
              f"title is a noun phrase, not a claim: {c.get('title')!r}", c.get("id"))
            for c in _content_cards(ir) if not _is_claim(c.get("title") or "")]


def check_answer_first(ir):
    if (ir.get("meta") or {}).get("archetype") not in ANSWER_FIRST:
        return []
    cards = _cards(ir)
    if any(c.get("role") == "recommendation" for c in cards[:3]):
        return []
    where = next((f"card {i + 1} ({c.get('id')})" for i, c in enumerate(cards)
                  if c.get("role") == "recommendation"), "nowhere")
    return [F("answer-first", "error",
              f"no role:recommendation in the first 3 cards (found: {where})")]


def check_card_count(ir):
    arch = (ir.get("meta") or {}).get("archetype")
    limit = CARD_LIMITS.get(arch)
    if not limit:
        return []
    n = sum(1 for c in _cards(ir) if c.get("role") != "appendix")
    if n > limit:
        return [F("card-count", "error", f"{n} cards exceeds {arch} limit of {limit} (appendix excluded)")]
    return []


def check_title_length(ir):
    f = []
    for c in _cards(ir):
        words = len(str(c.get("title") or "").split())
        if words > 14:
            f.append(F("title-length", "warn", f"title is {words} words (max 14)", c.get("id")))
    return f


def check_one_message(ir):
    f = []
    for c in _content_cards(ir):
        top = c.get("blocks") or []
        if len(top) > 4:
            f.append(F("one-message", "warn", f"{len(top)} blocks on one content card (max 4)", c.get("id")))
        charts = sum(1 for b, _ in _iter_blocks(top) if b.get("type") == "chart")
        if charts > 1:
            f.append(F("one-message", "warn", f"{charts} charts on one card (max 1)", c.get("id")))
    return f


def check_evidence(ir):
    f = []
    for c in _content_cards(ir):
        has_ev = any(b.get("type") != "text" for b, _ in _iter_blocks(c.get("blocks")))
        if not has_ev and not re.search(r"\d", str(c.get("title") or "")):
            f.append(F("evidence-present", "warn", "no non-text block and no figure in title", c.get("id")))
    return f


def check_text_budget(ir):
    f = []
    for c in _cards(ir):
        for b, _ in _iter_blocks(c.get("blocks")):
            t, bid, cid = b.get("type"), b.get("id"), c.get("id")
            if t == "text" and len(str(b.get("text") or "")) > 240:
                f.append(F("text-budget", "warn", f"text is {len(b['text'])} chars (max 240)", cid, bid))
            elif t == "bullets":
                items = b.get("items") or []
                if len(items) > 6:
                    f.append(F("text-budget", "warn", f"{len(items)} bullets (max 6)", cid, bid))
                for i, it in enumerate(items):
                    if len(str(it)) > 90:
                        f.append(F("text-budget", "warn", f"bullet {i + 1} is {len(str(it))} chars (max 90)", cid, bid))
            elif t == "callout" and len(str(b.get("text") or "")) > 140:
                f.append(F("text-budget", "warn", f"callout is {len(b['text'])} chars (max 140)", cid, bid))
    return f


def check_chart_fit(ir):
    f = []
    for c in _cards(ir):
        for b, _ in _iter_blocks(c.get("blocks")):
            if b.get("type") != "chart" or b.get("chart") not in CHARTS:
                continue
            cats = (b.get("data") or {}).get("categories") or []
            kind, cid, bid = b["chart"], c.get("id"), b.get("id")
            temporal = sum(1 for x in cats if _TEMPORAL.match(str(x).strip()))
            is_time = cats and temporal >= max(2, len(cats) / 2)
            if is_time and kind != "line":
                f.append(F("chart-fit", "warn", f"time-series categories suit line, not {kind}", cid, bid))
            elif not is_time and kind == "line":
                f.append(F("chart-fit", "warn", "categorical comparison suits bar/hbar, not line", cid, bid))
            if kind == "pie" and len(cats) > 5:
                f.append(F("chart-fit", "warn", f"pie with {len(cats)} slices; use bar", cid, bid))
    return f


def check_notes(ir):
    return [F("notes-present", "info", "content card has no speaker notes", c.get("id"))
            for c in _content_cards(ir) if not c.get("notes")]


# ---- theme-dependent checks ------------------------------------------------

def _lum(hexstr):
    r, g, b = (int(hexstr[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _ratio(fg, bg):
    l1, l2 = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def check_contrast(theme):
    c, f = theme["color"], []
    for fg, bg in (("text", "bg"), ("text", "surface"), ("muted", "bg"), ("muted", "surface")):
        r = _ratio(c[fg], c[bg])
        if r < 4.5:
            f.append(F("contrast", "error", f"{fg} on {bg} is {r:.2f}:1 (needs 4.5:1)"))
    return f


def check_min_type(theme):
    body = theme["type"]["scale"]["body"]
    if body < 16:
        return [F("min-type-size", "error", f"type.scale.body {body}pt is below 16pt")]
    return []


def _text_lines(s, size, width):
    cpl = max(1, int(width / (size * 0.52)))
    return max(1, math.ceil(len(str(s)) / cpl))


def _block_h(b, th, width, scale):
    sc, gap, lh = th["type"]["scale"], th["space"]["blockGap"], th["type"]["lineHeight"]
    body, cap = sc["body"] * scale, sc["caption"] * scale
    t = b.get("type")
    if t == "text":
        return _text_lines(b.get("text", ""), body, width) * body * lh
    if t == "bullets":
        items = b.get("items") or []
        return (sum(_text_lines(i, body, width - 24) * body * lh for i in items)
                + max(0, len(items) - 1) * gap / 2)
    if t == "kpi":
        return sc["title"] * lh + body * lh + (cap * lh if b.get("delta") else 0)
    if t == "chart":
        return 240 + ((cap * lh + gap / 2) if b.get("caption") else 0)
    if t == "table":
        return (len(b.get("rows") or []) + 1) * (body * lh + 2 * gap / 3)
    if t == "callout":
        return _text_lines(b.get("text", ""), body, width - 2 * gap) * body * lh + 2 * gap / 1.5
    if t == "quote":
        return (_text_lines(b.get("text", ""), body, width) * body * lh
                + ((cap * lh + gap / 2) if b.get("attribution") else 0))
    if t == "image":
        return 240
    if t == "divider":
        return 1
    if t == "columns":
        cols = b.get("children") or []
        cw = (width - (len(cols) - 1) * gap) / max(1, len(cols))
        return max((sum(_block_h(cb, th, cw, scale) for cb in col)
                    + max(0, len(col) - 1) * gap) for col in cols) if cols else 0
    return 0


def check_overflow(ir, theme):
    f = []
    pad, gap = theme["space"]["cardPad"], theme["space"]["blockGap"]
    lh, sc = theme["type"]["lineHeight"], theme["type"]["scale"]
    width, avail = 960 - 2 * pad, 540 - 2 * pad
    floor = max(0.85, 16.0 / sc["body"])  # ramp may never take body below 16pt
    for c in _content_cards(ir):
        blocks = c.get("blocks") or []
        h_title = (_text_lines(c.get("title", ""), sc["cardTitle"], width)
                   * sc["cardTitle"] * lh + gap)
        h = h_title + sum(_block_h(b, theme, width, floor) for b in blocks) \
            + max(0, len(blocks) - 1) * gap
        if h > avail:
            f.append(F("overflow", "error",
                       f"content ≈{h:.0f}pt exceeds {avail}pt even at the "
                       f"{(1 - floor) * 100:.0f}% ramp floor — split the card", c.get("id")))
    return f


# ---- CLI -------------------------------------------------------------------

def validate(ir, theme=None):
    findings = []
    findings += check_schema(ir)
    findings += check_provenance(ir)
    findings += check_title_claim(ir)
    findings += check_answer_first(ir)
    findings += check_card_count(ir)
    findings += check_title_length(ir)
    findings += check_one_message(ir)
    findings += check_evidence(ir)
    findings += check_text_budget(ir)
    findings += check_chart_fit(ir)
    findings += check_notes(ir)
    if theme is not None:
        findings += check_contrast(theme)
        findings += check_min_type(theme)
        findings += check_overflow(ir, theme)
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ir", required=True)
    ap.add_argument("--theme", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--passes", type=int, default=0,
                    help="revision-pass count recorded into findings.json")
    args = ap.parse_args(argv)

    ir = json.loads(Path(args.ir).read_text(encoding="utf-8"))
    theme = json.loads(Path(args.theme).read_text(encoding="utf-8")) if args.theme else None
    if theme is None:
        print("validate: no --theme given; contrast, min-type-size and overflow "
              "checks skipped", file=sys.stderr)

    findings = validate(ir, theme)
    out = {"deck": (ir.get("meta") or {}).get("title", ""),
           "passes": args.passes, "findings": findings}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    counts = {}
    for x in findings:
        counts[x["severity"]] = counts.get(x["severity"], 0) + 1
    summary = " · ".join(f"{counts[s]} {s}" for s in
                         ("unverified", "error", "warn", "concern", "info") if s in counts) or "clean"
    errors = counts.get("error", 0)
    print(f"validate: {summary} → {'FAIL' if errors else 'PASS'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
