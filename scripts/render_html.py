#!/usr/bin/env python3
"""render_html.py — render the deck.json IR to one self-contained HTML file.

Pure renderer: render(ir, theme, out_path, css="", ir_dir=None) -> None. No globals,
env or network — css text and ir_dir are passed in, never discovered. Inline-SVG
charts, no JS; images embed as data URIs when ir_dir is given. pt x 4/3 -> px.
"""

import argparse, base64, copy, html, json, math, mimetypes, sys
from pathlib import Path

def _px(pt): return round(pt * 4 / 3, 2)

def _e(s): return html.escape(str(s), quote=True)

def _fmt(v): return f"{v:g}" if isinstance(v, (int, float)) else str(v)

# colours repeat past the theme's 5 — validate.py warns on >5 series upstream
def _ser(j, ncolors): return f"var(--color-series-{j % ncolors + 1})"

def _trunc(s, maxch): return s if len(s := str(s)) <= maxch else s[: max(1, maxch - 1)] + "…"

def _css_color(v):
    # allowlist: #RRGGBB only (shared contract with validate.py and render_pptx.py)
    s = str(v).strip()
    if len(s) == 7 and s[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in s[1:]):
        return s
    raise ValueError(f"theme colours must be #RRGGBB hex, got {s!r}")

def _css_text(v):
    s = str(v).strip()
    if any(c in "<>{}();:/\\" for c in s):
        raise ValueError(f"unsafe character in theme value: {s!r}")
    return s

# ---- theme -> CSS custom properties ---------------------------------------

def _css_vars(theme):
    c, t, s = theme["color"], theme["type"], theme["space"]
    sc = t["scale"]
    v = [f"--color-{k}: {_css_color(c[k])}" for k in ("bg", "surface", "text", "muted", "accent")]
    v += [f"--color-series-{i}: {_css_color(col)}" for i, col in enumerate(c["series"], 1)]
    v += [f"--color-tone-{k}: {_css_color(col)}" for k, col in c["tone"].items()]
    v += [
        f"--type-family: {_css_text(t['family'])}",
        f"--type-family-mono: {_css_text(t['familyMono'])}",
        f"--type-title: {_px(sc['title'])}px",
        f"--type-card-title: {_px(sc['cardTitle'])}px",
        f"--type-body: {_px(sc['body'])}px",
        f"--type-caption: {_px(sc['caption'])}px",
        f"--type-line-height: {_css_text(t['lineHeight'])}",
        f"--space-card-pad: {_px(s['cardPad'])}px",
        f"--space-block-gap: {_px(s['blockGap'])}px",
        f"--space-radius: {_px(s['radius'])}px",
        f"--card-w: {_px(960)}px", f"--card-h: {_px(540)}px",
        f"--stroke-hairline: {_px(1)}px", f"--stroke-accent: {_px(4.5)}px",
    ]
    return ":root { " + "; ".join(v) + "; }"

# ---- charts: inline SVG ----------------------------------------------------

def _legend(series, fs, nc, W):
    # returns (svg, rows); rows INCLUDES the third '+N more' marker row on overflow
    # — callers use it to push the plot top down. Truncation is loud, never silent.
    x, y, sw, parts = 0.0, 0.0, fs * 0.75, []
    for j, s in enumerate(series):
        name = _trunc(s["name"], 18)
        w_item = sw + fs * 0.45 + len(name) * fs * 0.62 + fs * 1.4
        if x > 0 and x + w_item > W:
            x, y = 0.0, y + fs * 1.4
            if y > fs * 1.5:
                parts.append(f'<text x="0" y="{y + fs * 0.6:.1f}" '
                             f'fill="var(--color-muted)">+{len(series) - j} more</text>')
                break
        parts.append(f'<rect x="{x:.1f}" y="{y + fs * 0.3:.1f}" width="{sw:.1f}" '
                     f'height="{sw:.1f}" rx="2" fill="{_ser(j, nc)}"/>')
        parts.append(f'<text x="{x + sw + fs * 0.45:.1f}" y="{y + fs:.1f}" '
                     f'fill="var(--color-muted)">{_e(name)}</text>')
        x += w_item
    return "".join(parts), round(y / (fs * 1.4)) + 1

def _axis(x1, y1, x2, y2):
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            'stroke="var(--color-muted)" stroke-opacity="0.45"/>')

