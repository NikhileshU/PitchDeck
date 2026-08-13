# PitchDeck — Test Case Catalogue

Every test case the codebase supports, by module. Status column: **✓** already in
the suite, **+** not yet written, **○** deliberately out of scope.

Artifact-producing tests write to `evals/out/` — see [Artifact convention](#artifact-convention)
at the end.

**Keeping this file true.** `python3 evals/check_catalogue.py` reads these tables,
scans `evals/test_*.py` for case ids, and reports the drift both ways — a ✓ no
test carries, a `+` that is already written, an id no table defines. It exits 1
on anything factually wrong with the catalogue, so a stale row fails the run
rather than quietly misleading the next person.

The link is **the case id in the test's docstring**:

```python
def test_out_parent_directory_is_created(self, artifacts):
    """C-13. The skill writes into out/, which may not exist on a first run."""
```

Nothing else is needed — no marker, no registry. A range banner
(`# C-10..C-13 — file ingestion`) is deliberately *not* a link: it names a span
of the file, not a case.

At the time of writing 3 of 115 ✓ cases carry their id, so `--strict` (which
makes unbacked ✓ fatal) is the goal, not yet the gate. `--todo` prints the work
list; `--xlsx` writes the whole catalogue and its drift as data.

---

## 1. `validate.py` — Tier-1 checks

Fourteen checks. The golden set proves each *fires somewhere*; these prove each
fires on the right input and stays quiet on the wrong one. Every check needs both
a positive and a negative case — a check that never returns clean is as broken as
one that never fires.

### 1.1 `schema-valid`

| # | Case | Expect | Status |
|---|---|---|---|
| V-01 | Well-formed IR | no findings | ✓ (01) |
| V-02 | Card missing `id` | error | ✓ (09) |
| V-03 | Duplicate card id | error | ✓ (09) |
| V-04 | Duplicate block id within a card | error | + |
| V-05 | Duplicate block id across cards | no finding (ids scope to card) | + |
| V-06 | Unknown `layout` value | error | ✓ (09) |
| V-07 | Unknown block `type` | error | ✓ (09) |
| V-08 | `subtitle` on a `content` layout | error | ✓ (09) |
| V-09 | `subtitle` on `title` / `section` | clean | + |
| V-10 | `role` outside the enum | error | ✓ (09) |
| V-11 | Block missing required field per type (10 cases) | error each | + |
| V-12 | `columns` nested inside `columns` | error | ✓ (09) |
| V-13 | `columns` with 1 child / 4 children | error (2–3 only) | + |
| V-14 | Chart with `categories` but no `series` | error | ✓ (09) |
| V-15 | Series values length ≠ categories length | error | + |
| V-16 | `schema` version absent or unrecognised | error | + |
| V-17 | `meta.archetype` outside the four | error | + |
| V-18 | Empty `cards` array | error | + |

### 1.2 `title-is-claim` — the hybrid rule

Corpus lives in `test_heuristics.py`; provenance per line matters more than count.

| # | Case | Expect | Status |
|---|---|---|---|
| V-20 | ≤3 tokens, no verb, no figure (`Next Steps`) | **error** | ✓ |
| V-21 | 4+ tokens, no verb, no figure (`Unit Economics Deep Dive`) | **warn** | ✓ (06) |
| V-22 | Finite verb in non-first position (`Revenue grew 12%`) | clean | ✓ |
| V-23 | Imperative opener (`Approve $1.2M…`) | clean | ✓ |
| V-24 | Strong figure + directional, verbless (`Churn up 12% since April`) | clean | ✓ |
| V-25 | Casing must not decide (`REVENUE FELL 14% IN Q3`) | clean | ✓ |
| V-26 | `-ed` participle after determiner (`Advanced Analytics Roadmap`) | flagged | ✓ |
| V-27 | Short past-tense claims (`Margins collapsed`) | clean | ✓ |
| V-28 | Documented residuals (`Margins compress`) | xfail(strict) | ✓ |
| V-29 | Single digit is not a strong figure (`Top 3 Growth Levers`) | flagged | ✓ |
| V-30 | Title on `title`/`section` layout | never checked | + |
| V-31 | Empty / whitespace-only title | no crash | + |
| V-32 | Non-ASCII title (accents, CJK) | no crash, sane verdict | + |

### 1.3 Remaining twelve checks

| # | Check | Positive case | Negative case | Status |
|---|---|---|---|---|
| V-40 | `card-count` | 21 non-appendix cards → error | 20 → clean | ✓ (09) / + |
| V-41 | `card-count` | appendix cards excluded from the count | | + |
| V-42 | `title-length` | >14 words → error | 14 → clean | ✓ (09) / + |
| V-43 | `one-message` | 2 charts + 2 tables on one card → error | 1 each → clean | ✓ (09) / + |
| V-44 | `evidence-present` | text-only card, no figure in title → warn | chart present → clean | ✓ (09) / + |
| V-45 | `evidence-present` | `divider` must not count as evidence | | + |
| V-46 | `evidence-present` | figure in title excuses a text-only card | | + |
| V-47 | `answer-first` | no `role:recommendation` in first 3 (business-stakeholder) → error | present → clean | ✓ (03) / ✓ (01) |
| V-48 | `answer-first` | must NOT run for product-demo / startup-pitch | | + |
| V-49 | `notes-present` | content card without `notes` → info | present → clean | ✓ (06) / ✓ |
| V-50 | `notes-present` | title/section cards exempt | | + |
| V-51 | `data-provenance` | chart/table/kpi without `source` → error | `source: user` → clean | ✓ (05) |
| V-52 | `data-provenance` | `source: placeholder` → unverified, exit 0 | | ✓ (05) |
| V-53 | `text-budget` | over word budget → error | at budget → clean | ✓ (04) / + |
| V-54 | `chart-fit` | ≥5 temporal categories on `bar` → warn | Q1–Q4 on `bar` → clean | ✓ (09) / + |
| V-55 | `chart-fit` | `1500` must not read as a year | | + |
| V-56 | `chart-fit` | >5 series → warn | | + |
| V-57 | `contrast` | text/bg below 4.5:1 → error | shipped themes → clean | ✓ (08) / ✓ |
| V-58 | `contrast` | accent/bg below 3:1 → error | | ✓ (08) |
| V-59 | `contrast` | any series pair <60 RGB apart → warn (all pairs, not adjacent) | | + |
| V-60 | `contrast` | series below 3:1 on surface → warn | | + |
| V-61 | `min-type-size` | `body` < 16pt → error | 16 → clean | ✓ (08) / + |
| V-62 | `overflow` | content > available even at ramp floor → error | 98.8% fill → clean | ✓ (04) |
| V-63 | `overflow` | ramp floor is `max(0.85, 16/body)` | | + |

### 1.4 Helpers and entry points

| # | Case | Expect | Status |
|---|---|---|---|
| V-70 | `_block_h` monotonic in content length | taller | ✓ |
| V-71 | `_block_h` narrower width → taller | | ✓ |
| V-72 | `_block_h` ramp floor reduces height | | ✓ |
| V-73 | `_block_h` caption adds height | | ✓ |
| V-74 | `_block_h` identical across all three themes | | ✓ |
| V-75 | `_block_h` for each of the 10 block types returns > 0 | | + |
| V-76 | `_text_lines` wraps at narrow widths | | ✓ |
| V-77 | `_ratio` symmetric, and 1.0 for identical colours | | + |
| V-78 | `_lum` / `_is_hex` reject non-`#RRGGBB` | named finding, no crash | + |
| V-79 | `validate(ir, theme=None)` skips theme-dependent checks, warns on stderr | | + |
| V-80 | `validate(ir, theme, ir_dir)` runs the image-existence gate | | + |
| V-81 | `validate(ir, theme)` without `ir_dir` skips it (library path) | | + |
| V-82 | Malformed JSON → one-line message, not a traceback | | + |
| V-83 | `--passes N` lands in `findings.json` | | + |
| V-84 | Exit 0 clean / 0 unverified-only / 1 on any error | | ✓ |

---

## 2. `report.py`

### 2.1 Gates

| # | Case | Expect | Status |
|---|---|---|---|
| R-01 | No `schema-valid` errors | Gate 1 ✓ | ✓ |
| R-02 | Resolved `schema-valid` error still fails Gate 1 | ✗ | + |
| R-03 | Zero errors | Gate 2 ✓ with counts | ✓ |
| R-04 | Errors present | Gate 2 ✗ with counts | ✓ |
| R-05 | **All errors resolved** — Gate 2 still reads ✗ while §2 drops "must not ship" | pinned, contested | ✓ (05) |
| R-06 | Mean ≥3.5 and no dimension <3 | Gate 3 PASS | ✓ |
| R-07 | Mean ≥3.5 but one dimension = 2 | FAIL | + |
| R-08 | Mean 3.4, all dimensions ≥3 | FAIL | + |

### 2.2 Judge contract

| # | Case | Expect | Status |
|---|---|---|---|
| R-10 | Score outside 1–5 | `judge-contract` error, no mean printed | + |
| R-11 | 4 of 5 dimensions | error naming the missing one; denominator not shrunk | + |
| R-12 | Unknown dimension | dropped from mean, listed under "Ignored" | + |
| R-13 | >5 concerns | cap error, first 5 shown, "showing 5 of N" | + |
| R-14 | Empty `judge.json` | Gate 3 `—`, no crash | + |
| R-15 | Note containing `\|` | escaped, table row intact | + |
| R-16 | Note containing a newline | flattened | + |
| R-17 | Non-integer score (`"4"`, `4.5`, `null`) | contract error | + |

### 2.3 Report sections

| # | Case | Expect | Status |
|---|---|---|---|
| R-20 | Six sections in §12's fixed order | | ✓ |
| R-21 | `unverified` findings first, before errors | | ✓ (05) |
| R-22 | `info` folds into §3 under "Also noted" | | ✓ (06) |
| R-23 | Resolved findings marked `*(resolved by revision)*` | | ✓ (05) |
| R-24 | Unresolved errors get the "must not ship" banner | | ✓ |
| R-25 | Clean deck → "None" in every issue section | | ✓ (01) |
| R-26 | Zero passes → "No revision passes were needed" | | ✓ |
| R-27 | N passes → revision log lists resolved findings | | ✓ (05) |
| R-28 | Concerns carry the "never auto-fixed" note | | ✓ |
| R-29 | Deck-level finding with no card → `deck` referent | | + |
| R-30 | Inline summary matches §13 shape exactly | | ✓ |
| R-31 | `1 errors` — fixed plural labels per §13 | pinned as-is | ✓ (03) |
| R-32 | Exit 0 even when gates fail | | ✓ |

---

## 3. `render_html.py`

| # | Case | Expect | Status |
|---|---|---|---|
| H-01 | Every fixture × every theme renders | no exception | ✓ |
| H-02 | No `<script>`, no `on*=` handlers | | ✓ |
| H-03 | No `file://` anywhere | | ✓ |
| H-04 | Every `<img src>` is a `data:` URI | | ✓ |
| H-05 | Relative src with no `ir_dir` → clear `ValueError` | | ✓ (R13-M3) |
| H-06 | `render()` does not mutate the caller's IR | | ✓ (R13-M4) |
| H-07 | Card count in output = card count in IR | | ✓ |
| H-08 | All 10 block types render | | + |
| H-09 | All 4 layouts render | | + |
| H-10 | All 4 chart kinds render | | + |
| H-11 | Negative bar values → all bars drawn, inside viewBox | | + |
| H-12 | All-negative series → baseline at top, labels inside | | + |
| H-13 | Single negative line point → on-canvas | | + |
| H-14 | Flat series (all equal) → symmetric padding | | + |
| H-15 | 12 series → `+N more`, plot top shifts, no overlap | | + |
| H-16 | Long series names → legend wraps, within width | | + |
| H-17 | Long hbar category labels → truncated, not off-canvas | | + |
| H-18 | Theme value with `<`, `{`, `}` → rejected by `_css_color` | | + |
| H-19 | Non-`#RRGGBB` theme colour → `ValueError` | | + |
| H-20 | `url(...)` in a theme value → rejected | | + |
| H-21 | HTML-special chars in text/titles → escaped | | + |
| H-22 | Unknown `tone` / `fit` → `ValueError` with block id | | + |
| H-23 | Duplicate image across cards → embedded once (cache) | | + |
| H-24 | Image >2MB → stderr warning, still embeds | | + |
| H-25 | Missing `base.css` → exit 1, clear message | | + |
| H-26 | `css=""` produces unstyled output — **R13-M2** | currently silent | + |
| H-27 | Output is deterministic: same input → identical bytes | | + |

---

## 4. `render_pptx.py`

| # | Case | Expect | Status |
|---|---|---|---|
| P-01 | Every fixture renders | no exception | ✓ |
| P-02 | Slide count = card count | | ✓ |
| P-03 | Canvas 960×540pt | | ✓ |
| P-04 | Clause 6: every frame `MSO_AUTO_SIZE.NONE` (API) | | ✓ |
| P-05 | Clause 6: `<a:noAutofit/>` in XML, no `normAutofit`/`spAutoFit` | | ✓ |
| P-06 | Clause 6 covers table cells | | ✓ |
| P-07 | Clause 6 covers decorative autoshapes | | ✓ |
| P-08 | Every `anchor="t"` | | ✓ |
| P-09 | Charts are `<p:graphicFrame>`, never `<p:pic>` | | ✓ |
| P-10 | `ppt/media/` count ≤ real `image` block count | | ✓ |
| P-11 | `ppt/charts/chartN.xml` exists per chart | | ✓ |
| P-12 | Native `<a:tbl>` for tables | | + |
| P-13 | Text selectable — `<a:t>` runs present | | ✓ |
| P-14 | Theme family reaches PowerPoint | | ✓ |
| P-15 | Theme series colours applied per series | | + |
| P-16 | Pie per-point fills | | + |
| P-17 | Hero + image → full-bleed, title overlay (clause 4) | | + |
| P-18 | Hero + kpi → centred at 2× (clause 4) | | + |
| P-19 | `title`/`section` centre vertically | | + |
| P-20 | `render()` does not mutate caller IR | | ✓ |
| P-21 | Relative src + `ir_dir` resolves | | ✓ |
| P-22 | Chart height tracks `_block_h` when a caption is present | | + |
| P-23 | Embedded worksheet (`externalData`) present per chart | | + |

---

## 5. Peer agreement — `card-schema.md` §5.1

| # | Case | Expect | Status |
|---|---|---|---|
| X-01 | Every block emits a named shape (incl. `columns` marker) | | ✓ |
| X-02 | Top edges match `_block_h` within 0.01pt | | ✓ |
| X-03 | Block order preserved vs IR | | ✓ |
| X-04 | Slide count = card count | | ✓ |
| X-05 | Geometry identical across all three themes | | ✓ |
| X-06 | Both renderers reject the same bad IR, same-shaped `ValueError` | | ✓ |
| X-07 | Error messages carry card and block ids in both | | ✓ |
| X-08 | Nested `columns` children land at the same x offsets in both | | + |

---

## 6. `export_pdf.py`

**These are the artifact tests** — see the convention below. Every case that
produces a PDF keeps it.

| # | Case | Expect | Artifact | Status |
|---|---|---|---|---|
| E-01 | `find_browser()` with no browser | clean message, exit 1, no traceback | — | ✓ |
| E-02 | `find_browser(override)` with a bad path | exit 1 | — | + |
| E-03 | `find_browser` requires executable, not merely present | | — | + |
| E-04 | Stale PDF removed before render | prior file gone on failure | — | ✓ |
| E-05 | Page count = card count | pass | `out/e05/deck.pdf` | ✓ |
| E-06 | Page count ≠ card count | `RuntimeError`, pagination message | — | ✓ |
| E-07 | Unreadable page count (0) | gate skipped with warning, not failure | — | ✓ |
| E-08 | Browser exits non-zero | surfaced, not swallowed | — | + |
| E-09 | Browser writes nothing | `RuntimeError`, no stale file | — | ✓ |
| E-10 | **Real export, all fixtures** | `%PDF-`, page count = cards | `out/pdf/<fixture>.pdf` | ✓ (one) |
| E-11 | **Real export, all three themes** | | `out/pdf/<theme>.pdf` | + |
| E-12 | MediaBox = 13.333 × 7.5 in | | as E-10 | + |
| E-13 | Text selectable in the PDF (`Tj`/`TJ` operators) | | as E-10 | + |
| E-14 | No `/Image` XObjects except real image blocks | | as E-10 | + |
| E-15 | 400-word card overflows visibly rather than shrinking | | `out/pdf/overflow.pdf` | + |
| E-16 | `--no-sandbox` accepted | | — | + |

---

## 7. Pipeline / CLI wiring

| # | Case | Expect | Status |
|---|---|---|---|
| C-01 | validate → report handoff via `findings.json` | | ✓ |
| C-02 | Both renderers from one IR | | ✓ |
| C-03 | All three themes through the whole chain | | ✓ |
| C-04 | Exit 1 on error findings | | ✓ |
| C-05 | Exit 0 on clean | | ✓ |
| C-06 | Exit 0 on unverified-only | | ✓ |
| C-07 | report exits 0 when gates fail | | ✓ |
| C-08 | Renderer exits 1 on invalid IR | | ✓ |
| C-09 | Inline summary goes to stdout for verbatim relay | | ✓ |
| C-10 | Missing `--ir` file → clean message, not traceback (**R13-L5**) | | + |
| C-11 | Missing `--theme` file → clean message | | + |
| C-12 | Unwritable `--out` path → clean message | | ✓ |
| C-13 | `--out` parent directory created if absent | | ✓ |
| C-14 | stdlib-only scripts import with `pptx`/`PIL` blocked | | ✓ |
| C-15 | Missing browser fails only the PDF; HTML untouched | | ✓ |
| C-16 | Missing `python-pptx` fails only the PPTX | | ✓ |

---

## 8. Golden set

| # | Case | Expect | Status |
|---|---|---|---|
| G-01 | All 9 fixtures match `expected/` | | ✓ |
| G-02 | All 14 Tier-1 checks exercised; `--coverage` exits 1 otherwise | | ✓ |
| G-03 | `--only NN` isolates one fixture | | + |
| G-04 | `--update` prints `CREATED` + counts on a new baseline | | + |
| G-05 | `runs.json` `passes` / `resolved` selectors applied | | ✓ |
| G-06 | Mutation: silencing any check turns the set red | | + (manual) |

---

## 9. Themes

| # | Case | Expect | Status |
|---|---|---|---|
| T-01 | Each shipped theme passes its own contrast gate | | ✓ |
| T-02 | All series pairs ≥60 RGB apart | | ✓ |
| T-03 | Every series ≥3:1 on surface | | ✓ |
| T-04 | All three share identical scale and spacing | | ✓ |
| T-05 | Every theme has the same key shape | | + |
| T-06 | Every colour is `#RRGGBB` | | + |
| T-07 | `base.css` contains zero hex literals | | + |
| T-08 | Every CSS var `base.css` uses is emitted by `_css_vars` | | + |

---

## 10. Docs, skills, packaging

| # | Case | Expect | Status |
|---|---|---|---|
| D-01 | Playbook card budgets match `CARD_LIMITS` | | + |
| D-02 | Playbooks claiming answer-first match `ANSWER_FIRST` | | + |
| D-03 | Playbook example "good claim" titles pass the checker | | + |
| D-04 | Playbook example "bad label" titles fail it | | + |
| D-05 | No hardcoded absolute paths in either SKILL.md | | + |
| D-06 | Both SKILL.md files have valid frontmatter | | + |
| D-07 | Themes offered by SKILL.md all exist in `themes/` | | + |
| D-08 | Packaged subset runs standalone (no `evals/`, no spec) | | ✓ (CI) |
| D-09 | Archive validates `--strict` clean | | + |
| D-10 | `plugin.json` version matches the tag | | + |
| D-11 | No file in the archive references an excluded path | | + |

---

## 11. Out of scope

| # | Case | Why |
|---|---|---|
| ○-01 | Claude authoring `deck.json` | LLM in the loop — an eval, not a test |
| ○-02 | Tier-2 judge scoring | same |
| ○-03 | Revision-loop convergence | same; `runs.json` pins the output shape only |
| ○-04 | Visual correctness ("does it look good") | human review |
| ○-05 | Cowork install | different runtime, not reachable from CI |
| ○-06 | PowerPoint/Keynote open-and-edit behaviour | needs the real apps |

---

## Artifact convention

Everything above that produces a file writes it under `evals/out/`, kept after
the run rather than discarded with `tmp_path`. Rationale: a failing PDF assertion
tells you a number is wrong; the PDF itself tells you why. Artifacts are also
what you hand to someone reviewing a change.

```
evals/out/
├── html/<fixture>-<theme>.html
├── pptx/<fixture>-<theme>.pptx
├── pdf/<fixture>-<theme>.pdf
└── report/<fixture>.md
```

Add to `evals/conftest.py`:

```python
OUT = ROOT / "evals" / "out"


@pytest.fixture(scope="session", autouse=True)
def _clean_out():
    """Wipe once per session, not per test — a stale artifact from a previous
    run is worse than no artifact, but wiping per test loses everything the
    moment the session ends."""
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    yield


@pytest.fixture
def artifacts(request):
    """A per-test directory under evals/out/, named for the test node so a
    parametrised case does not overwrite its siblings."""
    safe = re.sub(r"[^\w.-]+", "_", request.node.name)
    d = OUT / safe
    d.mkdir(parents=True, exist_ok=True)
    return d
```

Then swap `tmp_path` → `artifacts` in the render, export and pipeline tests.
Keep `tmp_path` where the file is scratch and nobody would look at it — the
stub-browser PDFs in E-06/E-07, for instance.

Add `evals/out/` to `.gitignore`, and upload it from CI as an artifact so a
failed run on GitHub still gives you the files:

```yaml
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-artifacts-py${{ matrix.python-version }}
          path: evals/out/
```

`if: always()` matters — the artifacts are most useful precisely when the step
before them failed.

---

## Counts

| Section | Existing | To write |
|---|---|---|
| validate.py | ~35 | ~45 |
| report.py | ~18 | ~17 |
| render_html.py | 7 | 20 |
| render_pptx.py | 12 | 11 |
| Peer agreement | 7 | 1 |
| export_pdf.py | 6 | 10 |
| Pipeline / CLI | 12 | 7 |
| Golden set | 3 | 3 |
| Themes | 4 | 4 |
| Docs / packaging | 1 | 10 |
| **Total** | **~105** | **~128** |

Priority if you are not writing all of them: the chart-geometry cases (H-11
through H-17) reproduce five bugs that actually shipped and are the highest-value
gap; the judge-contract cases (R-10 through R-17) guard the only remaining
unvalidated LLM input; D-01 through D-04 catch doc/code drift, which is what
rots first once four playbooks exist.
