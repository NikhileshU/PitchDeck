#!/usr/bin/env python3
"""check_catalogue.py — keep the test catalogue honest against the suite.

`pitchdeck-test-catalogue.md` carries 200-odd cases with stable ids and a status
column: ✓ written, + not yet, ○ out of scope. Nothing connected that column to
reality, so it could only ever be right on the day it was edited. This reads the
catalogue, scans the suite for case ids, and reports the drift both ways:

  unbacked      ✓ in the catalogue, but no test carries the id — the claim is
                either stale or the test exists and is not linked
  undercounted  + in the catalogue, but a test carries the id — the work is done
                and the catalogue has not caught up
  mislabelled   ○ out of scope, but a test carries the id
  unknown       an id in a test that the catalogue does not define

**The linking convention is the id in the test's docstring**, which is what
test_pipeline.py already does ("C-12. A directory where a file is expected").
Nothing else is required — no marker, no registry, no import.

    python3 evals/check_catalogue.py               # report; exit 1 on real drift
    python3 evals/check_catalogue.py --strict      # unbacked ✓ also fails
    python3 evals/check_catalogue.py --todo        # just the work list
    python3 evals/check_catalogue.py --xlsx PATH   # the same, as data

Exit 1 on undercounted, mislabelled or unknown ids — each is a factual error in
the catalogue and each is fixed by editing one line of markdown. Unbacked ids
only fail under --strict, because backfilling ~100 docstring tags is a project,
not a precondition for using this.
"""

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import report as R  # noqa: E402  (the stdlib xlsx writer lives with report.py)

CATALOGUE = ROOT / "evals" / "pitchdeck-test-catalogue.md"
SUITE = sorted((ROOT / "evals").glob("test_*.py"))

ID = re.compile(r"^(?:[A-Z]{1,2}|○)-\d+$")
DONE, TODO, SCOPE, PARTIAL = "done", "todo", "scope", "partial"


def parse_catalogue(path):
    """Rows of markdown tables whose first cell is a case id. Section comes from
    the nearest `## ` heading; a `### ` refines it for the per-check tables."""
    cases, section, sub, unparsed = {}, "(none)", "", []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section, sub = line[3:].strip(), ""
            continue
        if line.startswith("### "):
            sub = line[4:].strip()
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not ID.match(cells[0]):
            continue
        cid, last = cells[0], cells[-1]
        # `✓ (09) / +` means the positive case is written and the negative is
        # not. Testing for ✓ first counted seven of those as fully done and
        # dropped the other half out of --todo entirely (R14-M1), so a mixed
        # cell gets its own status rather than being rounded up.
        if cid.startswith("○") or "○" in last:
            status = SCOPE
        elif "✓" in last and "+" in last:
            status = PARTIAL
        elif "✓" in last:
            status = DONE
        elif "+" in last:
            status = TODO
        else:
            unparsed.append((cid, last))
            continue
        cases[cid] = {"id": cid, "section": section, "sub": sub,
                      "case": cells[1] if len(cells) > 1 else "",
                      # these tables vary in width: some carry one `Expect`
                      # column, the per-check ones carry positive and negative
                      "expect": " / ".join(cells[2:-1]),
                      "status": status, "note": last}
    return cases, unparsed


def _pat(i):
    """Range banners (`# C-10..C-13 — file ingestion`) are not links: they name a
    span of the file, not a case. A `..` on either side disqualifies the match."""
    return rf"(?<![\w-])(?<!\.\.){re.escape(i)}(?!\.\.)(?![\w-])"


