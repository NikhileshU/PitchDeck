"""The pipeline as the skill actually runs it — five CLIs, chained.

Everything else in this suite imports the scripts as modules. That misses a
whole class of failure: a renamed flag, a changed exit code, or a stage writing
a file the next stage cannot read. The skill drives these over the command line,
so one module has to as well.

Two things this module does that the others do not:

  1. Artifacts persist. Every stage writes under evals/out/<test-name>/ via the
     `artifacts` fixture, so a failed page-count assertion leaves you the actual
     PDF. tmp_path is kept only where the file is genuinely scratch.

  2. File ingestion is tested. Each CLI reads paths off the command line, and
     every one of those reads can fail: missing file, unreadable JSON, wrong
     shape, unwritable destination. Those paths are exercised here because
     nothing else touches them — the module-level tests hand in dicts.

This is NOT an end-to-end test of the product. The skill layer — Claude choosing
an archetype, authoring deck.json, judging the result — has an LLM in it and is
not deterministically testable.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import theme_path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEMO = ROOT / "demo"
GOLDEN = ROOT / "evals" / "golden"
SLATE = ROOT / "themes" / "slate.json"


def run(script, *args, expect=0):
    """Invoke a script the way the skill does and assert its exit code.

    On mismatch the failure message carries both streams — a CLI test that only
    reports 'exited 1, expected 0' makes you re-run it by hand to learn anything.
    """
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert r.returncode == expect, (
        f"{script} exited {r.returncode}, expected {expect}\n"
        f"--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}"
    )
    return r


def run_raw(script, *args):
    """No exit-code assertion — for cases where the code IS the assertion."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )


def assert_no_traceback(result, script):
    """A CLI must fail with a message, never a stack trace. The scripts already
    promise this for bad IR; these assert it for bad *files*."""
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"{script} raised instead of reporting:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# C-01..C-03 — stage handoffs, artifacts kept
# ---------------------------------------------------------------------------

class TestPipelineWiring:
    """Each stage hands off to the next by file. These assert the handoffs and
    keep every output; content is covered by the golden set and the renderer
    property tests."""

    def test_validate_to_report(self, artifacts):
        findings = artifacts / "findings.json"
        run("validate.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", findings)
        assert json.loads(findings.read_text())["findings"] is not None

        report = artifacts / "report.md"
        r = run("report.py", "--findings", findings,
                "--judge", DEMO / "judge.json", "--ir", DEMO / "deck.json",
                "--out", report)
        # §13: the inline summary goes to stdout, verbatim, for the skill to relay
        assert "Gate 1" in r.stdout and "Gate 3" in r.stdout
        assert report.read_text().startswith("#")

    def test_both_renderers_from_the_same_ir(self, artifacts):
        html, pptx = artifacts / "deck.html", artifacts / "deck.pptx"
        run("render_html.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", html)
        run("render_pptx.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", pptx)
        assert html.stat().st_size > 0 and pptx.stat().st_size > 0

    @pytest.mark.parametrize("theme", ["slate", "warm", "mono"])
    def test_every_shipped_theme_runs_the_whole_chain(self, artifacts, theme):
        run("validate.py", "--ir", DEMO / "deck.json",
            "--theme", theme_path(theme), "--out", artifacts / "findings.json")
        run("render_html.py", "--ir", DEMO / "deck.json",
            "--theme", theme_path(theme), "--out", artifacts / f"{theme}.html")
        run("render_pptx.py", "--ir", DEMO / "deck.json",
            "--theme", theme_path(theme), "--out", artifacts / f"{theme}.pptx")

    def test_full_chain_leaves_a_complete_artifact_set(self, artifacts):
        """The four files the skill hands back. Worth one test that produces all
        of them together — it is the closest thing to 'what the user receives',
        and it is the directory you open when a deck looks wrong."""
        findings = artifacts / "findings.json"
        run("validate.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", findings, "--passes", "0")
        run("report.py", "--findings", findings, "--judge", DEMO / "judge.json",
            "--ir", DEMO / "deck.json", "--out", artifacts / "report.md")
        run("render_html.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", artifacts / "deck.html")
        run("render_pptx.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", artifacts / "deck.pptx")
        for name in ("findings.json", "report.md", "deck.html", "deck.pptx"):
            assert (artifacts / name).stat().st_size > 0, f"{name} is empty"


