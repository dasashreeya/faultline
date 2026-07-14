"""Gauntlet runner: N scenarios x M seeds under the fault schedule.

Tier 0: asyncio.wait_for + task cancellation with a hard wall-clock kill.
ADD-BACK 5: per-run subprocess isolation. Owner: Person A, Day 2.
"""


async def run_gauntlet(scenarios, seeds, attempt: int):
    """Run every (scenario, seed) pair, write RunRecords to the ledger."""
    raise NotImplementedError("tier-0, day 2")
