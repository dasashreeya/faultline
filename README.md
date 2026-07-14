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

## Build log

**`82f641a` — scaffold.** Repo layout per the blueprint (§8), the five frozen
JSON schemas in `schemas/` (fault schedule, run record, dossier, patch result,
attack plan — the interface contract between Break and Judge & Fix), module
stubs carrying owner + build-day, MIT license, Makefile, GitHub Action stub.

**`6b2ddf7` — tier-0 core, working.** Everything needed for
`break → judge → score → report → gate`, plus the harden loop:

- **Faults (5):** `tool_timeout`, `tool_flapping` (the call *lands*, the
  response is lost — naive retries double-refund), `empty_result`,
  `stale_data`, `injected_instruction`. Seeded scheduler: schedule is a pure
  function of `(seed, scenario)`.
- **Interceptor:** wraps raw tool callables below any framework; records the
  transcript; works for both the Agents SDK agent and the scripted one.
- **Runner:** asyncio gauntlet with hard wall-clock kill; SQLite ledger.
- **Judge:** deterministic detectors (loop / budget / crash / end-state) +
  optional GPT structured-output rubric (`judge.mode: llm`).
- **Scorer/report:** Resilience Score, survival-curve SVG, static HTML report,
  CI `gate` exit code.
- **Hardener:** dossier builder → headless `codex exec --output-schema` →
  gatekeeper (golden traces + anti-cheat marker grep + monotone-score revert).
- **Support-bot example:** SQLite mock CRM, deliberately naive agent (SDK and
  scripted variants), 4 scenarios with end-state assertions.

Verified: 14 tests green including an offline end-to-end gauntlet and a
determinism test; `make demo` prints the baseline **RS 28.8/100 💀**. All
external surfaces (`codex exec` flags, Agents SDK, Responses API) checked
against installed versions.

**Not yet verified live:** `faultline harden` end-to-end (the `codex exec`
spike proved the mechanics but hit a ChatGPT usage limit), the LLM judge, and
the SDK agent — all need Codex credits / an `OPENAI_API_KEY`.

**Next up (add-back order):** live harden climb, GPT anti-cheat diff audit,
planner-lite, novelty-claims + prior-art README section, demo video.
