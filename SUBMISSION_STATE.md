# Faultline Submission State

Last updated: 2026-07-14

## Provenance And Session

| Item | Value |
| --- | --- |
| Build Week category | Developer tools |
| Primary OpenAI usage | Codex hardener loop, GPT-5.6 judge, GPT-5.6 planner, GPT-5.6 anti-cheat audit |
| Codex `/feedback` session ID | TODO: paste the session ID from the Codex `/feedback` command before Devpost submission |
| Provenance stance | Repo hygiene is fine; do not misrepresent authorship or hide required Build Week provenance. |

## Saved Decisions

| Decision | Status |
| --- | --- |
| Do not commit vendor-specific assistant config folders, generated tool trailers, or unrelated assistant config files. | Active |
| Keep the Build Week story honest: Faultline uses Codex as the hardening engine and GPT-5.6 for live planning/judging/auditing paths. | Active |
| Delete unrelated Copilot instruction content from `.github/copilot-instructions.md`. | Done |
| Prefer offline deterministic defaults so judges can run the project without API keys. | Active |
| Make live GPT-5.6 features opt-in to avoid surprise API spend. | Active |

## Current Build State

| Area | State |
| --- | --- |
| `faultline init` | Implemented. Writes starter `faultline.yaml` and `scenarios.yaml`. |
| `faultline plan` | Implemented. Supports `curated`, `random`, and `gpt` modes; writes `.faultline/attack_plan.json`. |
| GitHub Action | Implemented. Installs Python/uv, runs gauntlet/report, enforces `faultline gate`. |
| Fault library | Expanded from 5 to 13 faults across F1-F5 while preserving original demo faults. |
| Anti-cheat | Marker scan remains deterministic default; optional GPT-5.6 audit via `FAULTLINE_ANTICHEAT=gpt` or `required`. |
| Planner digest | Implemented. Summarizes files, functions, scenarios, and static risk hints. |
| Run isolation | Implemented. Default asyncio path remains; `isolation: subprocess` runs cases in killable child processes. |
| Tests | Local source test suite passes with `PYTHONPATH=src`: 23 tests. |

## Still Needs Live Verification

| Item | Required credential/tool | Acceptance check |
| --- | --- | --- |
| `uv run pytest -q` and `make demo` exactly as README states | `uv` installed | Commands pass from fresh checkout. |
| `faultline plan --mode gpt` | `OPENAI_API_KEY` | GPT-5.6 emits a schema-valid attack plan. |
| `judge.mode: llm` support-bot run | `OPENAI_API_KEY` | GPT-5.6 returns structured grades in the report. |
| `make demo-harden` | Authenticated Codex CLI | Baseline RS improves and accepted patch is recorded. |
| `FAULTLINE_ANTICHEAT=required faultline harden` | `OPENAI_API_KEY` and Codex CLI | Gate rejects overfit patches and accepts general fixes. |

## Demo Commands

Offline path:

```bash
uv sync
uv run pytest -q
make demo
```

Planner paths:

```bash
uv run faultline plan --path examples/support_bot
uv run faultline plan --path examples/support_bot --mode random --seed 7
uv run faultline plan --path examples/support_bot --mode gpt
```

Live hardening path:

```bash
make demo-harden
```

## Devpost Checklist

| Requirement | State |
| --- | --- |
| Working project | Offline path implemented; live path needs credentialed verification. |
| README | Updated with status, roadmap, demo script, and checklist. |
| Repository URL | https://github.com/dasashreeya/faultline |
| Demo video | TODO. Show break -> plan/report -> Codex harden -> improved report. |
| `/feedback` Codex session ID | TODO. Paste above and into Devpost. |
| Code license | MIT license present. |
