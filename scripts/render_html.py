#!/usr/bin/env python3
"""render_html.py — render the deck.json IR to one self-contained HTML file.

Pure renderer: render(ir, theme, out_path, css="") -> None. No globals, no env
reads, no network. Charts are inline SVG generated here — no JavaScript.
Every pt dimension is multiplied by 4/3 to become CSS px (960x540pt -> 1280x720px).
"""

import argparse
import html
import json
import math
import sys
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


# ---- theme -> CSS custom properties ---------------------------------------

def _css_vars(theme):
    c, t, s = theme["color"], theme["type"], theme["space"]
    sc = t["scale"]
    v = [
        f"--color-bg: {c['bg']}", f"--color-surface: {c['surface']}",
        f"--color-text: {c['text']}", f"--color-muted: {c['muted']}",
        f"--color-accent: {c['accent']}",
    ]
    v += [f"--color-series-{i}: {col}" for i, col in enumerate(c["series"], 1)]
    v += [f"--color-tone-{k}: {col}" for k, col in c["tone"].items()]
    v += [
        f"--type-family: {t['family']}", f"--type-family-mono: {t['familyMono']}",
        f"--type-title: {_px(sc['title'])}px",
        f"--type-card-title: {_px(sc['cardTitle'])}px",
        f"--type-body: {_px(sc['body'])}px",
        f"--type-caption: {_px(sc['caption'])}px",
        f"--type-line-height: {t['lineHeight']}",
        f"--space-card-pad: {_px(s['cardPad'])}px",
        f"--space-block-gap: {_px(s['blockGap'])}px",
        f"--space-radius: {_px(s['radius'])}px",
        f"--card-w: {_px(960)}px", f"--card-h: {_px(540)}px",
        f"--stroke-hairline: {_px(1)}px", f"--stroke-accent: {_px(4.5)}px",
    ]
    return ":root { " + "; ".join(v) + "; }"


# ---- charts: inline SVG ----------------------------------------------------

def _vmax(series):
    return max((float(v) for s in series for v in s["values"]), default=1) or 1


def _legend(series, fs, nc):
    x, sw, parts = 0.0, fs * 0.75, []
    for j, s in enumerate(series):
        name = str(s["name"])
        parts.append(f'<rect x="{x:.1f}" y="{fs * 0.3:.1f}" width="{sw:.1f}" '
                     f'height="{sw:.1f}" rx="2" fill="{_ser(j, nc)}"/>')
        tx = x + sw + fs * 0.45
        parts.append(f'<text x="{tx:.1f}" y="{fs:.1f}" fill="var(--color-muted)">{_e(name)}</text>')
        x = tx + len(name) * fs * 0.62 + fs * 1.4
    return "".join(parts)


def _axis(x1, y1, x2, y2):
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            'stroke="var(--color-muted)" stroke-opacity="0.45"/>')


def _bar_path(x, y, w, base, r):
    r = max(0, min(r, w / 2, base - y))
    return (f'M{x:.1f},{base:.1f} L{x:.1f},{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} '
            f'L{x + w - r:.1f},{y:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} '
            f'L{x + w:.1f},{base:.1f} Z')


def _hbar_path(x0, y, w, h, r):
    r, x1 = max(0, min(4, h / 2, w)), x0 + w
    return (f'M{x0:.1f},{y:.1f} L{x1 - r:.1f},{y:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} '
            f'L{x1:.1f},{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 - r:.1f},{y + h:.1f} '
            f'L{x0:.1f},{y + h:.1f} Z')


def _chart_bar(cats, series, W, H, fs, nc):
    m, n, vmax = len(series), len(cats), _vmax(series)
    top = fs * (2.6 if m > 1 else 1.6)
    base = H - fs * 1.5
    ph, gw, gap = base - top, W / n, 2.0
    bw = min((gw * 0.62 - gap * (m - 1)) / m, fs * 3.2)
    label_all = m * n <= 8
    out = [_legend(series, fs, nc)] if m > 1 else []
    for i, cat in enumerate(cats):
        x0 = i * gw + (gw - (bw * m + gap * (m - 1))) / 2
        out.append(f'<text x="{i * gw + gw / 2:.1f}" y="{H - fs * 0.35:.1f}" '
                   f'text-anchor="middle" fill="var(--color-muted)">{_e(cat)}</text>')
        for j, s in enumerate(series):
            v = float(s["values"][i])
            y = base - (ph * v / vmax if v > 0 else 0)
            x = x0 + j * (bw + gap)
            if v > 0:
                out.append(f'<path d="{_bar_path(x, y, bw, base, 4)}" fill="{_ser(j, nc)}"/>')
            if label_all:
                out.append(f'<text x="{x + bw / 2:.1f}" y="{y - fs * 0.35:.1f}" '
                           f'text-anchor="middle" fill="var(--color-text)">{_fmt(v)}</text>')
    out.append(_axis(0, base, W, base))
    return "".join(out)


