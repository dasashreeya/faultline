# Faultline

**Chaos engineering that fixes what it breaks.**

Faultline is a developer tool for testing and hardening AI agents. Point it at
an agent codebase and it runs a deterministic chaos gauntlet: inject
LLM-native faults, grade how the agent fails, calculate a Resilience Score, ask
Codex to harden the code, and re-run the same gauntlet until the score clears
the release gate.

Hackathon track: **Developer tools**. The project is designed for OpenAI Build
Week: Codex is part of the product loop, the optional live judge uses GPT-5.6
structured outputs, and the planned planner-lite add-back is scoped for GPT-5.6.

## Why This Can Win

Most agent evals stop at "the model answered incorrectly." Faultline turns that
into an engineering workflow:

1. **Break** the agent with realistic failures: stale tool data, empty results,
   flapping side effects, timeouts, and prompt injection hidden in tool output.
2. **Judge** the run with deterministic detectors and an optional GPT-5.6 rubric
   judge that sees the injected fault ground truth.
3. **Score** the agent with a repeatable Resilience Score and survival curve.
4. **Harden** the target by sending a failure dossier to headless `codex exec`.
5. **Gate** the patch with golden traces, anti-cheat checks, and monotone score
   improvement before accepting it.

The target demo is also the product: a fragile support bot fails the gauntlet,
Codex patches it, and Faultline proves whether the fix generalized.

## Quickstart

Prerequisites: Python 3.11+ and `uv`.

The default demo runs fully offline: no API key, no paid calls, and no live
agent dependency.

```bash
uv sync
uv run pytest -q
make demo
```

`make demo` runs:

```bash
uv run faultline break --path examples/support_bot
uv run faultline report --path examples/support_bot
```

The generated report is written to:

```text
examples/support_bot/.faultline/report.html
```

For the live hardening loop, authenticate the Codex CLI first, then run:

```bash
make demo-harden
```

To exercise the OpenAI Agents SDK target and GPT-5.6 judge, edit
`examples/support_bot/faultline.yaml`:

```yaml
target:
  agent: examples.support_bot.agent:run_task
judge:
  mode: llm
  model: gpt-5.6
```

That live path requires `OPENAI_API_KEY`.

## CLI Flow

```bash
faultline init                 # generate faultline.yaml + starter scenarios.yaml
faultline plan                 # ranked attack plan: curated, random, or GPT-5.6
faultline break                # run scenarios x seeds under injected faults
faultline harden               # Codex loop: dossier -> patch -> gate -> re-break
faultline report               # static HTML report with curve, runs, patches
faultline gate --min-score 85  # CI-style release gate
```

## Implementation Status

