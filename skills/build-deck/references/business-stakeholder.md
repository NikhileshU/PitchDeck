# business-stakeholder — archetype playbook

The audience is an executive or budget owner who must **decide something**. The deck
exists to get that decision. Every card either advances the decision or gets cut.

The Tier-2 judge scores `archetypeFit` against this file: required sections present,
in the prescribed order.

---

## Answer first — non-negotiable

A card with `role: "recommendation"` appears **within the first 3 cards** (Tier-1
error otherwise). Its title is the whole deck in one sentence: verb + amount +
timeframe. `"Approve $1.2M to dual-source APAC supply now"` — not `"Recommendation"`.

Executives read the first card and decide whether to keep listening. Do not build
suspense. The evidence *defends* the answer; it does not precede it.

---

## Required sections, in order

| # | Section | `role` | Cards | Carries |
|---|---|---|---|---|
| 1 | Title | — | 1 | `title` layout: deck title + owner/date subtitle |
| 2 | Recommendation | `recommendation` | 1 | The answer, its cost, its payback — one KPI or callout, no more |
| 3 | Problem / evidence | `problem` (first card), then `null` | 1–4 | Quantified drivers of the problem; one message per card |
| 4 | Solution | `solution` | 1–3 | How it works; options compared in a table if a choice exists |
| 5 | The ask | `ask` | 1 | The specific decision, its deadline, its number |
| 6 | Appendix | `appendix` | 0–5 | Backup detail; excluded from card count |

A `section` divider card between 3 and 4 is allowed when the deck runs long.
`hero` cards work for a single headline number.

**Budget: ≤20 cards excluding appendix (Tier-1 error). Target 8–12.** If the story
needs more, the story has two decks in it.

---

## Titles are claims

Sentence case, finite verb, a figure where one exists, ≤14 words. The card titles
read in order must *be* the argument (the judge's `storyline` dimension).

| Bad (label) | Good (claim) |
|---|---|
| Q3 Revenue Overview | Q3 revenue fell 14% below plan |
| Supply Chain Update | Two of three APAC suppliers missed committed volumes |
| Next Steps | We need sign-off before the August 29 vendor deadline |

Short label titles (≤3 words, no figure, no verb) are a Tier-1 **error**; longer
noun phrases draw a warn and cost `storyline`/`verticalLogic` points at the judge.

---

## Evidence discipline

- Every content card carries **≥1 non-text block** or a figure in its title.
- **One message per card**: ≤4 blocks, ≤1 chart. The card's evidence proves the
  card's title — nothing else (`verticalLogic`).
- Chart choice: trend over time → `line`; comparison across categories → `bar`/`hbar`;
  share of a whole, ≤5 slices → `pie`. Quarterly comparisons may stay bars.
- `table` for option comparisons (options as rows, criteria as columns).
- `kpi` for the headline number; its `delta` carries the comparison.
- `callout` (`warn`) for the risk that would surface in the room anyway;
  `callout` (`info`) for the deadline.

## Data honesty

`source` on every chart, table and KPI: `"user"` for numbers the user gave,
`"derived"` for numbers computed from them, `"placeholder"` for structure-only
values. **Never present an invented number as real** — placeholder data is
legitimate, unlabelled placeholder data is the one unforgivable defect. The report
lists every placeholder first; expect the user to be asked to confirm them.

## Speaker notes

On every content card. What to *say*, not what is shown: the transition in, the
one number to emphasise, the hard question this card will draw and its answer.

## Density

Absorbable in under 30 seconds without narration (`density`). When a card fails
this, split it — never shrink the type, never clip.

## Defaults

Theme `slate` unless the user chooses. Aspect is always 16:9. Card ids `c1…cn`,
block ids `<card>b1…` — stable across revisions, since the report references them.
