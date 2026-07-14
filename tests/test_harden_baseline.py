"""The hardener must compare patches with the source currently on disk."""

import asyncio

from faultline.cli import _fresh_harden_baseline
from faultline.harden.codex_loop import render_prompt
from faultline.ledger.store import Ledger


def test_harden_refreshes_a_stale_ledger_baseline(tmp_path, monkeypatch):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.add_score(0, 20.6)
    ledger.add_score(1, 43.5)

    calls = []

    async def fake_run_gauntlet(cfg, attempt):
        calls.append(attempt)
        return 20.6, []

    monkeypatch.setattr("faultline.cli.run_gauntlet_for_harden", fake_run_gauntlet)

    attempt, score = asyncio.run(_fresh_harden_baseline(object(), ledger))

    assert (attempt, score) == (2, 20.6)
    assert calls == [2]


def test_hardener_prompt_requires_behavioral_verification():
    prompt = render_prompt(
        {
            "scenario_id": "F3-stale-01",
            "fault_class": "F3",
            "fault_schedule": {},
            "judge_grade": "D",
            "judge_reasoning": "wrong end state",
            "end_state_diff": "expected refund ORD-1002; actual ORD-1001",
            "transcript_excerpt": "[]",
            "repo_hints": [],
        }
    )

    assert "changes the target's outcome" in prompt
    assert "expected end state" in prompt
    assert "supplied failing scenario" in prompt