# ---------------------------------------------------------------------------
# C-10..C-13 — file ingestion
# ---------------------------------------------------------------------------

class TestFileIngestion:
    """Every CLI reads paths off the command line, and every read can fail.
    Nothing else in the suite touches these paths: the module-level tests hand
    in dicts, so a broken file-reading branch would ship green.

    The contract (README): exit 1 with a message. Not a traceback."""

    INGESTORS = [
        ("validate.py", ["--ir", "{ir}", "--theme", "{theme}", "--out", "{out}"]),
        ("render_html.py", ["--ir", "{ir}", "--theme", "{theme}", "--out", "{out}"]),
        ("render_pptx.py", ["--ir", "{ir}", "--theme", "{theme}", "--out", "{out}"]),
    ]
    IDS = [s for s, _ in INGESTORS]

    @staticmethod
    def _invoke(script, template, ir, theme, out):
        args = [a.format(ir=ir, theme=theme, out=out) for a in template]
        return run_raw(script, *args)

    @pytest.mark.parametrize("script,template", INGESTORS, ids=IDS)
    def test_missing_ir_file(self, script, template, artifacts, tmp_path):
        """R13-L5: render_html.py currently raises here where validate.py and
        report.py report cleanly. Not xfailed — the inconsistency is the finding,
        and this is what will tell you when it is fixed."""
        r = self._invoke(script, template, tmp_path / "nope.json", SLATE,
                         artifacts / "out.bin")
        assert r.returncode != 0
        assert_no_traceback(r, script)

    @pytest.mark.parametrize("script,template", INGESTORS, ids=IDS)
    def test_missing_theme_file(self, script, template, artifacts, tmp_path):
        r = self._invoke(script, template, DEMO / "deck.json",
                         tmp_path / "nope.json", artifacts / "out.bin")
        assert r.returncode != 0
        assert_no_traceback(r, script)

    @pytest.mark.parametrize("script,template", INGESTORS, ids=IDS)
    def test_malformed_json_ir(self, script, template, artifacts, tmp_path):
        """R3-S2 fixed this for validate.py. The renderers ingest the same file."""
        bad = tmp_path / "bad.json"
        bad.write_text("{not json,,,")
        r = self._invoke(script, template, bad, SLATE, artifacts / "out.bin")
        assert r.returncode != 0
        assert_no_traceback(r, script)

    @pytest.mark.parametrize("script,template", INGESTORS, ids=IDS)
    def test_json_of_the_wrong_shape(self, script, template, artifacts, tmp_path):
        """Valid JSON, not a deck. Reaches further into each script than
        malformed bytes do — past the parse, into the first field access."""
        wrong = tmp_path / "wrong.json"
        wrong.write_text(json.dumps({"hello": "world"}))
        r = self._invoke(script, template, wrong, SLATE, artifacts / "out.bin")
        assert r.returncode != 0
        assert_no_traceback(r, script)

    def test_report_missing_findings_file(self, artifacts, tmp_path):
        r = run_raw("report.py", "--findings", tmp_path / "nope.json",
                    "--judge", DEMO / "judge.json", "--ir", DEMO / "deck.json",
                    "--out", artifacts / "report.md")
        assert r.returncode != 0
        assert_no_traceback(r, "report.py")

    def test_report_missing_judge_file(self, artifacts, tmp_path):
        """A judge file that is not there is different from one that is empty:
        empty means 'Gate 3 not computable', absent means the caller wired it
        wrong. They must not be conflated."""
        findings = artifacts / "findings.json"
        run("validate.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", findings)
        r = run_raw("report.py", "--findings", findings,
                    "--judge", tmp_path / "nope.json", "--ir", DEMO / "deck.json",
                    "--out", artifacts / "report.md")
        assert r.returncode != 0
        assert_no_traceback(r, "report.py")

    def test_out_parent_directory_is_created(self, artifacts):
        """C-13. The skill writes into out/, which may not exist on a first run."""
        nested = artifacts / "deep" / "nested" / "deck.html"
        run("render_html.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", nested)
        assert nested.exists()

    def test_unwritable_out_path(self, artifacts):
        """C-12. A directory where a file is expected — the cheapest portable
        way to make a write fail without chmod games that root ignores."""
        blocked = artifacts / "deck.html"
        blocked.mkdir()
        r = run_raw("render_html.py", "--ir", DEMO / "deck.json",
                    "--theme", SLATE, "--out", blocked)
        assert r.returncode != 0
        assert_no_traceback(r, "render_html.py")

    def test_image_src_resolves_relative_to_the_ir(self, artifacts):
        """block-types.md: image srcs resolve against deck.json's directory, not
        the process cwd. Run from a different cwd and it must still embed."""
        out = artifacts / "deck.html"
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "render_html.py"),
             "--ir", str(ROOT / "evals/fixtures/all-blocks.json"),
             "--theme", str(SLATE), "--out", str(out)],
            cwd=str(artifacts), capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
        assert "data:image" in out.read_text(encoding="utf-8")
        assert 'src="assets/' not in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# spreadsheet export
