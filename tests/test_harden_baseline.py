"""The hardener must compare patches with the source currently on disk."""

import asyncio
import json
from types import SimpleNamespace

from faultline.cli import _fresh_harden_baseline
from faultline.harden import codex_loop
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
            "task": "Refund the newest order.",
            "scenario_contract": '{"end_state": {"refunded_order": "ORD-1002"}}',
            "judge_grade": "D",
            "judge_reasoning": "wrong end state",
            "end_state_diff": "expected refund ORD-1002; actual ORD-1001",
            "failing_runs": [{"seed": 1, "grade": "D"}],
            "transcript_excerpt": "[]",
            "repo_hints": [],
        }
    )

    assert "changes the target's outcome" in prompt
    assert "expected end state" in prompt
    assert "supplied failing scenario" in prompt
    assert "Scenario contract and end-state oracle" in prompt
    assert "Failing seeds" in prompt


def test_codex_verification_cannot_overwrite_faultline_ledger(tmp_path, monkeypatch):
    state_dir = tmp_path / ".faultline"
    state_dir.mkdir()
    ledger_path = state_dir / "ledger.sqlite3"
    Ledger(ledger_path).add_score(0, 20.6)
    cfg = SimpleNamespace(root=tmp_path, state_dir=state_dir)

    def fake_codex(cmd, **kwargs):
        Ledger(ledger_path).add_score(0, 100.0)
        output = {
            "summary": "validate responses",
            "strategies": ["response_validator"],
            "files_changed": ["agent.py"],
            "rationale": "handles malformed responses generally",
            "risks": "fallback may surface an explicit failure",
        }
        output_path = cmd[cmd.index("-o") + 1]
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(output, handle)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(codex_loop.subprocess, "run", fake_codex)

    result = codex_loop.run_codex(cfg, {"scenario_id": "F3-stale-01"})

    assert result["summary"] == "validate responses"
    assert Ledger(ledger_path).scores() == [(0, 20.6)]
