#!/usr/bin/env python3
"""render_html.py — render the deck.json IR to one self-contained HTML file.

Pure renderer: render(ir, theme, out_path, css="") -> None. No globals/env/network.
Charts are inline SVG, no JavaScript; the CLI embeds images as base64 data URIs.
Every pt dimension x 4/3 -> CSS px (960x540pt -> 1280x720px). Negative values are
supported on bar/hbar/line; pie requires exactly one non-negative series.
"""

import argparse, base64, html, json, math, mimetypes, sys
from pathlib import Path

def _px(pt):
    return round(pt * 4 / 3, 2)

def _e(s):
    return html.escape(str(s), quote=True)

def _fmt(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return f"{v:g}" if isinstance(v, float) else str(v)

def _ser(j, ncolors):
    return f"var(--color-series-{j % ncolors + 1})"

def _trunc(s, maxch):
    s = str(s)
    return s if len(s) <= maxch else s[: max(1, maxch - 1)] + "…"

def _cssv(v):
    s = str(v)
    if "<" in s or "{" in s or "}" in s:  # keep theme values inside the style block
        raise ValueError(f"unsafe character in theme value: {s!r}")
    return s

# ---- theme -> CSS custom properties ---------------------------------------

def _css_vars(theme):
    c, t, s = theme["color"], theme["type"], theme["space"]
    sc = t["scale"]
    v = [
        f"--color-bg: {_cssv(c['bg'])}", f"--color-surface: {_cssv(c['surface'])}",
        f"--color-text: {_cssv(c['text'])}", f"--color-muted: {_cssv(c['muted'])}",
        f"--color-accent: {_cssv(c['accent'])}",
    ]
    v += [f"--color-series-{i}: {_cssv(col)}" for i, col in enumerate(c["series"], 1)]
    v += [f"--color-tone-{k}: {_cssv(col)}" for k, col in c["tone"].items()]
    v += [
        f"--type-family: {_cssv(t['family'])}",
        f"--type-family-mono: {_cssv(t['familyMono'])}",
        f"--type-title: {_px(sc['title'])}px",
        f"--type-card-title: {_px(sc['cardTitle'])}px",
        f"--type-body: {_px(sc['body'])}px",
        f"--type-caption: {_px(sc['caption'])}px",
        f"--type-line-height: {_cssv(t['lineHeight'])}",
        f"--space-card-pad: {_px(s['cardPad'])}px",
        f"--space-block-gap: {_px(s['blockGap'])}px",
        f"--space-radius: {_px(s['radius'])}px",
        f"--card-w: {_px(960)}px", f"--card-h: {_px(540)}px",
        f"--stroke-hairline: {_px(1)}px", f"--stroke-accent: {_px(4.5)}px",
    ]
    return ":root { " + "; ".join(v) + "; }"

# ---- charts: inline SVG ----------------------------------------------------

def _legend(series, fs, nc):
    x, sw, parts = 0.0, fs * 0.75, []
    for j, s in enumerate(series):
        name = _trunc(s["name"], 18)
        parts.append(f'<rect x="{x:.1f}" y="{fs * 0.3:.1f}" width="{sw:.1f}" '
                     f'height="{sw:.1f}" rx="2" fill="{_ser(j, nc)}"/>')
        tx = x + sw + fs * 0.45
        parts.append(f'<text x="{tx:.1f}" y="{fs:.1f}" fill="var(--color-muted)">{_e(name)}</text>')
        x = tx + len(name) * fs * 0.62 + fs * 1.4
    return "".join(parts)

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
    if hi == lo:
        hi = 1.0
    # below-baseline labels need room above the category-label row
    top, bot = fs * (2.6 if m > 1 else 1.6), H - fs * (2.6 if lo < 0 else 1.5)

    def Y(v):
        return top + (hi - v) / (hi - lo) * (bot - top)

    y0, gw, gap = Y(0), W / n, 2.0
    bw = min((gw * 0.62 - gap * (m - 1)) / m, fs * 3.2)
    label_all = m * n <= 8
    out = [_legend(series, fs, nc)] if m > 1 else []
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
    if hi == lo:
        hi = 1.0
    top = fs * 1.8 if m > 1 else fs * 0.4
    lw = min(W * 0.3, max(len(str(c)) for c in cats) * fs * 0.62 + fs * 0.8)
    pw, ah = W - lw - fs * 3.2, H - top - fs * 0.4

    def X(v):
        return lw + (v - lo) / (hi - lo) * pw

    x0, rh = X(0), ah / n
    bh = min((rh * 0.62 - 2 * (m - 1)) / m, fs * 1.5)
    label_all = m * n <= 12
    maxch = max(2, int(lw / (fs * 0.62)) - 1)
    out = [_legend(series, fs, nc)] if m > 1 else []
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
    top = fs * (2.2 if m > 1 else 1.2)
    base = H - fs * 1.6
    left, right = fs * 1.5, fs * 3.2
    ph, pw = base - top, W - left - right

    def X(i):
        return left + (pw * i / (n - 1) if n > 1 else pw / 2)

    def Y(v):
        return base - ph * (float(v) - lo) / (hi - lo)

    out = [_legend(series, fs, nc)] if m > 1 else []
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
    return f'<img class="b-image b-image--{fit}" src="{_e(b["src"])}" alt="{_e(b["alt"])}">'

def _b_columns(b, theme):
    cols = "".join('<div class="b-col">' + "".join(_block(cb, theme) for cb in col) + "</div>"
                   for col in b["children"])
    return f'<div class="b-columns b-columns--{len(b["children"])}">{cols}</div>'

def _b_divider(b, theme):
    return '<hr class="b-divider">'

_BLOCKS = {"text": _b_text, "bullets": _b_bullets, "kpi": _b_kpi, "chart": _b_chart,
           "table": _b_table, "callout": _b_callout, "quote": _b_quote,
           "image": _b_image, "columns": _b_columns, "divider": _b_divider}

def _block(b, theme):
    t = b.get("type")
    if t not in _BLOCKS:
        raise ValueError(f"unknown block type {t!r} (block {b.get('id')!r})")
    try:
        return _BLOCKS[t](b, theme)
    except (KeyError, ValueError, ZeroDivisionError, IndexError, TypeError) as e:
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

def render(ir, theme, out_path, css=""):
    cards = "".join(_card(c, theme) for c in ir["cards"])
    page = f"@page {{ size: {_px(960)}px {_px(540)}px; margin: 0; }}"
    doc = ('<!doctype html><html><head><meta charset="utf-8">'
           f'<title>{_e(ir["meta"]["title"])}</title>'
           f'<style>{page}\n{_css_vars(theme)}\n{css}</style></head>'
           f'<body><main class="deck">{cards}</main></body></html>')
    Path(out_path).write_text(doc, encoding="utf-8")

# ---- CLI -------------------------------------------------------------------

def _embed_images(blocks, base):
    # CLI-side: rewrite image srcs to data URIs on the freshly parsed IR dict
    # (local to main; nothing re-serialises it)
    for b in blocks:
        if b.get("type") == "image" and not str(b.get("src", "")).startswith("data:"):
            p = Path(b["src"])
            if not p.is_absolute():
                p = base / p
            if not p.exists():
                raise FileNotFoundError(f"image not found for block {b.get('id')!r}: {p}")
            mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            b["src"] = f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
        elif b.get("type") == "columns":
            for col in b.get("children", []):
                _embed_images(col, base)

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ir", required=True)
    ap.add_argument("--theme", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    ir = json.loads(Path(args.ir).read_text(encoding="utf-8"))
    theme = json.loads(Path(args.theme).read_text(encoding="utf-8"))
    css_path = Path(args.theme).with_name("base.css")
    if not css_path.exists():
        print(f"render_html: base.css not found next to theme: {css_path}", file=sys.stderr)
        return 1

    try:
        for card in ir.get("cards", []):
            _embed_images(card.get("blocks") or [], Path(args.ir).resolve().parent)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        render(ir, theme, args.out, css=css_path.read_text(encoding="utf-8"))
    except (ValueError, FileNotFoundError) as e:
        print(f"render_html: {e}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
