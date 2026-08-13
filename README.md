# deck-builder

A Claude Code plugin that turns a prompt into a presentation deck: **HTML, PDF, and
a native editable PPTX**, plus a quality report that names every number you have not
yet verified.

Claude authors exactly one thing — `deck.json`, the intermediate representation.
Two renderers read it independently; nothing is ever screenshotted, and the PPTX is
real text, real charts, real tables that open in PowerPoint and can be edited.

---

## Install

```bash
claude plugin marketplace add https://github.com/NikhileshU/PitchDeck
claude plugin install deck-builder@pitchdeck
pip install python-pptx Pillow
```

The plugin installs under `~/.claude/plugins/`, not into your working directory,
so `pip install -r requirements.txt` has nothing to resolve there. Install the two
packages by name as above — or, if you cloned the repository, run
`pip install -r requirements.txt` from the clone.

Python 3.9+. `python-pptx` and `Pillow` are needed for the PPTX renderer only.
PDF export shells out to a Chromium-family browser (Chrome, Chromium, Edge or
Brave) — if none is present, `export_pdf.py` exits 1 with a message and the HTML
and PPTX still ship.

## Use

Ask for a deck:

> Build me a deck for Thursday's exec review. We want $1.2M to dual-source APAC
> supply — Q3 revenue came in 14% under plan, and two of three suppliers missed
> committed volumes.

The `build-deck` skill establishes the archetype, writes the IR, runs the gates,
renders, and reports. Ask for a review instead and `review-deck` scores a
`deck.json` you already have without changing a line of it.

You get five files:

| File | What it is |
|---|---|
| `out/deck.pptx` | Native PowerPoint — editable text, native charts and tables |
| `out/deck.pdf` | 13.333 × 7.5 in, text selectable |
| `out/deck.html` | Self-contained; charts are server-generated inline SVG, no JavaScript |
| `out/report.md` | Unverified inputs first, then errors, warnings, concerns, scores |
| `out/report.xlsx` | The same report as data — one row per finding, dimension and concern |

---

## How it works

```
prompt → deck.json → gate 1+2 (validate.py) → gate 3 (Claude judges)
                            ↓ pass
              render_html.py  render_pptx.py     ← peers; neither reads the other
                     ↓              ↓
                export_pdf.py    report.md + report.xlsx
```

**The IR is the only source of truth.** A bad deck is fixed by regenerating
`deck.json` and re-rendering — never by hand-editing the HTML, the PPTX XML, or
the CSS. That single rule is what keeps three output formats from drifting apart.

**Renderers are peers, never chained.** `render_pptx.py` is not built from HTML;
it reads the IR and places every frame at the same point coordinates the HTML
reaches by flow. Both share one stacking model, so a block lands in the same place
in both.

### The gates

**Tier 1 — 14 deterministic checks**, no LLM: schema validity, data provenance,
claim titles, answer-first ordering, card count, title length, one message per
card, evidence present, text budgets, chart fit, speaker notes, contrast,
minimum type size, overflow. Any `error` and the deck does not ship.

**Tier 2 — Claude judges the IR** on storyline, vertical logic, archetype fit,
audience fit and density, 1–5 each. Gate: mean ≥ 3.5, nothing below 3.

**Findings carry one of five severities.** `unverified` values are placeholder data
and are listed first in every report. `concern` findings are editorial judgement
calls and are **never** auto-fixed — they exist to be handed to you.

**Overflow never gets absorbed.** Type ramps down at most 15% and never below 16pt,
and never the card title. Still too tall, and you get an `overflow` error naming the
card, because the fix is to split it. Auto-fit is explicitly disabled in the PPTX,
so PowerPoint cannot quietly shrink text that the gates said would not fit.

### Vocabulary — fixed, on purpose

**10 blocks:** `text` `bullets` `kpi` `chart` `table` `callout` `quote` `image`
`columns` `divider`
**4 layouts:** `title` `section` `content` `hero`
**4 archetypes:** `business-stakeholder` `product-demo` `startup-pitch` `idea-pitch`

If a block cannot be expressed in *both* renderers, it does not exist. The
archetype shapes the IR through its playbook; no renderer branches on it.

### Themes

