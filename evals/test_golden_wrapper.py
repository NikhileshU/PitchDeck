"""Wrap the existing golden harness so one command runs everything.

run_golden.py stays a standalone CLI — it is the phase-10 checkpoint and the
thing you run while iterating. This just means CI does not have to know about
two runners, and a golden failure surfaces in the same report as everything else.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "evals" / "run_golden.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(HARNESS), *args],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_all_fixtures_match_expected():
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_tier1_check_is_exercised():
    """A check no fixture reaches could be silently broken and still ship
    green — that was true of 8 of the 14 until phase 11."""
    r = _run("--coverage")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "14/14" in r.stdout, r.stdout
