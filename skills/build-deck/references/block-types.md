# block-types.md — the 10 block types

> **FROZEN (phase 1).** Both renderers are written against this file. A block type that
> cannot be expressed in **both** HTML and PPTX does not exist — the vocabulary is
> capped at these 10. If this file and `BUILD-SPEC.md` disagree, the spec wins — flag it.
> *(Repository only: `BUILD-SPEC.md` is development material and is not packaged
> with the plugin. Inside an installed plugin this file is the contract.)*

Every block has a stable, unique `id` and a `type` from the table below. No other
types, ever.

| `type` | Fields | HTML | PPTX |
|---|---|---|---|
| `text` | `text`, `emphasis?` (bool) | `<p class="b-text">` | text frame |
| `bullets` | `items[]` (≤6) | `<ul class="b-bullets">` | bulleted text frame |
| `kpi` | `value`, `label`, `delta?`, `source` | `<div class="b-kpi">` | grouped text boxes |
| `chart` | `chart`, `data`, `caption?`, `source` | **inline SVG** | **native PPTX chart** |
| `table` | `headers[]`, `rows[][]`, `source` | `<table class="b-table">` | **native PPTX table** |
| `callout` | `tone`, `text` | `<div class="b-callout b-callout--{tone}">` | rounded rect + text |
| `quote` | `text`, `attribution?` | `<blockquote class="b-quote">` | text frame |
| `image` | `src`, `alt`, `fit?` (`cover`\|`contain`) | `<img class="b-image">` | picture |
| `columns` | `children[][]` (2 or 3 arrays of blocks) | CSS grid | side-by-side frames |
| `divider` | — | `<hr class="b-divider">` | line shape |

`source` (`user | derived | placeholder`) is **required** on `chart`, `table`, and
`kpi` — absent is a Tier-1 `data-provenance` error. See `card-schema.md` §6.

---

## Per-type contracts

### `text`
- `text` (string, required), `emphasis` (bool, optional, default `false`).
- Budget: **≤240 chars** (`text-budget`, warn).
- HTML: `<p class="b-text">`; emphasis adds modifier class `b-text--emphasis`.
- PPTX: text frame; emphasis renders bold.

### `bullets`
- `items[]` (strings, required, **≤6 items**, **≤90 chars each** — `text-budget`, warn).
- Flat list only — no nested bullets.
- HTML: `<ul class="b-bullets">` of `<li>`. PPTX: bulleted text frame, one paragraph per item.

### `kpi`
- `value` (string, required — render verbatim, e.g. `"–14%"`, `"$3.4M"`),
  `label` (string, required), `delta` (string, optional, e.g. `"+2.1pp vs Q2"`),
  `source` (required).
- HTML: `<div class="b-kpi">` with value/label/delta elements.
  PPTX: grouped text boxes (value large, label and delta in `caption` scale).
- On a `hero` card a single `kpi` renders at large scale.

### `chart`
- `chart` (enum: `bar | hbar | line | pie`), `data` (required), `caption` (optional),
  `source` (required).
- **Charts are data, never images.** HTML gets inline SVG generated in Python — no
  JavaScript anywhere. PPTX gets a native chart object (editable, themed).
- `data` shape — identical for all four kinds:

  ```jsonc
  {
    "categories": ["Q1", "Q2", "Q3"],
    "series": [{ "name": "APAC", "values": [4.2, 4.0, 3.4] }]
  }
  ```

  Every `series[].values` has exactly one value per category. `pie` uses
  `categories` as slice labels and `series[0].values` as slice sizes — exactly one
  series. `hbar` is `bar` with axes swapped.
- Series colours come from the theme's `color.series`, in order.
- Chart-fit guidance (`chart-fit`, warn): time series → `line`; categorical
  comparison → `bar`/`hbar`; part-to-whole with ≤5 slices → `pie`, else `bar`.
- ≤1 chart per card (`one-message`, warn).

### `table`
- `headers[]` (strings, required), `rows[][]` (required — each row has one cell per
  header; cells are strings, rendered verbatim), `source` (required).
- HTML: `<table class="b-table">`. PPTX: **native PPTX table** (editable).

### `callout`
- `tone` (enum: `info | warn | good`, required), `text` (string, required,
  **≤140 chars** — `text-budget`, warn).
- HTML: `<div class="b-callout b-callout--{tone}">`; tone colour from
  `color.tone.{tone}`. PPTX: rounded rectangle + text.

### `quote`
- `text` (string, required), `attribution` (string, optional).
- HTML: `<blockquote class="b-quote">` with optional `<cite>`. PPTX: text frame.

### `image`
- `src` (string, required — **local file path**, absolute or relative to the
  `deck.json` file; renderers never fetch over the network),
  `alt` (string, required), `fit` (`cover | contain`, optional, default `contain`).
- HTML: `<img class="b-image">` with `object-fit`. PPTX: picture shape
  (`cover` crops to the frame, `contain` letterboxes).
- On a `hero` card a single `image` renders full-bleed.

### `columns`
- `children[][]`: **2 or 3** arrays of block objects, rendered side by side in
  equal-width columns.
- **Nests one level only.** A `columns` block may not contain another `columns`.
- Child blocks are full block objects with their own `id`s.
- HTML: CSS grid. PPTX: side-by-side frames, each column laid out like a narrow card.

### `divider`
- No fields beyond `id` and `type`.
- HTML: `<hr class="b-divider">`. PPTX: line shape.

---

## Rules that apply across blocks

- ≤4 blocks per `content` card; ≤1 `chart` per card (`one-message`, warn).
- Every `content` card should carry ≥1 non-`text` block or a figure in its title
  (`evidence-present`, warn).
- Overflow is handled at the card level (`card-schema.md` §5) — blocks are never
  individually clipped or scaled below the 15% ramp floor.
- No styling values in blocks. Colour, type, and spacing come from the theme;
  renderers map block semantics (tone, emphasis, series index) onto theme tokens.