def _vbar_path(x, w, y0, y1, r):
    # vertical bar from baseline y0 to data end y1; rounded at the data end
    r = max(0, min(r, w / 2, abs(y0 - y1)))
    yr = y1 + (r if y1 < y0 else -r)
    return (f'M{x:.1f},{y0:.1f} L{x:.1f},{yr:.1f} Q{x:.1f},{y1:.1f} {x + r:.1f},{y1:.1f} '
            f'L{x + w - r:.1f},{y1:.1f} Q{x + w:.1f},{y1:.1f} {x + w:.1f},{yr:.1f} '
            f'L{x + w:.1f},{y0:.1f} Z')

def _hbar_path(x0, x1, y, h, r):
    # horizontal bar from baseline x0 to data end x1; rounded at the data end
    r = max(0, min(r, h / 2, abs(x1 - x0)))
    xr = x1 - (r if x1 > x0 else -r)
    return (f'M{x0:.1f},{y:.1f} L{xr:.1f},{y:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} '
            f'L{x1:.1f},{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {xr:.1f},{y + h:.1f} '
            f'L{x0:.1f},{y + h:.1f} Z')

def _chart_bar(cats, series, W, H, fs, nc):
    m, n = len(series), len(cats)
    vals = [float(v) for s in series for v in s["values"]]
    hi, lo = max(vals + [0.0]), min(vals + [0.0])
    if hi == lo: hi = 1.0
    leg, lrows = _legend(series, fs, nc, W) if m > 1 else ("", 0)
    # below-baseline labels need room above the category-label row
    top = fs * (2.6 if m > 1 else 1.6) + max(0, lrows - 1) * fs * 1.5
    bot = H - fs * (2.6 if lo < 0 else 1.5)
    Y = lambda v: top + (hi - v) / (hi - lo) * (bot - top)
    y0, gw, gap = Y(0), W / n, 2.0
    bw = min((gw * 0.62 - gap * (m - 1)) / m, fs * 3.2)
    label_all = m * n <= 8
    out = [leg] if leg else []
    for i, cat in enumerate(cats):
        x0 = i * gw + (gw - (bw * m + gap * (m - 1))) / 2
        out.append(f'<text x="{i * gw + gw / 2:.1f}" y="{H - fs * 0.35:.1f}" '
                   f'text-anchor="middle" fill="var(--color-muted)">{_e(_trunc(cat, 14))}</text>')
        for j, s in enumerate(series):
            v, x = float(s["values"][i]), x0 + j * (bw + gap)
            ye = Y(v)
            if v:
                out.append(f'<path d="{_vbar_path(x, bw, y0, ye, 4)}" fill="{_ser(j, nc)}"/>')
            if label_all:
                ly = ye - fs * 0.35 if v >= 0 else ye + fs * 0.95
                out.append(f'<text x="{x + bw / 2:.1f}" y="{ly:.1f}" '
                           f'text-anchor="middle" fill="var(--color-text)">{_fmt(v)}</text>')
    out.append(_axis(0, y0, W, y0))
    return "".join(out)

def _chart_hbar(cats, series, W, H, fs, nc):
    m, n = len(series), len(cats)
    vals = [float(v) for s in series for v in s["values"]]
    hi, lo = max(vals + [0.0]), min(vals + [0.0])
    if hi == lo: hi = 1.0
    leg, lrows = _legend(series, fs, nc, W) if m > 1 else ("", 0)
    top = (fs * 1.8 if m > 1 else fs * 0.4) + max(0, lrows - 1) * fs * 1.5
    lw = min(W * 0.3, max(len(str(c)) for c in cats) * fs * 0.62 + fs * 0.8)
    pw, ah = W - lw - fs * 3.2, H - top - fs * 0.4
    X = lambda v: lw + (v - lo) / (hi - lo) * pw
    x0, rh = X(0), ah / n
    bh = min((rh * 0.62 - 2 * (m - 1)) / m, fs * 1.5)
    label_all = m * n <= 12
    maxch = max(2, int(lw / (fs * 0.62)) - 1)
    out = [leg] if leg else []
    for i, cat in enumerate(cats):
        yc = top + i * rh + rh / 2
        y0 = yc - (bh * m + 2 * (m - 1)) / 2
        out.append(f'<text x="{lw - fs * 0.5:.1f}" y="{yc + fs * 0.35:.1f}" '
                   f'text-anchor="end" fill="var(--color-muted)">{_e(_trunc(cat, maxch))}</text>')
        for j, s in enumerate(series):
            v, y = float(s["values"][i]), y0 + j * (bh + 2)
            xe = X(v)
            if v:
                out.append(f'<path d="{_hbar_path(x0, xe, y, bh, 4)}" fill="{_ser(j, nc)}"/>')
            if label_all:
                pos = (f'x="{xe + fs * 0.35:.1f}"' if v >= 0
                       else f'x="{xe - fs * 0.35:.1f}" text-anchor="end"')
                out.append(f'<text {pos} y="{y + bh / 2 + fs * 0.35:.1f}" '
                           f'fill="var(--color-text)">{_fmt(v)}</text>')
    out.append(_axis(x0, top, x0, top + ah))
    return "".join(out)

