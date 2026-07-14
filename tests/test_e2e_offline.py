"""End-to-end sandbox run: the full break pipeline (schedule → inject → run
naive agent → detectors → grade → score → ledger) with zero API calls."""

import asyncio
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from faultline.config import load_config  # noqa: E402
from faultline.ledger.store import Ledger  # noqa: E402
from faultline.run.gauntlet import run_gauntlet  # noqa: E402


@pytest.fixture()
def cfg(tmp_path):
    root = tmp_path / "support_bot"
    shutil.copytree(REPO / "examples" / "support_bot", root)
    c = load_config(root)
    assert c.judge_mode == "detectors"  # sandbox default: fully offline
    return c


def test_break_produces_low_baseline_score(cfg):
    rs, records = asyncio.run(run_gauntlet(cfg, attempt=0))
    assert len(records) == 4 * len(cfg.seeds)
    assert 0 <= rs < 60, f"naive agent should fail hard, got RS {rs}"

    grades = {(r["scenario_id"], r["seed"]): r["judge"]["grade"] for r in records}
    for seed in cfg.seeds:
        assert grades[("F3-stale-01", seed)] == "D"  # silent wrong refund
        assert grades[("F5-inject-04", seed)] == "D"  # obeyed injected instruction

    ledger = Ledger(cfg.state_dir / "ledger.sqlite3")
    assert ledger.scores() == [(0, rs)]
    assert len(ledger.runs_for_attempt(0)) == len(records)


def test_gauntlet_is_deterministic(cfg):
    rs1, recs1 = asyncio.run(run_gauntlet(cfg, attempt=0))
    rs2, recs2 = asyncio.run(run_gauntlet(cfg, attempt=0))
    assert rs1 == rs2
    g1 = [(r["scenario_id"], r["seed"], r["judge"]["grade"]) for r in recs1]
    g2 = [(r["scenario_id"], r["seed"], r["judge"]["grade"]) for r in recs2]
    assert g1 == g2
