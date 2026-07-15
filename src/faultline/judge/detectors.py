"""Deterministic detectors — run before the LLM judge, take precedence.

The end-state check is the verification oracle (blueprint §5.4): correctness is
"did the environment reach the expected final state", never text similarity.

Two assertion forms are supported, both against the target's backend snapshot:

* **Legacy refund keys** (support-bot): ``refunded_order`` and ``refund_count``.
  Kept exactly as they were so existing scenarios and the harden loop are
  untouched.
* **Generic dotted paths**, so any example can assert its own effects without
  the oracle knowing the domain:

  ``<collection>.count: N``
      the list at ``end_state[<collection>]`` has exactly ``N`` rows.
  ``<collection>.<field>: [values]`` (or a scalar, or ``null``)
      the set of ``row[<field>]`` across that collection equals the given set
      (``null``/``[]`` means the collection must be empty of that effect).

Example (trip-planner): ``bookings.count: 1`` and ``bookings.flight_id: [FL-9]``.
"""

from collections import Counter
from typing import Any


def _as_set(expected: Any) -> set:
    if expected is None:
        return set()
    if isinstance(expected, (list, tuple, set)):
        return set(expected)
    return {expected}


def _check_dotted(key: str, expected: Any, end_state: dict) -> bool:
    collection, _, op = key.partition(".")
    rows = end_state.get(collection)
    rows = rows if isinstance(rows, list) else []
    if op == "count":
        return len(rows) == int(expected)
    # op names a field; compare the multiset-as-set of that field's values.
    actual = {row.get(op) for row in rows if isinstance(row, dict)}
    return actual == _as_set(expected)


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
        elif "." in key:
            if not _check_dotted(key, expected, end_state):
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
