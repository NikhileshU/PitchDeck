# ADR-001: Deck Builder — Gamma-style architecture with dual peer renderers

**Status:** Accepted — Option C
**Date:** 2026-08-11
**Deciders:** Nikhilesh (sole)
**Scope:** Single-user Claude plugin. Built in Claude Code, consumed in Claude Code and Cowork. Multi-user is explicitly out of scope; see *Consequences → To revisit*.

---

## Context

**Goal.** Generate presentation decks across four archetypes — business/stakeholder, product demo, startup pitch, idea pitch — without paying for a commercial AI deck tool.

**Forces.**

| Force | Implication |
|---|---|
| Single user, no distribution problem | No auth, no multi-tenancy, no UI. Conversation is the interface. |
| Zero marginal cost required | LLM layer must be the existing Claude subscription, not an API key. |
| Must not look AI-generic | Design system quality is the differentiator, not generation cleverness. |
| Output sometimes needs to be editable | PPTX must contain real text, not screenshots. |
| Built with Claude Code | Favour CSS and small Python over layout geometry math. |
| Archetypes differ structurally, not visually | Structure lives in prompts; visuals live in themes. Keep them separate. |

**Non-goals.** Real-time collaboration. Animations, transitions, SmartArt. Pixel parity between HTML and PPTX. Anyone else using this.

---

## Decision

Adopt Gamma's **layer separation** (content model → design tokens → auto-layout → render) but replace its **lossy export chain** with **two peer renderers reading one intermediate representation**.

```
                                   ┌──→ render_html.py ──→ HTML ──→ export_pdf.py ──→ PDF
archetype playbook → Claude → deck.json (IR) ──┤
                                   └──→ render_pptx.py ──→ .pptx (native, editable)
                                        ▲
                          theme.json ───┘  (both renderers read the same tokens)
```

The IR is the contract. Renderers are peers, never chained. Nothing downstream of the IR is ever hand-edited by the agent — corrections go back to the IR and re-render.

---

## Options Considered

### Option A: True Gamma — HTML source of truth, convert to PPTX

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Output quality (web/PDF) | High |
| Output quality (PPTX) | Poor — rasterized or approximated |
| Effort | Lowest |

**Pros:** Least code. Best-looking HTML. No dual maintenance.
**Cons:** Inherits Gamma's single worst-reviewed weakness. Computed CSS layout has no faithful mapping to PPTX's absolutely-positioned shape model.

### Option B: PPTX-template-first (python-pptx + `.potx`)

| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Output quality (PPTX) | High — fully editable, on-theme |
| Output quality (web/PDF) | None without a second path |
| Effort | High — template built by hand |

**Pros:** Native PowerPoint output. Charts and tables stay editable.
**Cons:** Placeholder-index fragility (silent failures). python-pptx autofit does not recompute until PowerPoint opens the file, so text overflows invisibly. Template design is manual and is the long pole. Rejected on effort and brittleness.

### Option C: Dual peer renderers off a shared IR — **chosen**

| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Output quality | High on both paths |
| Effort | Medium (~300 extra lines for the second renderer) |
| Failure mode | Divergence between renderers |

**Pros:** Each target rendered natively. Export problem dissolves — there is no export. The IR already exists as a consequence of the layer separation.
**Cons:** Two renderers to keep in sync. Requires a deliberately small block vocabulary.

### Option D: Measure-and-place (headless Chrome geometry → PPTX)

| Dimension | Assessment |
|---|---|
| Complexity | High |
| Output quality | Pixel-matched, editable |
| Effort | Highest |

**Pros:** Best of both — editable *and* visually identical to HTML.
**Cons:** `getBoundingClientRect` → EMU conversion, font substitution, and reflow differences all fight you. Chrome becomes a hard dependency of the export path. Disproportionate for a personal tool. Revisit only if HTML/PPTX divergence becomes a real irritation.

---

## Trade-off Analysis

**Why the IR is the right contract.** Gamma's export is bad because HTML is its source of truth and PPTX is derived. The moment the IR — not the HTML — is authoritative, PPTX stops being a downgrade and becomes a peer target. The cost is a small amount of duplicated layout logic; the benefit is that neither output is second-class.

**Why themes must be JSON, not CSS.** `render_pptx.py` cannot parse CSS. Tokens live in `themes/*.json`; `render_html.py` injects them as CSS custom properties at render time, `render_pptx.py` reads them directly. If a colour is ever hardcoded in `base.css`, the renderers have silently diverged. **Invariant: `base.css` contains layout rules only, and every visual value is `var(--*)`.**

