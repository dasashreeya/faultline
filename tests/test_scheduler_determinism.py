"""Determinism is non-negotiable (blueprint §5.1): same (seed, scenario) → same schedule."""

from faultline.faults.scheduler import build_schedule

SCENARIO = {"id": "F3-stale-01", "tools": ["lookup_order", "refund_order"], "max_steps": 4}


def test_same_seed_same_schedule():
    assert build_schedule(SCENARIO, seed=7) == build_schedule(SCENARIO, seed=7)


def test_different_seeds_diverge_somewhere():
    schedules = {str(build_schedule(SCENARIO, seed=s)) for s in range(20)}
    assert len(schedules) > 1


def test_schedule_shape():
    sched = build_schedule(SCENARIO, seed=1)
    assert sched["scenario_id"] == SCENARIO["id"]
    entry = sched["entries"][0]
    assert entry["surface"] == "tool"
    assert entry["target"] in SCENARIO["tools"]
