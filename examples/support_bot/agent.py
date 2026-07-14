"""Support-bot: OpenAI Agents SDK agent with lookup_order + refund_order tools
against the mock backend. The primary demo agent.

Intentionally naive: no retries, no timeout, no freshness validation —
vulnerable to F3 stale-data and F5 injected-instruction. The point is that
`faultline harden` (Codex) adds the armor, not us. Owner: Person A, Day 1.
"""


def build_agent(db_path: str):
    raise NotImplementedError("tier-0, day 1")