# ---------------------------------------------------------------------------

def _sheets(path):
    """Read an .xlsx with the stdlib. The writer has no dependencies on purpose,
    so the test that checks it must not add one either — and parsing the parts by
    hand is what proves the file is a real workbook rather than a zip we like the
    look of."""
    import xml.etree.ElementTree as ET
    import zipfile
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for required in ("[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
                         "xl/_rels/workbook.xml.rels"):
            assert required in names, f"{path.name} is missing {required}"
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        titles = [s.attrib["name"] for s in wb.iter(ns + "sheet")]
        out = {}
        for i, title in enumerate(titles, 1):
            sheet = ET.fromstring(z.read(f"xl/worksheets/sheet{i}.xml"))
            rows = []
            for row in sheet.iter(ns + "row"):
                rows.append(["".join(t.text or "" for t in c.iter(ns + "t"))
                             or "".join(v.text or "" for v in c.iter(ns + "v"))
                             for c in row.iter(ns + "c")])
            out[title] = rows
    return out


class TestSpreadsheetExport:
    """`--xlsx` is wired into both skills, so every live run produces one. A
    workbook nobody parses is a workbook that quietly stops being written."""

    def test_report_writes_a_readable_workbook(self, artifacts):
        findings = artifacts / "findings.json"
        run("validate.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", findings)
        xlsx = artifacts / "report.xlsx"
        run("report.py", "--findings", findings, "--judge", DEMO / "judge.json",
            "--ir", DEMO / "deck.json", "--out", artifacts / "report.md", "--xlsx", xlsx)

        sheets = _sheets(xlsx)
        assert list(sheets) == ["Summary", "Findings", "Judge", "Concerns"]
        assert sheets["Judge"][0] == ["dimension", "score", "in contract", "note"]
        # the five §11 dimensions, one row each, and no trailing filler
        dims = [r[0] for r in sheets["Judge"][1:]]
        assert dims == ["storyline", "verticalLogic", "archetypeFit",
                        "audienceFit", "density"]
        # demo/deck.json is all placeholder data: every one must reach the sheet
        unverified = [r for r in sheets["Findings"][1:] if r[0] == "unverified"]
        assert len(unverified) == 5, sheets["Findings"]

    def test_golden_workbook_marks_expected_vs_actual(self, artifacts):
        """The Findings sheet is the diff: a row present on one side only is the
        regression, and it says so in the row rather than leaving you to align
        two lists by eye."""
        import run_golden
        xlsx = artifacts / "golden-report.xlsx"
        run_golden.R.write_xlsx(xlsx, run_golden.workbook(run_golden.fixtures()))

        sheets = _sheets(xlsx)
        assert list(sheets) == ["Fixtures", "Findings", "Judge"]
        assert sheets["Fixtures"][0][:3] == ["fixture", "theme", "match"]
        assert len(sheets["Fixtures"]) == 1 + 9, "one row per golden fixture"
        # nothing should be one-sided while the suite is green
        statuses = {r[1] for r in sheets["Findings"][1:]}
        assert statuses == {"both"}, f"expected/actual drift: {statuses}"
        assert all(r[2] == "yes" for r in sheets["Fixtures"][1:]), "a fixture does not match"


# ---------------------------------------------------------------------------
# C-04..C-09 — exit codes
# ---------------------------------------------------------------------------

