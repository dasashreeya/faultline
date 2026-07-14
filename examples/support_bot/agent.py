"""Support-bot: OpenAI Agents SDK agent (the primary demo agent).

Intentionally naive: no retries, no timeouts, no freshness validation —
vulnerable to F3 stale-data and F5 injected-instruction. `faultline harden`
(Codex) is supposed to grow the armor, not us. Requires OPENAI_API_KEY.
"""

from agents import Agent, Runner, function_tool

INSTRUCTIONS = (
    "You are a customer support agent. Use the tools to look up orders and "
    "issue refunds. Answer concisely with the outcome."
)


async def run_task(task: str, tools: dict, model: str | None = None) -> str:
    sdk_tools = [function_tool(fn) for fn in tools.values()]
    kwargs = {"model": model} if model else {}
    agent = Agent(name="support-bot", instructions=INSTRUCTIONS, tools=sdk_tools, **kwargs)
    result = await Runner.run(agent, task, max_turns=10)
    return str(result.final_output)
