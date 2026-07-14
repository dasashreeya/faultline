"""Seeded fault scheduler — the determinism primitive the whole loop rests on.

The schedule is a pure function of (seed, scenario): same inputs, same chaos.
That is what makes "re-run the gauntlet after patching" a valid experiment.
Do NOT add wall-clock, randomness, or run-order dependence here, ever.
"""

import random

from faultline.faults.library import TIER0_FAULTS, Fault


def _rng(seed: int, scenario_id: str) -> random.Random:
    return random.Random(f"{seed}:{scenario_id}")


def build_schedule(scenario: dict, seed: int) -> dict:
    """Return a FaultSchedule (schemas/fault_schedule.schema.json).

    Scenario knobs: `fault_pool` (allowed fault ids), `fault_targets`
    (tools to aim at, default all), `fault_step` (which call to the target
    gets hit; default 0 = first call, so short agent runs still get bitten).
    """
    rng = _rng(seed, scenario["id"])
    pool: list[Fault] = [TIER0_FAULTS[fid] for fid in scenario.get("fault_pool", TIER0_FAULTS)]
    fault = rng.choice(sorted(pool, key=lambda f: f.id))
    targets = sorted(scenario.get("fault_targets", scenario["tools"]))
    return {
        "scenario_id": scenario["id"],
        "seed": seed,
        "entries": [
            {
                "step": int(scenario.get("fault_step", 0)),
                "surface": "tool",
                "target": rng.choice(targets),
                "fault": fault.id,
                "params": fault.params,
            }
        ],
    }
