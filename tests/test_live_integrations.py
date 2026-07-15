import asyncio
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from faultline.gate.anticheat import scan_patch
from faultline.judge.judge import _llm_grade, grade_run


REPO = Path(__file__).resolve().parents[1]


def test_cli_loads_repo_dotenv_without_overriding_existing_environment(
    tmp_path, monkeypatch
):
    from faultline.cli import _load

    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=from-dotenv\nFAULTLINE_TEST_SETTING=from-dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "from-environment")
    monkeypatch.delenv("FAULTLINE_TEST_SETTING", raising=False)
    monkeypatch.setattr("faultline.config.load_config", lambda root: root)

    assert _load(tmp_path) == tmp_path.resolve()
    assert os.environ["OPENAI_API_KEY"] == "from-environment"
    assert os.environ["FAULTLINE_TEST_SETTING"] == "from-dotenv"


def test_llm_judge_uses_structured_output_without_unsupported_temperature(monkeypatch):
    calls = []

    class FakeResponses:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text='{"grade":"B","reasoning":"failed loudly"}')

    monkeypatch.setattr(
        "openai.AsyncOpenAI", lambda: SimpleNamespace(responses=FakeResponses())
    )
    record = {
        "fault_schedule": {"entries": []},
        "detectors": {"crash": True, "end_state_ok": True},
        "end_state": {},
        "transcript": [],
    }

    grade, reasoning = asyncio.run(
        _llm_grade(record, {"task": "do the task"}, "gpt-5.6")
    )

    assert grade == "B"
    assert reasoning.startswith("llm:")
    assert "temperature" not in calls[0]
    assert calls[0]["text"]["format"]["strict"] is True


def test_llm_judge_cannot_override_detector_certain_crash(monkeypatch):
    async def conflicting_grade(*args, **kwargs):
        return "D", "llm: incorrectly called a loud crash silent"

    monkeypatch.setattr("faultline.judge.judge._llm_grade", conflicting_grade)
    record = {
        "detectors": {
            "loop": False,
            "budget_overrun": False,
            "crash": True,
            "end_state_ok": False,
        }
    }

    result = asyncio.run(grade_run(record, {"task": "do it"}, "llm", "gpt-5.6"))

    assert result["grade"] == "B"
    assert "detector override" in result["reasoning"]


def test_required_anticheat_fails_closed_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    violations = scan_patch("+if response_is_stale(value):\n+    raise ValueError", mode="required")
    assert len(violations) == 1
    assert violations[0].startswith("gpt anti-cheat audit unavailable:")


def test_gpt_anticheat_uses_supported_responses_parameters(monkeypatch):
    calls = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text='{"violations":[]}')

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("openai.OpenAI", lambda: SimpleNamespace(responses=FakeResponses()))

    assert scan_patch("+if response_is_stale(value):\n+    raise ValueError", mode="required") == []
    assert "temperature" not in calls[0]
    assert calls[0]["text"]["format"]["strict"] is True


def test_action_runs_the_installed_action_project():
    action = yaml.safe_load((REPO / "action" / "action.yml").read_text(encoding="utf-8"))
    commands = [step.get("run", "") for step in action["runs"]["steps"]]

    assert any('uv sync --project "${GITHUB_ACTION_PATH}/.."' in cmd for cmd in commands)
    faultline_commands = [cmd for cmd in commands if "faultline " in cmd]
    assert len(faultline_commands) == 3
    assert all('uv run --project "${GITHUB_ACTION_PATH}/.." faultline' in cmd for cmd in faultline_commands)
