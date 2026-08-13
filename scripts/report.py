#!/usr/bin/env python3
"""report.py — assemble the quality report from findings.json + judge.json + the IR.

Deterministic, no LLM. Prints the inline summary (spec §13 shape) to stdout and
writes report.md with the six sections in fixed order — unverified inputs first,
always. judge.json is LLM output and is validated against the §11 contract: the
five dimensions must each carry a numeric score in 1–5; violations surface as
`judge-contract` findings in section 2 and fail gate 3. Unknown dimensions are
dropped from the mean and listed separately. Reporting is not a gate: exit 1
only when an input cannot be read.
"""

import argparse
import datetime
import json
import re
import sys
import zipfile
from pathlib import Path

DIMENSIONS = ("storyline", "verticalLogic", "archetypeFit", "audienceFit", "density")
CONCERN_CAP = 5
PLURAL = {"chart": "charts", "table": "tables", "kpi": "KPIs"}


# ---- xlsx ------------------------------------------------------------------
# An .xlsx is a zip of XML, so this needs no third-party library — which matters:
# requirements.txt ships two packages and both belong to the PPTX path only, and
# a spreadsheet export is not a reason to put openpyxl on the HTML/report path.

_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _xe(v):
    s = _ILLEGAL.sub("", str(v))
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _colname(i):
    s = ""
    while i >= 0:
        s, i = chr(ord("A") + i % 26) + s, i // 26 - 1
    return s


def _cell(ref, v):
    if isinstance(v, bool) or v is None:
        v = {True: "yes", False: "no", None: ""}[v]
    if isinstance(v, (int, float)):
        return f'<c r="{ref}"><v>{v:g}</v></c>'
    return (f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
            f'{_xe(v)}</t></is></c>')


def _sheet_xml(rows):
    """Row 0 is the header: frozen and filterable, because these workbooks exist
    to be sorted and sliced rather than read top to bottom."""
    width = max((len(r) for r in rows), default=1)
    body = []
    for y, row in enumerate(rows, start=1):
        cells = "".join(_cell(f"{_colname(x)}{y}", v) for x, v in enumerate(row))
        body.append(f'<row r="{y}">{cells}</row>')
    dim = f"A1:{_colname(width - 1)}{max(1, len(rows))}"
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<dimension ref="{dim}"/>'
            '<sheetViews><sheetView workbookViewId="0">'
            '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            '</sheetView></sheetViews>'
            f'<sheetData>{"".join(body)}</sheetData>'
            f'<autoFilter ref="A1:{_colname(width - 1)}1"/></worksheet>')


