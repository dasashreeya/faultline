# Faultline Team Workplan

This is the execution plan for the two-person team. It translates the target
architecture in [`../FAULTLINE_BLUEPRINT.md`](../FAULTLINE_BLUEPRINT.md) into
parallel work that can be developed separately and integrated deliberately.

The project has two different views:

```text
Runtime:     plan -> break -> judge -> score -> harden -> verify -> re-break
Development: P0 hardening loop || live integrations and breadth -> integration
```

The runtime is a pipeline. The engineering work is parallel. The shared JSON,
scenario, and configuration contracts are the boundary between the workstreams.

## Source Of Truth

Use these documents in this order:

1. `README.md` describes what a fresh user can run today.
2. `SUBMISSION_STATE.md` records what has actually been verified.
3. `FAULTLINE_BLUEPRINT.md` describes the full target architecture and stretch
   scope; it is not proof that every planned subsystem is implemented.
4. This file describes ownership, branch coordination, and integration.

Do not update documentation to claim a live path is complete until its
acceptance check has been run and recorded in `SUBMISSION_STATE.md`.

## Current Baseline

The default target is the deterministic scripted support bot:

```text
examples.support_bot.naive_agent:run_task
```

It is intentionally vulnerable. Faultline verifies behavior against the
support bot's SQLite backend and scenario end-state assertions, not against
the agent's final text alone.

Current verified facts:

- `uv run pytest -q`: 42 offline tests pass on `p0-hardener-convergence`.
- `make demo`: plan -> break -> report works without an API key.
- The clean support-bot baseline is `20.6/100` with the curated attack plan.
- Codex structured output and the gatekeeper can be exercised live.
- No live Codex patch has yet produced an accepted score increase; generated
  patches that leave the score unchanged are rejected.

The immediate P0 objective is therefore: produce and verify one general
Codex-generated repair that raises the score while preserving the happy path.

## Workstream A: P0 Hardening Loop

Owner: **you**

Goal: prove the product's central claim, namely that Faultline can turn a
failure dossier into a verified source-level improvement.

### Primary files

```text
src/faultline/harden/
src/faultline/gate/
src/faultline/cli.py          # harden command and attempt lifecycle
src/faultline/ledger/store.py # only when required by harden provenance
tests/test_harden_*.py
tests/test_gatekeeper.py
tests/test_schema_contracts.py
```

### Responsibilities

1. Make the dossier actionable for Codex: include the fault schedule, expected
   and actual end state, transcript evidence, planner hypothesis, and enough
   target context to choose a general repair.
2. Make Codex verify the supplied failing scenario before returning a patch.
3. Evaluate every patch in this order:

   ```text
   patch -> golden path -> deterministic anti-cheat -> re-break -> score gate
   ```

4. Reject both regressions and no-op patches.
5. Preserve rejected attempts in the ledger and report.
6. Ensure a stale ledger cannot be used as the current source baseline.
7. Add tests before changing hardener behavior.
8. Run the live hardening command in a clean target copy so ignored
   `.faultline/` state cannot hide a stale result.

### P0 acceptance tests

The work is complete only when all of these are true:

- a stale-data run initially refunds the wrong order;
- a Codex-generated general repair changes the post-fault end state;
- the fault-free golden scenarios still pass;
- the score is strictly higher than the fresh baseline;
- the accepted patch is committed by the gatekeeper;
- a rejected/no-op patch is reverted and remains visible in the ledger;
- the report shows the before/after survival curve;
- the exact command and resulting scores are recorded in
  `SUBMISSION_STATE.md`.

Do not use a manually authored support-bot fix as proof of the Codex loop. A
manual fix can be used as a fixture or test oracle, but the acceptance run must
exercise the real `codex exec` path.

## Workstream B: Live Integrations, CI, And Breadth

Owner: **teammate**

Goal: independently verify the live OpenAI paths and prepare the surrounding
architecture without changing the hardener's core contracts.

### Primary files

```text
src/faultline/plan/
src/faultline/judge/
src/faultline/intercept/
action/
examples/trip_planner/
examples/mcp_research/
tests/test_planner.py
tests/test_plan_steering.py
tests/test_*integration*.py
README.md
SUBMISSION_STATE.md
```

### Responsibilities

1. Verify `faultline plan --mode gpt` with `OPENAI_API_KEY` and record whether
   the returned attack plan passes its schema.
2. Verify `judge.mode: llm` and record whether structured grades appear in the
   report. Keep deterministic detectors as the source of truth for crashes,
   loops, budgets, and end-state correctness.
3. Verify `FAULTLINE_ANTICHEAT=required faultline harden` and record both a
   rejected overfit patch and the behavior when the audit credential is absent.
4. Verify the GitHub Action from a clean checkout. The action must install the
   project, run the gauntlet/report, and enforce `faultline gate`.