def _test_docstrings(path):
    """(qualified name, docstring) for every test function in a module.

    Only test functions count as links (R14-M2). Searching whole file bodies
    meant a module docstring, a section banner, or a comment left behind by a
    deleted test all registered as coverage — and the report could name the file
    but not the test, which is the thing you actually need when a case is
    supposedly covered and you want to read the assertion."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    out = []

    def visit(node, prefix=""):
        for child in node.body:
            if isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}::")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and child.name.startswith("test"):
                out.append((f"{path.name}::{prefix}{child.name}",
                            ast.get_docstring(child) or ""))

    visit(tree)
    return out


def scan_suite(ids):
    """Which test asserts each case. Searched literally against the ids the
    catalogue defines, so a token like `R13-M3` can never be mistaken for one."""
    hits = {i: [] for i in ids}
    for path in SUITE:
        for name, doc in _test_docstrings(path):
            if not doc:
                continue
            for i in ids:
                if re.search(_pat(i), doc):
                    hits[i].append(name)
    return hits


def _drift(cases, hits):
    unbacked = [c for c in cases.values() if c["status"] == DONE and not hits[c["id"]]]
    undercounted = [c for c in cases.values() if c["status"] == TODO and hits[c["id"]]]
    mislabelled = [c for c in cases.values() if c["status"] == SCOPE and hits[c["id"]]]
    return unbacked, undercounted, mislabelled


def _sections(cases):
    order, rows = [], {}
    for c in cases.values():
        if c["section"] not in rows:
            rows[c["section"]] = {DONE: 0, TODO: 0, SCOPE: 0, PARTIAL: 0}
            order.append(c["section"])
        rows[c["section"]][c["status"]] += 1
    return [(s, rows[s]) for s in order]


def _short(s, n):
    return s if len(s) <= n else s[: n - 1] + "…"


def report_text(cases, hits, unparsed):
    unbacked, undercounted, mislabelled = _drift(cases, hits)
    print(f"{'section':34} {'total':>6} {'done':>6} {'part':>6} {'todo':>6} {'scope':>6}")
    for name, counts in _sections(cases):
        total = sum(counts.values())
        print(f"  {_short(name, 32):32} {total:>6} {counts[DONE]:>6} "
              f"{counts[PARTIAL]:>6} {counts[TODO]:>6} {counts[SCOPE]:>6}")

    for label, items in (("UNBACKED (✓ in catalogue, no test carries the id)", unbacked),
                         ("UNDERCOUNTED (+ in catalogue, a test carries the id)", undercounted),
                         ("MISLABELLED (○ out of scope, a test carries the id)", mislabelled)):
        if items:
            print(f"\n{label}:")
            for c in items[:40]:
                print(f"    {c['id']:8} {_short(c['case'], 62)}")
            if len(items) > 40:
                print(f"    … and {len(items) - 40} more")

    if unparsed:
        print("\nUNPARSED status cells (row read, status not understood):")
        for cid, cell in unparsed[:10]:
            print(f"    {cid:8} {_short(cell, 50)!r}")

    done = sum(1 for c in cases.values() if c["status"] == DONE)
    part = sum(1 for c in cases.values() if c["status"] == PARTIAL)
    linked = sum(1 for c in cases.values() if hits[c["id"]])
    print(f"\n{len(cases)} cases · {done} marked done · {part} partial · {linked} linked to a test "
          f"· {len(unbacked)} unbacked · {len(undercounted)} undercounted "
          f"· {len(mislabelled)} mislabelled")
    return unbacked, undercounted, mislabelled


def workbook(cases, hits):
    rows = [["id", "section", "subsection", "case", "expect", "status",
             "linked", "tests"]]
    for c in cases.values():
        where = hits[c["id"]]
        rows.append([c["id"], c["section"], c["sub"], c["case"], c["expect"],
                     c["status"], bool(where), ", ".join(where)])

    unbacked, undercounted, mislabelled = _drift(cases, hits)
    drift = [["kind", "id", "section", "case", "tests"]]
    for kind, items in (("unbacked", unbacked), ("undercounted", undercounted),
                        ("mislabelled", mislabelled)):
        for c in items:
            drift.append([kind, c["id"], c["section"], c["case"],
                          ", ".join(hits[c["id"]])])

    summary = [["section", "total", "done", "partial", "todo", "scope", "linked"]]
    for name, counts in _sections(cases):
        linked = sum(1 for c in cases.values()
                     if c["section"] == name and hits[c["id"]])
        summary.append([name, sum(counts.values()), counts[DONE], counts[PARTIAL],
                        counts[TODO], counts[SCOPE], linked])
    return [("Cases", rows), ("Drift", drift), ("Summary", summary)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true",
                    help="unbacked ✓ cases also fail the run")
    ap.add_argument("--todo", action="store_true", help="print the work list only")
    ap.add_argument("--xlsx", default=None, help="write the catalogue and drift as data")
    args = ap.parse_args(argv)

    if not CATALOGUE.exists():
        print(f"check_catalogue: no catalogue at {CATALOGUE}", file=sys.stderr)
        return 1
    cases, unparsed = parse_catalogue(CATALOGUE)
    if not cases:
        print("check_catalogue: no case ids found — has the table format changed?",
              file=sys.stderr)
        return 1
    hits = scan_suite(list(cases))

    if args.todo:
        todo = [c for c in cases.values() if c["status"] in (TODO, PARTIAL)]
        for c in todo:
            mark = "half" if c["status"] == PARTIAL else "    "
            print(f"{c['id']:8} {mark} {c['section'][:28]:30} {c['case']}")
        n_part = sum(1 for c in todo if c["status"] == PARTIAL)
        print(f"\n{len(todo)} cases to write ({n_part} of them the missing half "
              f"of a case whose positive side exists)")
        return 0

    unbacked, undercounted, mislabelled = report_text(cases, hits, unparsed)
    if args.xlsx:
        R.write_xlsx(args.xlsx, workbook(cases, hits))
        print(f"→ {args.xlsx}")

    docs = "\n".join(doc for p in SUITE for _, doc in _test_docstrings(p) if doc)
    unknown = sorted(set(re.findall(r"(?<![\w-])(?<!\.\.)((?:[A-Z]{1,2})-\d{1,3})(?!\.\.)(?![\w-])",
                                    docs)) - set(cases))
    if unknown:
        print(f"\nUNKNOWN ids referenced by tests but absent from the catalogue: "
              f"{', '.join(unknown)}")

    hard = undercounted or mislabelled or unknown or unparsed
    return 1 if hard or (args.strict and unbacked) else 0


if __name__ == "__main__":
    sys.exit(main())
