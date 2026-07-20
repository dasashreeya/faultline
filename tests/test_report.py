"""Report rendering + ledger integrity.

The report is what judges open, and the survival curve is the claim the whole
project makes. These tests pin the two ways it could quietly lie: duplicated
runs inflating the tables, and unescaped tool output corrupting the page.
"""

import asyncio
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from faultline.config import load_config  # noqa: E402
from faultline.ledger.report.render import render_report  # noqa: E402
from faultline.ledger.store import Ledger  # noqa: E402
from faultline.run.gauntlet import run_gauntlet  # noqa: E402
from faultline.score.resilience import class_breakdown, resilience_score  # noqa: E402


@pytest.fixture()
def cfg(tmp_path):
    root = tmp_path / "support_bot"
    shutil.copytree(
        REPO / "examples" / "support_bot",
        root,
        ignore=shutil.ignore_patterns(".faultline", "__pycache__"),
    )
    return load_config(root)


def _row_count(cfg) -> int:
    conn = sqlite3.connect(cfg.state_dir / "ledger.sqlite3")
    try:
        return conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    finally:
        conn.close()


def test_rerunning_an_attempt_replaces_its_runs(cfg):
    """A re-run of the same attempt must not append a second set of rows.

    run_id is a fresh uuid per run, so without clear_attempt the ledger grew
    every time the gauntlet re-ran — and the harden loop re-runs the gauntlet
    per attempt, which would mix pre-patch and post-patch runs together.
    """
    asyncio.run(run_gauntlet(cfg, attempt=0))
    first = _row_count(cfg)
    assert first == 4 * len(cfg.seeds)

    asyncio.run(run_gauntlet(cfg, attempt=0))
    assert _row_count(cfg) == first, "re-running an attempt duplicated its runs"

    ledger = Ledger(cfg.state_dir / "ledger.sqlite3")
    assert len(ledger.runs_for_attempt(0)) == first


def test_breakdown_contributions_sum_to_the_score(cfg):
    """The heat map has to explain the headline number, not contradict it."""
    rs, records = asyncio.run(run_gauntlet(cfg, attempt=0))
    total = sum(row["contribution"] for row in class_breakdown(records))
    assert total == pytest.approx(resilience_score(records), abs=0.15)
    assert total == pytest.approx(rs, abs=0.15)


def test_report_renders_runs_curve_and_breakdown(cfg):
    asyncio.run(run_gauntlet(cfg, attempt=0))
    ledger = Ledger(cfg.state_dir / "ledger.sqlite3")
    html = render_report(ledger, gate=cfg.gate_min_score)

    assert "<svg" in html and 'class="curve"' in html
    assert "Fault-class heat map" in html
    assert "F3-stale-01" in html
    # one row per run, and no duplicates from a second render
    assert html.count("F3-stale-01") >= len(cfg.seeds)
    assert "Resilience" in html
    assert 'id="run-evidence"' in html
    assert 'class="run-card"' in html
    assert "latest attempt open" in html
    assert "How to read this" not in html


def test_report_renders_frontier_chart_and_exact_values(cfg):
    asyncio.run(run_gauntlet(cfg, attempt=0))
    ledger = Ledger(cfg.state_dir / "ledger.sqlite3")
    frontier = [
        {"intensity": 0.0, "resilience_score": 100.0, "critical_failures": 0, "faulted_runs": 0, "total_runs": 8},
        {"intensity": 1.0, "resilience_score": 20.6, "critical_failures": 6, "faulted_runs": 8, "total_runs": 8},
    ]

    html = render_report(ledger, gate=85.0, frontier=frontier)

    assert 'class="frontier"' in html
    assert 'aria-label="Resilience Score by fault intensity"' in html
    assert 'width="720" height="300"' in html
    assert "100" in html and "20.6" in html
    assert "fault intensity (lambda)" in html


def test_report_escapes_hostile_tool_output():
    """Transcripts embed raw tool results — including the F5 adversarial
    instruction. Markup in a tool result must not be able to inject into the
    report a judge opens in their browser."""

    rec = {
        "attempt": 0,
        "scenario_id": "F5-inject-04",
        "seed": 1,
        "fault_schedule": {"entries": [{"fault": "injected_instruction"}]},
        "judge": {"grade": "D", "weight": 0.0, "reasoning": "<img src=x onerror=alert(1)>"},
        "transcript": [{"type": "tool_result", "content": "</pre><script>alert(1)</script>"}],
        "detectors": {},
        "cost": {},
        "end_state": {},
    }

    class _FakeLedger:
        def scores(self):
            return [(0, 12.0)]

        def runs_for_attempt(self, attempt):
            return [rec]

        def patches(self):
            return []

    html = render_report(_FakeLedger(), gate=85.0)
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert '<svg class="curve"' in html  # trusted markup still renders
    assert 'width="720" height="300"' in html


def test_report_handles_empty_ledger(tmp_path):
    """A judge who runs `faultline report` before `break` gets a page, not a crash."""
    ledger = Ledger(tmp_path / "empty.sqlite3")
    html = render_report(ledger, gate=85.0)
    assert "<html" in html
    assert "faultline break" in html
    assert "faultline frontier" in html
