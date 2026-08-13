#!/usr/bin/env python3
"""run_golden.py — the phase-10 golden set: assert the *whole* report, not pass/fail.

For every `evals/golden/NN-*.json` fixture this runs `validate.py`'s library entry
and `report.py`'s, then compares the complete result — every finding in order, the
inline summary, and every line of `report.md` — against
`evals/golden/expected/NN-*.json`. A wording change, a reordered section, a shifted
severity or a moved overflow constant all surface as a line diff.

Judge input is fixed per fixture in `evals/golden/judges/NN-*.json` — the Tier-2
scores an honest judge would give that deck. `evals/golden/runs.json` supplies the
revision context a single validate pass cannot produce (`passes`, and which
findings count as resolved), so report.md §6 is pinned in both its branches.

A fixture's theme comes from `meta.theme`, resolved against `evals/golden/themes/`
first and `themes/` second — that is how `08-bad-theme.json` reaches a deliberately
broken theme without one ever sitting in the shipped theme directory.

This is a test harness, not a plugin script: the five scripts in `scripts/` are the
shipped surface (invariant 10) and this file stays out of it.

    python3 evals/run_golden.py             # assert — exit 1 on any mismatch
    python3 evals/run_golden.py --only 04   # a single fixture
    python3 evals/run_golden.py --coverage  # which of the 14 checks the set fires
    python3 evals/run_golden.py --update    # rewrite expected/ — read the diff first
"""

import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import report as R          # noqa: E402
import validate as V        # noqa: E402

GOLDEN = ROOT / "evals" / "golden"
EXPECTED = GOLDEN / "expected"
JUDGES = GOLDEN / "judges"
SEVERITIES = ("unverified", "error", "warn", "concern", "info")
# the 14 Tier-1 checks; the set is expected to fire every one of them
CHECKS = ("schema-valid", "data-provenance", "title-is-claim", "answer-first",
          "card-count", "title-length", "one-message", "evidence-present",
          "text-budget", "chart-fit", "notes-present", "contrast",
          "min-type-size", "overflow")


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fixtures(only=None):
    return [p for p in sorted(GOLDEN.glob("[0-9][0-9]-*.json"))
            if only is None or p.name.startswith(only)]


def _theme_path(name):
    """Fixture themes shadow shipped ones, so a broken theme never ships."""
    local = GOLDEN / "themes" / f"{name}.json"
    return local if local.exists() else ROOT / "themes" / f"{name}.json"


def run(fx):
    """Everything the pipeline says about one fixture, as comparable JSON."""
    ir = _read(fx)
    theme_name = (ir.get("meta") or {}).get("theme") or "slate"
    theme = _read(_theme_path(theme_name))
    judge = _read(JUDGES / fx.name)
    ctx = _read(GOLDEN / "runs.json").get(fx.name) or {}

    findings = V.validate(ir, theme, ir_dir=GOLDEN)
    for sel in ctx.get("resolved") or []:
        check, _, sev = sel.partition(":")
        for f in findings:
            if f["check"] == check and (not sev or f["severity"] == sev):
                f["resolved"] = True
    fjson = {"deck": (ir.get("meta") or {}).get("title", ""),
             "passes": ctx.get("passes", 0), "findings": findings}
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    return {
        "fixture": fx.name,
        "theme": theme_name,
        "exit": 1 if counts["error"] else 0,
        "counts": {s: n for s, n in counts.items() if n},
        "findings": findings,
        "inline_summary": R.inline_summary(ir, fjson, judge).split("\n"),
        "report_md": R.report_md(ir, fjson, judge).split("\n"),
    }


def _lines(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False).split("\n")


def _key(f):
    return (f.get("check"), f.get("severity"), f.get("card"), f.get("block"), f.get("message"))


