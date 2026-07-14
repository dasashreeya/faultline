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

    `scenario` supplies `id`, `tools` (names the agent may call), and
    `fault_pool` (fault ids allowed for this scenario, default: all tier-0).
    Tier-0 policy: pick one fault per scenario, aimed at a pseudo-random
    (tool, step). The planner (tier 0: curated JSON) can override `fault_pool`
    to aim the chaos instead.
    """
    rng = _rng(seed, scenario["id"])
    pool: list[Fault] = [TIER0_FAULTS[fid] for fid in scenario.get("fault_pool", TIER0_FAULTS)]
    fault = rng.choice(sorted(pool, key=lambda f: f.id))
    return {
        "scenario_id": scenario["id"],
        "seed": seed,
        "entries": [
            {
                "step": rng.randrange(0, scenario.get("max_steps", 4)),
                "surface": "tool",
                "target": rng.choice(sorted(scenario["tools"])),
                "fault": fault.id,
                "params": fault.params,
            }
        ],
    }
