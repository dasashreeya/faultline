"""The resilience frontier varies fault intensity without losing determinism."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from faultline.cli import app
from faultline.config import load_config
from faultline.plan.planner import build_plan
from faultline.score.frontier import run_frontier


REPO = Path(__file__).resolve().parents[1]
runner = CliRunner()


@pytest.fixture()
def cfg(tmp_path):
    root = tmp_path / "support_bot"
    shutil.copytree(
        REPO / "examples" / "support_bot",
        root,
        ignore=shutil.ignore_patterns(".faultline", "__pycache__"),
    )
    config = load_config(root)
    config.agent_entrypoint = "tests.vulnerable_support_agent:run_task"
    return config


def test_frontier_is_deterministic_and_reaches_both_endpoints(cfg):
    plan = build_plan(cfg, mode="curated")
    first = asyncio.run(run_frontier(cfg, [0.0, 1.0], plan=plan))
    second = asyncio.run(run_frontier(cfg, [0.0, 1.0], plan=plan))

    assert first == second
    assert [point["intensity"] for point in first] == [0.0, 1.0]
    assert first[0]["faulted_runs"] == 0
    assert first[0]["resilience_score"] == 100.0
    assert first[1]["faulted_runs"] == 8
    assert first[1]["resilience_score"] == 20.6


def test_frontier_rejects_invalid_intensity(cfg):
    with pytest.raises(ValueError, match="between 0 and 1"):
        asyncio.run(run_frontier(cfg, [-0.1]))


def test_frontier_cli_writes_json_without_loading_a_stale_plan(cfg):
    result = runner.invoke(
        app,
        [
            "frontier",
            "--path",
            str(cfg.root),
            "--no-plan",
            "--intensities",
            "0,1",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads((cfg.root / ".faultline" / "frontier.json").read_text())
    assert payload["plan"] is None
    assert payload["intensities"][0]["resilience_score"] == 100.0
    assert payload["intensities"][1]["resilience_score"] == 28.8