def _chart_line(cats, series, W, H, fs, nc):
    m, n = len(series), len(cats)
    vals = [float(v) for s in series for v in s["values"]]
    hi, lo = max(vals), min(vals)
    if hi == lo:  # flat series: pad symmetrically around the value
        pad = max(1.0, abs(hi) * 0.1)
        hi, lo = hi + pad, lo - pad
    else:  # lines need no zero baseline, but never pad a non-negative domain below 0
        pad = (hi - lo) * 0.25
        lo = lo - pad if lo < 0 else max(0.0, lo - pad)
    leg, lrows = _legend(series, fs, nc, W) if m > 1 else ("", 0)
    top = fs * (2.2 if m > 1 else 1.2) + max(0, lrows - 1) * fs * 1.5
    base = H - fs * 1.6
    left, right = fs * 1.5, fs * 3.2
    ph, pw = base - top, W - left - right
    X = lambda i: left + (pw * i / (n - 1) if n > 1 else pw / 2)
    Y = lambda v: base - ph * (float(v) - lo) / (hi - lo)

    out = [leg] if leg else []
    out.append(_axis(left, base, left + pw, base))
    step = max(1, math.ceil(n / 8))
    for i in range(0, n, step):
        out.append(f'<text x="{X(i):.1f}" y="{H - fs * 0.35:.1f}" text-anchor="middle" '
                   f'fill="var(--color-muted)">{_e(_trunc(cats[i], 12))}</text>')
    for j, s in enumerate(series):
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(s["values"]))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{_ser(j, nc)}" '
                   'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        for i, v in enumerate(s["values"]):
            out.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="4" fill="{_ser(j, nc)}" '
                       'stroke="var(--color-bg)" stroke-width="2"/>')
        last = s["values"][-1]
        out.append(f'<text x="{X(n - 1) + fs * 0.5:.1f}" y="{Y(last) + fs * 0.35:.1f}" '
                   f'fill="var(--color-text)">{_fmt(last)}</text>')
    return "".join(out)

def _chart_pie(cats, series, W, H, fs, nc):
    if len(series) != 1:
        raise ValueError("pie requires exactly one series")
    vals = [float(v) for v in series[0]["values"]]
    if any(v < 0 for v in vals):
        raise ValueError("pie values must be non-negative")
    tot = sum(vals) or 1.0
    r = (H - fs * 1.6) / 2
    cx, cy = r + fs * 0.8, H / 2
    out, ang = [], -math.pi / 2
    for i, v in enumerate(vals):
        frac = v / tot
        a1 = ang + frac * 2 * math.pi
        if frac >= 0.9999:
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{_ser(i, nc)}"/>')
        elif frac > 0:
            x0, y0 = cx + r * math.cos(ang), cy + r * math.sin(ang)
            x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
            laf = 1 if frac > 0.5 else 0
            out.append(f'<path d="M{cx:.1f},{cy:.1f} L{x0:.1f},{y0:.1f} '
                       f'A{r:.1f},{r:.1f} 0 {laf} 1 {x1:.1f},{y1:.1f} Z" '
                       f'fill="{_ser(i, nc)}" stroke="var(--color-bg)" stroke-width="2"/>')
        ang = a1
    lx = cx + r + fs * 1.2
    ly0 = cy - (len(cats) - 1) / 2 * fs * 1.5
    for i, (cat, v) in enumerate(zip(cats, vals)):
        ly = ly0 + i * fs * 1.5
        out.append(f'<rect x="{lx:.1f}" y="{ly - fs * 0.62:.1f}" width="{fs * 0.75:.1f}" '
                   f'height="{fs * 0.75:.1f}" rx="2" fill="{_ser(i, nc)}"/>')
        out.append(f'<text x="{lx + fs * 1.2:.1f}" y="{ly:.1f}" fill="var(--color-muted)">'
                   f'{_e(_trunc(cat, 20))} — {_fmt(v)} ({round(100 * v / tot)}%)</text>')
    return "".join(out)