| Area | Done now | Evidence in repo | Left to do for full-scale implementation |
| --- | --- | --- | --- |
| Core contracts | Frozen JSON contracts for fault schedules, run records, dossiers, patch results, and attack plans. | `schemas/`, `FAULTLINE_BLUEPRINT.md` | Add schema examples to docs and validate every emitted artifact in CI. |
| Offline demo | Reproducible support-bot sandbox with scripted fragile agent, SQLite backend, four scenarios, and deterministic judge mode. | `examples/support_bot/`, `tests/test_e2e_offline.py` | Commit a sample report artifact or screenshot for judges who skim before running. |
| Fault library | Thirteen faults across F1-F5, including timeout, flapping side effects, stale data, schema drift, malformed JSON, rate limits, auth failures, and prompt-injection variants. | `src/faultline/faults/library.py`, `tests/test_faults.py` | Expand toward the full 22-fault taxonomy and add intensity controls. |
| Fault scheduler | Seeded schedule is a pure function of `(seed, scenario)`, which makes before/after hardening comparisons fair. | `src/faultline/faults/scheduler.py`, `tests/test_scheduler_determinism.py` | Add multi-fault schedules and planner-selected targets while preserving determinism. |
| Tool interception | Tool wrapper records transcripts and injects failures below the agent framework. | `src/faultline/intercept/adapters/openai_agents.py` | Finish LLM proxy and MCP proxy add-backs for model-output and MCP-server fault injection. |
| Runner and budgets | Gauntlet runs every scenario/seed pair, records cost, stores results in SQLite, and supports opt-in subprocess isolation for killable runs. | `src/faultline/run/gauntlet.py`, `src/faultline/run/sandbox.py`, `src/faultline/ledger/store.py` | Make subprocess isolation the recommended production default after more live harden testing. |
| Deterministic judge | Detectors catch loops, budget overruns, crashes, and end-state failures without model calls. | `src/faultline/judge/detectors.py`, `src/faultline/judge/judge.py` | Calibrate the optional GPT-5.6 judge on live runs and document grade examples. |
| Resilience Score | Weighted score and survival curve turn run outcomes into one release-gate number. | `src/faultline/score/`, `tests/test_scorer.py` | Add per-fault-class breakdown to the HTML report and README demo results. |
| Report | Static HTML report shows survival curve, run matrix, judge reasons, and patch ledger. | `src/faultline/ledger/report/render.py` | Polish report styling and include direct links to transcripts/dossiers. |
| Codex hardener | Builds failure dossiers, renders a hardening prompt, calls headless `codex exec`, and parses structured output. | `src/faultline/harden/` | Run a full live harden climb with Codex credits and capture before/after Resilience Score for the video. |
| Patch gatekeeper | Accepts patches only if happy paths still pass, anti-cheat passes, and score does not regress. Marker anti-cheat is deterministic; GPT-5.6 audit is opt-in. | `src/faultline/gate/`, `tests/test_anticheat.py` | Live-calibrate GPT audit prompts against real Codex patches. |
| CLI polish | `init`, `plan`, `break`, `harden`, `report`, and `gate` are implemented. | `src/faultline/cli.py`, `Makefile` | Add richer target autodetection to `init`. |
| Planner | Offline curated/random planners and GPT-5.6 planner path are implemented over a repo digest. | `src/faultline/plan/`, `tests/test_planner.py` | Run `faultline plan --mode gpt` live and capture the plan in the demo. |
| GitHub Action | Composite action installs Python/uv, runs Faultline, renders the report, and enforces `faultline gate`. | `action/action.yml` | Dogfood it in this repo's workflow. |
| Tests | Unit and offline end-to-end tests cover scheduler determinism, fault mutation, detectors, scorer, planner, anti-cheat, and gauntlet. | `tests/` | Add live integration tests behind env flags for GPT-5.6 judge, SDK agent, and Codex hardener. |
| Submission package | MIT license, blueprint, install commands, sample data, offline path, and submission state file are present. | `LICENSE`, `README.md`, `SUBMISSION_STATE.md`, `FAULTLINE_BLUEPRINT.md` | Record demo video, add `/feedback` Codex session ID, publish/share repository, and fill Devpost fields. |

## Deadline Plan

