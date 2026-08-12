"""The pipeline as the skill actually runs it — five CLIs, chained.

Everything else in this suite imports the scripts as modules. That misses a
whole class of failure: a renamed flag, a changed exit code, or a stage writing
a file the next stage cannot read. The skill drives these over the command line,
so one test has to as well.

This is NOT an end-to-end test of the product. The skill layer — Claude choosing
an archetype, authoring deck.json, judging the result — has an LLM in it and is
not deterministically testable. This covers everything downstream of deck.json,
which is all of it that can be pinned.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEMO = ROOT / "demo"


def run(script, *args, expect=0):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert r.returncode == expect, (
        f"{script} exited {r.returncode}, expected {expect}\n"
        f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )
    return r


@pytest.fixture
def workdir(tmp_path):
    (tmp_path / "out").mkdir()
    return tmp_path


class TestPipelineWiring:
    """Each stage hands off to the next by file. These assert the handoffs, not
    the content — content is covered by the golden set and the renderer tests."""

    def test_validate_to_report(self, workdir):
        findings = workdir / "findings.json"
        run("validate.py", "--ir", DEMO / "deck.json",
            "--theme", ROOT / "themes/slate.json", "--out", findings)
        assert json.loads(findings.read_text())["findings"] is not None

        report = workdir / "out/report.md"
        r = run("report.py", "--findings", findings,
                "--judge", DEMO / "judge.json", "--ir", DEMO / "deck.json",
                "--out", report)
        # §13: the inline summary goes to stdout, verbatim, for the skill to relay
        assert "Gate 1" in r.stdout and "Gate 3" in r.stdout
        assert report.read_text().startswith("#")

    def test_both_renderers_from_the_same_ir(self, workdir):
        html, pptx = workdir / "out/deck.html", workdir / "out/deck.pptx"
        run("render_html.py", "--ir", DEMO / "deck.json",
            "--theme", ROOT / "themes/slate.json", "--out", html)
        run("render_pptx.py", "--ir", DEMO / "deck.json",
            "--theme", ROOT / "themes/slate.json", "--out", pptx)
        assert html.stat().st_size > 0 and pptx.stat().st_size > 0

    @pytest.mark.parametrize("theme", ["slate", "warm", "mono"])
    def test_every_shipped_theme_runs_the_whole_chain(self, workdir, theme):
        findings = workdir / f"{theme}.json"
        run("validate.py", "--ir", DEMO / "deck.json",
            "--theme", ROOT / f"themes/{theme}.json", "--out", findings)
        run("render_html.py", "--ir", DEMO / "deck.json",
            "--theme", ROOT / f"themes/{theme}.json",
            "--out", workdir / f"out/{theme}.html")
        run("render_pptx.py", "--ir", DEMO / "deck.json",
            "--theme", ROOT / f"themes/{theme}.json",
            "--out", workdir / f"out/{theme}.pptx")


class TestExitCodes:
    """`Every script is a pure CLI: exit 0 pass, 1 fail` — README. The skill
    branches on these, so a changed code silently changes the run flow."""

    def test_validate_exits_1_on_error_findings(self, workdir):
        run("validate.py", "--ir", ROOT / "evals/golden/02-topic-titles.json",
            "--theme", ROOT / "themes/slate.json",
            "--out", workdir / "f.json", expect=1)

    def test_validate_exits_0_on_a_clean_deck(self, workdir):
        run("validate.py", "--ir", ROOT / "evals/golden/01-good-business.json",
            "--theme", ROOT / "themes/slate.json", "--out", workdir / "f.json")

    def test_validate_exits_0_on_unverified_only(self, workdir):
        """`unverified` surfaces placeholder data but must not fail the gate —
        placeholders are legitimate, concealment is not."""
        run("validate.py", "--ir", DEMO / "deck.json",
            "--theme", ROOT / "themes/slate.json", "--out", workdir / "f.json")

    def test_report_exits_0_even_when_gates_fail(self, workdir):
        """report.py reports; validate.py gates. A failing deck must still
        produce its report, or the user cannot see why it failed."""
        findings = workdir / "f.json"
        run("validate.py", "--ir", ROOT / "evals/golden/02-topic-titles.json",
            "--theme", ROOT / "themes/slate.json", "--out", findings, expect=1)
        run("report.py", "--findings", findings,
            "--judge", ROOT / "evals/golden/judges/02-topic-titles.json",
            "--ir", ROOT / "evals/golden/02-topic-titles.json",
            "--out", workdir / "report.md")

    def test_renderer_exits_1_on_invalid_ir(self, workdir):
        run("render_pptx.py", "--ir", ROOT / "evals/golden/09-malformed.json",
            "--theme", ROOT / "themes/slate.json",
            "--out", workdir / "out/x.pptx", expect=1)


class TestGracefulDegradation:
    """The dependency split is a design claim: a missing PPTX dependency must
    not take the HTML path down, and a missing browser must not take either.
    Claims like that rot silently unless something asserts them."""

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

    def test_missing_browser_fails_only_the_pdf(self, workdir):
        """export_pdf exits 1 with a message; the HTML it was given is
        untouched and still shippable."""
        html = workdir / "out/deck.html"
        run("render_html.py", "--ir", DEMO / "deck.json",
            "--theme", ROOT / "themes/slate.json", "--out", html)
        before = html.read_bytes()
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "export_pdf.py"),
             "--html", str(html), "--out", str(workdir / "out/deck.pdf"),
             "--browser", "/nonexistent/browser"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert r.returncode == 1
        assert html.read_bytes() == before