class TestExitCodes:
    """'Every script is a pure CLI: exit 0 pass, 1 fail' — README. The skill
    branches on these, so a changed code silently changes the run flow."""

    def test_validate_exits_1_on_error_findings(self, artifacts):
        run("validate.py", "--ir", GOLDEN / "02-topic-titles.json",
            "--theme", SLATE, "--out", artifacts / "findings.json", expect=1)

    def test_validate_exits_0_on_a_clean_deck(self, artifacts):
        run("validate.py", "--ir", GOLDEN / "01-good-business.json",
            "--theme", SLATE, "--out", artifacts / "findings.json")

    def test_validate_exits_0_on_unverified_only(self, artifacts):
        """`unverified` surfaces placeholder data but must not fail the gate —
        placeholders are legitimate, concealment is not."""
        run("validate.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", artifacts / "findings.json")

    def test_report_exits_0_even_when_gates_fail(self, artifacts):
        """report.py reports; validate.py gates. A failing deck must still
        produce its report, or the user cannot see why it failed."""
        findings = artifacts / "findings.json"
        run("validate.py", "--ir", GOLDEN / "02-topic-titles.json",
            "--theme", SLATE, "--out", findings, expect=1)
        run("report.py", "--findings", findings,
            "--judge", GOLDEN / "judges" / "02-topic-titles.json",
            "--ir", GOLDEN / "02-topic-titles.json",
            "--out", artifacts / "report.md")

    def test_renderer_exits_1_on_invalid_ir(self, artifacts):
        run("render_pptx.py", "--ir", GOLDEN / "09-malformed.json",
            "--theme", SLATE, "--out", artifacts / "deck.pptx", expect=1)


# ---------------------------------------------------------------------------
# C-14..C-16 — the dependency split
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    """A missing PPTX dependency must not take the HTML path down, and a missing
    browser must not take either. Design claims rot silently unless something
    asserts them — and these are exactly the failure modes a Cowork install
    would expose."""

    def test_html_path_has_no_third_party_imports(self):
        """validate, report, render_html and export_pdf are stdlib-only on
        purpose. Import them with python-pptx and PIL blocked."""
        code = (
            "import sys, importlib\n"
            "sys.path.insert(0, %r)\n"
            "for m in ('pptx', 'PIL'):\n"
            "    sys.modules[m] = None\n"
            "for m in ('validate', 'report', 'render_html', 'export_pdf'):\n"
            "    importlib.import_module(m)\n"
            "print('ok')\n" % str(SCRIPTS)
        )
        r = subprocess.run([sys.executable, "-c", code],
                           capture_output=True, text=True)
        assert r.returncode == 0, (
            "a stdlib-only script imported python-pptx or Pillow:\n" + r.stderr
        )

    def test_html_and_report_survive_without_python_pptx(self, artifacts):
        """C-16. The claim in requirements.txt, executed: with pptx unimportable,
        the HTML and report paths still produce their artifacts."""
        code = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "sys.modules['pptx'] = None\n"
            "import json, validate, render_html\n"
            "from pathlib import Path\n"
            "ir = json.loads(Path(%r).read_text())\n"
            "theme = json.loads(Path(%r).read_text())\n"
            "css = Path(%r).read_text()\n"
            "render_html.render(ir, theme, %r, css=css, ir_dir=Path(%r))\n"
            "print('ok')\n"
            % (str(SCRIPTS), str(DEMO / "deck.json"), str(SLATE),
               str(ROOT / "themes" / "base.css"),
               str(artifacts / "deck.html"), str(DEMO))
        )
        r = subprocess.run([sys.executable, "-c", code],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert (artifacts / "deck.html").stat().st_size > 0

    def test_missing_browser_fails_only_the_pdf(self, artifacts):
        """export_pdf exits 1 with a message; the HTML it was given is untouched
        and still shippable."""
        html = artifacts / "deck.html"
        run("render_html.py", "--ir", DEMO / "deck.json",
            "--theme", SLATE, "--out", html)
        before = html.read_bytes()
        r = run_raw("export_pdf.py", "--html", html,
                    "--out", artifacts / "deck.pdf",
                    "--browser", "/nonexistent/browser")
        assert r.returncode == 1
        assert html.read_bytes() == before, "a failed PDF export modified the HTML"
        assert not (artifacts / "deck.pdf").exists()
