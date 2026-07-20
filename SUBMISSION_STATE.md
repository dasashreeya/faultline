# Faultline Submission State

Last updated: 2026-07-19

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
| Support-bot demo fixture | Intentionally vulnerable `examples/support_bot/vulnerable_agent.py` is the public offline target; `naive_agent.py` retains the accepted hardened reference. |
| GitHub Action | Implemented. Installs Python/uv from the action checkout, runs gauntlet/report, and enforces `faultline gate` even when the consuming repo is not a Python project. |
| Fault library | Expanded to 21 faults across F1-F5: 13 tool/MCP-surface faults plus 8 F1 LLM-transport faults. Original demo faults preserved. `faultline faults` lists them all. |
| LLM interception (Workstream B) | Implemented + live-verified. Pure F1 fault core (`intercept/faults_llm.py`) + OpenAI-compatible ASGI proxy (`intercept/llm_proxy.py`) forwards to the real endpoint and injects 500/429/context-overflow, empty/truncated/garbage completions, and mid-stream cutoff. Offline ASGI coverage is complete; a real OpenAI request through `faultline serve-proxy --fault llm_empty_completion` returned an injected empty completion. |
| MCP interception (Workstream B) | Implemented + offline-verified. JSON-RPC man-in-the-middle (`intercept/mcp_proxy.py`) corrupts `tools/call` results using the shared F2-F5 fault library (stale data, empty result, schema drift, injected instruction), and gets transport semantics right (short-circuit vs land-then-drop). Verified against an in-memory server. |
| Raw-MCP research example | Implemented + offline-verified. `examples/mcp_research` speaks MCP-shaped JSON-RPC through the interceptor to a stateful SQLite server; clean, `stale_data`, and `empty_result` behavior are pinned by tests and `make demo-mcp`. |
| LangGraph adapter + 2nd example (Workstream B) | Implemented + live-verified. `intercept/adapters/langgraph.py` reuses the shared injection core and converts wrapped tools to LangChain StructuredTools (signature preserved). `examples/trip_planner` is a booking domain (F2 flapping double-book, F4 schema drift) with a scripted offline agent and a live LangGraph agent; baseline RS `35.0/100`. The live GPT-5.6 Chat Completions path explicitly sets `reasoning_effort="none"` so tool calls are accepted. |
| End-state oracle | Generalized. Legacy `refunded_order`/`refund_count` keys unchanged; added a generic dotted-path form (`<collection>.count`, `<collection>.<field>`) so a second example asserts its own effects without the judge knowing the domain. |
| Anti-cheat | Marker scan remains deterministic default; optional GPT-5.6 audit via `FAULTLINE_ANTICHEAT=gpt` or `required`. |
| Planner digest | Implemented. Summarizes files, functions, scenarios, and static risk hints. |
| Run isolation | Implemented. Default asyncio path remains; `isolation: subprocess` runs cases in killable child processes. |
| Report | Rewritten. KPI tiles, survival curve with gate line, fault-class heat map, grade distribution, per-run evidence (fault + transcript + end state), patch ledger incl. rejected patches. Dark-mode aware, self-contained, autoescaped. |
| Ledger integrity | Fixed: re-running an attempt used to append a duplicate set of runs (fresh uuid per run defeated `INSERT OR REPLACE`), which would have corrupted the survival curve during the harden loop. `clear_attempt` now makes an attempt a true re-run. |
| Windows support | Fixed: `break`/`report` use UTF-8, and the Codex wrapper restores the elevated Windows workspace-write sandbox after `--ignore-user-config`. |
| Codex hardening loop | Live verified and accepted. Three gatekeeper commits raised the curated support-bot score `20.6 → 41.2 → 64.7 → 100.0`; a later no-op was rejected at `100.0 → 100.0`. |
| Resilience frontier backend | Implemented. `faultline frontier` runs deterministic clean-to-full fault probabilities without touching the hardening ledger, writes `.faultline/frontier.json`, and renders the frontier chart plus exact-value table in the static report. Demo narration remains tomorrow's user-facing handoff. |
| Tests | 129 tests, all offline, all green. |

## P0 Acceptance Verification (2026-07-15)

The run used authenticated Codex CLI `0.144.2` in a clean Git worktree at
baseline commit `1862aee`. `uv` was unavailable on the Windows host PATH, so
the equivalent venv entrypoint was invoked directly:

```powershell
.\.venv\Scripts\faultline.exe plan --path examples/support_bot
.\.venv\Scripts\faultline.exe harden --path examples/support_bot
.\.venv\Scripts\faultline.exe report --path examples/support_bot
.\.venv\Scripts\faultline.exe gate --path examples/support_bot --min-score 85
.\.venv\Scripts\python.exe -m pytest -q
```

| Acceptance item | Observed result |
| --- | --- |
| Fresh vulnerable baseline | `20.6/100`; both stale-data seeds refunded `ORD-1001` instead of expected `ORD-1002`. |
| General stale-read repair | Gatekeeper commit `88c874e`; score `20.6 → 41.2`. |
| Uncertain side-effect repair | Gatekeeper commit `a4a5ed7`; score `41.2 → 64.7`. |
| Untrusted tool-output repair | Gatekeeper commit `5effab2`; score `64.7 → 100.0`. |
| Golden path | Passed before every accepted commit; final `faultline gate --min-score 85` passed at `100.0`. |
| Rejected/no-op provenance | Real Codex attempt 4 rejected and reverted at `100.0 → 100.0`; retained in the patch ledger/report. |
| Survival curve/report | `20.6 → 41.2 → 64.7 → 100.0 → 100.0`; rendered to `examples/support_bot/.faultline/report.html`. |
| Offline regression suite | `129 passed` after adding deterministic frontier intensity, CLI, and static-report coverage. |

