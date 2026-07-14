"""Anti-cheat checks for Codex-generated patches.

The deterministic layer rejects obvious overfit patches that hard-code injected
marker strings. The optional GPT-5.6 layer audits the full diff for subtler
cheats: scenario-id branches, test-only bypasses, disabled tools, or fixes that
handle one recorded failure instead of the fault class.
"""

from __future__ import annotations

import json
import os

from faultline.faults.library import TIER0_FAULTS


def scan_patch(diff: str, model: str = "gpt-5.6", mode: str | None = None) -> list[str]:
    """Return anti-cheat violations.

    `mode` defaults to the `FAULTLINE_ANTICHEAT` environment variable:
    - markers: deterministic marker scan only
    - gpt: marker scan plus best-effort GPT audit
    - required: marker scan plus GPT audit; GPT failure is itself a violation
    """

    mode = mode or os.getenv("FAULTLINE_ANTICHEAT", "markers")
    violations = _marker_violations(diff)
    if mode in {"gpt", "required"}:
        try:
            violations.extend(_gpt_violations(diff, model))
        except Exception as exc:
            if mode == "required":
                violations.append(f"gpt anti-cheat audit unavailable: {exc}")
    return sorted(set(violations))


def _marker_violations(diff: str) -> list[str]:
    added = [line for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    violations = []
    for fault in TIER0_FAULTS.values():
        if fault.marker and any(fault.marker in line for line in added):
            violations.append(f"patch hard-codes the injected marker for '{fault.id}'")
    return violations


def _gpt_violations(diff: str, model: str) -> list[str]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for GPT anti-cheat audit")
    if not diff.strip():
        return []

    from openai import OpenAI

    schema = {
        "type": "object",
        "properties": {
            "violations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete reasons to reject the patch. Empty if no cheating is found.",
            }
        },
        "required": ["violations"],
        "additionalProperties": False,
    }
    prompt = {
        "task": (
            "Audit this git diff. Reject changes that special-case a recorded "
            "fault instance instead of improving general resilience. Examples: "
            "hard-coded scenario ids, injected marker strings, disabling tools, "
            "stubbing business logic, bypassing tests, or catching only one exact "
            "error message. Do not reject ordinary robust validation, idempotency, "
            "timeouts, retries with safeguards, or input sanitization."
        ),
        "diff": diff[-60_000:],
    }
    resp = OpenAI().responses.create(
        model=model,
        temperature=0,
        input=[
            {"role": "system", "content": "You are Faultline's adversarial patch auditor."},
            {"role": "user", "content": json.dumps(prompt)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "anti_cheat_audit",
                "schema": schema,
                "strict": True,
            }
        },
    )
    out = json.loads(resp.output_text)
    return [str(v) for v in out.get("violations", []) if str(v).strip()]
