"""export_pdf.py — the gate logic, without needing a browser.

The actual render needs a Chromium-family binary, which no CI runner is
guaranteed to have. So the browser-dependent test skips, and everything that
does NOT need a browser is tested unconditionally: browser discovery, the
stale-output unlink, and the page-count gate.

Those three are where the real bugs were. R1-C4 was a stale PDF passing both
the size and %PDF- checks because the output was never removed first; R4-H2/H3
were the page-count gate coupling to renderer markup and hard-failing on an
unreadable count.
"""

import shutil

import pytest

import export_pdf


def _browser_available():
    try:
        return export_pdf.find_browser() is not None
    except SystemExit:
        return False
    except Exception:
        return False


needs_browser = pytest.mark.skipif(
    not _browser_available(), reason="no Chromium-family browser on this machine"
)


class TestBrowserDiscovery:
    def test_returns_executable_or_none(self):
        """Must not raise on a machine with no browser — export_pdf's contract
        is a clear message and exit 1, never a traceback."""
        try:
            found = export_pdf.find_browser()
        except SystemExit:
            found = None
        if found is not None:
            assert shutil.which(found) or str(found)


class TestStaleOutputGuard:
    def test_previous_pdf_is_removed_before_render(self, tmp_path):
        """R1-C4. A leftover file from an earlier run satisfied both the size
        and the %PDF- magic check, so a failed export reported success with
        yesterday's deck. `out.unlink(missing_ok=True)` runs before the browser
        is invoked, so even a browser that writes nothing leaves no stale file."""
        out = tmp_path / "deck.pdf"
        out.write_bytes(b"%PDF-1.4 stale content from a previous run")
        html = tmp_path / "deck.html"
        html.write_text("<html><body><div class='card '></div></body></html>")

        # A browser that exits 0 and writes nothing. Resolved rather than
        # hardcoded as /bin/true: that path exists on Linux but not on macOS,
        # where `true` lives in /usr/bin and the hardcoded form raised
        # FileNotFoundError instead of the RuntimeError under test.
        true_bin = shutil.which("true")
        assert true_bin, "no `true` on PATH"
        with pytest.raises(RuntimeError, match="no PDF"):
            export_pdf.export(str(html), str(out), browser=true_bin, cards=1)
        assert not out.exists(), "stale PDF survived a failed export"


class TestPageCountGate:
    """R4-H2/H3: this is a PAGINATION gate, not an overflow detector — a
    fixed-height card paints past its box without adding pages. What it must
    do is fail on a real mismatch and skip cleanly when the count is
    unreadable, rather than hard-failing on a compressed object stream.

    export() has no seam for this, so these drive it through a stub browser
    that writes a PDF with a known page count."""

    @staticmethod
    def _fake_browser(tmp_path, pages):
        """A shell script that writes a minimal PDF with `pages` /Type /Page
        objects to whatever --print-to-pdf= path it is handed."""
        body = "%PDF-1.4\n" + "".join(f"{i} 0 obj\n/Type /Page\nendobj\n"
                                       for i in range(1, pages + 1))
        script = tmp_path / "fake-browser"
        script.write_text(
            "#!/bin/sh\n"
            'for a in "$@"; do case "$a" in --print-to-pdf=*) '
            'out="${a#--print-to-pdf=}";; esac; done\n'
            f"printf '%s' '{body}' > \"$out\"\n"
        )
        script.chmod(0o755)
        return str(script)

    def _run(self, tmp_path, pages, cards):
        html = tmp_path / "deck.html"
        html.write_text("<html><body></body></html>")
        out = tmp_path / "deck.pdf"
        export_pdf.export(str(html), str(out),
                          browser=self._fake_browser(tmp_path, pages), cards=cards)

    def test_matching_count_passes(self, tmp_path):
        self._run(tmp_path, pages=8, cards=8)

    def test_mismatch_raises(self, tmp_path):
        with pytest.raises(RuntimeError, match="pagination broke"):
            self._run(tmp_path, pages=7, cards=8)

    def test_unreadable_count_skips_rather_than_failing(self, tmp_path, capsys):
        """pages == 0 means 'could not read', not 'zero pages' — a compressed
        object stream must not become a hard, wrong failure."""
        self._run(tmp_path, pages=0, cards=8)
        assert "gate skipped" in capsys.readouterr().err


@needs_browser
class TestRealExport:
    def test_produces_a_pdf_with_one_page_per_card(self, all_blocks, slate, tmp_path):
        """One page per card is a property of base.css — the fixed card box and
        its page-break rule. render() takes the CSS as *text* and never discovers
        it (invariant 3), so a library caller has to pass it, exactly as the CLI
        does. Calling render() without css produces an unstyled document that
        Chromium paginates by content flow: 11 cards came out as 7 pages, and the
        page-count gate caught it. That trap is filed as R13-M2."""
        import render_html
        from conftest import FIXTURES, ROOT
        html = tmp_path / "deck.html"
        pdf = tmp_path / "deck.pdf"
        # ir_dir as well as css: render_html refuses to emit an <img> that is not a
        # data URI, because "self-contained" is the file's whole promise.
        render_html.render(all_blocks, slate, str(html), ir_dir=FIXTURES,
                           css=(ROOT / "themes" / "base.css").read_text(encoding="utf-8"))
        export_pdf.export(str(html), str(pdf), browser=export_pdf.find_browser(),
                          cards=len(all_blocks["cards"]))
        assert pdf.read_bytes()[:5] == b"%PDF-"