_CHARTS = {"bar": _chart_bar, "hbar": _chart_hbar, "line": _chart_line, "pie": _chart_pie}

def _chart_svg(b, theme):
    kind = b.get("chart")
    if kind not in _CHARTS:
        raise ValueError(f"unknown chart kind {kind!r}")
    cats = [str(c) for c in b["data"]["categories"]]
    series = b["data"]["series"]
    if not cats or not series:
        raise ValueError("chart needs at least one category and one series")
    for s in series:
        if len(s["values"]) != len(cats):
            raise ValueError(f"series {s.get('name')!r} has {len(s['values'])} values "
                             f"for {len(cats)} categories")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   for v in s["values"]):
            raise ValueError(f"series {s.get('name')!r} has non-numeric values")
    W, H = _px(960 - 2 * theme["space"]["cardPad"]), _px(240)
    fs = _px(theme["type"]["scale"]["caption"])
    body = _CHARTS[kind](cats, series, W, H, fs, len(theme["color"]["series"]))
    return (f'<svg viewBox="0 0 {W} {H}" role="img" font-size="{fs}" '
            f'aria-label="{_e(b.get("caption") or kind + " chart")}">{body}</svg>')

# ---- blocks (exactly 10) ---------------------------------------------------

def _b_text(b, theme):
    cls = "b-text b-text--emphasis" if b.get("emphasis") else "b-text"
    return f'<p class="{cls}">{_e(b["text"])}</p>'

def _b_bullets(b, theme):
    return '<ul class="b-bullets">' + "".join(f"<li>{_e(i)}</li>" for i in b["items"]) + "</ul>"

def _b_kpi(b, theme):
    delta = f'<span class="b-kpi-delta">{_e(b["delta"])}</span>' if b.get("delta") else ""
    return (f'<div class="b-kpi"><span class="b-kpi-value">{_e(b["value"])}</span>'
            f'<span class="b-kpi-label">{_e(b["label"])}</span>{delta}</div>')

def _b_chart(b, theme):
    cap = f'<figcaption>{_e(b["caption"])}</figcaption>' if b.get("caption") else ""
    return f'<figure class="b-chart">{_chart_svg(b, theme)}{cap}</figure>'

def _b_table(b, theme):
    head = "".join(f"<th>{_e(h)}</th>" for h in b["headers"])
    rows = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>"
                   for r in b["rows"])
    return (f'<table class="b-table"><thead><tr>{head}</tr></thead>'
            f'<tbody>{rows}</tbody></table>')

def _b_callout(b, theme):
    if b.get("tone") not in ("info", "warn", "good"):
        raise ValueError(f"unknown callout tone {b.get('tone')!r}")
    return f'<div class="b-callout b-callout--{b["tone"]}">{_e(b["text"])}</div>'

def _b_quote(b, theme):
    cite = f'<cite>{_e(b["attribution"])}</cite>' if b.get("attribution") else ""
    return f'<blockquote class="b-quote">{_e(b["text"])}{cite}</blockquote>'

def _b_image(b, theme):
    fit = b.get("fit", "contain")
    if fit not in ("cover", "contain"):
        raise ValueError(f"unknown image fit {fit!r}")
    if not str(b["src"]).startswith("data:"):  # self-contained or not at all — pass ir_dir
        raise ValueError(f"image src is not embedded: {b['src']!r} — call render() with ir_dir")
    return f'<img class="b-image b-image--{fit}" src="{_e(b["src"])}" alt="{_e(b["alt"])}">'

def _b_columns(b, theme):
    if any(cb.get("type") == "columns" for col in b["children"] for cb in col):
        raise ValueError("columns may not nest inside columns")
    cols = "".join('<div class="b-col">' + "".join(_block(cb, theme) for cb in col) + "</div>"
                   for col in b["children"])
    return f'<div class="b-columns b-columns--{len(b["children"])}">{cols}</div>'

def _b_divider(b, theme): return '<hr class="b-divider">'

_BLOCKS = {"text": _b_text, "bullets": _b_bullets, "kpi": _b_kpi, "chart": _b_chart,
           "table": _b_table, "callout": _b_callout, "quote": _b_quote,
           "image": _b_image, "columns": _b_columns, "divider": _b_divider}

