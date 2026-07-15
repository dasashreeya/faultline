from pathlib import Path

from faultline.config import load_config
from faultline.plan.planner import _gpt_plan_schema, build_plan


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
