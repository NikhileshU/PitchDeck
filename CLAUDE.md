# CLAUDE.md — deck-builder

Single-user Claude plugin that turns a prompt into a presentation deck: HTML, PDF, and native editable PPTX, plus a quality report.

## Read order

1. **This file** — invariants and session protocol. Reloaded every session.
2. **`BUILD-SPEC.md`** — the complete spec. Read the phase you are on.
3. **`ADR-001-deck-builder.md`** — rationale only. Read when you want to know *why*, not *what*.

`BUILD-SPEC.md` is authoritative. If this file and the spec disagree, the spec wins — and flag the discrepancy.

---

## CURRENT PHASE: 5

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
3. **Renderers are pure:** `render(ir: dict, theme: dict, out_path: str) -> None` (the HTML renderer adds a `css: str = ""` kwarg — the CLI passes base.css *text* in; the pure core never discovers files). No globals, no env reads, no network. Paths passed in.
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

<!-- dgc-policy-v11 -->
# Dual-Graph Context Policy

This project uses a local dual-graph MCP server for efficient context retrieval.

## MANDATORY: Always follow this order

1. **Call `graph_continue` first** — before any file exploration, grep, or code reading.

2. **If `graph_continue` returns `needs_project=true`**: call `graph_scan` with the
   current project directory (`pwd`). Do NOT ask the user.

3. **If `graph_continue` returns `skip=true`**: project has fewer than 5 files.
   Do NOT do broad or recursive exploration. Read only specific files if their names
   are mentioned, or ask the user what to work on.

4. **Read `recommended_files`** using `graph_read` — **one call per file**.
   - `graph_read` accepts a single `file` parameter (string). Call it separately for each
     recommended file. Do NOT pass an array or batch multiple files into one call.
   - `recommended_files` may contain `file::symbol` entries (e.g. `src/auth.ts::handleLogin`).
     Pass them verbatim to `graph_read(file: "src/auth.ts::handleLogin")` — it reads only
     that symbol's lines, not the full file.
   - Example: if `recommended_files` is `["src/auth.ts::handleLogin", "src/db.ts"]`,
     call `graph_read(file: "src/auth.ts::handleLogin")` and `graph_read(file: "src/db.ts")`
     as two separate calls (they can be parallel).

5. **Check `confidence` and obey the caps strictly:**
   - `confidence=high` -> Stop. Do NOT grep or explore further.
   - `confidence=medium` -> If recommended files are insufficient, call `fallback_rg`
     at most `max_supplementary_greps` time(s) with specific terms, then `graph_read`
     at most `max_supplementary_files` additional file(s). Then stop.
   - `confidence=low` -> Call `fallback_rg` at most `max_supplementary_greps` time(s),
     then `graph_read` at most `max_supplementary_files` file(s). Then stop.

## Token Usage

A `token-counter` MCP is available for tracking live token usage.

- To check how many tokens a large file or text will cost **before** reading it:
  `count_tokens({text: "<content>"})`
- To log actual usage after a task completes (if the user asks):
  `log_usage({input_tokens: <est>, output_tokens: <est>, description: "<task>"})`
- To show the user their running session cost:
  `get_session_stats()`

Live dashboard URL is printed at startup next to "Token usage".

## Rules

- Do NOT use `rg`, `grep`, or bash file exploration before calling `graph_continue`.
- Do NOT do broad/recursive exploration at any confidence level.
- `max_supplementary_greps` and `max_supplementary_files` are hard caps - never exceed them.
- Do NOT dump full chat history.
- Do NOT call `graph_retrieve` more than once per turn.
- After edits, call `graph_register_edit` with the changed files. Use `file::symbol` notation (e.g. `src/auth.ts::handleLogin`) when the edit targets a specific function, class, or hook.

## Context Store

Whenever you make a decision, identify a task, note a next step, fact, or blocker during a conversation, call `graph_add_memory`.

**To add an entry:**
```
graph_add_memory(type="decision|task|next|fact|blocker", content="one sentence max 15 words", tags=["topic"], files=["relevant/file.ts"])
```

**Do NOT write context-store.json directly** — always use `graph_add_memory`. It applies pruning and keeps the store healthy.

**Rules:**
- Only log things worth remembering across sessions (not every minor detail)
- `content` must be under 15 words
- `files` lists the files this decision/task relates to (can be empty)
- Log immediately when the item arises — not at session end

## Session End

When the user signals they are done (e.g. "bye", "done", "wrap up", "end session"), proactively update `CONTEXT.md` in the project root with:
- **Current Task**: one sentence on what was being worked on
- **Key Decisions**: bullet list, max 3 items
- **Next Steps**: bullet list, max 3 items

Keep `CONTEXT.md` under 20 lines total. Do NOT summarize the full conversation — only what's needed to resume next session.
