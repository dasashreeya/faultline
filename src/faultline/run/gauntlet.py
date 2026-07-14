"""Gauntlet runner: N scenarios x M seeds under the fault schedule."""

from __future__ import annotations

import asyncio
import json
import time
import uuid

from faultline.config import Config, load_scenarios, resolve
from faultline.faults.scheduler import attack_for, build_schedule
from faultline.intercept.adapters.openai_agents import Transcript, wrap_tools
from faultline.judge.detectors import run_detectors
from faultline.judge.judge import grade_run
from faultline.ledger.store import Ledger
from faultline.score.resilience import resilience_score


async def run_one(
    cfg: Config,
    scenario: dict,
    seed: int,
    attempt: int,
    schedule: dict | None = None,
    plan: dict | None = None,
) -> dict:
    """One faulted run. Pass schedule={'entries': []} for a fault-free golden run."""

    agent_fn = resolve(cfg.agent_entrypoint)
    build_tools = resolve(cfg.tools_entrypoint)
    reset_backend = resolve(cfg.reset_entrypoint)
    snapshot = resolve(cfg.snapshot_entrypoint)

    db_path = str(cfg.state_dir / f"backend-{scenario['id']}-s{seed}.sqlite3")
    reset_backend(db_path)
    attack = attack_for(plan, scenario["id"])
    if schedule is None:
        schedule = build_schedule(scenario, seed, attack=attack)
    transcript = Transcript()
    tools = wrap_tools(build_tools(db_path), schedule, transcript)

    start = time.monotonic()
    try:
        answer = await asyncio.wait_for(
            agent_fn(scenario["task"], tools, cfg.agent_model), timeout=cfg.run_timeout_s
        )
        transcript.add("final_answer", content=answer)
    except TimeoutError:
        if time.monotonic() - start >= cfg.run_timeout_s:
            transcript.add("exception", content="run exceeded wall-clock budget; killed")
        else:
            transcript.add("exception", content="TimeoutError: tool call timed out")
    except Exception as exc:
        transcript.add("exception", content=repr(exc))

    end_state = snapshot(db_path)
    record = {
        "run_id": uuid.uuid4().hex[:12],
        "scenario_id": scenario["id"],
        "seed": seed,
        "attempt": attempt,
        "fault_schedule": schedule,
        "transcript": transcript.events,
        "end_state": end_state,
        "detectors": run_detectors(transcript.events, end_state, scenario),
        # The planner's prediction rides along into the dossier, so Codex sees
        # *why* this fault was aimed here, not just that it landed.
        "planner_hypothesis": attack.get("hypothesis") if attack else None,
        "cost": {
            "tool_calls": sum(1 for e in transcript.events if e["type"] == "tool_call"),
            "wall_time_s": round(time.monotonic() - start, 3),
        },
    }
    record["judge"] = await grade_run(record, scenario, cfg.judge_mode, cfg.judge_model)
    return record


def load_plan_if_any(cfg: Config) -> dict | None:
    """Use the attack plan from `faultline plan` when one exists.

    The gauntlet is still fully seeded without it — the plan only *aims* the
    faults it names. Absent a plan, the scheduler's seeded draw stands.
    """
    plan_path = cfg.state_dir / "attack_plan.json"
    if not plan_path.exists():
        return None
    try:
        return json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


async def run_gauntlet(
    cfg: Config,
    attempt: int,
    on_run=None,
    plan: dict | None = None,
    persist: bool = True,
) -> tuple[float, list[dict]]:
    """Full gauntlet for one attempt. Persists runs + score; returns (RS, records).

    `persist=False` scores a gauntlet without touching the ledger — used by the
    planner-vs-random eval, which must not pollute the survival curve.
    """

    scenarios = load_scenarios(cfg.scenarios_path)
    if plan is None:
        plan = load_plan_if_any(cfg)
    ledger = Ledger(cfg.state_dir / "ledger.sqlite3") if persist else None
    if ledger:
        ledger.clear_attempt(attempt)  # an attempt is a complete re-run; old rows are stale
    records = []
    for scenario in scenarios:
        for seed in cfg.seeds:
            if cfg.isolation == "subprocess":
                from faultline.run.sandbox import run_one_subprocess

                rec = await run_one_subprocess(cfg, scenario, seed, attempt, plan=plan)
            else:
                rec = await run_one(cfg, scenario, seed, attempt, plan=plan)
            if ledger:
                ledger.add_run(rec)
            records.append(rec)
            if on_run:
                on_run(rec)
    rs = resilience_score(records)
    if ledger:
        ledger.add_score(attempt, rs)
    return rs, records
