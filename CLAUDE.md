# CLAUDE.md — deck-builder

Single-user Claude plugin that turns a prompt into a presentation deck: HTML, PDF, and native editable PPTX, plus a quality report.

## Read order

1. **This file** — invariants and session protocol. Reloaded every session.
2. **`BUILD-SPEC.md`** — the complete spec. Read the phase you are on.
3. **`ADR-001-deck-builder.md`** — rationale only. Read when you want to know *why*, not *what*.

`BUILD-SPEC.md` is authoritative. If this file and the spec disagree, the spec wins — and flag the discrepancy.

---

## CURRENT PHASE: 4

Update this line at the end of every session.

---

## Session protocol

1. Read `CLAUDE.md` and the current phase in `BUILD-SPEC.md` §14.
2. **Plan before writing code.** Show the plan.
3. Implement **only the current phase**.
4. Run the phase checkpoint. **Paste the actual command output** — not a claim that it passed.
5. Stop. Report. Do not begin the next phase.

If you think the spec is wrong, **say so and stop.** Do not implement a different design and explain afterwards.

Commit at every phase boundary.

---

## Invariants

Violating any of these breaks the architecture.

1. **`deck.json` (the IR) is the only source of truth.** Fix a bad deck by regenerating the IR and re-rendering. Never hand-edit generated HTML, PPTX XML, or CSS to correct deck content.
2. **Renderers are peers, never chained.** `render_html` and `render_pptx` each read the IR independently. PPTX is never produced from HTML.
3. **Renderers are pure:** `render(ir: dict, theme: dict, out_path: str) -> None`. No globals, no env reads, no network. Paths passed in.
4. **`base.css` is layout only.** Every colour, size, spacing value is `var(--*)`. Zero hex literals.
5. **Themes are JSON.** `render_pptx.py` cannot parse CSS. Both renderers read `themes/*.json`.
6. **No archetype logic in `scripts/`.** No `if archetype == ...` anywhere in a renderer. Archetype shapes the IR, prompt-side.
7. **10 block types, 4 card layouts. No more.** If a block cannot be expressed in *both* renderers, it does not exist.
8. **All internal paths use `${CLAUDE_PLUGIN_ROOT}`.** Never hardcode.
9. **Every run emits a report.** A silent pass is indistinguishable from an unchecked run.
10. **No MCP servers, no hooks, no agents.** Two skills, five scripts, data files.

---

## Do not

- Write OOXML by hand. If python-pptx can't do it, drop the feature — don't work around it in raw XML.
- Add a config framework, a plugin system, or an abstraction layer for a second LLM provider.
- Add block types or card layouts beyond the specified 10 and 4.
- Let `render_html.py` or `render_pptx.py` exceed **400 lines**.
- Introduce a class hierarchy. Plain functions and dicts.
- Use JavaScript in rendered HTML. Charts are server-generated inline SVG.
- Auto-fix a `concern`. Concerns are surfaced for the human, never resolved by the agent.
- Ship a deck with unresolved `error` findings.
- Start the next phase because the current one finished early.

---

## Quick reference

**Units.** Everything in points. Card canvas **960×540pt**. HTML multiplies every pt by **4/3** → 1280×720px. PPTX uses pt directly (`1pt = 12700 EMU`). Never introduce a second unit.

**Blocks (10).** `text` `bullets` `kpi` `chart` `table` `callout` `quote` `image` `columns` `divider`
**Card layouts (4).** `title` `section` `content` `hero`
**Archetypes (4).** `business-stakeholder` `product-demo` `startup-pitch` `idea-pitch`
**Severity (5).** `unverified` `error` `warn` `concern` `info`

**`source` is required** on every `chart`, `table`, and `kpi` block: `user | derived | placeholder`. Missing → Tier-1 error. Placeholder values are listed first in the report.

**Overflow.** Ramp `body`/`caption` down by up to 15%. Never the card title. Still overflowing → `overflow` error, split the card in the IR. Never clip.

### Scripts

```bash
validate.py     --ir deck.json [--theme themes/slate.json] --out findings.json
render_html.py  --ir deck.json --theme themes/slate.json --out out/deck.html
render_pptx.py  --ir deck.json --theme themes/slate.json --out out/deck.pptx
export_pdf.py   --html out/deck.html --out out/deck.pdf
report.py       --findings findings.json --judge judge.json --ir deck.json --out out/report.md
```

Exit `0` = pass, `1` = fail. `validate.py` exits `1` on any `error` finding.

### Tree

```
.claude-plugin/plugin.json
skills/build-deck/{SKILL.md,references/}
skills/review-deck/SKILL.md
themes/{base.css,slate.json,warm.json,mono.json}
scripts/{render_html,render_pptx,export_pdf,validate,report}.py
evals/golden/
```

---

## Phases and checkpoints

| # | Phase | Checkpoint — paste the evidence |
|---|---|---|
| 0 | Verify runtime | `pip install python-pptx`, open+save a file. Does headless Chrome exist? **Report only, no code.** If python-pptx fails, stop and raise it. |
| 1 | `card-schema.md`, `block-types.md` — then **freeze** | Both files complete against spec §4–§6 |
| 2 | `themes/slate.json`, `themes/base.css` | `grep -c '#' themes/base.css` → 0. All contrast pairs ≥4.5:1 |
| 3 | `render_html.py` | Renders all 10 blocks and all 4 layouts from a fixture |
| 4 | `export_pdf.py` | PDF is 13.333×7.5in, text selectable |
| 5 | `validate.py` — 14 checks | Passes `01-good-business.json`; catches the specific defect in each bad fixture |
| 6 | `report.py` | Produces inline summary + `report.md` from `findings.json` + `judge.json` |
| 7 | `business-stakeholder.md`, `build-deck/SKILL.md` | Playbook complete |
| 8 | **Generate one real deck** | **Human go/no-go. Stop and wait.** |
| 9 | `render_pptx.py` | Same fixture as phase 3. Text selectable, charts and tables are native objects |
| 10 | Golden set (6 fixtures + `expected/`) | Assert on full report output, not just pass/fail |
| 11 | 3 remaining playbooks, `warm.json`, `mono.json`, `review-deck/SKILL.md` | — |
| 12 | `plugin.json`, `README.md`, `requirements.txt`, package `.plugin` | Installs in Claude Code and Cowork |

---

## Open question (resolve in phase 0)

If headless Chrome is unavailable in the Cowork runtime, PDF export becomes Claude Code-only, or LibreOffice headless becomes the fallback. **Report which — do not silently pick one.**
