"""check_catalogue.py — the tool that keeps the catalogue honest.

Round 14 found three defects in it in a single pass, all of the same kind: the
tool reported more coverage than existed. That is the worst direction for a
coverage tool to be wrong in, so its own behaviour is pinned here.

Every fixture uses synthetic ids (`ZZ-`, `QQ-`) written to temporary files, with
`CATALOGUE` and `SUITE` monkeypatched. Real ids must never appear in this
module's docstrings — the tool scans `evals/test_*.py`, so a real id here would
report itself as covered.
"""

import pytest

import check_catalogue as CC


def _catalogue(tmp_path, body):
    p = tmp_path / "cat.md"
    p.write_text(body, encoding="utf-8")
    return p


def _suite(tmp_path, body):
    p = tmp_path / "test_sample.py"
    p.write_text(body, encoding="utf-8")
    return [p]


class TestStatusParsing:
    """R14-M1: a cell holding both marks means half the case is written. Testing
    for the tick first counted seven such rows as done and dropped the other half
    out of the work list entirely."""

    CAT = """## 1. Section one

| # | Check | Positive case | Negative case | Status |
|---|---|---|---|---|
| ZZ-01 | done both ways | fires | clean | ✓ (09) / ✓ |
| ZZ-02 | half written | fires | clean | ✓ (09) / + |
| ZZ-03 | not written | fires | clean | + |
| ZZ-04 | fully done | fires | | ✓ |

## 2. Out of scope

| # | Case | Why |
|---|---|---|
| ○-01 | needs a human | judgement |
"""

    def test_mixed_cell_is_partial_not_done(self, tmp_path):
        cases, unparsed = CC.parse_catalogue(_catalogue(tmp_path, self.CAT))
        assert cases["ZZ-02"]["status"] == CC.PARTIAL
        assert cases["ZZ-01"]["status"] == CC.DONE, "two ticks is done, not partial"
        assert cases["ZZ-03"]["status"] == CC.TODO
        assert cases["ZZ-04"]["status"] == CC.DONE
        assert not unparsed

    def test_out_of_scope_rows_parse_without_a_status_column(self, tmp_path):
        cases, unparsed = CC.parse_catalogue(_catalogue(tmp_path, self.CAT))
        assert cases["○-01"]["status"] == CC.SCOPE
        assert not unparsed, "a table with no Status column must not read as broken"

    def test_wide_tables_keep_both_expectation_columns(self, tmp_path):
        cases, _ = CC.parse_catalogue(_catalogue(tmp_path, self.CAT))
        assert cases["ZZ-01"]["expect"] == "fires / clean"


class TestLinking:
    """R14-M2: linking was file-level, so a module docstring, a section banner or
    a comment from a deleted test all read as coverage."""

    SUITE = '''"""Module docstring mentioning ZZ-01, which is not a link."""

# ZZ-02..ZZ-04 — a section banner, also not a link


class TestThing:
    """Class docstring mentioning ZZ-03, still not a link."""

    def test_real(self):
        """ZZ-04. This one is a link: a test function docstring."""

    def test_untagged(self):
        # ZZ-01 in a comment is not a link either
        pass


def helper_mentions(x):
    """ZZ-02 in a helper docstring is not a test."""
'''

    @pytest.fixture
    def hits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(CC, "SUITE", _suite(tmp_path, self.SUITE))
        return CC.scan_suite(["ZZ-01", "ZZ-02", "ZZ-03", "ZZ-04"])

    def test_only_test_function_docstrings_count(self, hits):
        assert hits["ZZ-04"], "a test docstring must link"
        assert not hits["ZZ-01"], "module docstring and comments must not link"
        assert not hits["ZZ-03"], "a class docstring must not link"

    def test_range_banner_endpoints_do_not_link(self, hits):
        assert not hits["ZZ-02"], "`ZZ-02..ZZ-04` names a span, not a case"

    def test_report_names_the_test_not_the_file(self, hits):
        assert hits["ZZ-04"] == ["test_sample.py::TestThing::test_real"]


class TestUnknownIds:
    """R14-L3: the sweep required exactly two digits, so a one- or three-digit id
    slipped through — fine for today's numbering, silently wrong the moment a
    section passes 99 cases."""

    @pytest.mark.parametrize("ident", ["QQ-1", "QQ-007", "QQ-100"])
    def test_ids_outside_two_digits_are_still_seen(self, ident, tmp_path, monkeypatch):
        body = f'def test_x():\n    """{ident}. An id no table defines."""\n'
        monkeypatch.setattr(CC, "SUITE", _suite(tmp_path, body))
        monkeypatch.setattr(CC, "CATALOGUE", _catalogue(
            tmp_path, "## 1. S\n\n| # | Case | Expect | Status |\n|---|---|---|---|\n"
                      "| ZZ-01 | a case | fires | ✓ |\n"))
        assert CC.main([]) == 1, f"{ident} should be reported as unknown"


class TestExitCodes:
    """Factual errors in the catalogue fail the run; the backlog of untagged
    tests does not, or the check would be red from birth and learned to ignore."""

    def _setup(self, tmp_path, monkeypatch, status, doc):
        monkeypatch.setattr(CC, "CATALOGUE", _catalogue(
            tmp_path, f"## 1. S\n\n| # | Case | Expect | Status |\n|---|---|---|---|\n"
                      f"| ZZ-09 | a case | fires | {status} |\n"))
        monkeypatch.setattr(CC, "SUITE", _suite(tmp_path, doc))

    def test_undercounted_fails(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, "+",
                    'def test_x():\n    """ZZ-09. Written after all."""\n')
        assert CC.main([]) == 1

    def test_unbacked_passes_by_default_and_fails_under_strict(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, "✓", "def test_x():\n    pass\n")
        assert CC.main([]) == 0
        assert CC.main(["--strict"]) == 1
