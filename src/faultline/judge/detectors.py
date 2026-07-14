"""Deterministic detectors — run before the LLM judge, take precedence.

loop (>=3 identical (tool, args-hash) calls), budget overrun, crash,
end-state check against scenario assertions. Owner: Person B, Day 1.
"""


def run_detectors(run_record: dict) -> dict:
    """Return {loop, budget_overrun, crash, end_state_ok} booleans."""
    raise NotImplementedError("tier-0, day 1")