`slate` (dark, default), `warm` (light warm paper, serif), `mono` (light neutral,
achromatic). Themes are JSON — both renderers read them, and `base.css` carries
layout only, with every colour and dimension a `var(--*)`. All three clear the
same contrast gates: text pairs at 4.5:1, accent at 3:1, series colours separated
by 60 in sRGB and legible on the surface they are drawn on.

Type scale and spacing are deliberately identical across all three, so switching
theme can never change whether a card overflows.

---

## Scripts

Every script is a pure CLI: exit `0` pass, `1` fail.

```bash
validate.py     --ir deck.json [--theme themes/slate.json] --out findings.json [--passes N]
render_html.py  --ir deck.json --theme themes/slate.json --out out/deck.html
render_pptx.py  --ir deck.json --theme themes/slate.json --out out/deck.pptx
export_pdf.py   --html out/deck.html --out out/deck.pdf [--cards N]
report.py       --findings findings.json --judge judge.json --ir deck.json --out out/report.md [--xlsx out/report.xlsx]
```

`validate.py` exits 1 on any `error` finding. Pass `--theme` or the contrast,
minimum-type and overflow checks silently do not run.

## Development

From a clone of the repository — `evals/`, `demo/`, `BUILD-SPEC.md` and `CLAUDE.md`
are development material and are not part of an installed plugin.

```bash
python3 evals/run_all.py                # everything below, one summary, exit 1 on any failure

python3 evals/run_golden.py             # 9 fixtures, full report output asserted
python3 evals/run_golden.py --coverage  # all 14 Tier-1 checks must fire somewhere
python3 evals/run_golden.py --update    # rebaseline — read the diff before committing
python3 evals/run_golden.py --xlsx evals/out/golden-report.xlsx   # expected vs actual, as data
python3 evals/check_catalogue.py        # does the test catalogue match the suite?
python3 evals/check_catalogue.py --todo # the remaining work list
```

`evals/pitchdeck-test-catalogue.md` is the catalogue of every case the codebase
supports. `check_catalogue.py` keeps its status column honest: it links a case to
a test by the id in the test's docstring, and fails on a `+` that is already
written, a ✓ nothing carries, or an id no table defines.

Every `pytest` run writes `evals/out/golden-report.xlsx` on the way out: a
Fixtures sheet (expected vs actual counts per fixture), a Findings sheet where
each row is marked `both`, `expected only — REGRESSION` or `actual only — NEW`,
and a Judge sheet of every dimension score. Test artifacts stay under
`evals/out/<test-name>/`, wiped at the start of each session and pruned of
directories nothing wrote to, so what remains is exactly what the run produced.

The golden set asserts the *whole* report per fixture — every finding in order, the
inline summary, and every line of `report.md` — so a wording change or a moved
constant shows up as a line diff rather than a silent pass.

Package a release:

```bash
mkdir -p dist && rm -f dist/deck-builder.plugin
zip -r dist/deck-builder.plugin .claude-plugin skills scripts themes \
    README.md requirements.txt -x '*/__pycache__/*' '*.DS_Store'
claude plugin validate .claude-plugin/plugin.json --strict
```

The archive carries the runtime only. `BUILD-SPEC.md`, `CLAUDE.md`, `evals/` and
`demo/` are development material and stay in the repository.

## Known limits

- **PDF export needs a local Chromium-family browser.** Verified against Brave and
  Chrome. There is no pure-Python fallback; the other three artifacts do not
  depend on it.
- **Installation is verified in Claude Code.** The Cowork runtime has not been
  tested from here — the skills and scripts use `${CLAUDE_PLUGIN_ROOT}` throughout
  and shell out only to `python3` and a browser, but that is an expectation, not a
  measurement.
- **Placeholder data is legitimate; unlabelled placeholder data is not.** Every
  chart, table and KPI carries a `source` of `user`, `derived` or `placeholder`,
  and the report lists every placeholder before anything else. Confirm them before
  you present.
- **No JavaScript in rendered HTML**, no animations, no transitions, no SmartArt,
  and no pixel parity between HTML and PPTX — the two agree on geometry, not on
  text wrapping.

## Licence

Single-user project, no licence granted.