def write_xlsx(path, sheets):
    """sheets: [(name, [[cell, ...], ...]), ...] — row 0 of each is the header."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    names = [_ILLEGAL.sub("", n)[:31] or f"Sheet{i}" for i, (n, _) in enumerate(sheets, 1)]
    ct = "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType='
                 '"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                 for i in range(1, len(sheets) + 1))
    rels = "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/'
                   f'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                   for i in range(1, len(sheets) + 1))
    tabs = "".join(f'<sheet name="{_xe(n)}" sheetId="{i}" r:id="rId{i}"/>'
                   for i, n in enumerate(names, 1))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
                   'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + ct + "</Types>")
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
                   '2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   f'<sheets>{tabs}</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                   f'relationships">{rels}</Relationships>')
        for i, (_, rows) in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(rows))
    return path


def _load(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"report: cannot load {what}: {e}", file=sys.stderr)
        raise SystemExit(1)


def _ref(f):
    return "/".join(x for x in (f.get("card"), f.get("block")) if x) or "deck"


def _sev(findings, *sevs):
    return [f for f in findings if f.get("severity") in sevs]


def _mdcell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def _judge_contract(judge):
    """§11 contract violations — each fails gate 3 and lands in section 2."""
    violations = []
    sc = judge.get("scores") or {}
    for d in DIMENSIONS:
        e = sc.get(d)
        s = e.get("score") if isinstance(e, dict) else None
        if isinstance(s, bool) or not isinstance(s, (int, float)):
            violations.append(f"dimension {d!r} is missing or unscored")
        elif not 1 <= s <= 5:
            violations.append(f"dimension {d!r} score {s!r} is outside the 1–5 scale")
    if len(judge.get("concerns") or []) > CONCERN_CAP:
        violations.append(f"{len(judge['concerns'])} concerns exceed the contract cap "
                          f"of {CONCERN_CAP}")
    return violations


def _scores(judge):
    """(valid-known-dimension rows, unknown-dimension rows) — unknown never gates."""
    sc = judge.get("scores") or {}
    valid, unknown = [], []
    for d, v in sc.items():
        s = v.get("score") if isinstance(v, dict) else None
        row = (d, s, v.get("note", "") if isinstance(v, dict) else "")
        if d in DIMENSIONS:
            if isinstance(s, (int, float)) and not isinstance(s, bool) and 1 <= s <= 5:
                valid.append(row)
        else:
            unknown.append(row)
    valid.sort(key=lambda r: DIMENSIONS.index(r[0]))
    return valid, unknown


def _block_types(ir):
    types = {}

    def walk(blocks):
        for b in blocks or []:
            if isinstance(b, dict):
                types[b.get("id")] = b.get("type")
                if b.get("type") == "columns":
                    for col in b.get("children") or []:
                        walk(col)

    for c in ir.get("cards") or []:
        walk(c.get("blocks"))
    return types


def inline_summary(ir, fjson, judge):
    meta = ir.get("meta") or {}
    findings = fjson.get("findings") or []
    passes = fjson.get("passes", 0)
    errs, warns = _sev(findings, "error"), _sev(findings, "warn")
    unv = _sev(findings, "unverified")
    schema_ok = not any(f.get("check") == "schema-valid" for f in errs)
    lines = [
        f"{meta.get('title', fjson.get('deck', '?'))} · {meta.get('archetype', '?')} · "
        f"{meta.get('theme', '?')} · {len(ir.get('cards') or [])} cards · "
        f"{passes} revision pass{'es' if passes != 1 else ''}",
        "",
        f"Gate 1  schema         {'✓' if schema_ok else '✗'}",
        f"Gate 2  deterministic  {'✓' if not errs else '✗'}  "
        f"{len(errs)} errors · {len(warns)} warnings",
    ]
    violations = _judge_contract(judge)
    valid, _ = _scores(judge)
    if violations:
        lines.append("Gate 3  judged         ✗ invalid judge output — see report.md")
    elif valid:
        mean = sum(s for _, s, _ in valid) / len(valid)
        low = min(valid, key=lambda x: x[1])
        lines.append(f"Gate 3  judged         {mean:.1f} / 5   (lowest: {low[0]} {low[1]:g})")
    else:
        lines.append("Gate 3  judged         — (no scores in judge.json)")
    extras = []
    if unv:
        types = _block_types(ir)
        kinds = sorted({PLURAL.get(types.get(f.get("block")), "values") for f in unv})
        cards = sorted({f["card"] for f in unv if f.get("card")})
        where = f" on {', '.join(cards)}" if cards else ""
        extras.append(f"⚠  {len(unv)} unverified value{'s' if len(unv) != 1 else ''} — "
                      f"{', '.join(kinds)}{where} use placeholder data")
    n_conc = len(judge.get("concerns") or []) + len(_sev(findings, "concern"))
    if n_conc:
        extras.append(f"!  {n_conc} concern{'s' if n_conc != 1 else ''} raised — see report.md")
    return "\n".join(lines + ([""] + extras if extras else []))


def _finding_line(f):
    state = " *(resolved by revision)*" if f.get("resolved") else ""
    return f"- `{_ref(f)}` [{f.get('check', '?')}] — {f.get('message', '')}{state}"


def report_md(ir, fjson, judge):
    meta = ir.get("meta") or {}
    findings = fjson.get("findings") or []
    passes = fjson.get("passes", 0)
    errs, warns = _sev(findings, "error"), _sev(findings, "warn")
    unv, infos = _sev(findings, "unverified"), _sev(findings, "info")
    violations = _judge_contract(judge)
    valid, unknown = _scores(judge)
    out = [f"# {meta.get('title', fjson.get('deck', 'Deck'))} — quality report", ""]
    out.append(f"{meta.get('archetype', '?')} · {meta.get('theme', '?')} · "
               f"{len(ir.get('cards') or [])} cards · {passes} revision "
               f"pass{'es' if passes != 1 else ''}")
    out.append("")

    out += ["## 1 · Unverified inputs", ""]
    if unv:
        out.append("These values are placeholders. Confirm or replace them before presenting.")
        out.append("")
        out += [_finding_line(f) for f in unv]
    else:
        out.append("None — every chart, table and KPI is user-supplied or derived.")
    out.append("")

    out += ["## 2 · Errors", ""]
    vlines = [f"- `judge` [judge-contract] — {v}" for v in violations]
    unresolved = len([f for f in errs if not f.get("resolved")]) + len(vlines)
    out += ([_finding_line(f) for f in errs] + vlines) or ["None."]
    if unresolved:
        out += ["", f"**{unresolved} unresolved — this deck must not ship.**"]
    out.append("")

    out += ["## 3 · Warnings", ""]
    out += [_finding_line(f) for f in warns] or ["None."]
    if infos:
        out += ["", "Also noted (info):", ""] + [_finding_line(f) for f in infos]
    out.append("")

    out += ["## 4 · Concerns", ""]
    concerns = [{"card": c.get("card"), "message": c.get("message", "")}
                for c in (judge.get("concerns") or [])]
    concerns += [{"card": f.get("card"), "message": f.get("message", "")}
                 for f in _sev(findings, "concern")]
    if concerns:
        shown = concerns[:CONCERN_CAP]
        out += [f"- `{c['card'] or 'deck'}` — {c['message']}" for c in shown]
        if len(concerns) > CONCERN_CAP:
            out.append(f"- … showing {CONCERN_CAP} of {len(concerns)} "
                       "(contract cap exceeded — see section 2)")
        out += ["", "Concerns are editorial judgment calls. They are never auto-fixed."]
    else:
        out.append("None raised.")
    out.append("")

    out += ["## 5 · Tier-2 scorecard", ""]
    if valid or unknown:
        out += ["| Dimension | Score | Note |", "|---|---|---|"]
        out += [f"| {d} | {s:g} | {_mdcell(n)} |" for d, s, n in valid]
        if violations:
            out += ["", "**Gate 3 not computable — judge output violates the §11 "
                        "contract (see section 2).**"]
        else:
            mean = sum(s for _, s, _ in valid) / len(valid)
            low = min(s for _, s, _ in valid)
            verdict = "PASS" if mean >= 3.5 and low >= 3 else "FAIL"
            out += ["", f"Mean **{mean:.1f} / 5**, lowest **{low:g}** — "
                        f"gate (mean ≥ 3.5, no dimension < 3): **{verdict}**"]
        if unknown:
            out += ["", "Ignored (not in the §11 contract): "
                    + ", ".join(f"{d} ({s!r})" for d, s, _ in unknown)]
    else:
        out.append("No Tier-2 scores available.")
    out.append("")

    out += ["## 6 · Revision log", ""]
    resolved = [f for f in findings if f.get("resolved")]
    if passes == 0 and not resolved:
        out.append("No revision passes were needed.")
    else:
        out.append(f"{passes} revision pass{'es' if passes != 1 else ''}.")
        out += ([""] + [_finding_line(f) for f in resolved]) if resolved \
            else ["", "No findings recorded as resolved."]
    out.append("")
    return "\n".join(out)


def workbook(ir, fjson, judge):
    """The same report as report.md, shaped for a spreadsheet: one row per thing
    rather than prose, so runs can be compared and sliced. A live run has no
    baseline to diff against — `expected` columns belong to the golden set, which
    is where run_golden.py builds its own workbook."""
    meta = ir.get("meta") or {}
    findings = fjson.get("findings") or []
    valid, unknown = _scores(judge)
    violations = _judge_contract(judge)
    errs = [f for f in _sev(findings, "error") if not f.get("resolved")]
    mean = sum(s for _, s, _ in valid) / len(valid) if valid else None
    low = min((s for _, s, _ in valid), default=None)

    summary = [["field", "value"],
               ["generated", datetime.datetime.now().isoformat(timespec="seconds")],
               ["deck", meta.get("title", fjson.get("deck", ""))],
               ["archetype", meta.get("archetype", "")],
               ["theme", meta.get("theme", "")],
               ["cards", len(ir.get("cards") or [])],
               ["revision passes", fjson.get("passes", 0)]]
    for sev in ("unverified", "error", "warn", "concern", "info"):
        summary.append([f"findings: {sev}", len(_sev(findings, sev))])
    summary += [["gate 1 schema", "pass" if not any(
                    f.get("check") == "schema-valid" for f in _sev(findings, "error")) else "fail"],
                ["gate 2 deterministic", "pass" if not errs else "fail"],
                ["gate 3 mean", mean if mean is not None else ""],
                ["gate 3 lowest", low if low is not None else ""],
                ["gate 3 verdict", "not computable" if violations else
                 ("" if mean is None else
                  ("pass" if mean >= 3.5 and low >= 3 else "fail"))]]

    frows = [["severity", "check", "card", "block", "resolved", "message"]]
    for sev in ("unverified", "error", "warn", "concern", "info"):
        for f in _sev(findings, sev):
            frows.append([sev, f.get("check", ""), f.get("card") or "", f.get("block") or "",
                          bool(f.get("resolved")), f.get("message", "")])

    jrows = [["dimension", "score", "in contract", "note"]]
    jrows += [[d, s, True, n] for d, s, n in valid]
    jrows += [[d, s if isinstance(s, (int, float)) else str(s), False, n] for d, s, n in unknown]
    if violations:  # no separator row when there is nothing to separate
        jrows += [["", "", "", ""]] + [["contract violation", "", "", v] for v in violations]

    crows = [["card", "source", "message"]]
    crows += [[c.get("card") or "deck", "judge", c.get("message", "")]
              for c in (judge.get("concerns") or [])]
    crows += [[f.get("card") or "deck", "tier-1", f.get("message", "")]
              for f in _sev(findings, "concern")]

    return [("Summary", summary), ("Findings", frows), ("Judge", jrows), ("Concerns", crows)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--judge", required=True)
    ap.add_argument("--ir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--xlsx", default=None,
                    help="also write the report as a spreadsheet for analysis")
    args = ap.parse_args(argv)

    fjson = _load(args.findings, "findings")
    judge = _load(args.judge, "judge")
    ir = _load(args.ir, "IR")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report_md(ir, fjson, judge), encoding="utf-8")
    if args.xlsx:
        write_xlsx(args.xlsx, workbook(ir, fjson, judge))
    print(inline_summary(ir, fjson, judge))
    if args.xlsx:
        print(f"\nspreadsheet: {args.xlsx}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
