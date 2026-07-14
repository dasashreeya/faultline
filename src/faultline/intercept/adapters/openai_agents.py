"""Tool-surface fault injection for the OpenAI Agents SDK (tier 0).

Monkeypatches tool execution so each call consults the FaultSchedule
before hitting the real tool. Owner: Person A, Day 1.
"""


def install(schedule):
    """Patch the Agents SDK tool runner to route calls through `schedule`."""
    raise NotImplementedError("tier-0, day 1")