**Why the block vocabulary stays at ~10.** Divergence risk scales with vocabulary size. The governing rule: *if a block type cannot be expressed in both renderers, it does not get added.* At ten blocks this costs nearly nothing.

**Accepted divergence.** Line breaks and vertical spacing will differ between HTML and PPTX. This is correct, not a defect — a PPTX should look PowerPoint-native rather than like a screenshot of a web page.

---

## Component Design

### 1. Content IR (`deck.json`)

```jsonc
{
  "meta": {
    "title": "Q3 Launch Review",
    "archetype": "business-stakeholder",   // selects playbook + eval profile
    "theme": "slate",
    "aspect": "16:9"
  },
  "cards": [
    {
      "id": "c1",
      "layout": "title",                    // title | section | content | hero
      "title": "Q3 Launch Review",
      "subtitle": "Commercial Ops · August 2026",
      "blocks": []
    },
    {
      "id": "c2",
      "layout": "content",
      "title": "APAC supply constraints cut Q3 revenue 14%",   // ACTION TITLE — a claim
      "blocks": [
        { "type": "chart", "chart": "bar", "caption": "Revenue by region, Q1–Q3",
          "source": "user",                     // user | derived | placeholder
          "data": { "categories": ["Q1","Q2","Q3"],
                    "series": [{ "name": "APAC", "values": [4.2, 4.0, 3.4] }] } },
        { "type": "callout", "tone": "warn",
          "text": "Two of three APAC suppliers missed committed volumes." }
      ],
      "notes": "Lead with the number. The vendor question comes next."
    }
  ]
}
```

**`title` is a first-class card field, never a block.** The action-title discipline is the single largest quality lever, and the evals must be able to check it structurally rather than guessing which heading is the title.

### 2. Block types

| Type | Fields | HTML | PPTX |
|---|---|---|---|
| `text` | `text`, `emphasis?` | `<p>` | text frame |
| `bullets` | `items[]` | `<ul>` | bulleted text frame |
| `kpi` | `value`, `label`, `delta?` | flex card | grouped text boxes |
| `chart` | `chart`, `data`, `caption?` | inline SVG | **native PPTX chart** |
| `table` | `headers[]`, `rows[][]` | `<table>` | **native PPTX table** |
| `callout` | `tone`, `text` | bordered div | rounded rect + text |
| `quote` | `text`, `attribution?` | `<blockquote>` | text frame |
| `image` | `src`, `alt`, `fit?` | `<img>` | picture |
| `columns` | `children[][]` | CSS grid | side-by-side frames |
| `divider` | — | `<hr>` | line shape |

Charts are specified as **data, never as images** — inline SVG for HTML (no JS, so headless-Chrome PDF export is deterministic), native chart objects for PPTX. Both stay crisp; the PPTX one stays editable.

### 3. Theme tokens (`themes/slate.json`)

```jsonc
{
  "color": { "bg": "#0F1419", "surface": "#1A2027", "text": "#E8EAED",
             "muted": "#9AA4AF", "accent": "#4F9CF9",
             "series": ["#4F9CF9", "#7C5CFF", "#2DD4A7", "#F2B13C"] },
  "type":  { "family": "Inter, system-ui, sans-serif",
             "scale": { "title": 40, "cardTitle": 28, "body": 18, "caption": 13 } },
  "space": { "cardPad": 56, "blockGap": 24, "radius": 12 }
}
```

Both renderers consume this file. Contrast pairs are validated (see evals).

### 4. Layout engine

Fixed **16:9 card container** with auto-layout inside — flexible block model, presentable aspect ratio, clean PDF export.

**Overflow policy (must be explicit, not emergent):** blocks stack vertically with `blockGap`. If measured content exceeds card height, scale the block-level type ramp down by up to 15%; if it still overflows, the card **fails validation** and Claude splits it in the IR. Never silently clip, never auto-shrink beyond the floor.

---

## Render Flow

```
1  User request                                    (Cowork or Claude Code)
2  Skill triggers → loads archetype playbook       references/<archetype>.md
3  Claude emits deck.json                          IR only; no HTML, no XML
4  validate.py --schema                            ── gate 1: structural
5  render_html.py  +  render_pptx.py               peers, run independently
6  export_pdf.py                                   headless Chrome → PDF
7  validate.py --quality                           ── gate 2: deterministic evals
8  Claude self-scores IR against Tier-2 rubric     ── gate 3: judged + concerns
9  Any gate fails → revise deck.json → goto 4      max 3 iterations
10 report.py assembles report.md                   all gates + revision log
11 present outputs + inline summary                .pptx, .pdf, .html, report.md
```

