"""The two hand-tuned heuristics — `_is_claim` and `_block_h`.

Both were rewritten repeatedly against probe sets that lived only in review
transcripts. That is the worst place for them: the next person to touch the
lexicon cannot see what previously moved. This file is that corpus, committed.

`_is_claim` is a deterministic approximation of English POS and will never
reach 100%. The point is not perfection — it is that a change shows you
exactly which titles flipped.
"""

import json

import pytest

from validate import _block_h, _is_claim, _ratio, _text_lines, check_contrast

# --------------------------------------------------------------------------
# _is_claim — every probe from the review rounds, with provenance.
# True  = reads as a claim (no finding)
# False = reads as a noun phrase / label (finding)
# --------------------------------------------------------------------------

CLAIM_CORPUS = [
    # --- labels that must be caught (round 3 baseline) ---
    ("Cost Reduction Plan", False, "r3: lemma 'cost' anywhere used to pass it"),
    ("Marketing Spend Overview", False, "r3: lemma 'spend'"),
    ("Advanced Analytics Roadmap", False, "r3: -ed on an adjective"),
    ("Revenue Growth Drivers", False, "r3"),
    ("Pricing Committee Update", False, "r3"),
    ("Headcount Freeze", False, "r3"),
    # --- round 4: casing heuristic false positives ---
    ("Needs Assessment Framework", False, "r4: AUX 'needs' in noun position"),
    ("Q4 Under Review", False, "r4: digit + directional, but Q4 is not a figure"),
    ("The cost of delay", False, "r4: sentence-case noun phrase"),
    ("Our supply chain risk", False, "r4"),
    ("A build vs buy decision", False, "r4: bare vs-comparison, no figure"),
    # --- round 5: real claims the lexicon used to miss ---
    ("Latency regressions correlate with the new cache", True, "r5: 'correlate'"),
    ("Support costs scale linearly with seats", True, "r5: 'scale'"),
    ("Pricing power sits with the buyer now", True, "r5: 'sits'"),
    # --- round 5: false positives on unseen labels ---
    ("Product Launch Timeline", False, "r5: 'launch' in noun position"),
    ("Onboarding Funnel Drop Off", False, "r5: 'drop' in noun position"),
    # --- casing must not decide (round 4 false negatives) ---
    ("Revenue Fell 14% In Q3", True, "r4: Title Case claim"),
    ("REVENUE FELL 14% IN Q3", True, "r4: all caps claim"),
    ("Revenue grew 12% in Q3", True, "baseline"),
    # --- subject-verb-object is a claim even Title-Cased ---
    ("Data Migration Has Risk", True, "r5: reviewer conceded this one"),
    # --- figure-carrying verb-less claims ---
    ("Churn up 12% since April", True, "r3: strong figure + directional"),
    ("Three risks ahead of launch", True, "r3"),
    # --- imperatives open a claim (the recommendation-title formula) ---
    ("Approve $1.2M to dual-source APAC supply now", True, "playbook example"),
    ("Two of three APAC suppliers missed committed volumes", True, "playbook example"),
    # --- longer noun phrases: warn path, still not claims ---
    ("Competitive Landscape and Market Review", False, "fixture 06"),
    ("Unit Economics Deep Dive", False, "fixture 06"),
    ("Roadmap Sequencing and Scope Options", False, "fixture 06"),
    ("Churn Rate by Segment", False, "r9 corpus"),
    ("FY26 Planning Assumptions", False, "r9 corpus"),
    ("Top 3 Growth Levers", False, "r9: single digit is not a strong figure"),
    # --- short past-tense claims must survive the narrow-error rule ---
    ("Margins collapsed", True, "r8: -ed clause"),
    ("Pilots underperformed", True, "r8: -ed clause"),
    ("Runway shortened", True, "r8: -ed clause"),
    ("Demand softened", True, "r8: -ed clause"),
    # --- documented residuals: WRONG, and pinned so a fix is visible ---
    pytest.param("Margins compress", True, "r8 residual: out-of-lexicon verb",
                 marks=pytest.mark.xfail(reason="documented residual", strict=True)),
    pytest.param("Latency spikes", True, "r8 residual: noun/verb homonym",
                 marks=pytest.mark.xfail(reason="documented residual", strict=True)),
]


def _label(case):
    # pytest.param is itself a NamedTuple, so check for .values first.
    return getattr(case, "values", case)[0]


