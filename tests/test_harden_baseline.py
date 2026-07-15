"""The hardener must compare patches with the source currently on disk."""

import asyncio
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


def test_run_codex_restores_windows_workspace_write_and_decodes_utf8(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        output = cmd[cmd.index("-o") + 1]
        with open(output, "w", encoding="utf-8") as handle:
            handle.write('{"summary": "ok"}')
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(codex_loop.sys, "platform", "win32")
    monkeypatch.setattr(codex_loop.subprocess, "run", fake_run)
    cfg = SimpleNamespace(root=tmp_path, state_dir=tmp_path)

    assert codex_loop.run_codex(cfg, {}) == {"summary": "ok"}
    assert 'windows.sandbox="elevated"' in captured["cmd"]
    assert captured["kwargs"]["encoding"] == "utf-8"
    assert captured["kwargs"]["errors"] == "replace"
