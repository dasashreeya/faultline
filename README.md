# Faultline

**Chaos engineering that fixes what it breaks.**

Point Faultline at an agent codebase. It breaks the agent with LLM-native
faults, grades *how* it fails, then unleashes Codex to harden the code and
re-runs the gauntlet until the Resilience Score clears your gate.

> Status: **tier-0 core working.** `break → judge → score → report → gate`
> runs fully offline (scripted sandbox agent + deterministic detectors);
> `harden` shells out to headless `codex exec` behind the golden-trace /
> anti-cheat / monotone-score gatekeeper. Scope source of truth:
> [`FAULTLINE_BLUEPRINT.md`](FAULTLINE_BLUEPRINT.md).

## Quickstart (offline, no API keys)

```bash
uv sync
uv run pytest -q          # includes an end-to-end offline gauntlet
make demo                 # break + report on the support-bot → RS ~29 💀
```

The sandbox default in `examples/support_bot/faultline.yaml` uses the
scripted naive agent and detectors-only judging, so judges can run the whole
thing for free. Flip `target.agent` to the OpenAI Agents SDK entry and
`judge.mode: llm` (needs `OPENAI_API_KEY`) for the real thing; `faultline
harden` additionally needs the `codex` CLI authed.

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