def _chart_hbar(cats, series, W, H, fs, nc):
    m, n, vmax = len(series), len(cats), _vmax(series)
    top = fs * 1.8 if m > 1 else fs * 0.4
    lw = min(W * 0.3, max(len(str(c)) for c in cats) * fs * 0.62 + fs * 0.8)
    pw, ah = W - lw - fs * 3.2, H - top - fs * 0.4
    rh = ah / n
    bh = min((rh * 0.62 - 2 * (m - 1)) / m, fs * 1.5)
    out = [_legend(series, fs, nc)] if m > 1 else []
    for i, cat in enumerate(cats):
        yc = top + i * rh + rh / 2
        y0 = yc - (bh * m + 2 * (m - 1)) / 2
        out.append(f'<text x="{lw - fs * 0.5:.1f}" y="{yc + fs * 0.35:.1f}" '
                   f'text-anchor="end" fill="var(--color-muted)">{_e(cat)}</text>')
        for j, s in enumerate(series):
            v = float(s["values"][i])
            w = pw * v / vmax if v > 0 else 0
            y = y0 + j * (bh + 2)
            if v > 0:
                out.append(f'<path d="{_hbar_path(lw, y, w, bh, 4)}" fill="{_ser(j, nc)}"/>')
            out.append(f'<text x="{lw + w + fs * 0.35:.1f}" y="{y + bh / 2 + fs * 0.35:.1f}" '
                       f'fill="var(--color-text)">{_fmt(v)}</text>')
    out.append(_axis(lw, top, lw, top + ah))
    return "".join(out)


def _chart_line(cats, series, W, H, fs, nc):
    m, n = len(series), len(cats)
    vals = [float(v) for s in series for v in s["values"]]
    hi, lo = max(vals, default=1), min(vals, default=0)
    lo = max(0.0, lo - (hi - lo) * 0.25) if hi > lo else lo * 0.9  # lines need no zero baseline
    hi = hi if hi > lo else lo + 1
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
                   f'fill="var(--color-muted)">{_e(cats[i])}</text>')
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
    vals = [float(v) for v in series[0]["values"]]
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
                   f'{_e(cat)} — {_fmt(v)} ({round(100 * v / tot)}%)</text>')
    return "".join(out)


_CHARTS = {"bar": _chart_bar, "hbar": _chart_hbar, "line": _chart_line, "pie": _chart_pie}


def _chart_svg(b, theme):
    cats = [str(c) for c in b["data"]["categories"]]
    series = b["data"]["series"]
    W, H = _px(960 - 2 * theme["space"]["cardPad"]), _px(240)
    fs = _px(theme["type"]["scale"]["caption"])
    nc = len(theme["color"]["series"])
    body = _CHARTS[b["chart"]](cats, series, W, H, fs, nc)
    return (f'<svg viewBox="0 0 {W} {H}" role="img" font-size="{fs}" '
            f'aria-label="{_e(b.get("caption") or b["chart"] + " chart")}">{body}</svg>')


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
    return f'<div class="b-callout b-callout--{_e(b["tone"])}">{_e(b["text"])}</div>'


def _b_quote(b, theme):
    cite = f'<cite>{_e(b["attribution"])}</cite>' if b.get("attribution") else ""
    return f'<blockquote class="b-quote">{_e(b["text"])}{cite}</blockquote>'


def _b_image(b, theme):
    fit = b.get("fit", "contain")
    return f'<img class="b-image b-image--{_e(fit)}" src="{_e(b["src"])}" alt="{_e(b["alt"])}">'


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
    return _BLOCKS[b["type"]](b, theme)


# ---- cards and document ----------------------------------------------------

def _card(card, theme):
    lay = card["layout"]
    bits = []
    if card.get("title"):
        bits.append(f'<h2 class="card-title">{_e(card["title"])}</h2>')
    if card.get("subtitle") and lay in ("title", "section"):
        bits.append(f'<p class="card-subtitle">{_e(card["subtitle"])}</p>')
    blocks = card.get("blocks") or []
    if lay == "content":
        bits.append('<div class="card-blocks">'
                    + "".join(_block(b, theme) for b in blocks) + "</div>")
    else:
        # hero image is absolutely positioned; render it first so the title sits above
        bits = [_block(b, theme) for b in blocks] + bits
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

def _resolve_images(blocks, base):
    for b in blocks:
        if b.get("type") == "image" and not Path(b["src"]).is_absolute():
            b["src"] = str((base / b["src"]).resolve())
        elif b.get("type") == "columns":
            for col in b.get("children", []):
                _resolve_images(col, base)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ir", required=True)
    ap.add_argument("--theme", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    ir = json.loads(Path(args.ir).read_text(encoding="utf-8"))
    theme = json.loads(Path(args.theme).read_text(encoding="utf-8"))
    css_path = Path(args.theme).with_name("base.css")
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

    for card in ir.get("cards", []):
        _resolve_images(card.get("blocks") or [], Path(args.ir).resolve().parent)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    render(ir, theme, args.out, css=css)
    return 0


if __name__ == "__main__":
    sys.exit(main())
