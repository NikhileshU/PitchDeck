# deck-builder — Build Specification

**Read this whole file before writing any code.** This is the complete spec for a Claude plugin that generates presentation decks. Decisions here are settled; do not re-litigate them. Where something is unspecified, ask rather than invent.

Companion doc: `ADR-001-deck-builder.md` explains *why* these choices were made. This file is *what to build*.

---

## 0. Goal and constraints

Build a single-user Claude plugin that turns a prompt into a presentation deck, emitting three artifacts (HTML, PDF, native editable PPTX) plus a quality report.

| Constraint | Consequence |
|---|---|
| One user, no distribution | No auth, no database, no web UI, no API server |
| Zero marginal cost | Claude is the LLM layer. No external API keys, no local model |
| Must not look AI-generic | Design tokens and layout discipline carry the quality |
| PPTX must be editable | Real text, native charts, native tables — never screenshots |
| Four deck archetypes | business-stakeholder, product-demo, startup-pitch, idea-pitch |

**Out of scope:** animations, transitions, SmartArt, collaboration, multi-user, pixel parity between HTML and PPTX.

---

## 1. Invariants

These are non-negotiable. Violating any one of them breaks the architecture.

1. **`deck.json` (the IR) is the only source of truth.** To fix a bad deck, regenerate the IR and re-render. Never hand-edit generated HTML, PPTX XML, or CSS to correct deck content.
2. **Renderers are peers, never chained.** `render_html` and `render_pptx` both read the IR independently. PPTX is never produced from HTML.
3. **Renderers are pure functions:** `render(ir: dict, theme: dict, out_path: str) -> None`. No globals, no environment reads, no network. All paths passed in as arguments.
4. **`base.css` contains layout rules only.** Every colour, size, and spacing value is `var(--*)`. A hardcoded hex in `base.css` means the two renderers have silently diverged.
5. **Themes are JSON, not CSS.** `render_pptx.py` cannot parse CSS. Both renderers read `themes/*.json`.
6. **No archetype logic in renderers.** If `render_html.py` or `render_pptx.py` ever contains `if archetype == ...`, the separation is broken. Archetype shapes the IR (prompt-side), never the rendering.
7. **If a block type cannot be expressed in both renderers, it does not get added.** Vocabulary is capped at 10 block types and 4 card layouts.
8. **All internal paths use `${CLAUDE_PLUGIN_ROOT}`.** Never hardcode absolute paths.
9. **Every run emits a report.** A silent pass is indistinguishable from an unchecked run.
10. **No MCP servers, no hooks, no agents.** Two skills, five scripts, some data files.

---

## 2. File tree

```
deck-builder/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── build-deck/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── card-schema.md
│   │       ├── block-types.md
│   │       ├── business-stakeholder.md
│   │       ├── product-demo.md
│   │       ├── startup-pitch.md
│   │       └── idea-pitch.md
│   └── review-deck/
│       └── SKILL.md
├── themes/
│   ├── base.css
│   ├── slate.json
│   ├── warm.json
│   └── mono.json
├── scripts/
│   ├── render_html.py
│   ├── render_pptx.py
│   ├── export_pdf.py
│   ├── validate.py
│   └── report.py
├── evals/
│   ├── run_golden.py                   test harness — not a shipped script
│   └── golden/
│       ├── 01-good-business.json
│       ├── 02-topic-titles.json        (bad: titles are noun phrases)
│       ├── 03-buried-answer.json       (bad: recommendation on card 9)
│       ├── 04-overflow.json            (bad: two cards overflow; one sits at ~99%)
│       ├── 05-placeholder-data.json    (bad: unlabelled invented metrics)
│       ├── 06-warn-titles.json         (warn path: noun-phrase titles, no error)
│       ├── 07-good-pitch.json
│       ├── 08-bad-theme.json           (bad: theme fails contrast and min-type)
│       ├── 09-malformed.json           (bad: schema-valid and the shape checks)
│       ├── judges/                     fixed judge.json input, one per fixture
│       ├── themes/                     broken themes, shadowing themes/ by name
│       ├── runs.json                   per-fixture passes and resolved findings
│       └── expected/                   one .json per fixture
├── requirements.txt
└── README.md
```

