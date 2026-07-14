"""GPT-5.6 judge: grades the *manner* of failure with ground truth in hand.

Sees transcript + fault schedule (what was injected) + end-state diff.
Structured output; deterministic detectors override. Owner: Person B, Day 1-2.
"""


async def grade_run(run_record: dict) -> dict:
    """Return {grade, weight, reasoning} per the rubric."""
    raise NotImplementedError("tier-0, day 1")
