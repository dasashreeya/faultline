"""Seeded fault scheduler — the determinism primitive the whole loop rests on.

The schedule is a pure function of (seed, scenario): same inputs, same chaos.
That is what makes "re-run the gauntlet after patching" a valid experiment.
Do NOT add wall-clock, randomness, or run-order dependence here, ever.
"""

import random

from faultline.faults.library import TIER0_FAULTS, Fault


def _rng(seed: int, scenario_id: str) -> random.Random:
    return random.Random(f"{seed}:{scenario_id}")


def attack_for(plan: dict | None, scenario_id: str) -> dict | None:
    """The planner's best-ranked attack against this scenario, if it named one.

    Ties break on rank then fault id, so the choice stays a pure function of
    the plan file — no dict-order dependence.
    """
    if not plan:
        return None
    attacks = [a for a in plan.get("attacks", []) if a.get("scenario_id") == scenario_id]
    if not attacks:
        return None
    return min(attacks, key=lambda a: (int(a.get("rank", 10**6)), str(a.get("fault", ""))))


def build_schedule(scenario: dict, seed: int, attack: dict | None = None) -> dict:
    """Return a FaultSchedule (schemas/fault_schedule.schema.json).

    Scenario knobs: `fault_pool` (allowed fault ids), `fault_targets`
    (tools to aim at, default all), `fault_step` (which call to the target
    gets hit; default 0 = first call, so short agent runs still get bitten).

    When the planner supplied an `attack` for this scenario, it aims the fault
    instead of the seeded draw — this is what makes `faultline plan` steer the
    chaos rather than just describe it. The seed still selects everything the
    plan left unspecified, so a planned gauntlet is just as reproducible.
    """
    rng = _rng(seed, scenario["id"])
    pool: list[Fault] = [TIER0_FAULTS[fid] for fid in scenario.get("fault_pool", TIER0_FAULTS)]
    fault = rng.choice(sorted(pool, key=lambda f: f.id))
    targets = sorted(scenario.get("fault_targets", scenario["tools"]))
    target = rng.choice(targets)
    step = int(scenario.get("fault_step", 0))

    if attack:
        # The plan may name a fault we don't ship, or a tool this scenario
        # doesn't use — ignore those rather than crash the gauntlet on a bad plan.
        if attack.get("fault") in TIER0_FAULTS:
            fault = TIER0_FAULTS[attack["fault"]]
        if attack.get("target") in scenario["tools"]:
            target = attack["target"]
        if attack.get("step_hint") is not None:
            step = int(attack["step_hint"])

    return {
        "scenario_id": scenario["id"],
        "seed": seed,
        "entries": [
            {
                "step": step,
                "surface": "tool",
                "target": target,
                "fault": fault.id,
                "params": fault.params,
            }
        ],
    }