@pytest.mark.parametrize("title,is_claim,why", CLAIM_CORPUS,
                         ids=[_label(c) for c in CLAIM_CORPUS])
def test_is_claim(title, is_claim, why):
    assert _is_claim(title) is is_claim, f"{why}"


# --------------------------------------------------------------------------
# _block_h — the overflow estimator (R3-S3).
# Phase 8 measured 7 real cards in Chromium: the estimator ran conservative by
# ~5pp across a 35-84% fill band. 04-overflow pins one boundary point at 98.8%;
# this pins the band, so a constant that drifts shows up as a number, not as a
# fixture that happens to still pass.
# --------------------------------------------------------------------------

class TestBlockHeight:
    def test_monotonic_in_content(self, slate):
        """More content is never shorter. Sounds trivial; a ramp-floor bug
        breaks it."""
        w = 876.0
        short = {"type": "text", "text": "one line"}
        long = {"type": "text", "text": "word " * 200}
        assert _block_h(long, slate, w, 1.0) > _block_h(short, slate, w, 1.0)

    def test_narrower_width_is_taller(self, slate):
        b = {"type": "text", "text": "word " * 60}
        assert _block_h(b, slate, 400.0, 1.0) > _block_h(b, slate, 876.0, 1.0)

    def test_ramp_floor_reduces_height(self, slate):
        """The 15% ramp must actually buy vertical space, or the overflow
        policy is decorative."""
        b = {"type": "text", "text": "word " * 120}
        assert _block_h(b, slate, 876.0, 0.85) < _block_h(b, slate, 876.0, 1.0)

    def test_caption_adds_height(self, slate):
        bare = {"type": "chart", "chart": "bar"}
        capped = {"type": "chart", "chart": "bar", "caption": "A caption"}
        assert _block_h(capped, slate, 876.0, 1.0) > _block_h(bare, slate, 876.0, 1.0)

    def test_theme_invariant_geometry(self):
        """R11-N4: type scale and spacing are identical across themes so that
        theme choice can never change whether a card overflows. If someone
        gives warm a roomier cardPad, this is the test that objects."""
        from conftest import theme_for
        b = {"type": "text", "text": "word " * 80}
        heights = {n: _block_h(b, theme_for(n), 876.0, 1.0)
                   for n in ("slate", "warm", "mono")}
        assert len(set(heights.values())) == 1, heights

    @pytest.mark.parametrize("size,width,at_least", [(18, 876.0, 1), (18, 100.0, 3)])
    def test_text_lines_wraps(self, size, width, at_least):
        assert _text_lines("word " * 20, size, width) >= at_least


# --------------------------------------------------------------------------
# Theme contrast — every shipped theme must pass its own gate.
# A theme is data, so this is the cheapest possible regression guard.
# --------------------------------------------------------------------------

class TestShippedThemes:
    @pytest.mark.parametrize("name", ["slate", "warm", "mono"])
    def test_theme_passes_its_own_contrast_gate(self, name):
        from conftest import theme_for
        assert check_contrast(theme_for(name)) == [], (
            f"{name} fails the contrast gate it ships under"
        )

    @pytest.mark.parametrize("name", ["slate", "warm", "mono"])
    def test_all_series_pairs_separated(self, name):
        """R11-M2: the check compared array neighbours only, so warm's series
        1 and 4 sat 48.6 apart, unflagged, side by side in any 4-series chart."""
        import itertools
        from conftest import theme_for
        s = theme_for(name)["color"]["series"]
        rgb = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
        for a, b in itertools.combinations(s, 2):
            d = sum((x - y) ** 2 for x, y in zip(rgb(a), rgb(b))) ** 0.5
            assert d >= 60, f"{name}: {a}/{b} separated by only {d:.1f}"

    @pytest.mark.parametrize("name", ["slate", "warm", "mono"])
    def test_every_series_legible_on_surface(self, name):
        """R11-M3: mono's fifth series measured 2.02:1 on the surface it was
        drawn on. Capping mono at four was the fix; this keeps it capped."""
        from conftest import theme_for
        t = theme_for(name)["color"]
        for i, v in enumerate(t["series"]):
            r = _ratio(v, t["surface"])
            assert r >= 3.0, f"{name}: series[{i}] {v} is {r:.2f}:1 on surface"
