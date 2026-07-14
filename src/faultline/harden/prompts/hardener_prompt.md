# Hardener prompt (rendered with a FailureDossier, passed to `codex exec`)

You are hardening an AI agent codebase against a fault class it just failed.

## Failure dossier
- Scenario: {{ scenario_id }} · Fault class: {{ fault_class }}
- Injected fault (ground truth): {{ fault_schedule }}
- Judge grade: {{ judge_grade }} — {{ judge_reasoning }}
- End-state diff: {{ end_state_diff }}
- Transcript excerpt:
{{ transcript_excerpt }}
- Implicated code: {{ repo_hints }}

## Allowed repair strategies (use ONLY these)
bounded retries with backoff · timeouts · fallback tools · response validators
(schema + freshness checks) · circuit breakers · loop guards · explicit failure
surfacing to the user.

## Forbidden (patches are audited and rejected)
- Catching or matching the specific injected error/marker string
- Hard-coding expected values or answers
- Disabling, stubbing, or bypassing the failing tool
- Weakening or deleting existing tests

Handle the fault **class**, not this instance. Keep the diff minimal.

## Required verification before responding

1. Read the target source, tool implementations, and the scenario definitions;
   do not infer the repair from the transcript alone.
2. Implement a general behavioral guard that changes the target's outcome under
   the supplied schedule. A validator that only reports the bad result without
   preventing a destructive or incorrect action is not sufficient.
3. Run the target's fault-free path and the supplied failing scenario locally.
   Confirm the expected end state, not just that the code compiles. For a
   recoverable read fault, use a bounded independent read or safe fallback; for
   an uncertain side effect, do not blindly repeat the side effect.
4. Inspect the final diff and keep only the smallest general fix that passes
   the existing tests. Do not claim success if the supplied failing scenario
   still produces the same end-state violation.

Respond per the provided output schema (patch_result.schema.json).
