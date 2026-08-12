# startup-pitch — archetype playbook

The audience is an investor deciding whether to take a second meeting. The deck
exists to get that meeting. An investor reads the titles in ninety seconds and
either asks a question or does not; every card is built for that read.

The Tier-2 judge scores `archetypeFit` against this file: required sections present,
in the prescribed order.

---

## Traction before market

Investors discount market size and believe traction. Put what is already true —
revenue, users, retention, pilots — ahead of what could be true. A deck that opens
with a $40B TAM and reaches its first real number on card 11 reads as a deck with
nothing to show on card 3.

`answer-first` is **not** enforced for this archetype: a pitch builds to the ask
rather than opening with it. The ask still lands on a card of its own, tied to a
milestone — never as a number floating on the last slide.

---

## Required sections, in order

| # | Section | `role` | Cards | Carries |
|---|---|---|---|---|
| 1 | Title | — | 1 | `title` layout: company + round and date subtitle |
| 2 | Problem | `problem` | 1 | Whose pain, how expensive, in their units — hours, dollars, churn |
| 3 | Solution | `solution` | 1 | What you built, in one sentence a non-user would repeat correctly |
| 4 | Product | `null` | 1–2 | How it actually works; the artifact it produces |
| 5 | Traction | `null` | 1–2 | Revenue, users, retention — the strongest true number you have |
| 6 | Market | `null` | 1 | **Bottom-up** sizing: units × price, with the units named |
| 7 | Business model | `null` | 1 | Price, motion, and the unit economics behind them |
| 8 | Competition | `null` | 0–1 | Why the obvious alternative loses — a `table`, not a magic quadrant |
| 9 | Team | `null` | 0–1 | Why these people, on this problem, now |
| 10 | The ask | `ask` | 1 | Amount, structure, runway, and the milestone it buys |
| 11 | Appendix | `appendix` | 0–5 | Cohorts, pipeline, detailed model; excluded from card count |

A `section` divider before Market is allowed when the deck runs long.

**Budget: ≤15 cards excluding appendix (Tier-1 error). Target 10–12.** A seed deck
that needs sixteen cards is usually two arguments competing for the same round.

---

## The ask card

Amount, structure, runway, milestone — in the title where possible:
`"We are raising $3M to reach 1,000 crews by 2027"`. Then one `callout` with the
terms and one `bullets` block with use of funds, at most three lines. Use of funds
that does not add up to the amount asked for is the single most-caught error in the
room; check the arithmetic before the deck ships.

---

## Titles are claims

Sentence case, finite verb, a figure where one exists, ≤14 words. Read alone and in
order, the titles must be the pitch (the judge's `storyline`).

| Bad (label) | Good (claim) |
|---|---|
| Market Opportunity | 180,000 US contractors run crews of five or more |
| Traction | Revenue grew from zero to $480K ARR in nine months |
| Unit Economics | Unit economics hold at 4.6x LTV to CAC |

Short label titles are a Tier-1 **error** when all three hold: **≤3 alphabetic
tokens** (not words — `"Top 3 Growth Levers"` is 4 words but 3 tokens, since a lone
digit is not a token), **no strong figure** (two digits, a `%`, currency, or a
decimal — a bare `3` or `Q4` does not count), and **no verb token**. Longer noun
phrases draw a warn and cost `storyline`/`verticalLogic` points at the judge.

**Write to the claim standard, not to the checker's boundary.** "Traction" is an
error and "Traction and Early Customer Signal" is a warn — both are the same
non-claim, and the judge scores them the same way.

---

## Evidence discipline

- Every content card carries **≥1 non-text block** or a figure in its title.
- **One message per card**: ≤4 blocks, ≤1 chart. Investors read one number per card.
- Growth over time → `line`; segment comparison → `bar`/`hbar`; market build-up and
  competition → `table` (segments or competitors as rows, criteria as columns).
- `kpi` for the headline number of the card; its `delta` carries the comparison
  that makes the number mean something ("+118% NRR", "payback in 7 months").
- `callout` (`warn`) for the risk you know they will raise. Raising it yourself is
  worth more than the risk costs.

## Data honesty

`source` on every chart, table and KPI: `"user"` for numbers the founder gave,
`"derived"` for numbers computed from them, `"placeholder"` for structure-only
values. **Never present an invented number as real** — in a fundraise, an
unlabelled placeholder that reaches a diligence call is not a formatting mistake.
The report lists every placeholder first; expect to confirm each one before the
deck leaves the room.

## Speaker notes

On every content card. What to *say*: the transition in, the one number to
emphasise, the hard question this card will draw and its answer. Never restate the
card title in the notes — the title already makes the claim; the notes carry what
the title cannot.

## Density

Absorbable in under 30 seconds without narration (`density`) — investors read
ahead of the speaker. When a card fails this, split it; never shrink the type,
never clip.

## Defaults

Theme `slate` unless the user chooses. Aspect is always 16:9. Card ids `c1…cn`,
block ids `<card>b1…` — stable across revisions, since the report references them.
