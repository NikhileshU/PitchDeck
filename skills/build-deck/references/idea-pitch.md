# idea-pitch — archetype playbook

The audience is a colleague, a leadership group, or a forum that must **back an
idea** — with attention, headcount, or permission, not usually with a budget line.
The deck exists to convert a room from "interesting" to "let's do it".

The Tier-2 judge scores `archetypeFit` against this file: required sections present,
in the prescribed order.

---

## Answer first — non-negotiable

A card with `role: "recommendation"` appears **within the first 3 cards** (Tier-1
error otherwise). Its title is the idea in one sentence, stated as a proposal:
`"We should run reviews weekly instead of quarterly"` — not `"A New Review Cadence"`.

An idea pitch loses the room by withholding. Nobody is obliged to hear you out;
state the idea, then spend the deck defending it. The evidence follows the answer.

---

## Required sections, in order

| # | Section | `role` | Cards | Carries |
|---|---|---|---|---|
| 1 | Title | — | 1 | `title` layout: the idea as a phrase + owner/date subtitle |
| 2 | The idea | `recommendation` | 1 | The proposal in one sentence — one `kpi`, `callout`, or `hero` |
| 3 | Why it matters now | `problem` | 1–2 | What is wrong today, and what makes now the moment |
| 4 | How it would work | `solution` | 1–2 | The mechanism, concretely enough to argue with |
| 5 | What it would take | `null` | 1 | Effort, people, time — honest, including what you would stop doing |
| 6 | The ask | `ask` | 1 | The specific next step and who has to agree to it |
| 7 | Appendix | `appendix` | 0–3 | Detail for the sceptic; excluded from card count |

**Budget: ≤10 cards excluding appendix (Tier-1 error). Target 5–7.** This is the
tightest budget of the four archetypes, and deliberately so: an idea that needs
twelve cards is not ready to be pitched.

---

## The cost of the idea, stated by you

Section 5 is what separates a proposal from a wish. Name the effort, the people,
and the thing that gets dropped to make room. A room that has to derive the cost
itself will overestimate it, and an idea whose cost is never stated reads as one
nobody has thought through.

`callout` (`warn`) is the right block for the objection you expect. Put it on the
card that provokes it, not in an appendix.

---

## Titles are claims

Sentence case, finite verb, a figure where one exists, ≤14 words. Read in order,
the titles must argue the idea (the judge's `storyline`).

| Bad (label) | Good (claim) |
|---|---|
| Current Process | Quarterly reviews miss the problems they exist to catch |
| Proposed Approach | Weekly reviews would surface the same issues six weeks earlier |
| Resourcing | Two engineers for one quarter, taken from the backlog triage |

Short label titles are a Tier-1 **error** when all three hold: **≤3 alphabetic
tokens** (not words — `"Top 3 Growth Levers"` is 4 words but 3 tokens, since a lone
digit is not a token), **no strong figure** (two digits, a `%`, currency, or a
decimal — a bare `3` or `Q4` does not count), and **no verb token**. Longer noun
phrases draw a warn and cost `storyline`/`verticalLogic` points at the judge.

**Write to the claim standard, not to the checker's boundary.** An idea pitch is
made entirely of claims; a label title on any card is a card that has not decided
what it is arguing.

---

## Evidence discipline

- Every content card carries **≥1 non-text block** or a figure in its title. An
  idea deck often has less data than the other archetypes — that is the reason to
  use every real number you do have, not a licence to invent one.
- **One message per card**: ≤4 blocks, ≤1 chart.
- `quote` earns its place here more than anywhere else: one line from the person
  who lives the problem is worth a chart you had to assemble. `attribution` is
  required for it to carry any weight.
- `table` for the before/after comparison of the mechanism; `bullets` for what it
  would take, at most three lines.

## Data honesty

`source` on every chart, table and KPI: `"user"` for numbers the user gave,
`"derived"` for numbers computed from them, `"placeholder"` for structure-only
values. **Never present an invented number as real.** Idea decks are the most
tempting place to fabricate a supporting figure and the worst place to be caught
doing it — the idea is all you have. The report lists every placeholder first.

## Speaker notes

On every content card. What to *say*: the transition in, the one point to land, and
the objection this card will draw with the answer you would actually give. Never
restate the card title in the notes — the title already makes the claim; the notes
carry what the title cannot.

## Density

Absorbable in under 30 seconds without narration (`density`). At five to seven
cards there is no excuse for a crowded one. When a card fails, split it — never
shrink the type, never clip.

## Defaults

Theme `slate` unless the user chooses. Aspect is always 16:9. Card ids `c1…cn`,
block ids `<card>b1…` — stable across revisions, since the report references them.
