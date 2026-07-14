.PHONY: setup test demo lint

setup:
	uv sync

test:
	uv run pytest -q

# One-command reproduce for judges (submission checklist).
# Tier 0: break + harden + report on the support-bot with fixed seeds.
demo:
	@echo "TODO(day 3): uv run faultline break && uv run faultline harden && uv run faultline report"
	@exit 1

lint:
	uv run python -m compileall -q src
