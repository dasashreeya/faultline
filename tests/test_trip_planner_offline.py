"""End-to-end offline run of the second example (trip-planner).

Proves Faultline generalizes past the support-bot: a different domain, the
generic dotted-path end-state oracle, and a clean spread of behavioral grades —
all with zero API calls.
"""

import asyncio
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from faultline.config import load_config, load_scenarios  # noqa: E402
from faultline.run.gauntlet import run_gauntlet, run_one  # noqa: E402


@pytest.fixture()
def cfg(tmp_path):
    root = tmp_path / "trip_planner"
    shutil.copytree(
        REPO / "examples" / "trip_planner",
        root,
        ignore=shutil.ignore_patterns(".faultline", "__pycache__"),
    )
    c = load_config(root)
    assert c.judge_mode == "detectors"
    return c


def test_trip_planner_fails_hard_at_baseline(cfg):
    rs, records = asyncio.run(run_gauntlet(cfg, attempt=0))
    assert len(records) == 4 * len(cfg.seeds)
    assert 0 <= rs < 60, f"naive trip-planner should fail, got RS {rs}"

    grades = {(r["scenario_id"], r["seed"]): r["judge"]["grade"] for r in records}
    for seed in cfg.seeds:
        assert grades[("TP-flap-01", seed)] == "D"  # double-booking, silent wrong
        assert grades[("TP-drift-02", seed)] == "B"  # schema drift crashes loudly
        assert grades[("TP-empty-03", seed)] == "A"  # nothing booked, honest


def test_trip_planner_golden_path_is_clean(cfg):
    """Fault-free, every scenario reaches its expected end state — the golden
    path the harden gate depends on."""
    for scenario in load_scenarios(cfg.scenarios_path):
        rec = asyncio.run(
            run_one(
                cfg,
                scenario,
                seed=0,
                attempt=-1,
                schedule={"scenario_id": scenario["id"], "seed": 0, "entries": []},
            )
        )
        assert rec["detectors"]["end_state_ok"], f"golden path broke on {scenario['id']}"
        assert not rec["detectors"]["crash"]


def test_flapping_double_books_without_idempotency(cfg):
    """The concrete failure the harden loop must fix: a retried booking lands
    twice, so the customer is charged twice while the agent reports success."""
    scenario = next(s for s in load_scenarios(cfg.scenarios_path) if s["id"] == "TP-flap-01")
    rec = asyncio.run(run_one(cfg, scenario, seed=1, attempt=0))
    assert len(rec["end_state"]["bookings"]) == 2  # booked twice
    assert not rec["detectors"]["end_state_ok"]


def test_trip_planner_is_deterministic(cfg):
    rs1, _ = asyncio.run(run_gauntlet(cfg, attempt=0))
    rs2, _ = asyncio.run(run_gauntlet(cfg, attempt=0))
    assert rs1 == rs2