---

## 3. Units

**One rule: every dimension in the theme and IR is in points (pt).**

- Card canvas: **960pt × 540pt** (16:9, equals 13.333in × 7.5in)
- `render_html.py` multiplies every pt value by **4/3** to get CSS px → canvas renders at 1280×720 px
- `render_pptx.py` uses pt directly via `Pt()`; for EMU, `1pt = 12700 EMU`

This makes HTML and PPTX dimensionally identical by construction. Do not introduce a second unit anywhere.

---

## 4. Schema — `deck.json`

```jsonc
{
  "schema": "1.0",                          // required; do not omit
  "meta": {
    "title": "Q3 Launch Review",
    "archetype": "business-stakeholder",    // business-stakeholder | product-demo | startup-pitch | idea-pitch
    "theme": "slate",                       // filename stem in themes/
    "aspect": "16:9"                        // only value supported in v1
  },
  "cards": [
    {
      "id": "c1",                           // stable, unique, referenced by the report
      "layout": "title",                    // title | section | content | hero
      "title": "Q3 Launch Review",
      "subtitle": "Commercial Ops · August 2026",   // title/section layouts only
      "role": null,                         // null | recommendation | problem | solution | ask | appendix
      "blocks": [],
      "notes": null
    },
    {
      "id": "c2",
      "layout": "content",
      "title": "APAC supply constraints cut Q3 revenue 14%",
      "role": "recommendation",
      "blocks": [
        {
          "id": "b1",
          "type": "chart",
          "chart": "bar",                   // bar | hbar | line | pie
          "caption": "Revenue by region, Q1–Q3 (US$M)",
          "source": "user",                 // user | derived | placeholder   ← REQUIRED on chart/table/kpi
          "data": {
            "categories": ["Q1", "Q2", "Q3"],
            "series": [{ "name": "APAC", "values": [4.2, 4.0, 3.4] }]
          }
        },
        {
          "id": "b2",
          "type": "callout",
          "tone": "warn",                   // info | warn | good
          "text": "Two of three APAC suppliers missed committed volumes."
        }
      ],
      "notes": "Lead with the number. The vendor question comes next."
    }
  ]
}
```

### Field rules

- `card.title` is a **first-class field, never a block.** The action-title checks depend on this.
- `card.id` and `block.id` are stable and unique across the deck. Required — the report references them and per-block regeneration needs them.
- `role` drives the `answer-first` check. Set it on cards that carry structural weight; `null` otherwise.
- `source` is **required** on `chart`, `table`, and `kpi` blocks. Absent → Tier-1 error.
- `notes` (speaker notes) expected on every `content` card.

---

## 5. Block types (exactly 10)

| `type` | Fields | HTML | PPTX |
|---|---|---|---|
| `text` | `text`, `emphasis?` (`bool`) | `<p class="b-text">` | text frame |
| `bullets` | `items[]` (≤6) | `<ul class="b-bullets">` | bulleted text frame |
| `kpi` | `value`, `label`, `delta?`, `source` | `<div class="b-kpi">` | grouped text boxes |
| `chart` | `chart`, `data`, `caption?`, `source` | **inline SVG** | **native PPTX chart** |
| `table` | `headers[]`, `rows[][]`, `source` | `<table class="b-table">` | **native PPTX table** |
| `callout` | `tone`, `text` | `<div class="b-callout b-callout--{tone}">` | rounded rect + text |
| `quote` | `text`, `attribution?` | `<blockquote class="b-quote">` | text frame |
| `image` | `src`, `alt`, `fit?` (`cover`\|`contain`) | `<img class="b-image">` | picture |
| `columns` | `children[][]` (2 or 3 arrays of blocks) | CSS grid | side-by-side frames |
| `divider` | — | `<hr class="b-divider">` | line shape |

**Charts are data, never images.** HTML gets inline SVG generated in Python — no JavaScript, so headless-Chrome PDF export is deterministic. PPTX gets a native chart object so it stays editable and on-theme.

`columns` may nest one level only. A `columns` block may not contain another `columns`.

---

## 6. Card layouts (exactly 4)

