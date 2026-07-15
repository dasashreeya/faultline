"""The attack plan must actually steer the chaos.

`faultline plan` used to write attack_plan.json that nothing ever read, which
made the "adversarial planning" claim cosmetic. These tests pin the wiring:
a plan aims the fault, an absent plan falls back to the seeded draw, a bogus
plan cannot crash the gauntlet, and the planner's hypothesis reaches the run
record (and therefore the Codex dossier).
"""

import asyncio
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from faultline.config import load_config, load_scenarios  # noqa: E402
from faultline.faults.scheduler import attack_for, build_schedule  # noqa: E402
from faultline.plan.planner import build_plan  # noqa: E402
from faultline.run.gauntlet import run_gauntlet  # noqa: E402


@pytest.fixture()
def cfg(tmp_path):
    root = tmp_path / "support_bot"
    shutil.copytree(
        REPO / "examples" / "support_bot",
        root,
        ignore=shutil.ignore_patterns(".faultline", "__pycache__"),
    )
    config = load_config(root)
    config.agent_entrypoint = "tests.vulnerable_support_agent:run_task"
    return config


def _scenario(cfg, sid="F2-flap-03"):
    return next(s for s in load_scenarios(cfg.scenarios_path) if s["id"] == sid)


def test_attack_for_picks_the_best_ranked_attack():
    plan = {
        "attacks": [
            {"rank": 3, "scenario_id": "S1", "fault": "empty_result", "target": "t"},
            {"rank": 1, "scenario_id": "S1", "fault": "stale_data", "target": "t"},
            {"rank": 2, "scenario_id": "S2", "fault": "tool_timeout", "target": "t"},
        ]
    }
    assert attack_for(plan, "S1")["fault"] == "stale_data"
    assert attack_for(plan, "S2")["fault"] == "tool_timeout"
    assert attack_for(plan, "missing") is None
    assert attack_for(None, "S1") is None


def test_plan_overrides_the_seeded_draw(cfg):
    scenario = _scenario(cfg)  # fault_pool: [tool_flapping, tool_timeout]
    plan = {
        "attacks": [
            {
                "rank": 1,
                "scenario_id": scenario["id"],
                "fault": "stale_data",  # deliberately NOT in this scenario's pool
                "target": "lookup_orders",
                "step_hint": 0,
                "hypothesis": "planner says so",
            }
        ]
    }
    sched = build_schedule(scenario, seed=1, attack=attack_for(plan, scenario["id"]))
    entry = sched["entries"][0]
    assert entry["fault"] == "stale_data"
    assert entry["target"] == "lookup_orders"


def test_schedule_without_a_plan_is_unchanged(cfg):
    """No plan => the seeded draw still governs, so determinism is preserved."""
    scenario = _scenario(cfg)
    a = build_schedule(scenario, seed=1)
    b = build_schedule(scenario, seed=1, attack=None)
    assert a == b
    assert a["entries"][0]["fault"] in scenario["fault_pool"]


def test_bogus_plan_cannot_crash_the_gauntlet(cfg):
    """A plan naming an unknown fault/tool falls back rather than exploding —
    important because the GPT planner can hallucinate either one."""
    scenario = _scenario(cfg)
    attack = {
        "rank": 1,
        "scenario_id": scenario["id"],
        "fault": "no_such_fault",
        "target": "no_such_tool",
    }
    sched = build_schedule(scenario, seed=1, attack=attack)
    entry = sched["entries"][0]
    assert entry["fault"] in scenario["fault_pool"]  # fell back to the seeded draw
    assert entry["target"] in scenario["tools"]


def test_planner_hypothesis_reaches_the_run_record(cfg):
    """The dossier hands Codex the planner's prediction; it must be populated."""
    plan = build_plan(cfg, mode="curated")
    _, records = asyncio.run(run_gauntlet(cfg, attempt=0, plan=plan, persist=False))
    assert records
    assert all(r["planner_hypothesis"] for r in records)


def test_planned_chaos_beats_blind_chaos(cfg):
    """The core claim of `faultline plan`: aiming finds failures random misses.

    Averaged over baseline seeds so this is not a lucky-draw assertion.
    """

    def critical(plan):
        _, records = asyncio.run(run_gauntlet(cfg, attempt=0, plan=plan, persist=False))
        return sum(1 for r in records if r["judge"]["grade"] in ("D", "E"))

    planned = critical(build_plan(cfg, mode="curated"))
    blind = [critical(build_plan(cfg, mode="random", seed=s)) for s in range(5)]

    assert planned > sum(blind) / len(blind), (
        f"planner found {planned} critical failures; blind chaos averaged "
        f"{sum(blind) / len(blind)} — the planner must beat random"
    )
