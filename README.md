# Faultline

**Chaos engineering that fixes what it breaks.**

Point Faultline at an agent codebase. It breaks the agent with LLM-native
faults, grades *how* it fails, then unleashes Codex to harden the code and
re-runs the gauntlet until the Resilience Score clears your gate.

> Status: **scaffold**. The JSON schemas in `schemas/` are the frozen
> interface contract; module stubs mark ownership and build order.
> Scope source of truth: [`FAULTLINE_BLUEPRINT.md`](FAULTLINE_BLUEPRINT.md)
> (tier-0 cut: one agent, tool-surface injection, 5 faults, curated attack
> plan, hybrid judge, Codex hardener, minimal gatekeeper).

## Setup

```bash
uv sync
uv run faultline --help
uv run pytest -q
```

## The loop

```bash
faultline init      # detect framework, write faultline.yaml
faultline plan      # ranked attack plan (tier 0: curated JSON)
faultline break     # gauntlet: scenarios × seeds, graded → Resilience Score
faultline harden    # codex exec loop: patch → gate → re-break until it clears
faultline report    # survival curve + fault matrix
faultline gate --min-score 85   # CI exit code
```

## Layout

```
schemas/            frozen JSON contracts (fault schedule, run record, dossier, patch result, attack plan)
src/faultline/
  intercept/        tool-surface adapter (tier 0) · llm/mcp proxies (add-backs)
  faults/           fault library + seeded deterministic scheduler
  plan/             attack planner (tier 0: curated)
  run/              gauntlet runner, isolation, budgets
  judge/            deterministic detectors + GPT-5.6 rubric judge
  score/            Resilience Score + survival curve
  harden/           failure dossier → codex exec loop
  gate/             golden traces, anti-cheat, gatekeeper
  ledger/           SQLite store + report templates
examples/support_bot/   primary demo agent (deliberately fragile)
action/             GitHub Action wrapping `faultline gate` (add-back)
```

## Ownership

- **Person A — Break:** intercept, faults, run, ledger, examples
- **Person B — Judge & Fix:** judge, score, harden, gate, plan

Rule one: never start an add-back while the core loop is broken.