def workbook(fxs):
    """Expected vs actual, one row per fixture and one per finding, plus the
    judge scorecard — the diff in a form you can sort and pivot rather than read.
    A finding present on one side only is the whole point, so `status` carries it
    explicitly instead of leaving you to line two lists up by eye."""
    fixtures = [["fixture", "theme", "match", "exit expected", "exit actual"]
                + [f"{s} expected" for s in SEVERITIES]
                + [f"{s} actual" for s in SEVERITIES]
                + ["judge mean", "judge lowest", "gate 3"]]
    findings = [["fixture", "status", "severity", "check", "card", "block", "resolved", "message"]]
    judge_rows = [["fixture", "dimension", "score", "note"]]

    for fx in fxs:
        actual = run(fx)
        exp_path = EXPECTED / fx.name
        expected = _read(exp_path) if exp_path.exists() else {}
        judge = _read(JUDGES / fx.name)
        valid, _ = R._scores(judge)
        mean = sum(s for _, s, _ in valid) / len(valid) if valid else ""
        low = min((s for _, s, _ in valid), default="")
        verdict = "" if not valid else ("pass" if mean >= 3.5 and low >= 3 else "fail")
        ec, ac = expected.get("counts") or {}, actual["counts"]
        fixtures.append(
            [fx.name, actual["theme"], expected == actual,
             expected.get("exit", ""), actual["exit"]]
            + [ec.get(s, 0) for s in SEVERITIES] + [ac.get(s, 0) for s in SEVERITIES]
            + [round(mean, 2) if valid else "", low, verdict])

        exp_f = {_key(f): f for f in expected.get("findings") or []}
        act_f = {_key(f): f for f in actual["findings"]}
        for k in sorted(set(exp_f) | set(act_f), key=lambda k: tuple(str(x) for x in k)):
            f = act_f.get(k) or exp_f[k]
            status = ("both" if k in exp_f and k in act_f
                      else "expected only — REGRESSION" if k in exp_f else "actual only — NEW")
            findings.append([fx.name, status, f.get("severity", ""), f.get("check", ""),
                             f.get("card") or "", f.get("block") or "",
                             bool(f.get("resolved")), f.get("message", "")])

        for d, s, n in valid:
            judge_rows.append([fx.name, d, s, n])

    return [("Fixtures", fixtures), ("Findings", findings), ("Judge", judge_rows)]


def coverage(fxs):
    """Which fixture exercises which Tier-1 check. A check no fixture fires is a
    check that could be silently broken and still ship green (R10-M1/R11-H1)."""
    hits = {c: [] for c in CHECKS}
    unknown = set()
    for fx in fxs:
        for f in run(fx)["findings"]:
            (hits[f["check"]] if f["check"] in hits else unknown).append(fx.name[:2])
    for c in CHECKS:
        where = sorted(set(hits[c]))
        print(f"  {c:16s} {len(hits[c]):3d} findings  "
              f"{'in ' + ', '.join(where) if where else 'NEVER FIRES'}")
    if unknown:
        print(f"\n  check names not in CHECKS: {sorted(set(unknown))}")
    missing = [c for c in CHECKS if not hits[c]]
    print(f"\n{len(CHECKS) - len(missing)}/{len(CHECKS)} Tier-1 checks exercised"
          + (f" — UNEXERCISED: {', '.join(missing)}" if missing else ""))
    return 1 if missing or unknown else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true",
                    help="rewrite expected/ from current behaviour")
    ap.add_argument("--only", default=None, help="fixture number or name prefix")
    ap.add_argument("--coverage", action="store_true",
                    help="report which Tier-1 checks the set fires; exit 1 if any is unexercised")
    ap.add_argument("--xlsx", default=None,
                    help="write expected vs actual and the judge scores to a spreadsheet")
    args = ap.parse_args(argv)

    fxs = fixtures(args.only)
    if not fxs:
        print("run_golden: no fixtures matched", file=sys.stderr)
        return 1
    if args.coverage:
        return coverage(fxs)
    if args.xlsx:
        R.write_xlsx(args.xlsx, workbook(fxs))
        print(f"spreadsheet: {args.xlsx}")
    EXPECTED.mkdir(parents=True, exist_ok=True)

    failed = []
    for fx in fxs:
        actual = run(fx)
        exp_path = EXPECTED / fx.name
        if args.update:
            new = not exp_path.exists()
            exp_path.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
            # a first baseline has no diff to review, so print what it recorded —
            # otherwise a wrong baseline is invisible at exactly the moment it is
            # cheapest to catch (R10-L2)
            tally = " · ".join(f"{n} {s}" for s, n in actual["counts"].items()) or "clean"
            print(f"{'CREATED' if new else 'updated'}  {fx.name}  "
                  f"exit {actual['exit']}  {tally}")
            if new:
                for f in actual["findings"]:
                    print(f"             {f['severity']:10s} {f['check']:16s} "
                          f"{f.get('card') or 'deck'}  {f['message']}")
            continue
        if not exp_path.exists():
            failed.append(fx.name)
            print(f"MISSING  {fx.name} — no expected/{fx.name}; run --update")
            continue
        expected = _read(exp_path)
        if expected == actual:
            c = actual["counts"]
            tally = " · ".join(f"{n} {s}" for s, n in c.items()) or "clean"
            print(f"ok       {fx.name}  exit {actual['exit']}  {tally}")
        else:
            failed.append(fx.name)
            print(f"FAIL     {fx.name}")
            diff = difflib.unified_diff(_lines(expected), _lines(actual),
                                        fromfile=f"expected/{fx.name}",
                                        tofile=f"actual/{fx.name}", lineterm="", n=2)
            print("\n".join("    " + d for d in diff))

    if args.update:
        print(f"\n{len(fxs)} expected file(s) rewritten — review the diff before committing.")
        return 0
    print(f"\n{len(fxs) - len(failed)}/{len(fxs)} fixtures match expected output"
          + (f" — FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