| Priority | Work item | Why it matters | Acceptance check |
| --- | --- | --- | --- |
| P0 | Run clean `uv sync`, `uv run pytest -q`, and `make demo` on a fresh checkout. | Judges need a no-surprises first run. | README commands work from scratch and generate `report.html`. |
| P0 | Run live `faultline harden` with the Codex CLI authenticated. | This is the core Build Week story: Codex fixes failures found by Faultline. | Video shows baseline RS, Codex patch attempt, accepted patch, and improved RS. |
| P0 | Verify GPT-5.6 judge mode and OpenAI Agents SDK target. | Confirms the live OpenAI path, not only the offline sandbox. | `judge.mode: llm` produces structured grades without breaking the report. |
| P0 | Dogfood `faultline init` on a fresh tiny repo. | Proves the project works beyond the bundled demo. | Generated config needs only entrypoint edits before `break`. |
| P0 | Dogfood the GitHub Action in this repository. | Turns Faultline into a visible CI gate, which strengthens the developer-tools category. | A workflow calls the action and fails when RS is below threshold. |
| P1 | Live-run GPT-5.6 planner-lite. | Shows GPT-5.6 doing strategic fault selection, not just rubric grading. | `faultline plan --mode gpt` emits `attack_plan.json` with ranked targets and reasons. |
| P1 | Live-run GPT-5.6 anti-cheat diff audit. | Prevents patches that only memorize the injected failure. | `FAULTLINE_ANTICHEAT=required` rejects overfit patches and explains why. |
| P1 | Polish report output. | The report is what judges will inspect after the video. | Report includes score, curve, matrix, transcripts, dossiers, and patch verdicts. |
| P1 | Add demo artifacts. | Reduces judging friction. | README links to sample report, sample transcript, and expected baseline score. |
| P2 | Expand from 13 faults to the full 22-fault taxonomy. | Increases product depth after the core story is locked. | Remaining faults include memory poison, permission drift, malformed tool envelopes, and multi-fault schedules. |
| P2 | Add MCP and LLM proxy injection. | Broadens framework coverage. | Faultline can perturb MCP tool responses and model responses, not only raw tool callables. |
| P2 | Add a second example agent. | Proves generality beyond support workflows. | Trip planner or research MCP example runs through the same gauntlet. |

## Architecture

```text
schemas/                  JSON contracts for all exchanged artifacts
src/faultline/
  intercept/              adapters and proxy hooks for fault injection
  faults/                 fault library and seeded scheduler
  plan/                   curated planner now; GPT-5.6 planner-lite next
  run/                    gauntlet runner, budgets, sandbox helpers
  judge/                  deterministic detectors and optional GPT-5.6 judge
  score/                  Resilience Score and survival curve
  harden/                 failure dossier and Codex hardening loop
  gate/                   golden traces, anti-cheat checks, monotone score gate
  ledger/                 SQLite run store and report renderer
examples/support_bot/     primary fragile demo agent and sample data
action/                   GitHub Action wrapper for `faultline gate`
tests/                    offline unit and end-to-end coverage
```

## Demo Script

1. Start with the support bot passing normal happy-path work.
2. Run `make demo` to show the agent failing under stale data, prompt injection,
   and flapping side effects.
3. Open `examples/support_bot/.faultline/report.html` and explain the
   Resilience Score, survival curve, and failure matrix.
4. Run `make demo-harden` with Codex authenticated.
5. Show the Codex-generated patch being accepted only after golden traces,
   anti-cheat checks, and monotone score improvement.
6. Re-open the report and compare baseline vs. hardened score.

Keep the final video under three minutes and explicitly say where Codex and
GPT-5.6 were used.

## Devpost Submission Checklist

| Requirement | Status | Notes |
| --- | --- | --- |
| Working project | In progress | Offline gauntlet works; live harden climb still needs final verification. |
| Category | Ready | Submit under Developer tools. |
| Project description | Drafted | Use the pitch and workflow sections above. |
| Demo video under 3 minutes | TODO | Show plan -> break -> report -> Codex harden -> improved report. |
| Public or shared repository | TODO | Public with MIT license, or private shared with required judging emails. |
| README setup instructions | Ready | Quickstart above covers offline and live paths. |
| Sample data | Ready | Support-bot SQLite backend is generated from repo-local fixtures. |
| Codex/GPT-5.6 usage explanation | In progress | README describes intended usage; final video should show the live loop. |
| `/feedback` Codex session ID | TODO | Add the session ID from the main build session to `SUBMISSION_STATE.md` and Devpost. |
| Plugin/developer tool install notes | Ready | GitHub Action usage is available in `action/action.yml`. |

## Current Scope Contract

The detailed product and build blueprint lives in
[`FAULTLINE_BLUEPRINT.md`](FAULTLINE_BLUEPRINT.md). Tier-0 scope is the offline
break/judge/score/report/gate loop plus the Codex hardener scaffold. The
remaining work above is ordered to maximize judging impact before the July 21,
2026 deadline.
