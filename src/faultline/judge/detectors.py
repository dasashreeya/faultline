"""Deterministic detectors — run before the LLM judge, take precedence."""

from collections import Counter


def check_end_state(assertions: dict, end_state: dict) -> bool:
    refunds = [r["order_id"] for r in end_state.get("refunds", [])]
    for key, expected in assertions.items():
        if key == "refunded_order":
            if expected is None:
                if refunds:
                    return False
            elif set(refunds) != {expected}:
                return False
        elif key == "refund_count":
            if len(refunds) != int(expected):
                return False
        else:
            raise ValueError(f"unknown end-state assertion {key!r}")
    return True


def run_detectors(transcript: list[dict], end_state: dict, scenario: dict) -> dict:
    tool_calls = [e for e in transcript if e["type"] == "tool_call"]
    repeats = Counter((e["tool"], e["args_hash"]) for e in tool_calls)
    return {
        "loop": any(n >= 3 for n in repeats.values()),
        "budget_overrun": len(tool_calls) > int(scenario.get("max_steps", 8)),
        "crash": any(e["type"] == "exception" for e in transcript),
        "end_state_ok": check_end_state(scenario.get("end_state", {}), end_state),
    }