Two convergence defects were fixed during the run: Windows `--ignore-user-config`
had silently reduced Codex to a read-only sandbox, and the gate was reusing the
pre-patch Python module cache. Codex verification is also isolated from the
parent SQLite ledger so rejected attempts cannot overwrite baseline evidence.

## Path B Verification (2026-07-15)

The repository-root `.env` was used without printing or committing its value.
All live modes remained explicit opt-ins.

| Item | Command/check | Observed result |
| --- | --- | --- |
| Offline suite | `uv run pytest -q` | 51 passed at time of Path B; 110 passed after the Workstream B interception build (LLM proxy, MCP proxy, LangGraph adapter, trip-planner). |
| Offline demo | `make demo` on `examples/support_bot` | Curated plan reproduced `20.6/100`; report rendered from the public vulnerable fixture. |
| GPT planner | `uv run faultline plan --path examples/support_bot --mode gpt`, with only `.env` providing the key | GPT-5.6 emitted a strict structured five-attack plan. The first pre-fix call exposed unsupported `temperature`; the corrected call succeeded. |
| LLM judge | One-seed support-bot gauntlet with `cfg.judge_mode = "llm"`, followed by `render_report` | Score `37.1`; grades `D, A, B, D`; structured `llm:` reasoning was present in `report-live-judge.html`. Detector-certain grades remained authoritative. |
| Required anti-cheat audit | `scan_patch(..., mode="required")` against an overfit scenario-ID/fixed-answer diff and a general freshness validator | GPT rejected the overfit diff and returned no violations for the general validator. |
| Required audit without key | Disposable one-attempt `FAULTLINE_ANTICHEAT=required faultline harden` with `OPENAI_API_KEY` absent | Failed closed at the anti-cheat gate; the rejected attempt and reason were preserved in the ledger. |
| Required audit with key | Disposable one-attempt `FAULTLINE_ANTICHEAT=required faultline harden` with the key present | GPT audit completed; the patch then failed the monotonic gate because the score stayed `28.8 -> 28.8`. The rejection remained in the ledger. |
| Codex hardener | `make demo-harden` in a fresh detached checkout with authenticated Codex CLI | Clean ledger recorded `(0, 20.6), (1, 20.6), (2, 41.2), (3, 64.7), (4, 100.0)`; accepted Codex patches raised the score `20.6 → 41.2 → 64.7 → 100.0`. Generated target-agent commits remain outside the intentionally vulnerable baseline fixture. |
| Composite Action | Clean isolated consumer workspace: sync action project, `break`, `report`, `gate --min-score 20` | Passed at `28.8/100`; report existed. The action now runs from `${GITHUB_ACTION_PATH}/..`, fixing external-repo consumption. |
| Hosted workflow | `.github/workflows/faultline-gate.yml` | Manual dispatch runs `29447160856` (`main`, SHA `e087de1`) and `29451150274` (`integration-demo-live-verification`, SHA `d78498f`) passed on 2026-07-15. GitHub emitted only a Node.js 20 deprecation annotation from upstream setup actions. |
| Live LLM proxy smoke | `uv run --extra proxy faultline serve-proxy --fault llm_rate_limit` plus a real local HTTP request | Uvicorn served the proxy and returned the expected `429` response without contacting an upstream. |
| Live MCP stdio smoke | `serve_stdio` with a temporary child JSON-RPC server and a `stale_data` schedule | The newline-delimited proxy path changed a two-order response into the expected stale single-order response. |
| LangGraph local live smoke | `uv run --with langgraph --with langchain-openai` against a local OpenAI-compatible mock | `examples/trip_planner/agent.py` completed a real two-call LangGraph ReAct run through the adapter; no external API was contacted. |
| Real OpenAI LangGraph smoke | `uv run --with langgraph --with langchain-openai` with repository `.env` loaded | `examples/trip_planner/agent.py` completed against OpenAI and returned the cheapest flight (`FL-200`, `$310`) after the GPT-5.6 tool-calling compatibility fix. |
| Real OpenAI proxy smoke | `faultline serve-proxy --fault llm_empty_completion` plus LangChain `ChatOpenAI(base_url=...)` | OpenAI returned `200` upstream; Faultline injected the empty completion and the client received content length `0`. |

## Still Open

| Item | State |
| --- | --- |
| Third-party MCP endpoint | A real server remains pending because no server command or credentials are configured. The raw JSON-RPC example, in-memory proxy, and local MCP stdio subprocess paths are verified. |
| Submission presentation | Record and upload the Devpost demo video, then complete the external Devpost form. |

## Demo Commands

Offline path:

```bash
uv sync
uv run pytest -q
make demo
make demo-mcp
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
| Working project | Offline path, Path B live integrations, and accepted score-improving Codex hardening are verified. |
| README | Updated with status, roadmap, demo script, and checklist. |
| Repository URL | https://github.com/dasashreeya/faultline |
| Demo video | Tomorrow's handoff: show break -> plan/report -> Codex harden -> improved report, then use the frontier chart as the new breadth signal. |
| `/feedback` Codex session ID | `019f610b-2665-7f51-9f4a-c13a7e700e8e` |
| Code license | MIT license present. |
