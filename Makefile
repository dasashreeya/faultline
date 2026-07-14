.PHONY: setup test demo lint

setup:
	uv sync

test:
	uv run pytest -q

# One-command reproduce for judges (submission checklist).
# Runs fully offline: scripted sandbox agent + detectors-only judge.
demo:
	uv run faultline break --path examples/support_bot
	uv run faultline report --path examples/support_bot

# The full loop (needs `codex` CLI authed; flip judge.mode/agent in
# examples/support_bot/faultline.yaml for the LLM judge + SDK agent).
demo-harden:
	uv run faultline harden --path examples/support_bot
	uv run faultline report --path examples/support_bot

lint:
	uv run python -m compileall -q src