**Invariant: the correction loop operates on the IR.** The agent never edits HTML, PPTX XML, or CSS to fix a deck. If output is wrong, either the IR is wrong (regenerate) or the renderer is wrong (a code change, made deliberately in Claude Code — not mid-deck).

---

## Evals

Two tiers plus a golden set. Tier 1 is code and runs every time; Tier 2 is Claude reading the IR against a rubric.

### Tier 1 — deterministic (`validate.py`, no LLM)

| Check | Rule | Severity |
|---|---|---|
| `title-is-claim` | Card title contains a finite verb; is not a bare noun phrase | error |
| `title-length` | ≤ 14 words | warn |
| `answer-first` | For `business-stakeholder` / `idea-pitch`: a card tagged `recommendation` appears in the first 3 | error |
| `card-count` | Within archetype ceiling (pitch ≤ 15, demo ≤ 12, idea ≤ 10, business open with appendix split) | error |
| `one-message` | ≤ 4 blocks per content card; ≤ 1 chart per card | warn |
| `evidence-present` | Every content card has ≥ 1 non-`text` block, or a figure in its title | warn |
| `text-budget` | Per-block character caps (`text` ≤ 240, `bullets` ≤ 6 items × 90 chars, `callout` ≤ 140) | warn |
| `overflow` | Measured card height ≤ container after the 15% ramp-down floor | error |
| `contrast` | Every text-on-background token pair ≥ 4.5:1 (WCAG AA) | error |
| `chart-fit` | Time series → `line`; categorical comparison → `bar`; part-to-whole ≤ 5 slices → `pie`, else `bar` | warn |
| `data-provenance` | Every `chart` / `table` / `kpi` block carries `source`; every `placeholder` value is listed in the run report | error |
| `notes-present` | Speaker notes on every content card | info |

**Gate:** zero errors.

> **Why `data-provenance` is an error, not a warning.** The most dangerous failure mode of this tool is inventing plausible metrics and rendering them in a polished chart. A fabricated 14% looks exactly like a real one. Placeholder data is legitimate — you often want the shape before you have the numbers — but it must never reach a deck unlabelled.

### Tier 2 — judged (Claude scores the IR, 1–5)

| Dimension | Question |
|---|---|
| Storyline | Read only the card titles in order. Do they form a coherent, persuasive argument? *(read-through test)* |
| Vertical logic | Does each card's evidence prove that card's title — and nothing else? |
| Archetype fit | Are the playbook's required sections present, in the prescribed order? |
| Audience fit | Are the metrics and framing right for this audience (exec / buyer / investor / sponsor)? |
| Density | Is each card absorbable in under 30 seconds without narration? |

**Gate:** mean ≥ 3.5, no single dimension below 3.

### Golden set

`evals/golden/` holds 6–8 fixture `deck.json` files with expected Tier-1 output and Tier-2 scores — including deliberately bad ones (topic titles instead of claims, recommendation buried on card 9, an overflowing card). Run these after any prompt or renderer change. **They are the regression suite; without them, prompt tuning is guesswork.**

---

## Run Report

Every run emits a report — a short inline summary in chat, plus a full `report.md` written beside the deck. **Non-optional.** A silent pass is indistinguishable from an unchecked run, and the whole point of building the evals is that you see them.

### Severity taxonomy

| Level | Meaning | Behaviour |
|---|---|---|
| `unverified` | Claude could not confirm a factual input | Surfaced **first**, always, regardless of count |
| `error` | Hard rule violated | Blocks output. Auto-revised, max 3 passes. Still failing after 3 → surfaced, deck not shipped |
| `warn` | Soft rule breached | One auto-revision attempt; surfaced either way |
| `concern` | Judgment call, no rule broken | **Never auto-fixed.** Surfaced for the human to decide |

The distinction that matters: errors and warnings are the machine's business, concerns are yours. Auto-fixing a concern would mean the agent silently overruling an editorial judgment it isn't equipped to make.

### Inline summary (every run)

```
Q3 Launch Review · business-stakeholder · slate · 11 cards · 2 revision passes

Gate 1  schema         ✓
Gate 2  deterministic  ✓  0 errors · 3 warnings
Gate 3  judged         4.2 / 5   (lowest: density 3)

⚠  4 unverified values — charts on c4, c7 use placeholder data
!  3 concerns raised — see report.md
```

### `report.md` — sections, in this order

1. **Unverified inputs** — every `placeholder: true` value, by card. First, always. If the deck contains invented numbers, that is the most important thing on the page.
2. **Errors** — what failed, which card, what the revision changed.
3. **Warnings** — same, plus anything auto-revision could not resolve.
4. **Concerns** — one line each, card-referenced.
5. **Tier-2 scorecard** — five dimensions, score, one-sentence justification each.
6. **Revision log** — what changed between passes.

