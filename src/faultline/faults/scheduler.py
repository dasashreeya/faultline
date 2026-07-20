"""Seeded fault scheduler — the determinism primitive the whole loop rests on.

The schedule is a pure function of (seed, scenario): same inputs, same chaos.
That is what makes "re-run the gauntlet after patching" a valid experiment.
Do NOT add wall-clock, randomness, or run-order dependence here, ever.
"""

import random

from faultline.faults.library import TIER0_FAULTS, Fault


def _rng(seed: int, scenario_id: str) -> random.Random:
    return random.Random(f"{seed}:{scenario_id}")


def resolve_fault(fault_id: str) -> Fault | None:
    """Look a fault up across every surface's registry (tool and LLM).

    Kept lazy so the scheduler doesn't import the interception package at
    module load — the two only meet through this one function.
    """
    if fault_id in TIER0_FAULTS:
        return TIER0_FAULTS[fault_id]
    from faultline.intercept.faults_llm import LLM_FAULTS

    return LLM_FAULTS.get(fault_id)


def fault_surface(fault_id: str) -> str:
    """Which injection surface a fault fires on: 'llm' or 'tool'/'mcp'."""
    from faultline.intercept.faults_llm import is_llm_fault

    return "llm" if is_llm_fault(fault_id) else "tool"


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


def build_schedule(
    scenario: dict,
    seed: int,
    attack: dict | None = None,
    intensity: float = 1.0,
) -> dict:
    """Return a FaultSchedule (schemas/fault_schedule.schema.json).

    Scenario knobs: `fault_pool` (allowed fault ids), `fault_targets`
    (tools to aim at, default all), `fault_step` (which call to the target
    gets hit; default 0 = first call, so short agent runs still get bitten).

    When the planner supplied an `attack` for this scenario, it aims the fault
    instead of the seeded draw — this is what makes `faultline plan` steer the
    chaos rather than just describe it. The seed still selects everything the
    plan left unspecified, so a planned gauntlet is just as reproducible.
    """
    if not 0.0 <= intensity <= 1.0:
        raise ValueError("fault intensity must be between 0 and 1")

    rng = _rng(seed, scenario["id"])
    pool_ids = list(scenario.get("fault_pool", TIER0_FAULTS))
    pool: list[Fault] = [f for f in (resolve_fault(fid) for fid in pool_ids) if f is not None]
    if not pool:  # a scenario with an all-unknown pool degrades to the tool library
        pool = list(TIER0_FAULTS.values())
    fault = rng.choice(sorted(pool, key=lambda f: f.id))
    targets = sorted(scenario.get("fault_targets", scenario["tools"]))
    # Always draw the target, even for LLM faults, so a tool-surface scenario's
    # RNG sequence is byte-for-byte what it was before LLM faults existed.
    target = rng.choice(targets)
    step = int(scenario.get("fault_step", 0))

    if attack:
        # The plan may name a fault we don't ship, or a tool this scenario
        # doesn't use — ignore those rather than crash the gauntlet on a bad plan.
        resolved = resolve_fault(attack.get("fault", ""))
        if resolved is not None:
            fault = resolved
        if attack.get("target") in scenario.get("tools", []):
            target = attack["target"]
        if attack.get("step_hint") is not None:
            step = int(attack["step_hint"])

    # The surface follows the fault: an LLM fault fires on the model endpoint,
    # so its target is the 'llm' surface, not a named tool.
    surface = fault_surface(fault.id)
    if surface == "llm":
        target = "llm"

    # A frontier point keeps the potential fault in the schedule metadata even
    # when the Bernoulli draw skips injection. This lets the scorer classify a
    # clean run against the fault it was meant to survive.
    if intensity < 1.0 and (intensity == 0.0 or rng.random() >= intensity):
        return {
            "scenario_id": scenario["id"],
            "seed": seed,
            "potential_fault": fault.id,
            "entries": [],
        }

    return {
        "scenario_id": scenario["id"],
        "seed": seed,
        "entries": [
            {
                "step": step,
                "surface": surface,
                "target": target,
                "fault": fault.id,
                "params": fault.params,
            }
        ],
    }
