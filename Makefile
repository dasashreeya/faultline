.PHONY: setup test demo demo-eval demo-trip demo-mcp demo-frontier demo-harden lint

setup:
	uv sync

test:
	uv run pytest -q

# One-command reproduce for judges (submission checklist).
# Runs fully offline: scripted sandbox agent + detectors-only judge.
demo:
	uv run faultline plan --path examples/support_bot
	uv run faultline break --path examples/support_bot
	uv run faultline report --path examples/support_bot

# The planner-vs-random mini-eval: does reading the code first actually pay off?
# Offline, no API key.
demo-eval:
	uv run faultline eval-plan --path examples/support_bot

# The second example (booking domain, LangGraph): breadth signal, offline.
demo-trip:
	uv run faultline break --path examples/trip_planner
	uv run faultline report --path examples/trip_planner

# Raw JSON-RPC research agent through the MCP interceptor, fully offline.
demo-mcp:
	uv run python -m examples.mcp_research.demo --fault stale_data

# Frontier artifact plus the static report's resilience chart.
demo-frontier:
	uv run faultline plan --path examples/support_bot
	uv run faultline frontier --path examples/support_bot

# The full loop (needs `codex` CLI authed; flip judge.mode/agent in
# examples/support_bot/faultline.yaml for the LLM judge + SDK agent).
demo-harden:
	uv run faultline harden --path examples/support_bot
	uv run faultline report --path examples/support_bot

lint:
	uv run python -m compileall -q src
