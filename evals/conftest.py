"""Shared fixtures for the deck-builder test suite.

The five scripts are CLIs, not a package, so every test module reaches them
the same way run_golden.py does: prepend scripts/ to sys.path and import.
Keep that in one place.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

GOLDEN = ROOT / "evals" / "golden"
FIXTURES = ROOT / "evals" / "fixtures"
THEMES = ROOT / "themes"

# Fixtures that are valid IR. 09-malformed is excluded from render tests:
# it exists to fail validation, and asking a renderer to draw it is meaningless.
def _is_ir(path):
    """golden/ also holds runs.json (run context, not a deck), so select on
    shape rather than on filename."""
    try:
        return isinstance(json.loads(path.read_text(encoding="utf-8")).get("cards"), list)
    except Exception:
        return False


# Two fixtures are excluded from render tests because both exist to FAIL a
# gate, and a renderer is never reached with input the gates rejected:
#   09-malformed  — invalid IR by construction
#   08-bad-theme  — valid IR, deliberately broken theme (non-hex colour)
NOT_RENDERABLE = ("malformed", "bad-theme")

RENDERABLE = sorted(
    p for p in GOLDEN.glob("*.json")
    if p.is_file() and _is_ir(p)
    and not any(k in p.name for k in NOT_RENDERABLE)
)

ALL_THEMES = ["slate", "warm", "mono"]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def theme_for(name):
    """Themes resolve against evals/golden/themes/ first, themes/ second —
    the same order run_golden.py uses, so 08's deliberately broken theme
    never has to sit in the shipped directory."""
    local = GOLDEN / "themes" / f"{name}.json"
    return load(local if local.exists() else THEMES / f"{name}.json")


@pytest.fixture(scope="session")
def slate():
    return theme_for("slate")


@pytest.fixture(params=ALL_THEMES)
def any_theme(request):
    return request.param, theme_for(request.param)


def resolve_images(ir, base):
    """Neither render() resolves relative image srcs — only the CLI main() does
    (render_pptx._resolve_images / render_html._embed_images). A library caller
    has to do it itself, so the tests do what the CLI does first."""
    import render_pptx
    for card in ir["cards"]:
        render_pptx._resolve_images(card.get("blocks"), Path(base).resolve())
    return ir


@pytest.fixture(params=RENDERABLE, ids=lambda p: p.stem)
def renderable_ir(request):
    ir = resolve_images(load(request.param), request.param.parent)
    return request.param, ir


@pytest.fixture(scope="session")
def all_blocks():
    return resolve_images(load(FIXTURES / "all-blocks.json"), FIXTURES)
