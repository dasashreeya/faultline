"""The Codex dossier must preserve the behavioral contract, not just a transcript."""

import json

from faultline.harden.dossier import build_dossiers


def _record(seed: int, order_id: str) -> dict:
    return {
        "run_id": f"run-{seed}",
        "scenario_id": "F3-stale-01",
        "seed": seed,
        "fault_schedule": {
            "scenario_id": "F3-stale-01",
            "seed": seed,
            "entries": [
                {
                    "step": 0,
                    "surface": "tool",
                    "target": "lookup_orders",
                    "fault": "stale_data",
                    "params": {},
                }
            ],
        },
        "transcript": [],
        "end_state": {"refunds": [{"order_id": order_id}]},
        "judge": {
            "grade": "D",
            "weight": 0.0,
            "reasoning": "wrong end state",
        },
    }


def test_dossier_includes_scenario_oracle_and_all_failing_seeds():
    scenario = {
        "id": "F3-stale-01",
        "task": "Refund avery's most recent order.",
        "tools": ["lookup_orders", "refund_order"],
        "fault_pool": ["stale_data"],
        "fault_targets": ["lookup_orders"],
        "max_steps": 6,
        "end_state": {"refunded_order": "ORD-1002"},
    }

    dossier = build_dossiers(
        [_record(1, "ORD-1001"), _record(3, "ORD-1001")],
        [scenario],
        ["examples.support_bot.naive_agent:run_task"],
    )[0]

    contract = json.loads(dossier["scenario_contract"])
    assert dossier["task"] == scenario["task"]
    assert contract["end_state"] == {"refunded_order": "ORD-1002"}
    assert [run["seed"] for run in dossier["failing_runs"]] == [1, 3]
    assert len(dossier["failing_runs"]) == 2
