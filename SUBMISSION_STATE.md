# Faultline Submission State

Last updated: 2026-07-15

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
| GitHub Action | Implemented. Installs Python/uv from the action checkout, runs gauntlet/report, and enforces `faultline gate` even when the consuming repo is not a Python project. |
| Fault library | Expanded from 5 to 13 faults across F1-F5 while preserving original demo faults. |
| Anti-cheat | Marker scan remains deterministic default; optional GPT-5.6 audit via `FAULTLINE_ANTICHEAT=gpt` or `required`. |
| Planner digest | Implemented. Summarizes files, functions, scenarios, and static risk hints. |
| Run isolation | Implemented. Default asyncio path remains; `isolation: subprocess` runs cases in killable child processes. |
| Report | Rewritten. KPI tiles, survival curve with gate line, fault-class heat map, grade distribution, per-run evidence (fault + transcript + end state), patch ledger incl. rejected patches. Dark-mode aware, self-contained, autoescaped. |
| Ledger integrity | Fixed: re-running an attempt used to append a duplicate set of runs (fresh uuid per run defeated `INSERT OR REPLACE`), which would have corrupted the survival curve during the harden loop. `clear_attempt` now makes an attempt a true re-run. |
| Windows support | Fixed: `break`/`report` crashed on stock Windows consoles (cp1252 could not encode the rich emoji / report ⚡). stdout and all file I/O are now explicitly UTF-8. |
| Tests | 57 tests, all offline, all green on the merged local `main` working tree. |

## Path B Verification (2026-07-15)

The repository-root `.env` was used without printing or committing its value.
All live modes remained explicit opt-ins.

| Item | Command/check | Observed result |
| --- | --- | --- |
| Offline suite | `uv run pytest -q` | 57 passed. |
| Offline demo | `faultline plan`, `break`, and `report` on `examples/support_bot` | Curated plan reproduced `20.6/100`; report rendered. GNU Make was unavailable on the Windows verification host, so the three commands behind `make demo` were run directly. |
| GPT planner | `uv run faultline plan --path examples/support_bot --mode gpt`, with only `.env` providing the key | GPT-5.6 emitted a strict structured five-attack plan. The first pre-fix call exposed unsupported `temperature`; the corrected call succeeded. |
| LLM judge | One-seed support-bot gauntlet with `cfg.judge_mode = "llm"`, followed by `render_report` | Score `37.1`; grades `D, A, B, D`; structured `llm:` reasoning was present in `report-live-judge.html`. Detector-certain grades remained authoritative. |
| Required anti-cheat audit | `scan_patch(..., mode="required")` against an overfit scenario-ID/fixed-answer diff and a general freshness validator | GPT rejected the overfit diff and returned no violations for the general validator. |
| Required audit without key | Disposable one-attempt `FAULTLINE_ANTICHEAT=required faultline harden` with `OPENAI_API_KEY` absent | Failed closed at the anti-cheat gate; the rejected attempt and reason were preserved in the ledger. |
| Required audit with key | Disposable one-attempt `FAULTLINE_ANTICHEAT=required faultline harden` with the key present | GPT audit completed; the patch then failed the monotonic gate because the score stayed `28.8 -> 28.8`. The rejection remained in the ledger. |
| Codex hardener | `make demo-harden` in a fresh detached checkout with authenticated Codex CLI | Clean ledger recorded `(0, 20.6), (1, 20.6), (2, 41.2), (3, 64.7), (4, 100.0)`; accepted Codex patches raised the score `20.6 → 41.2 → 64.7 → 100.0`. Generated target-agent commits remain outside the intentionally vulnerable baseline fixture. |
| Composite Action | Clean isolated consumer workspace: sync action project, `break`, `report`, `gate --min-score 20` | Passed at `28.8/100`; report existed. The action now runs from `${GITHUB_ACTION_PATH}/..`, fixing external-repo consumption. |
| Hosted workflow | `.github/workflows/faultline-gate.yml` | Existing GitHub-hosted run `29390728477` passed on 2026-07-15 at SHA `f793e1a`; the new external-consumer fix still requires push/PR before hosted verification. |

## Still Open

| Item | State |
| --- | --- |
| Hosted verification of the latest action changes | Requires pushing the merged commit and observing a fresh GitHub-hosted run. |
| P2 interception/second example | Intentionally not started. `TEAM_WORKPLAN.md` gates this on P0 acceptance; LLM/MCP proxy and trip-planner placeholders remain planned. |

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
| Working project | Offline path, P0 hardening, and Path B live integrations verified; hosted verification of the latest action changes remains. |
| README | Updated with status, roadmap, demo script, and checklist. |
| Repository URL | https://github.com/dasashreeya/faultline |
| Demo video | TODO. Show break -> plan/report -> Codex harden -> improved report. |
| `/feedback` Codex session ID | `019f610b-2665-7f51-9f4a-c13a7e700e8e` |
| Code license | MIT license present. |
