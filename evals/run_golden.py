#!/usr/bin/env python3
"""run_golden.py — the phase-10 golden set: assert the *whole* report, not pass/fail.

For every `evals/golden/NN-*.json` fixture this runs `validate.py`'s library entry
and `report.py`'s, then compares the complete result — every finding in order, the
inline summary, and every line of `report.md` — against
`evals/golden/expected/NN-*.json`. A wording change, a reordered section, a shifted
severity or a moved overflow constant all surface as a line diff.

Judge input is fixed per fixture in `evals/golden/judges/NN-*.json` — the Tier-2
scores an honest judge would give that deck. `passes` is 0 for every fixture: the
revision branch of report.md §6 needs a `resolved` finding, which `validate.py`
never emits, so the golden set covers that section's zero-pass branch only.

This is a test harness, not a plugin script: the five scripts in `scripts/` are the
shipped surface (invariant 10) and this file stays out of it.

    python3 evals/run_golden.py            # assert — exit 1 on any mismatch
    python3 evals/run_golden.py --only 04  # a single fixture
    python3 evals/run_golden.py --update   # rewrite expected/ — read the diff first
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


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fixtures(only=None):
    return [p for p in sorted(GOLDEN.glob("[0-9][0-9]-*.json"))
            if only is None or p.name.startswith(only)]


def run(fx):
    """Everything the pipeline says about one fixture, as comparable JSON."""
    ir = _read(fx)
    theme_name = (ir.get("meta") or {}).get("theme") or "slate"
    theme = _read(ROOT / "themes" / f"{theme_name}.json")
    judge = _read(JUDGES / fx.name)

    findings = V.validate(ir, theme, ir_dir=GOLDEN)
    fjson = {"deck": (ir.get("meta") or {}).get("title", ""), "passes": 0,
             "findings": findings}
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true",
                    help="rewrite expected/ from current behaviour")
    ap.add_argument("--only", default=None, help="fixture number or name prefix")
    args = ap.parse_args(argv)

    fxs = fixtures(args.only)
    if not fxs:
        print("run_golden: no fixtures matched", file=sys.stderr)
        return 1
    EXPECTED.mkdir(parents=True, exist_ok=True)

    failed = []
    for fx in fxs:
        actual = run(fx)
        exp_path = EXPECTED / fx.name
        if args.update:
            exp_path.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
            print(f"updated  {fx.name}")
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
