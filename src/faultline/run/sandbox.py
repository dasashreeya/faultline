"""Run isolation helpers.

Async cancellation is cheap and works for cooperative agents, but it cannot
kill a sync tool stuck in a worker thread. Subprocess mode runs one gauntlet
case in a child process and terminates the whole process when the wall-clock
budget expires.
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import queue
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

from faultline.config import Config, resolve
from faultline.faults.scheduler import build_schedule
from faultline.judge.detectors import run_detectors
from faultline.judge.judge import grade_run


def _child_run_one(
    cfg_root: str,
    cwd: str,
    scenario: dict[str, Any],
    seed: int,
    attempt: int,
    schedule: dict[str, Any] | None,
    plan: dict[str, Any] | None,
    intensity: float,
    out: mp.Queue,
) -> None:
    try:
        sys.path.insert(0, cwd)
        from faultline.config import load_config
        from faultline.run.gauntlet import run_one

        cfg = load_config(Path(cfg_root))
        record = asyncio.run(
            run_one(
                cfg,
                scenario,
                seed,
                attempt,
                schedule=schedule,
                plan=plan,
                intensity=intensity,
            )
        )
        out.put({"record": record})
    except Exception:
        out.put({"error": traceback.format_exc()})


async def run_one_subprocess(
    cfg: Config,
    scenario: dict[str, Any],
    seed: int,
    attempt: int,
    schedule: dict | None = None,
    plan: dict | None = None,
    intensity: float = 1.0,
) -> dict[str, Any]:
    """Run one faulted scenario in a killable child process."""

    result = await asyncio.to_thread(
        _run_one_subprocess_sync, cfg, scenario, seed, attempt, schedule, plan, intensity
    )
    if "record" in result:
        return result["record"]
    return await _infra_failure_record(
        cfg, scenario, seed, attempt, schedule, result["error"], intensity=intensity
    )


def _run_one_subprocess_sync(
    cfg: Config,
    scenario: dict[str, Any],
    seed: int,
    attempt: int,
    schedule: dict | None,
    plan: dict | None = None,
    intensity: float = 1.0,
) -> dict[str, Any]:
    ctx = mp.get_context("spawn")
    out: mp.Queue = ctx.Queue()
    proc = ctx.Process(
        target=_child_run_one,
        args=(
            str(cfg.root),
            str(Path.cwd().resolve()),
            scenario,
            seed,
            attempt,
            schedule,
            plan,
            intensity,
            out,
        ),
    )
    proc.start()
    proc.join(float(cfg.run_timeout_s) + 2.0)
    if proc.is_alive():
        proc.terminate()
        proc.join(3.0)
        if proc.is_alive():
            proc.kill()
            proc.join()
        return {"error": "subprocess exceeded wall-clock budget; killed"}
    try:
        return out.get(timeout=1.0)
    except queue.Empty:
        return {"error": f"subprocess exited with code {proc.exitcode} without a run record"}


async def _infra_failure_record(
    cfg: Config,
    scenario: dict[str, Any],
    seed: int,
    attempt: int,
    schedule: dict | None,
    error: str,
    intensity: float = 1.0,
) -> dict[str, Any]:
    schedule = schedule or build_schedule(scenario, seed, intensity=intensity)
    transcript = [{"type": "exception", "content": error[-4000:]}]
    db_path = str(cfg.state_dir / f"backend-{scenario['id']}-s{seed}.sqlite3")
    snapshot = {}
    try:
        snapshot = resolve(cfg.snapshot_entrypoint)(db_path)
    except Exception:
        snapshot = {}
    record = {
        "run_id": uuid.uuid4().hex[:12],
        "scenario_id": scenario["id"],
        "seed": seed,
        "attempt": attempt,
        "fault_schedule": schedule,
        "transcript": transcript,
        "end_state": snapshot,
        "detectors": run_detectors(transcript, snapshot, scenario),
        "planner_hypothesis": None,
        "cost": {"tool_calls": 0, "wall_time_s": float(cfg.run_timeout_s)},
    }
    record["judge"] = await grade_run(record, scenario, cfg.judge_mode, cfg.judge_model)
    return record
