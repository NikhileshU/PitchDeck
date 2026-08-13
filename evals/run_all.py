#!/usr/bin/env python3
"""run_all.py — every check this repo has, one command, one summary.

Five stages, in the order that fails cheapest first:

  pytest          the suite (which writes evals/out/golden-report.xlsx on exit)
  golden          9 fixtures, full report output asserted
  coverage        all 14 Tier-1 checks fire somewhere
  catalogue       the test catalogue agrees with the suite
  package         the .plugin archive builds and runs from the packaged subset
                  alone — the check that catches a script reaching for evals/ or
                  BUILD-SPEC.md, which otherwise breaks only after a user installs

Every stage is a subprocess: a stage that dies takes its own output with it and
the rest still run, which is what you want from a summary. Output is captured and
replayed only for the stages that failed — a green run should be five lines.

    python3 evals/run_all.py                # everything
    python3 evals/run_all.py --skip package # skip the slow one
    python3 evals/run_all.py -v             # replay output for every stage
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def _run(cmd, cwd=ROOT):
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def stage_pytest():
    # no -q here: pytest.ini already sets it, and a second one is -qq, which
    # suppresses the summary line this stage exists to report
    code, out = _run([PY, "-m", "pytest"])
    tail = [l for l in out.splitlines() if "passed" in l or "failed" in l or "error" in l]
    return code, (tail[-1].strip() if tail else "no summary line"), out


def stage_golden():
    code, out = _run([PY, "evals/run_golden.py"])
    tail = [l for l in out.splitlines() if "fixtures" in l]
    return code, (tail[-1].strip() if tail else out.strip()[:60]), out


def stage_coverage():
    code, out = _run([PY, "evals/run_golden.py", "--coverage"])
    tail = [l for l in out.splitlines() if "Tier-1 checks" in l]
    return code, (tail[-1].strip() if tail else out.strip()[:60]), out


def stage_catalogue():
    code, out = _run([PY, "evals/check_catalogue.py"])
    tail = [l for l in out.splitlines() if "cases ·" in l]
    if not tail:
        return code, out.strip()[:60], out
    n = {w: v for v, w in re.findall(r"(\d+) (cases|marked done|unbacked)", tail[-1])}
    return code, (f"{n.get('cases', '?')} cases · {n.get('marked done', '?')} done "
                  f"· {n.get('unbacked', '?')} unbacked"), out


def stage_package():
    """Build the archive, unpack it somewhere clean, and drive the pipeline using
    only what shipped. Nothing else in the suite can catch a runtime file that was
    left out of the zip."""
    dist = ROOT / "dist" / "deck-builder.plugin"
    dist.parent.mkdir(parents=True, exist_ok=True)
    dist.unlink(missing_ok=True)
    with zipfile.ZipFile(dist, "w", zipfile.ZIP_DEFLATED) as z:
        for name in (".claude-plugin", "skills", "scripts", "themes",
                     "README.md", "requirements.txt"):
            src = ROOT / name
            if src.is_file():
                z.write(src, name)
                continue
            for p in sorted(src.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store":
                    z.write(p, str(p.relative_to(ROOT)))

    tmp = Path(tempfile.mkdtemp(prefix="deck-pkg-"))
    try:
        with zipfile.ZipFile(dist) as z:
            z.extractall(tmp)
        ir = ROOT / "demo" / "deck.json"
        for script, out_name in (("validate.py", "findings.json"),
                                 ("render_html.py", "deck.html"),
                                 ("render_pptx.py", "deck.pptx")):
            flag = "--ir"
            code, out = _run([PY, str(tmp / "scripts" / script), flag, str(ir),
                              "--theme", str(tmp / "themes" / "slate.json"),
                              "--out", str(tmp / "out" / out_name)], cwd=tmp)
            if code != 0:
                return code, f"{script} failed from the packaged subset", out
        size = dist.stat().st_size
        return 0, f"archive {size // 1024}KB, pipeline runs from the packaged subset", ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


STAGES = [("pytest", stage_pytest), ("golden", stage_golden),
          ("coverage", stage_coverage), ("catalogue", stage_catalogue),
          ("package", stage_package)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip", action="append", default=[],
                    choices=[n for n, _ in STAGES], help="skip a stage (repeatable)")
    ap.add_argument("--only", action="append", default=[],
                    choices=[n for n, _ in STAGES], help="run only these stages")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="replay captured output for every stage, not just failures")
    args = ap.parse_args(argv)

    chosen = [(n, f) for n, f in STAGES
              if n not in args.skip and (not args.only or n in args.only)]
    print()
    failures, total = [], time.time()
    for name, fn in chosen:
        t0 = time.time()
        try:
            code, summary, out = fn()
        except Exception as e:  # a broken stage is a failed stage, not a crash
            code, summary, out = 1, f"{type(e).__name__}: {e}", ""
        mark = "ok  " if code == 0 else "FAIL"
        print(f"  {mark} {name:12} {summary:52} {time.time() - t0:6.1f}s")
        if code != 0:
            failures.append((name, out))
        if args.verbose and out:
            print("\n".join("       " + l for l in out.splitlines()))

    if failures:
        for name, out in failures:
            print(f"\n--- {name} ---\n{out.rstrip()}")
    ok = len(chosen) - len(failures)
    print(f"\n  {'PASS' if not failures else 'FAIL'} · {ok}/{len(chosen)} stages "
          f"· {time.time() - total:.1f}s")
    print("  → evals/out/golden-report.xlsx")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
