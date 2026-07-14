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
Respond per the provided output schema (patch_result.schema.json).
