"""Attack planner.

Tier 0: load a curated attack_plan.json (see schemas/attack_plan.schema.json).
ADD-BACK 3: one-shot GPT-5.6 planner-lite emitting the same schema.
"""

import json
from pathlib import Path


def load_plan(path: Path) -> dict:
    """Tier 0: the 'planner' is a hand-curated JSON file."""
    return json.loads(path.read_text())
