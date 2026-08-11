# card-schema.md — the `deck.json` IR

> **FROZEN (phase 1).** Both renderers, the validator, and the playbooks are written
> against this file. Changing it after phase 1 means rewriting `render_html.py` and
> `render_pptx.py`. If this file and `BUILD-SPEC.md` disagree, the spec wins — flag it.

`deck.json` is the **only source of truth** for a deck. To fix a bad deck, regenerate
the IR and re-render. Generated HTML, PPTX XML, and CSS are never hand-edited.

---

## 1. Units

Every dimension in the IR and in themes is in **points (pt)**. There is no second unit.

| Surface | Rule |
|---|---|
| Card canvas | **960pt × 540pt** (16:9 — equals 13.333in × 7.5in) |
| HTML | every pt value × **4/3** → CSS px; canvas renders at 1280×720 px |
| PPTX | pt used directly via `Pt()`; for EMU, `1pt = 12700 EMU` |

---

## 2. Top-level shape

```jsonc
{
  "schema": "1.0",                          // required; do not omit
  "meta": {
    "title": "Q3 Launch Review",
    "archetype": "business-stakeholder",    // business-stakeholder | product-demo | startup-pitch | idea-pitch
    "theme": "slate",                       // filename stem in themes/ (slate | warm | mono)
    "aspect": "16:9"                        // only value supported in v1
  },
  "cards": [ /* card objects, in presentation order */ ]
}
```

### `meta` fields

| Field | Type | Rule |
|---|---|---|
| `title` | string | Deck title; also appears on the `title` card |
| `archetype` | enum | One of the four archetypes. Shapes the IR prompt-side only — **renderers never branch on it** |
| `theme` | string | Filename stem resolved to `themes/<theme>.json` by the caller; renderers receive the loaded theme dict, never a path to resolve |
| `aspect` | string | `"16:9"` only in v1 |

---

## 3. Card object

```jsonc
{
  "id": "c1",             // stable, unique across the deck; referenced by the report
  "layout": "title",      // title | section | content | hero
  "title": "Q3 Launch Review",
  "subtitle": "Commercial Ops · August 2026",   // title/section layouts only
  "role": null,           // null | recommendation | problem | solution | ask | appendix
  "blocks": [],           // block objects — see block-types.md
  "notes": null           // speaker notes; expected on every content card
}
```

### Field rules

- **`title` is a first-class field, never a block.** The `title-is-claim` and
  `title-length` checks depend on this. On `content` cards the title must be a claim
  (contains a finite verb, not a bare noun phrase) and ≤14 words.
- **`id` is stable and unique** across the deck, for cards and blocks alike. Required —
  the report references ids, and per-block regeneration needs them.
- **`subtitle`** is valid on `title` and `section` layouts only.
- **`role`** drives the `answer-first` check. Set it on cards that carry structural
  weight; `null` otherwise.
- **`notes`** (speaker notes) are expected on every `content` card (`notes-present`, info).

### `role` values

| Value | Meaning |
|---|---|
| `null` | No structural weight |
| `recommendation` | The answer/ask of the deck. For `business-stakeholder` and `idea-pitch`, a `recommendation` card must appear **within the first 3 cards** (`answer-first`, error) |
| `problem` | States the problem being addressed |
| `solution` | States the proposed solution |
| `ask` | The specific request (budget, decision, headcount) |
| `appendix` | Backup material. Excluded from the `card-count` limit |

### Card-count limits (excluding `role: appendix`)

`startup-pitch` ≤15 · `product-demo` ≤12 · `idea-pitch` ≤10 · `business-stakeholder` ≤20

---

## 4. Layouts (exactly 4)

| `layout` | Use | Rendering |
|---|---|---|
| `title` | Deck opener | Centred title + subtitle, accent rule |
| `section` | Divider between sections | Large centred title on `surface` background |
| `content` | Default working card | Title at top, blocks stacked below separated by `blockGap` |
| `hero` | Single statement or full-bleed image | Title only, or one `image`/`kpi` block at large scale |

No fifth layout exists. If a card cannot be expressed with these four, restructure the IR.

---

## 5. Content area and overflow

Content area = `960 − 2×cardPad` wide × `540 − 2×cardPad` tall (pt, from the theme's
`space.cardPad`). `content` cards stack: title, then blocks separated by `blockGap`.

**Overflow policy — exactly this, no improvisation:**

1. Measure total content height.
2. If it exceeds the content area, scale the type ramp down by up to **15%**
   (`body` and `caption` only — **never the card title**). `body` must stay ≥16pt
   after ramp-down (`min-type-size`, error).
3. Still overflowing → **do not clip, do not shrink further.** Emit a Tier-1
   `overflow` error naming the card. The fix is to split the card in the IR.

---

## 6. Data provenance

`source` is **required** on every `chart`, `table`, and `kpi` block
(`data-provenance`, error — a fabricated metric in a clean chart is
indistinguishable from a real one):

| `source` | Meaning |
|---|---|
| `user` | Value supplied by the user |
| `derived` | Computed from user-supplied values |
| `placeholder` | Invented for structure; **listed first in every report** as unverified |

---

## 7. What the schema will never grow

- No layouts beyond the 4. No block types beyond the 10 (see `block-types.md`).
- No archetype-conditional fields — archetype shapes which cards exist, not how they render.
- No styling in the IR. Colour, type, spacing live in `themes/*.json` only.