| `layout` | Use | Rendering |
|---|---|---|
| `title` | Deck opener | Centred title + subtitle, accent rule |
| `section` | Divider between sections | Large centred title on `surface` background |
| `content` | Default working card | Title at top, blocks stacked below with `blockGap` |
| `hero` | Single statement or full-bleed image | Title only, or one `image`/`kpi` block at large scale |

---

## 7. Schema — `themes/*.json`

```jsonc
{
  "name": "slate",
  "color": {
    "bg":      "#0F1419",
    "surface": "#1A2027",
    "text":    "#E8EAED",
    "muted":   "#9AA4AF",
    "accent":  "#4F9CF9",
    "series":  ["#4F9CF9", "#7C5CFF", "#2DD4A7", "#F2B13C", "#F27A7A"],
    "tone":    { "info": "#4F9CF9", "warn": "#F2B13C", "good": "#2DD4A7" }
  },
  "type": {
    "family":   "Inter, system-ui, sans-serif",
    "familyMono": "ui-monospace, monospace",
    "scale": {                              // POINTS
      "title":     40,
      "cardTitle": 28,
      "body":      18,
      "caption":   12
    },
    "lineHeight": 1.35
  },
  "space": {                                // POINTS
    "cardPad":  42,
    "blockGap": 18,
    "radius":    9
  }
}
```

`render_html.py` emits these as CSS custom properties (`--color-bg`, `--type-body`, `--space-cardPad`, …) after ×4/3 conversion for dimensional values. `render_pptx.py` reads them directly.

---

## 8. Layout and overflow

Content area = `960 − 2×cardPad` wide × `540 − 2×cardPad` tall.

`content` cards stack: title, then blocks separated by `blockGap`.

**Overflow policy — implement exactly this, do not improvise:**

1. Measure total content height.
2. If it exceeds the content area, scale the block-level type ramp down by up to **15%** (`body` and `caption` only; never the card title).
3. If it still overflows, **do not clip and do not shrink further.** Emit a Tier-1 `overflow` error naming the card. The IR gets revised to split the card.

---

## 9. Script contracts

All scripts are CLI-invocable and importable. Exit code `0` = success, `1` = failure.

```bash
validate.py     --ir deck.json [--theme themes/slate.json] --out findings.json
render_html.py  --ir deck.json --theme themes/slate.json --out out/deck.html
render_pptx.py  --ir deck.json --theme themes/slate.json --out out/deck.pptx
export_pdf.py   --html out/deck.html --out out/deck.pdf
report.py       --findings findings.json --judge judge.json --ir deck.json --out out/report.md
```

`validate.py` exits `1` if any finding has severity `error`.

### `findings.json`

```jsonc
{
  "deck": "Q3 Launch Review",
  "passes": 2,
  "findings": [
    {
      "check": "one-message",
      "severity": "warn",                   // unverified | error | warn | concern | info
      "card": "c5",
      "block": "b3",                        // nullable
      "message": "5 blocks on one content card",
      "resolved": true                      // true if a revision pass fixed it
    }
  ]
}
```

### `judge.json` (written by Claude, not by a script)

```jsonc
{
  "scores": {
    "storyline":    { "score": 4, "note": "..." },
    "verticalLogic":{ "score": 4, "note": "..." },
    "archetypeFit": { "score": 5, "note": "..." },
    "audienceFit":  { "score": 4, "note": "..." },
    "density":      { "score": 3, "note": "..." }
  },
  "concerns": [
    { "card": "c6", "message": "Restates c4's point in different words — candidate for cutting" }
  ]
}
```

---

## 10. Evals — Tier 1 (`validate.py`, deterministic, no LLM)