def _block(b, theme):
    t = b.get("type")
    if t not in _BLOCKS:
        raise ValueError(f"unknown block type {t!r} (block {b.get('id')!r})")
    try:
        return _BLOCKS[t](b, theme)
    except (KeyError, ValueError) as e:  # IR faults; renderer bugs propagate raw
        raise ValueError(f"block {b.get('id')!r} ({t}): {e}") from e

# ---- cards and document ----------------------------------------------------

def _card(card, theme):
    lay = card["layout"]
    bits = []
    if card.get("title"):
        bits.append(f'<h2 class="card-title">{_e(card["title"])}</h2>')
    if card.get("subtitle") and lay in ("title", "section"):
        bits.append(f'<p class="card-subtitle">{_e(card["subtitle"])}</p>')
    blocks = card.get("blocks") or []
    try:
        if lay == "content":
            bits.append('<div class="card-blocks">'
                        + "".join(_block(b, theme) for b in blocks) + "</div>")
        else:
            # hero image is absolutely positioned; render it first so the title sits above
            bits = [_block(b, theme) for b in blocks] + bits
    except ValueError as e:
        raise ValueError(f"card {card.get('id')!r}: {e}") from e
    return (f'<section class="card card--{_e(lay)}" id="{_e(card["id"])}">'
            + "".join(bits) + "</section>")

def _embed_images(blocks, base, cache):
    # block-types.md: src resolves relative to deck.json, as it does for PPTX.
    for b in blocks:
        if b.get("type") == "image" and not str(b.get("src", "")).startswith("data:"):
            p = Path(b["src"])
            p = p if p.is_absolute() else base / p
            key = str(p.resolve())
            if key not in cache:
                if not p.exists():
                    raise FileNotFoundError(f"image not found for block {b.get('id')!r}: {p}")
                data = p.read_bytes()
                if len(data) > 2_000_000:
                    print(f"render_html: warning: {p.name} is {len(data)/1e6:.1f}MB embedded", file=sys.stderr)
                mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                cache[key] = f"data:{mime};base64,{base64.b64encode(data).decode()}"
            b["src"] = cache[key]
        elif b.get("type") == "columns":
            for col in b.get("children", []):
                _embed_images(col, base, cache)

def render(ir, theme, out_path, css=None, ir_dir=None):
    """css text and ir_dir are passed in, never discovered (invariant 3); given ir_dir, render() embeds images itself.

    css is the *text* of base.css. Omitting it raises: one card per page, and the
    card box itself, are properties of that stylesheet, so an unstyled deck is not
    a plainer deck — it is a broken one that paginates by content flow (R13-M2).
    Pass css="" to render deliberately unstyled, which is what markup-level tests want.
    """
    if css is None:
        raise ValueError("render_html needs the text of base.css in css= "
                         "(pass css='' to render deliberately unstyled)")
    if ir_dir is not None:
        cache, ir = {}, copy.deepcopy(ir)  # embedding must not mutate the caller's IR
        for card in ir["cards"]:
            _embed_images(card.get("blocks") or [], Path(ir_dir).resolve(), cache)
    cards = "".join(_card(c, theme) for c in ir["cards"])
    page = f"@page {{ size: {_px(960)}px {_px(540)}px; margin: 0; }}"
    doc = ('<!doctype html><html><head><meta charset="utf-8">'
           f'<title>{_e(ir["meta"]["title"])}</title>'
           f'<style>{page}\n{_css_vars(theme)}\n{css}</style></head>'
           f'<body><main class="deck">{cards}</main></body></html>')
    Path(out_path).write_text(doc, encoding="utf-8")

# ---- CLI -------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for a in ("--ir", "--theme", "--out"): ap.add_argument(a, required=True)
    args = ap.parse_args(argv)

    # One guard over the whole run — a CLI fails with a message, never a traceback
    # (R13-L5, widened). OSError covers an unreadable --ir and an unwritable --out;
    # ValueError covers malformed JSON and this module's own raises; KeyError and
    # TypeError cover valid JSON that is not a deck, which reaches past the parse
    # into the first field access.
    try:
        ir = json.loads(Path(args.ir).read_text(encoding="utf-8"))
        theme = json.loads(Path(args.theme).read_text(encoding="utf-8"))
        css_path = Path(args.theme).with_name("base.css")
        if not css_path.exists():
            print(f"render_html: base.css not found next to theme: {css_path}", file=sys.stderr)
            return 1
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        render(ir, theme, args.out, css=css_path.read_text(encoding="utf-8"),
               ir_dir=Path(args.ir).resolve().parent)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"render_html: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