### What counts as a concern

Concerns are the judge's editorial observations — things that break no rule but that a good reviewer would raise:

- `c6` restates `c4`'s point in different words — candidate for cutting
- The ask on `c9` is not quantified
- Competition framing on `c8` assumes the reader already knows the category
- Traction chart on `c5` shows growth but gives no baseline
- The complication is stated but its cost is never made concrete

Claude generates these while scoring Tier 2. Cap at ~5 per deck; beyond that they stop being read.

---

## Plugin Packaging

```
deck-builder/
├── .claude-plugin/
│   └── plugin.json                 { name: "deck-builder", version: "0.1.0" }
├── skills/
│   ├── build-deck/
│   │   ├── SKILL.md                workflow + IR contract summary
│   │   └── references/
│   │       ├── card-schema.md      full IR spec
│   │       ├── block-types.md      block → renderer mapping
│   │       ├── business-stakeholder.md
│   │       ├── product-demo.md
│   │       ├── startup-pitch.md
│   │       └── idea-pitch.md
│   └── review-deck/
│       └── SKILL.md                Tier-1 + Tier-2 on an existing deck
├── themes/
│   ├── base.css                    LAYOUT ONLY — all values var(--*)
│   ├── slate.json
│   ├── warm.json
│   └── mono.json
├── scripts/
│   ├── render_html.py
│   ├── render_pptx.py
│   ├── export_pdf.py
│   ├── validate.py
│   └── report.py                   assembles report.md + inline summary
├── evals/golden/
└── README.md
```

**Two skills, not one.** `review-deck` grades any deck without triggering generation — useful far more often than expected, and it is the tool that tells you whether `build-deck` is improving.

**Use `${CLAUDE_PLUGIN_ROOT}` for every internal path.** Never hardcode; this is what lets one bundle resolve correctly in both Claude Code and Cowork.

**No MCP servers, no hooks, no agents.** No external service integration and no event-driven behaviour is required. Two skills, four scripts, some assets.

---

## Consequences

**Easier**
- No `.potx` to build by hand; no placeholder indices; no python-pptx autofit bug
- Adding an archetype is a markdown file
- Adding a theme is a JSON file
- Both PDF and editable PPTX from one generation pass
- Claude Code works in CSS and small Python rather than layout geometry

**Harder**
- Two renderers to keep in sync; every new block type costs double
- HTML and PPTX will not match pixel-for-pixel
- Overflow must be measured explicitly rather than delegated to PowerPoint autofit
- Theme tokens must stay disciplined or the renderers silently diverge

**To revisit**
- If HTML/PPTX divergence becomes irritating → reconsider Option D (measure-and-place)
- If headless Chrome is unavailable in the Cowork runtime → PDF export moves to Claude Code only, or LibreOffice becomes the fallback
- If block vocabulary pressure exceeds ~12 → the two-renderer bet needs re-examining
- If Tier-2 scores plateau below 3.5 → the problem is the archetype playbooks, not the renderer

---

## Action Items

1. [ ] **Verify the runtime.** In Cowork: `pip install python-pptx`, open and save a file. Confirm whether headless Chrome exists. *This gates everything.*
2. [ ] Write `card-schema.md` — the IR contract. Freeze it before writing any renderer.
3. [ ] Write `base.css` — 10 block styles, 16:9 card, overflow policy.
4. [ ] Write `themes/slate.json`; verify all contrast pairs ≥ 4.5:1.
5. [ ] `render_html.py` — block-type switch, inline SVG charts.
6. [ ] `export_pdf.py` — headless Chrome.
7. [ ] `validate.py` Tier 1 — the 12 checks above, `data-provenance` included from the start.
8. [ ] `report.py` — inline summary + `report.md`. Build alongside `validate.py`, not after.
9. [ ] `business-stakeholder.md` playbook (Minto/SCQA, action titles, answer-first) + Tier-2 rubric and concern-generation instructions in `SKILL.md`.
10. [ ] **Generate one real deck end to end. Open it. Read the report. Would you send it?** ← go/no-go
11. [ ] `render_pptx.py` — peer renderer against the frozen IR.
12. [ ] Golden set (6–8 fixtures, including bad ones). Assert on report output, not just pass/fail.
13. [ ] Remaining three playbooks + two themes.
14. [ ] `plugin.json`, `README.md`, package as `.plugin`.

Steps 2–4 determine whether output looks designed or generic. Step 9 is the honest checkpoint — if the answer is no, fix the playbook and theme, not the architecture.
