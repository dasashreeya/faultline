from pathlib import Path
from types import SimpleNamespace

from faultline.config import load_config
from faultline.plan.planner import _gpt_plan, _gpt_plan_schema, build_plan


REPO = Path(__file__).resolve().parents[1]


def test_curated_plan_ranks_support_bot_attacks():
    cfg = load_config(REPO / "examples" / "support_bot")
    plan = build_plan(cfg, mode="curated")
    assert plan["generated_by"] == "curated"
    assert plan["attacks"]
    first = plan["attacks"][0]
    assert set(first) == {"rank", "scenario_id", "fault", "target", "step_hint", "hypothesis"}
    assert first["rank"] == 1


def test_random_plan_is_seeded():
    cfg = load_config(REPO / "examples" / "support_bot")
    assert build_plan(cfg, mode="random", seed=7) == build_plan(cfg, mode="random", seed=7)


def test_gpt_plan_schema_requires_every_attack_property():
    schema = _gpt_plan_schema()
    attack = schema["properties"]["attacks"]["items"]

    assert set(attack["required"]) == set(attack["properties"])
    assert attack["additionalProperties"] is False


def test_gpt_plan_uses_supported_responses_parameters(monkeypatch):
    calls = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                output_text=(
                    '{"generated_by":"gpt","attacks":['
                    '{"rank":1,"scenario_id":"S1","fault":"stale_data",'
                    '"target":"lookup","step_hint":0,"hypothesis":"likely stale"}]}'
                )
            )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("openai.OpenAI", lambda: SimpleNamespace(responses=FakeResponses()))

    plan = _gpt_plan({"scenarios": [{"id": "S1", "tools": ["lookup"]}]}, "gpt-5.6")

    assert plan["generated_by"] == "gpt"
    assert "temperature" not in calls[0]
    assert calls[0]["text"]["format"]["strict"] is True
