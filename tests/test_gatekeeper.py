import asyncio
from types import SimpleNamespace

from faultline.gate import gatekeeper


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
