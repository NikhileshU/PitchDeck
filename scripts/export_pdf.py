#!/usr/bin/env python3
"""export_pdf.py — print the rendered HTML deck to PDF via headless Chromium.

Page geometry comes from the @page rule render_html.py emits (1280x720 CSS px
= 960x540 PDF pt = 13.333x7.5 in). Any Chromium-family browser works; the
binary is autodetected from a fixed candidate list or passed via --browser.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/brave-browser",
    "/usr/bin/microsoft-edge",
]


def find_browser(override=None):
    if override:
        if Path(override).exists():
            return override
        raise FileNotFoundError(f"--browser not found: {override}")
    for c in CANDIDATES:
        if os.access(c, os.X_OK):
            return c
    return None


def export(html_path, out_path, browser, no_sandbox=False):
    html_uri = Path(html_path).resolve().as_uri()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)  # a stale PDF must never pass as this run's output
    cmd = [
        browser,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        # let images and webfonts settle before printing
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=10000",
        f"--print-to-pdf={out.resolve()}",
        html_uri,
    ]
    if no_sandbox:
        cmd.insert(1, "--no-sandbox")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(
            f"browser produced no PDF (exit {proc.returncode}):\n{proc.stderr[-2000:]}")
    raw = out.read_bytes()
    if raw[:5] != b"%PDF-":
        raise RuntimeError(f"{out} is not a PDF")
    # one card must equal one page — a mismatch means clipping or pagination fault
    cards = Path(html_path).read_text(encoding="utf-8").count('class="card ')
    pages = len(re.findall(rb"/Type\s*/Page[^s]", raw))
    if cards and pages != cards:
        raise RuntimeError(f"PDF has {pages} pages for {cards} cards — "
                           "content overflowed the page or pagination broke")
    if proc.returncode != 0:
        print(f"export_pdf: warning: browser exited {proc.returncode} after writing "
              f"the PDF:\n{proc.stderr[-1000:]}", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--html", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--browser", default=None,
                    help="path to a Chromium-family binary (autodetected if omitted)")
    ap.add_argument("--no-sandbox", action="store_true",
                    help="pass --no-sandbox to the browser (container runtimes)")
    args = ap.parse_args(argv)

    if not Path(args.html).exists():
        print(f"export_pdf: HTML not found: {args.html}", file=sys.stderr)
        return 1

    browser = find_browser(args.browser)
    if browser is None:
        print("export_pdf: no Chromium-family browser found. Install Chrome/"
              "Chromium/Brave/Edge or pass --browser <path>. PDF export is "
              "unavailable in this runtime.", file=sys.stderr)
        return 1

    try:
        export(args.html, args.out, browser, no_sandbox=args.no_sandbox)
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"export_pdf: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
