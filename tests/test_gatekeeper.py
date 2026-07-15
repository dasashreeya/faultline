import asyncio
import sys
from types import ModuleType
from types import SimpleNamespace

from faultline.gate import gatekeeper
from faultline.ledger.store import Ledger


def _cfg():
    return SimpleNamespace(root=".", judge_model="gpt-5.6")


def test_equal_score_is_rejected(monkeypatch):
    reverted = []
    commits = []

    async def happy_path_ok(_cfg):
        return True, "happy path preserved"

    async def run_gauntlet(_cfg, attempt):
        return 28.8, []

    monkeypatch.setattr(gatekeeper, "happy_path_ok", happy_path_ok)
    monkeypatch.setattr(gatekeeper, "scan_patch", lambda diff, model: [])
    monkeypatch.setattr(gatekeeper, "_git", lambda cfg, *args: "")
    monkeypatch.setattr(gatekeeper, "revert_worktree", lambda cfg: reverted.append(cfg))
    monkeypatch.setattr("faultline.run.gauntlet.run_gauntlet", run_gauntlet)
    monkeypatch.setattr(gatekeeper.subprocess, "run", lambda cmd, **kw: commits.append(cmd))

    accepted, reason, rs = asyncio.run(
        gatekeeper.evaluate_patch(_cfg(), ledger=None, attempt=1, prev_rs=28.8, summary="noop")
    )

    assert not accepted
    assert rs == 28.8
    assert reason == "improvement gate: score did not improve 28.8 \u2192 28.8"
    assert len(reverted) == 1
    assert commits == []


def test_improved_score_is_accepted_and_committed(monkeypatch):
    commits = []

    async def happy_path_ok(_cfg):
        return True, "happy path preserved"

    async def run_gauntlet(_cfg, attempt):
        return 43.5, []

    monkeypatch.setattr(gatekeeper, "happy_path_ok", happy_path_ok)
    monkeypatch.setattr(gatekeeper, "scan_patch", lambda diff, model: [])
    monkeypatch.setattr(gatekeeper, "_git", lambda cfg, *args: "")
    monkeypatch.setattr("faultline.run.gauntlet.run_gauntlet", run_gauntlet)
    monkeypatch.setattr(gatekeeper.subprocess, "run", lambda cmd, **kw: commits.append(cmd))

    accepted, reason, rs = asyncio.run(
        gatekeeper.evaluate_patch(_cfg(), ledger=None, attempt=1, prev_rs=28.8, summary="fix")
    )

    assert accepted
    assert rs == 43.5
    assert reason == "accepted: 28.8 \u2192 43.5"
    assert commits[0][:4] == ["git", "-C", ".", "add"]
    assert commits[1][:4] == ["git", "-C", ".", "commit"]


def test_target_modules_are_evicted_before_patch_evaluation(monkeypatch):
    cfg = SimpleNamespace(
        agent_entrypoint="examples.support_bot.naive_agent:run_task",
        tools_entrypoint="examples.support_bot.tools:build_tools",
        reset_entrypoint="examples.support_bot.tools:reset_backend",
        snapshot_entrypoint="examples.support_bot.tools:snapshot",
    )
    target_modules = (
        "examples.support_bot",
        "examples.support_bot.naive_agent",
        "examples.support_bot.tools",
        "examples.support_bot.backend",
    )
    for name in target_modules:
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    unrelated = ModuleType("examples.trip_planner.agent")
    monkeypatch.setitem(sys.modules, "examples.trip_planner.agent", unrelated)

    gatekeeper.refresh_target_imports(cfg)

    assert all(name not in sys.modules for name in target_modules)
    assert sys.modules["examples.trip_planner.agent"] is unrelated


