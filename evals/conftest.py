"""Shared fixtures for the deck-builder test suite.

The five scripts are CLIs, not a package, so every test module reaches them
the same way run_golden.py does: prepend scripts/ to sys.path and import.
Keep that in one place.

Artifacts (HTML, PPTX, PDF, report.md) are written under evals/out/ and kept
after the run rather than discarded with tmp_path — a failing assertion tells
you a number is wrong; the artifact tells you why.
"""

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

GOLDEN = ROOT / "evals" / "golden"
FIXTURES = ROOT / "evals" / "fixtures"
THEMES = ROOT / "themes"
OUT = ROOT / "evals" / "out"

# Two fixtures are excluded from render tests because both exist to FAIL a
# gate, and a renderer is never reached with input the gates rejected:
#   09-malformed  — invalid IR by construction
#   08-bad-theme  — valid IR, deliberately broken theme (non-hex colour)
NOT_RENDERABLE = ("malformed", "bad-theme")

ALL_THEMES = ["slate", "warm", "mono"]


def _is_ir(path):
    """golden/ also holds runs.json (run context, not a deck), so select on
    shape rather than on filename."""
    try:
        return isinstance(json.loads(path.read_text(encoding="utf-8")).get("cards"), list)
    except Exception:
        return False


RENDERABLE = sorted(
    p for p in GOLDEN.glob("*.json")
    if p.is_file() and _is_ir(p)
    and not any(k in p.name for k in NOT_RENDERABLE)
)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def theme_for(name):
    """Themes resolve against evals/golden/themes/ first, themes/ second —
    the same order run_golden.py uses, so 08's deliberately broken theme never
    has to sit in the shipped directory."""
    local = GOLDEN / "themes" / f"{name}.json"
    return load(local if local.exists() else THEMES / f"{name}.json")


def theme_path(name):
    """Same resolution order, but the path — CLI tests pass paths, not dicts."""
    local = GOLDEN / "themes" / f"{name}.json"
    return local if local.exists() else THEMES / f"{name}.json"


# ---- artifacts -------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _clean_out():
    """Wipe once per session, not per test. Per-test cleanup would lose every
    artifact the moment the run ends, which defeats the point; leaving stale
    files from a previous run is worse than having none."""
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture
def artifacts(request):
    """A per-test directory under evals/out/, named for the test node so a
    parametrised case cannot overwrite its siblings.

    Use this wherever the output is worth looking at. Keep tmp_path where the
    file is genuinely scratch — the stub-browser PDFs, for instance."""
    safe = re.sub(r"[^\w.-]+", "_", request.node.name).strip("_")
    d = OUT / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---- IR and themes ---------------------------------------------------------

@pytest.fixture(scope="session")
def slate():
    return theme_for("slate")


@pytest.fixture(params=ALL_THEMES)
def any_theme(request):
    return request.param, theme_for(request.param)


@pytest.fixture(params=RENDERABLE, ids=lambda p: p.stem)
def renderable_ir(request):
    """Yields (path, ir). Pass the path's parent as `ir_dir` when rendering —
    both render() signatures take it now (R13-M1), so nothing here needs to
    pre-resolve image srcs."""
    return request.param, load(request.param)


@pytest.fixture(scope="session")
def all_blocks():
    return load(FIXTURES / "all-blocks.json")


@pytest.fixture(scope="session")
def all_blocks_dir():
    return FIXTURES
