"""The public support-bot demo must start vulnerable, not pre-hardened."""

import asyncio
import shutil
from pathlib import Path

from faultline.config import load_config
from faultline.plan.planner import build_plan
from faultline.run.gauntlet import run_gauntlet


REPO = Path(__file__).resolve().parents[1]


def test_bundled_demo_uses_vulnerable_agent_and_fails_first(tmp_path):
    root = tmp_path / "support_bot"
    shutil.copytree(
        REPO / "examples" / "support_bot",
        root,
        ignore=shutil.ignore_patterns(".faultline", "__pycache__"),
    )

    cfg = load_config(root)
    plan = build_plan(cfg, mode="curated")
    score, records = asyncio.run(run_gauntlet(cfg, attempt=0, plan=plan))

    assert cfg.agent_entrypoint == "examples.support_bot.vulnerable_agent:run_task"
    assert score == 20.6
    assert all(record["judge"]["grade"] == "D" for record in records if record["scenario_id"] in {"F3-stale-01", "F5-inject-04"})
