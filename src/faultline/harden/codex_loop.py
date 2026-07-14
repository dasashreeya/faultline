"""The Hardener: codex exec loop. THE project.

    codex exec --sandbox workspace-write \
      --output-schema schemas/patch_result.schema.json \
      "$(rendered hardener_prompt + dossier)"

One branch + one conventional commit per attempt; budgeted (default 3 attempts).
SPIKE THIS ON DAY 1 (Person B) — it is the go/no-go gate for the whole plan.
"""

MAX_ATTEMPTS = 3
