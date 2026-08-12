# product-demo — archetype playbook

The audience is evaluating a product they do not yet use. The deck exists to make
them **believe it works** and know what happens next. Every card either shows the
product doing something or proves it held up when someone else used it.

The Tier-2 judge scores `archetypeFit` against this file: required sections present,
in the prescribed order.

---

## Show, then prove — in that order

A demo deck earns attention with capability and keeps it with evidence. Lead with
what the product does in the user's own workflow; hold the metrics until after they
have seen it work. This is the one archetype where the answer does **not** come
first — there is no decision to front-load, and `answer-first` is not enforced here.

The failure mode is a feature tour: eight cards of capability, no proof, no ask.
Three capabilities shown well beat eight listed.

---

## Required sections, in order

| # | Section | `role` | Cards | Carries |
|---|---|---|---|---|
| 1 | Title | — | 1 | `title` layout: product name + audience/date subtitle |
| 2 | The problem, in their words | `problem` | 1 | The workflow as it is today, quantified if you have the number |
| 3 | What it does | `solution` | 1 | One sentence of capability — a `kpi` or `callout`, not a feature list |
| 4 | The demo spine | `null` | 3–5 | **One capability per card**, each with the artifact it produces |
| 5 | Proof it works | `null` | 1–2 | Usage, retention, or a named customer outcome — real numbers only |
| 6 | Adoption path | `null` | 1 | What rollout costs in time, training, and integration |
| 7 | The ask | `ask` | 1 | The trial, the pilot, the next meeting — with a date |
| 8 | Appendix | `appendix` | 0–4 | Security, integrations, pricing detail; excluded from card count |

**Budget: ≤12 cards excluding appendix (Tier-1 error). Target 7–10.**

A `section` divider before the demo spine helps when the deck runs to ten cards.

---

## The demo spine

Each spine card answers one question: *what does the product do here, and what does
the user get out of it?*

- **`image` for the artifact, not for the interface.** A screenshot of the output —
  the filed report, the generated schedule — beats a screenshot of the settings
  screen. Every `image` needs a truthful `alt`; the PDF and PPTX both carry it.
- **`hero` with a single image** when one screen is the whole point. The title
  overlays it, so keep the title short.
- Sequence the spine as the user's actual sequence. If the product's first screen
  is not the first spine card, say why in the notes.

---

## Titles are claims

Sentence case, finite verb, a figure where one exists, ≤14 words. The titles read
in order must be the demo's argument, not its menu (the judge's `storyline`).

| Bad (label) | Good (claim) |
|---|---|
| Dashboard Overview | The dashboard answers "are we on schedule" in one screen |
| Integrations | It reads your existing schedule without an import step |
| Customer Results | Three pilot teams cut their reporting time by 71% |

Short label titles are a Tier-1 **error** when all three hold: **≤3 alphabetic
tokens** (not words — `"Top 3 Growth Levers"` is 4 words but 3 tokens, since a lone
digit is not a token), **no strong figure** (two digits, a `%`, currency, or a
decimal — a bare `3` or `Q4` does not count), and **no verb token**. Longer noun
phrases draw a warn and cost `storyline`/`verticalLogic` points at the judge.

**Write to the claim standard, not to the checker's boundary.** "Integrations" and
"Integration Options and Setup" are the same card; only one of them trips the error.

---

## Evidence discipline

- Every content card carries **≥1 non-text block** or a figure in its title.
- **One message per card**: ≤4 blocks, ≤1 chart. On spine cards the artifact is the
  evidence — an `image` plus one line of text is usually the whole card.
- Adoption and proof cards take `table` (what integrates, what it replaces) and
  `chart` (usage over time → `line`; before/after → `bar`).
- `callout` (`good`) for the thing that surprises people in the room;
  `callout` (`info`) for the constraint they will hit in week one. Name it before
  they find it.

## Data honesty

`source` on every chart, table and KPI: `"user"` for numbers the user gave,
`"derived"` for numbers computed from them, `"placeholder"` for structure-only
values. **Never present an invented number as real.** In a demo deck this matters
most on the proof cards — invented adoption metrics are the fastest way to lose a
room that has seen a real one. The report lists every placeholder first.

## Speaker notes

On every content card. What to *say* while the screen is up: what to click, the one
number to point at, the question this screen always draws and its answer. Never
restate the card title in the notes — the title already makes the claim; the notes
carry what the title cannot.

## Density

Absorbable in under 30 seconds without narration (`density`). A demo card is
carrying too much when the presenter has to say "and over here on the left". Split
it — never shrink the type, never clip.

## Defaults

Theme `slate` unless the user chooses. Aspect is always 16:9. Card ids `c1…cn`,
block ids `<card>b1…` — stable across revisions, since the report references them.
