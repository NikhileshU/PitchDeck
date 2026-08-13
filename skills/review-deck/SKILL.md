---
name: review-deck
description: Review an existing deck against the deck-builder quality gates — runs Tier-1 validation and a Tier-2 judgement over deck.json and produces a quality report with ranked fixes. Use when the user asks to review, critique, check, or score a deck they already have; not for building one.
---

# review-deck

Judge a deck that already exists. **This skill changes nothing.** It reads
`deck.json`, runs the gates, scores the deck, and hands back a report with the
fixes ranked. Applying them is the user's call — and when they say go, it is
`build-deck` that revises the IR and re-renders.

## 1 · Find the IR

`deck.json` is the only reviewable artifact. It is the source of truth; the HTML,
PDF and PPTX are outputs of it.

- No `deck.json` in the working directory → ask where it is.
- Only a `.pptx`, `.pdf` or `.html` exists → **stop and say so.** A rendered file
  cannot be reviewed against these gates and must never be reverse-engineered into
  an IR. Offer to build a deck from the source material instead.

## 2 · Load the contracts

Read, in this order:

1. `${CLAUDE_PLUGIN_ROOT}/skills/build-deck/references/<archetype>.md` — the
   playbook for `meta.archetype`; it is the standard the deck is judged against
2. `${CLAUDE_PLUGIN_ROOT}/skills/build-deck/references/card-schema.md` — the IR contract
3. `${CLAUDE_PLUGIN_ROOT}/skills/build-deck/references/block-types.md` — the 10 blocks

If `meta.archetype` is missing or unknown, say so and ask which one applies rather
than guessing — the archetype decides half the findings.

## 3 · Gate 1 + 2 — deterministic validation

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" --ir deck.json \
  --theme "${CLAUDE_PLUGIN_ROOT}/themes/<theme>.json" --out findings.json --passes 0
```

Use the theme named in `meta.theme` (`slate`, `warm`, `mono`). Pass `--passes 0`:
a review is a measurement of the deck as it stands, not a revision pass. Without
`--theme` the contrast, minimum-type and overflow checks silently do not run, so
always pass it.

## 4 · Gate 3 — judge the IR

Score the deck honestly against the playbook, 1–5 per dimension, and write
`judge.json`:

```json
{ "scores": { "storyline": {"score": 3, "note": "…"},
              "verticalLogic": {"score": 3, "note": "…"},
              "archetypeFit": {"score": 4, "note": "…"},
              "audienceFit": {"score": 4, "note": "…"},
              "density": {"score": 2, "note": "…"} },
  "concerns": [ {"card": "c6", "message": "…"} ] }
```

All five dimensions, integer scores 1–5, **up to 5 concerns** — `report.py`
enforces this contract and fails Gate 3 on violations. Read only the card titles,
in order, for `storyline`. Claim quality of titles is judged **here** at error
grade: score non-claim titles down in `storyline`/`verticalLogic`.
Gate: mean ≥ 3.5, no dimension below 3.

Score what is on the cards. A review that scores every dimension 4 is not a review.

## 5 · Report

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/report.py" --findings findings.json \
  --judge judge.json --ir deck.json --out review.md --xlsx review.xlsx
```

`--xlsx` writes the same review as a spreadsheet — one row per finding, per
dimension and per concern. A review exists to be acted on and re-run; the
workbook is what makes two reviews of the same deck comparable.

Relay the inline summary it prints **verbatim**, then add what the report cannot
compute: the fixes, ranked by what they cost and what they buy.

- **Blocking** — every `error`. The deck cannot ship with these; name the card and
  the specific edit (split c4, add `source` to c2b1, rewrite the c7 title as a claim).
- **Worth fixing** — `warn` findings and any dimension scored below 3.
- **Your call** — `concern` findings and judgement calls. Present them; do not
  resolve them. Concerns are only ever resolved by the user.

Give the count of unverified placeholder values first, before anything else — the
user needs to know what to confirm even if they change nothing else.

## 6 · Hand off

If the user wants the fixes applied, that is `build-deck`: it regenerates
`deck.json` and re-renders. Do not edit the IR here, and never hand-edit rendered
output — a fix that does not live in the IR is undone by the next render.

## Hard rules

- Review the IR, never the rendered artifact.
- Never auto-fix a `concern`, and never revise `deck.json` in this skill.
- Never invent data to resolve a placeholder — an unverified value stays unverified
  until the user supplies the real one.
- A review without a report did not happen. Always run step 5.
