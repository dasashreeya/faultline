"""Failure dossier builder — everything Codex needs to harden one failing
scenario, per schemas/dossier.schema.json. Worst failures first."""

import json

from faultline.faults.library import TIER0_FAULTS


def _end_state_diff(scenario: dict, record: dict) -> str:
    refunds = [r["order_id"] for r in record["end_state"].get("refunds", [])]
    return f"expected end state {scenario.get('end_state', {})}; actual refunds issued: {refunds or 'none'}"


def build_dossiers(records: list[dict], scenarios: list[dict], repo_hints: list[str]) -> list[dict]:
    """One dossier per failing scenario (worst run), sorted worst-first."""
    by_id = {s["id"]: s for s in scenarios}
    worst: dict[str, dict] = {}
    for rec in records:
        cur = worst.get(rec["scenario_id"])
        if cur is None or rec["judge"]["weight"] < cur["judge"]["weight"]:
            worst[rec["scenario_id"]] = rec

    dossiers = []
    for sid, rec in worst.items():
        if rec["judge"]["weight"] >= 1.0:
            continue  # scenario survived; nothing to harden
        fault_id = rec["fault_schedule"]["entries"][0]["fault"]
        dossiers.append(
            {
                "scenario_id": sid,
                "fault_class": TIER0_FAULTS[fault_id].fault_class,
                "fault_schedule": rec["fault_schedule"],
                "run_ids": [r["run_id"] for r in records if r["scenario_id"] == sid],
                "judge_grade": rec["judge"]["grade"],
                "judge_reasoning": rec["judge"]["reasoning"],
                "transcript_excerpt": json.dumps(rec["transcript"][-15:], indent=1, default=str),
                "end_state_diff": _end_state_diff(by_id[sid], rec),
                "planner_hypothesis": rec.get("planner_hypothesis"),
                "repo_hints": repo_hints,
            }
        )
    return sorted(dossiers, key=lambda d: (d["judge_grade"] != "E", d["judge_grade"] != "D"))
