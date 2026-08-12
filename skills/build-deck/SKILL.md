---
name: build-deck
description: Build a presentation deck from a prompt — emits HTML, PDF and native editable PPTX plus a quality report. Use when the user asks to create a deck, presentation, slides, or pitch; for business reviews, product demos, startup pitches, or idea pitches.
---

# build-deck

Turn the user's request into a validated, rendered deck. **The IR (`deck.json`) is
the only thing you author.** Never write HTML, CSS, or PPTX XML — the renderers own
those. Never hand-edit a rendered artifact to fix content: fix the IR, re-render.

## 1 · Frame the request

Establish, asking only when genuinely unclear:

- **Archetype**: `business-stakeholder` (a decision from an executive) ·
  `product-demo` (show a product) · `startup-pitch` (raise money) ·
  `idea-pitch` (win support for an idea). Default to `business-stakeholder`
  for internal/decision decks.
- **Audience and the single outcome** the deck must produce.
- **Data**: what the user supplied. Numbers they give are `source: "user"`;
  numbers you compute from theirs are `"derived"`; structure-only values you
  invent are `"placeholder"` — and marking them is mandatory, not optional.
- **Theme**: `slate` (dark, default) · `warm` (light, serif, warm paper) ·
  `mono` (light, near-monochrome). All three share the same type scale and
  spacing, so the theme never changes whether a card overflows. If a requested
  theme has no file in `${CLAUDE_PLUGIN_ROOT}/themes/`, fall back to `slate` and
  say so rather than failing.

## 2 · Load the contracts

Read, in this order:

1. `${CLAUDE_PLUGIN_ROOT}/skills/build-deck/references/<archetype>.md` — the playbook; it shapes the IR
2. `${CLAUDE_PLUGIN_ROOT}/skills/build-deck/references/card-schema.md` — the IR contract
3. `${CLAUDE_PLUGIN_ROOT}/skills/build-deck/references/block-types.md` — the 10 blocks

## 3 · Emit the IR

Write `deck.json` in the working directory: schema `"1.0"`, the playbook's section
order, claim titles, one message per card, sourced data, speaker notes on every
content card. Card ids `c1…cn`, block ids `<card>b1…` — keep ids stable across
revisions; the report references them.

## 4 · Gate 1 + 2 — deterministic validation

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" --ir deck.json \
  --theme "${CLAUDE_PLUGIN_ROOT}/themes/<theme>.json" --out findings.json --passes <N>
```

`--passes` is the revision count so far (0 on the first run — increment it on every
re-validation).

## 5 · Gate 3 — judge the IR

Score the IR honestly against the playbook, 1–5 per dimension, and write
`judge.json`:

```json
{ "scores": { "storyline": {"score": 4, "note": "…"},
              "verticalLogic": {"score": 4, "note": "…"},
              "archetypeFit": {"score": 5, "note": "…"},
              "audienceFit": {"score": 4, "note": "…"},
              "density": {"score": 3, "note": "…"} },
  "concerns": [ {"card": "c6", "message": "…"} ] }
```

All five dimensions, integer scores 1–5, **up to 5 concerns** — `report.py`
enforces this contract and fails Gate 3 on violations. Read only the card titles
in order for `storyline`. Score what is there, not what you meant to write.
Claim quality of titles is judged **here** at error grade: score non-claim titles
down in `storyline`/`verticalLogic`. Gate: mean ≥ 3.5, no dimension below 3.

## 6 · Revise — bounded

- Any `error`, or Gate 3 failing → revise `deck.json` (split the overflowing card,
  fix the title, add the missing source…), then rerun steps 4–5 with `--passes`
  incremented. **Maximum 3 passes.**
- `warn` → one revision attempt, then let it stand.
- `concern` → **never act on it.** Concerns are surfaced to the user, only ever
  resolved by the user.
- Still failing after 3 passes → stop. Render nothing. Present the report and say
  plainly what would not resolve.

## 7 · Render — only after gates pass

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_html.py" --ir deck.json \
  --theme "${CLAUDE_PLUGIN_ROOT}/themes/<theme>.json" --out out/deck.html
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_pptx.py" --ir deck.json \
  --theme "${CLAUDE_PLUGIN_ROOT}/themes/<theme>.json" --out out/deck.pptx
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/export_pdf.py" --html out/deck.html \
  --out out/deck.pdf --cards <number of cards in deck.json>
```

The renderers are peers — both read `deck.json`, neither reads the other's output.
If `render_pptx.py` is not present in this build, say so and deliver HTML + PDF.
If no Chromium-family browser exists, `export_pdf.py` exits 1 with a message —
deliver HTML + PPTX and report that PDF export is unavailable in this runtime.

## 8 · Report — every run, no exceptions

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/report.py" --findings findings.json \
  --judge judge.json --ir deck.json --out out/report.md
```

Relay the inline summary it prints **verbatim** in your reply, then list the
artifacts (`out/deck.html`, `out/deck.pdf`, `out/deck.pptx`, `out/report.md`).
A run without a report did not happen.

## Hard rules

- Ship nothing with unresolved `error` findings.
- Placeholder values are surfaced first, always — the user must know what to verify.
- Never auto-fix a `concern`; never hand-edit rendered output; never render from
  a failing IR "just to show something".
