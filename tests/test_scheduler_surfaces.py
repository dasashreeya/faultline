"""The scheduler must route each fault to the right surface, deterministically,
without disturbing the byte-for-byte behaviour of tool-only scenarios."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from faultline.faults.scheduler import build_schedule, fault_surface, resolve_fault  # noqa: E402


def test_resolve_fault_spans_both_registries():
    assert resolve_fault("stale_data").fault_class == "F3"  # tool
    assert resolve_fault("llm_rate_limit").fault_class == "F1"  # llm
    assert resolve_fault("does_not_exist") is None


def test_fault_surface_classification():
    assert fault_surface("stale_data") == "tool"
    assert fault_surface("llm_empty_completion") == "llm"
    # context_truncation is F1 but a *tool*-output fault, not an LLM one
    assert fault_surface("context_truncation") == "tool"


def test_llm_scenario_produces_llm_surface_entry():
    scenario = {
        "id": "L1",
        "tools": ["chat"],
        "fault_pool": ["llm_empty_completion"],
        "fault_targets": ["chat"],
    }
    entry = build_schedule(scenario, seed=3)["entries"][0]
    assert entry["surface"] == "llm"
    assert entry["target"] == "llm"  # aimed at the model endpoint, not the tool
    assert entry["fault"] == "llm_empty_completion"


def test_tool_scenario_entry_is_unchanged():
    scenario = {
        "id": "F3-stale-01",
        "tools": ["lookup_orders", "refund_order"],
        "fault_pool": ["stale_data"],
        "fault_targets": ["lookup_orders"],
    }
    entry = build_schedule(scenario, seed=1)["entries"][0]
    assert entry["surface"] == "tool"
    assert entry["target"] == "lookup_orders"


def test_llm_scenario_is_deterministic():
    scenario = {
        "id": "L2",
        "tools": ["chat"],
        "fault_pool": ["llm_rate_limit", "llm_truncated_response", "llm_garbage_tokens"],
        "fault_targets": ["chat"],
    }
    assert build_schedule(scenario, seed=5) == build_schedule(scenario, seed=5)


def test_planned_llm_attack_aims_the_surface():
    scenario = {"id": "L3", "tools": ["chat"], "fault_pool": ["llm_empty_completion"], "fault_targets": ["chat"]}
    attack = {"fault": "llm_server_error", "target": "llm", "step_hint": 2}
    entry = build_schedule(scenario, seed=1, attack=attack)["entries"][0]
    assert entry["fault"] == "llm_server_error"
    assert entry["surface"] == "llm"
    assert entry["step"] == 2


def test_intensity_zero_skips_injection_but_preserves_potential_fault():
    scenario = {
        "id": "F3-intensity",
        "tools": ["lookup_orders"],
        "fault_pool": ["stale_data"],
        "fault_targets": ["lookup_orders"],
    }
    schedule = build_schedule(scenario, seed=3, intensity=0.0)

    assert schedule["entries"] == []
    assert schedule["potential_fault"] == "stale_data"


def test_full_intensity_matches_default_schedule():
    scenario = {
        "id": "F3-intensity",
        "tools": ["lookup_orders"],
        "fault_pool": ["stale_data"],
        "fault_targets": ["lookup_orders"],
    }

    assert build_schedule(scenario, seed=3) == build_schedule(scenario, seed=3, intensity=1.0)
