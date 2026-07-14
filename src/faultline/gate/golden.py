"""Golden-trace gate: the full scenario suite re-run FAULT-FREE after a patch.

End-state equivalence, not transcript equality — agents are non-deterministic
in wording, deterministic-ish in effects.
"""

from faultline.config import Config, load_scenarios


async def happy_path_ok(cfg: Config) -> tuple[bool, str]:
    from faultline.run.gauntlet import run_one

    for scenario in load_scenarios(cfg.scenarios_path):
        rec = await run_one(cfg, scenario, seed=0, attempt=-1, schedule={"scenario_id": scenario["id"], "seed": 0, "entries": []})
        if not rec["detectors"]["end_state_ok"] or rec["detectors"]["crash"]:
            return False, f"happy path broken on {scenario['id']}"
    return True, "happy path preserved"