| Check | Rule | Severity |
|---|---|---|
| `schema-valid` | Conforms to §4; required fields present; ids unique | error |
| `data-provenance` | Every `chart`/`table`/`kpi` has `source`; every `placeholder` is collected for the report | error |
| `title-is-claim` | Every `content` card title contains a finite verb; is not a bare noun phrase | warn; **error** when the title has ≤3 alphabetic tokens AND no strong figure AND no verb token (deterministic heuristics cannot grade English claims at error severity — the Tier-2 judge owns claim quality, §11) |
| `answer-first` | `business-stakeholder`, `idea-pitch`: a card with `role: recommendation` appears within the first 3 | error |
| `card-count` | startup-pitch ≤15, product-demo ≤12, idea-pitch ≤10, business-stakeholder ≤20 excluding `role: appendix` | error |
| `overflow` | Card fits after the 15% ramp-down floor (§8) | error |
| `contrast` | Every text-on-background token pair ≥ 4.5:1 (WCAG AA); `muted` on `bg` ≥ 4.5:1 | error |
| `min-type-size` | `type.scale.body` ≥ 16pt after any ramp-down | error |
| `title-length` | Card title ≤ 14 words | warn |
| `one-message` | ≤4 blocks per `content` card; ≤1 `chart` per card | warn |
| `evidence-present` | Every `content` card has ≥1 non-`text` block, or a figure in its title | warn |
| `text-budget` | `text` ≤240 chars; `bullets` ≤6 items ×90 chars; `callout` ≤140 chars | warn |
| `chart-fit` | time series → `line`; categorical comparison → `bar`/`hbar`; part-to-whole with ≤5 slices → `pie`, else `bar` | warn |
| `notes-present` | Speaker notes on every `content` card | info |

**Gate: zero `error` findings.**

`data-provenance` is an error rather than a warning because a fabricated metric rendered in a clean chart is indistinguishable from a real one. Placeholder data is legitimate; unlabelled placeholder data is not.

---

## 11. Evals — Tier 2 (Claude judges the IR, 1–5)

Scored by Claude reading `deck.json` against the archetype playbook. Written to `judge.json`.

| Dimension | Question |
|---|---|
| `storyline` | Read only the card titles in order. Do they form a coherent, persuasive argument? |
| `verticalLogic` | Does each card's evidence prove that card's title — and nothing else? |
| `archetypeFit` | Are the playbook's required sections present, in the prescribed order? |
| `audienceFit` | Are the metrics and framing right for this audience? |
| `density` | Is each card absorbable in under 30 seconds without narration? |

**Gate: mean ≥ 3.5 and no single dimension below 3.**

Claim quality of card titles is an **error-grade Tier-2 responsibility**: the judge reads titles with real language understanding and scores non-claim titles down in `storyline`/`verticalLogic`. Tier-1's `title-is-claim` only warns, except for the narrow deterministic error in §10.

Claude also emits up to **5 concerns** — editorial observations that break no rule (redundant cards, unquantified asks, missing baselines, unsupported assumptions).

---

## 12. Severity taxonomy

| Level | Meaning | Behaviour |
|---|---|---|
| `unverified` | Placeholder or unconfirmed factual input | Surfaced **first**, always |
| `error` | Hard rule violated | Blocks output. Auto-revise, max 3 passes. Still failing → surface, do not ship |
| `warn` | Soft rule breached | One auto-revision attempt; surfaced either way |
| `concern` | Judgment call, no rule broken | **Never auto-fixed.** Surfaced for the human |
| `info` | Noted | Surfaced only in `report.md` |

Concerns are never auto-resolved. Auto-fixing one means the agent silently overruling an editorial judgment it is not equipped to make.

`info` findings surface in `report.md` §3 (Warnings) under **"Also noted"** — they have no section of their own. Phase-10 expected-output files assert against this placement.

---

## 13. Run flow

```
1   User request                                  (Cowork or Claude Code)
2   build-deck skill triggers → load playbook     references/<archetype>.md
3   Claude emits deck.json                        IR only — never HTML, never XML
4   validate.py --ir deck.json                    ── gate 1 + 2
5   Claude scores Tier 2 → judge.json             ── gate 3
6   Any gate fails → revise deck.json → goto 4    max 3 passes
7   render_html.py  +  render_pptx.py             peers, independent
8   export_pdf.py                                 headless Chrome
9   report.py → out/report.md
10  Present out/deck.pptx, deck.pdf, deck.html, report.md
    + inline summary in chat
```

### Inline summary (every run, verbatim shape)