def test_anticheat_scans_staged_and_unstaged_diff(monkeypatch):
    seen = []
    git_calls = []

    async def happy_path_ok(_cfg):
        return True, "happy path preserved"

    async def run_gauntlet(_cfg, attempt):
        return 43.5, []

    monkeypatch.setattr(gatekeeper, "happy_path_ok", happy_path_ok)
    monkeypatch.setattr(gatekeeper, "scan_patch", lambda diff, model: seen.append(diff) or [])
    monkeypatch.setattr(
        gatekeeper,
        "_git",
        lambda cfg, *args: git_calls.append(args) or "staged and unstaged patch",
    )
    monkeypatch.setattr("faultline.run.gauntlet.run_gauntlet", run_gauntlet)
    monkeypatch.setattr(gatekeeper.subprocess, "run", lambda cmd, **kw: SimpleNamespace(returncode=0))

    accepted, _, _ = asyncio.run(
        gatekeeper.evaluate_patch(_cfg(), ledger=None, attempt=1, prev_rs=28.8, summary="fix")
    )

    assert accepted
    assert git_calls == [("diff", "HEAD")]
    assert seen == ["staged and unstaged patch"]


def test_rejected_trial_score_is_removed_from_ledger(tmp_path, monkeypatch):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.add_score(0, 28.8)

    async def happy_path_ok(_cfg):
        return True, "happy path preserved"

    async def run_gauntlet(_cfg, attempt):
        ledger.add_score(attempt, 28.8)
        return 28.8, []

    monkeypatch.setattr(gatekeeper, "happy_path_ok", happy_path_ok)
    monkeypatch.setattr(gatekeeper, "scan_patch", lambda diff, model: [])
    monkeypatch.setattr(gatekeeper, "_git", lambda cfg, *args: "diff")
    monkeypatch.setattr(gatekeeper, "revert_worktree", lambda cfg: None)
    monkeypatch.setattr("faultline.run.gauntlet.run_gauntlet", run_gauntlet)

    accepted, _, _ = asyncio.run(
        gatekeeper.evaluate_patch(_cfg(), ledger=ledger, attempt=1, prev_rs=28.8, summary="noop")
    )

    assert not accepted
    assert ledger.scores() == [(0, 28.8)]


def test_commit_failure_rejects_patch_and_removes_trial_score(tmp_path, monkeypatch):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.add_score(0, 28.8)
    reverted = []

    async def happy_path_ok(_cfg):
        return True, "happy path preserved"

    async def run_gauntlet(_cfg, attempt):
        ledger.add_score(attempt, 43.5)
        return 43.5, []

    def fake_run(cmd, **kw):
        return SimpleNamespace(returncode=0 if cmd[3] == "add" else 1, stderr="commit failed")

    monkeypatch.setattr(gatekeeper, "happy_path_ok", happy_path_ok)
    monkeypatch.setattr(gatekeeper, "scan_patch", lambda diff, model: [])
    monkeypatch.setattr(gatekeeper, "_git", lambda cfg, *args: "diff")
    monkeypatch.setattr(gatekeeper, "revert_worktree", lambda cfg: reverted.append(True))
    monkeypatch.setattr("faultline.run.gauntlet.run_gauntlet", run_gauntlet)
    monkeypatch.setattr(gatekeeper.subprocess, "run", fake_run)

    accepted, reason, score = asyncio.run(
        gatekeeper.evaluate_patch(_cfg(), ledger=ledger, attempt=1, prev_rs=28.8, summary="fix")
    )

    assert not accepted
    assert score == 28.8
    assert reason == "commit gate: git commit failed"
    assert reverted == [True]
    assert ledger.scores() == [(0, 28.8)]


def test_discard_attempt_keeps_rejection_audit_record(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.add_score(0, 28.8)
    ledger.add_score(1, 28.8)
    ledger.add_patch(1, "F3-stale-01", False, "improvement gate rejected", "noop")

    ledger.discard_attempt(1)

    assert ledger.scores() == [(0, 28.8)]
    assert ledger.patches()[0]["accepted"] == 0
    assert ledger.patches()[0]["reason"] == "improvement gate rejected"