5. Keep live paths opt-in. Offline commands must not require an API key.
6. Implement only the next blueprint subsystem after P0 is accepted:
   first complete the LLM/MCP interception boundary or the second example
   agent, based on the agreed demo priority.
7. Add tests for every integration behavior before implementation changes.

### Explicit non-goals before P0

Do not spend the current cycle on:

- resilience frontier charts;
- public leaderboard or certification badge;
- multi-agent cascade faults;
- a third example agent;
- broad fault-library expansion;
- a full MCP server for Faultline itself.

Those are blueprint stretch goals. They do not prove the central harden-retest
claim.

## Shared Contracts

Both workstreams must preserve these interfaces unless the change is discussed
and both sides update their tests.

### Target configuration

`faultline.yaml` supplies importable entrypoints for the agent, tools, backend
reset, and backend snapshot. A target must remain runnable without Faultline
internals leaking into its business logic.

### Scenario contract

Each scenario defines:

```yaml
id:
task:
tools:
fault_pool:
fault_targets:
max_steps:
end_state:
```

`end_state` is the verification oracle. Do not replace it with text matching.

### Fault schedule contract

Schedules remain deterministic functions of `(seed, scenario)`. Planned attacks
may select the fault, target, or step, but they must not make a run depend on
wall-clock time or dictionary ordering.

### Run record contract

Every run must retain the scenario, seed, fault schedule, transcript, end
state, detector result, judge result, planner hypothesis, and cost metadata.

### Patch result contract

Codex output must remain strict structured JSON with:

```text
summary, strategies, files_changed, rationale, risks
```

The root schema and the packaged schema in
`src/faultline/harden/patch_result.schema.json` must stay identical.

## Branch And Handoff Rules

Start from the pushed P0 branch:

```bash
git fetch origin
git switch --track origin/p0-harden-loop
```

Then create separate branches:

```bash
# You
git switch -c p0-hardener-convergence

# Teammate
git switch -c teammate/live-integrations
```

Avoid editing the same files. In particular:

- you own `harden/`, `gate/`, and harden-specific tests;
- the teammate owns `plan/`, `judge/`, `intercept/`, `action/`, and live
  verification documentation;
- both people may add tests, but test files should be named by workstream;
- shared README/status edits should be coordinated, not overwritten.

Every handoff must include:

```text
Branch and commit:
Files changed:
Behavior changed:
Tests added:
Commands run:
Observed output:
Known limitations:
Documentation updated:
```

Do not hand off “implemented” without command output or a named blocker.

## Integration Sequence

Integration happens only after both workstreams have completed their current
acceptance checks.

1. Both branches fetch the latest `origin/main` and inspect conflicts.
2. The P0 owner opens the hardener branch for review first.
3. Create the integration branch from the reviewed P0 branch:

   ```bash
   git switch p0-harden-loop
   git switch -c integrate/p0-live-verification
   ```

4. Merge the teammate's live-integration branch into the integration branch.
5. Resolve conflicts by preserving frozen schemas and the offline default.
6. Run the complete verification matrix:

   ```bash
   uv run pytest -q
   make demo
   uv run faultline eval-plan --path examples/support_bot
   make demo-harden
   uv run faultline gate --path examples/support_bot --min-score 85
   ```

7. Run credentialed checks separately and record credential/tool availability
   without placing secrets in the repository.
8. Review the generated HTML report and patch ledger manually.
9. Update `README.md` only with behavior that is now reproducible.
10. Update `SUBMISSION_STATE.md` with exact commands, results, and remaining
    gaps.
11. Merge to `main` only after both people approve the integration branch.

If the live hardener still fails to raise the score, do not merge a claim that
the full closed loop is complete. Merge only the tested infrastructure fixes
and document the hardener convergence blocker.

## Documentation Rules

For every completed feature, update the smallest authoritative document:

- user command or setup change: `README.md`;
- verified versus unverified state: `SUBMISSION_STATE.md`;
- ownership, handoff, or integration procedure: this file;
- architecture or future scope: `FAULTLINE_BLUEPRINT.md` only when the target
  architecture itself changes.

Documentation must distinguish these labels:

```text
Implemented       code exists
Offline verified  tests/demo pass without external credentials
Live verified     credentialed path was actually exercised
Accepted          gatekeeper accepted a patch and score increased
Planned           blueprint target, not yet implemented
```

The README's offline quickstart must remain valid for a fresh checkout. Never
make an API key, Codex login, or ignored local state a requirement for the
offline path.

## Definition Of Done

### P0

The harden-retest loop produces an accepted score increase, preserves the
golden path, rejects overfit/no-op patches, and records the full evidence.

### P1

Live planner, judge, anti-cheat, and GitHub Action paths are verified and
documented without weakening offline reproducibility.

### P2

The LLM/MCP interception surfaces and additional example agents are implemented
only after P0 and P1 are stable.

### Stretch

Frontier charts, certification, public leaderboard, Faultline MCP, and
multi-agent faults come last.
