#!/usr/bin/env python3
"""report.py — assemble the quality report from findings.json + judge.json + the IR.

Deterministic, no LLM. Prints the inline summary (spec §13 shape) to stdout and
writes report.md with the six sections in fixed order — unverified inputs first,
always. Reporting is not a gate: exit 1 only when an input cannot be read.
"""

import argparse
import json
import sys
from pathlib import Path

DIMENSIONS = ("storyline", "verticalLogic", "archetypeFit", "audienceFit", "density")
PLURAL = {"chart": "charts", "table": "tables", "kpi": "KPIs"}


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


def _scores(judge):
    sc = judge.get("scores") or {}
    out = [(d, sc[d].get("score"), sc[d].get("note", "")) for d in DIMENSIONS
           if isinstance(sc.get(d), dict) and isinstance(sc[d].get("score"), (int, float))]
    out += [(d, v.get("score"), v.get("note", "")) for d, v in sc.items()
            if d not in DIMENSIONS and isinstance(v, dict)
            and isinstance(v.get("score"), (int, float))]
    return out


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
    scores = _scores(judge)
    if scores:
        mean = sum(s for _, s, _ in scores) / len(scores)
        low = min(scores, key=lambda x: x[1])
        lines.append(f"Gate 3  judged         {mean:.1f} / 5   (lowest: {low[0]} {low[1]:g})")
    else:
        lines.append("Gate 3  judged         — (no scores in judge.json)")
    extras = []
    if unv:
        kinds = sorted({PLURAL.get(f.get("message", "").split(" ")[0], "values") for f in unv})
        cards = sorted({f["card"] for f in unv if f.get("card")})
        extras.append(f"⚠  {len(unv)} unverified value{'s' if len(unv) != 1 else ''} — "
                      f"{', '.join(kinds)} on {', '.join(cards)} use placeholder data")
    concerns = (judge.get("concerns") or []) + _sev(findings, "concern")
    if concerns:
        extras.append(f"!  {len(concerns)} concern{'s' if len(concerns) != 1 else ''} "
                      "raised — see report.md")
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
    scores = _scores(judge)
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
    unresolved = [f for f in errs if not f.get("resolved")]
    out += [_finding_line(f) for f in errs] or ["None."]
    if unresolved:
        out += ["", f"**{len(unresolved)} unresolved — this deck must not ship.**"]
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
        out += [f"- `{c['card'] or 'deck'}` — {c['message']}" for c in concerns]
        out += ["", "Concerns are editorial judgment calls. They are never auto-fixed."]
    else:
        out.append("None raised.")
    out.append("")

    out += ["## 5 · Tier-2 scorecard", ""]
    if scores:
        out += ["| Dimension | Score | Note |", "|---|---|---|"]
        out += [f"| {d} | {s:g} | {n} |" for d, s, n in scores]
        mean = sum(s for _, s, _ in scores) / len(scores)
        low = min(s for _, s, _ in scores)
        verdict = "PASS" if mean >= 3.5 and low >= 3 else "FAIL"
        out += ["", f"Mean **{mean:.1f} / 5**, lowest **{low:g}** — "
                    f"gate (mean ≥ 3.5, no dimension < 3): **{verdict}**"]
    else:
        out.append("No Tier-2 scores available.")
    out.append("")

    out += ["## 6 · Revision log", ""]
    resolved = [f for f in findings if f.get("resolved")]
    if passes == 0 and not resolved:
        out.append("No revision passes were needed.")
    else:
        out.append(f"{passes} revision pass{'es' if passes != 1 else ''}.")
        if resolved:
            out += [""] + [_finding_line(f) for f in resolved]
        else:
            out += ["", "No findings recorded as resolved."]
    out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--judge", required=True)
    ap.add_argument("--ir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    fjson = _load(args.findings, "findings")
    judge = _load(args.judge, "judge")
    ir = _load(args.ir, "IR")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report_md(ir, fjson, judge), encoding="utf-8")
    print(inline_summary(ir, fjson, judge))
    return 0


if __name__ == "__main__":
    sys.exit(main())