```
Q3 Launch Review · business-stakeholder · slate · 11 cards · 2 revision passes

Gate 1  schema         ✓
Gate 2  deterministic  ✓  0 errors · 3 warnings
Gate 3  judged         4.2 / 5   (lowest: density 3)

⚠  4 unverified values — charts on c4, c7 use placeholder data
!  3 concerns raised — see report.md
```

### `report.md` sections, in this order

1. **Unverified inputs** — every `placeholder` value, by card. First, always.
2. **Errors** — what failed, which card, what the revision changed.
3. **Warnings** — same, plus anything auto-revision could not resolve.
4. **Concerns** — one line each, card-referenced.
5. **Tier-2 scorecard** — five dimensions, score, one-sentence justification.
6. **Revision log** — what changed between passes.

---

## 14. Build order

Each phase has a checkpoint. Do not start the next phase until the checkpoint passes.

| # | Phase | Checkpoint |
|---|---|---|
| 0 | **Verify runtime.** `pip install python-pptx`; confirm it opens and saves a file. Confirm whether headless Chrome exists. | Report findings before writing anything. If python-pptx is unavailable, stop and raise it. |
| 1 | Write `card-schema.md` and `block-types.md` from §4–§6. **Freeze them.** | Both renderers will be written against these. Changing them later means rewriting both. |
| 2 | `themes/slate.json` + `themes/base.css` (layout only, all `var(--*)`) | Grep `base.css` for `#` — zero hex literals. All contrast pairs ≥4.5:1. |
| 3 | `render_html.py` — block-type switch, inline SVG charts | Renders all 10 block types and all 4 layouts from a hand-written fixture. |
| 4 | `export_pdf.py` — headless Chrome | PDF is 13.333×7.5in, text selectable. |
| 5 | `validate.py` Tier 1 — all 14 checks | Passes `01-good-business.json`; catches the specific defect in each bad fixture. |
| 6 | `report.py` — build alongside §5, not after | Produces both the inline summary and `report.md` from `findings.json` + `judge.json`. |
| 7 | `business-stakeholder.md` playbook + `build-deck/SKILL.md` | — |
| 8 | **Generate one real deck end to end.** | Open the PDF. Read the report. Go/no-go before continuing. |
| 9 | `render_pptx.py` — peer renderer against the frozen IR | Same fixture as phase 3. Text is selectable; charts and tables are native objects. **Peer agreement:** `all-blocks.json` through both renderers — same block order, same top edge (card-schema.md §5.1). |
| 10 | Golden set — 9 fixtures (01–09; the pitch fixture is `07-good-pitch.json`, since 06 asserts the title-warn path; 08 and 09 exist to exercise the theme and schema checks no deck fixture reaches) + `expected/` | Assert on full report output, not just pass/fail: `python3 evals/run_golden.py` → 9/9, comparing every finding, the inline summary and every line of `report.md`. Judge input is fixed per fixture in `golden/judges/`. **Coverage:** `python3 evals/run_golden.py --coverage` → 14/14 Tier-1 checks fired; a check no fixture reaches could be silently broken and still ship green. |
| 11 | Remaining 3 playbooks, `warm.json`, `mono.json`, `review-deck/SKILL.md` | — |
| 12 | `plugin.json`, `README.md`, `requirements.txt`; package as `.plugin` | Structure validates; installs in Claude Code and Cowork. |

---

## 15. Do not

- Do not write OOXML by hand. If python-pptx cannot do something, drop the feature or change the block spec — do not work around it in raw XML.
- Do not add a config framework, plugin system, or abstraction layer for a second LLM provider.
- Do not add block types or card layouts beyond the 10 and 4 specified.
- Do not let `render_html.py` or `render_pptx.py` exceed **400 lines** each. If either does, the block switch has grown logic that belongs elsewhere.
- Do not introduce a class hierarchy. Plain functions and dicts.
- Do not use JavaScript in the rendered HTML. Charts are server-generated SVG.
- Do not put archetype names anywhere in `scripts/`.
- Do not auto-fix a `concern`.
- Do not ship a deck with unresolved `error` findings.

---

## 16. Open question to resolve in phase 0

If headless Chrome is unavailable in the Cowork runtime, PDF export becomes Claude Code-only, or LibreOffice headless becomes the fallback. Report which is the case before proceeding to phase 4 — do not silently pick one.
