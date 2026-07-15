# Faultline Submission State

Last updated: 2026-07-14

## Provenance And Session

| Item | Value |
| --- | --- |
| Build Week category | Developer tools |
| Primary OpenAI usage | Codex hardener loop, GPT-5.6 judge, GPT-5.6 planner, GPT-5.6 anti-cheat audit |
| Codex `/feedback` session ID | `019f610b-2665-7f51-9f4a-c13a7e700e8e` |
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
| Plan → break wiring | Implemented. The attack plan now *aims* the faults (`build_schedule(attack=...)`) and the planner's hypothesis rides into the run record and the Codex dossier. Previously the plan was written but never read. |
| `faultline eval-plan` | Implemented. Planner-vs-random mini-eval, averaged over baseline seeds, ledger-free. Offline result on support-bot: random chaos scores the agent 77.2 (1.2/8 critical failures), the planner scores it 20.6 (6/8). |
| GitHub Action | Implemented. Installs Python/uv, runs gauntlet/report, enforces `faultline gate`. Dogfooded by `.github/workflows/faultline-gate.yml` as a smoke test (low threshold: the demo agent is fragile by design). |
| Fault library | Expanded from 5 to 13 faults across F1-F5 while preserving original demo faults. |
| Anti-cheat | Marker scan remains deterministic default; optional GPT-5.6 audit via `FAULTLINE_ANTICHEAT=gpt` or `required`. |
| Planner digest | Implemented. Summarizes files, functions, scenarios, and static risk hints. |
| Run isolation | Implemented. Default asyncio path remains; `isolation: subprocess` runs cases in killable child processes. |
| Report | Rewritten. KPI tiles, survival curve with gate line, fault-class heat map, grade distribution, per-run evidence (fault + transcript + end state), patch ledger incl. rejected patches. Dark-mode aware, self-contained, autoescaped. |
| Ledger integrity | Fixed: re-running an attempt used to append a duplicate set of runs (fresh uuid per run defeated `INSERT OR REPLACE`), which would have corrupted the survival curve during the harden loop. `clear_attempt` now makes an attempt a true re-run. |
| Windows support | Fixed: `break`/`report` crashed on stock Windows consoles (cp1252 could not encode the rich emoji / report ⚡). stdout and all file I/O are now explicitly UTF-8. |
| Tests | 45 tests, all offline, all green on merged local `main`. |

## Still Needs Live Verification

Everything below requires a credential or tool we have not run against. Nothing
in the README claims these have been executed.

| Item | Required credential/tool | Acceptance check |
| --- | --- | --- |
| `uv run pytest -q` and `make demo` exactly as README states | `uv` installed | 45 tests pass and the offline demo reproduces the planned `20.6/100` baseline on merged local `main`. |
| `faultline plan --mode gpt` | `OPENAI_API_KEY` | GPT-5.6 emits a schema-valid attack plan. |
| `judge.mode: llm` support-bot run | `OPENAI_API_KEY` | GPT-5.6 returns structured grades in the report. |
| `make demo-harden` | Authenticated Codex CLI | Codex invocation and structured output work; current generated patches do not yet improve the fresh `20.6` baseline, so no patch is accepted. |
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
| `/feedback` Codex session ID | `019f610b-2665-7f51-9f4a-c13a7e700e8e` |
| Code license | MIT license present. |
