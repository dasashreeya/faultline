from faultline.faults.library import (
    EXFILTRATION_INSTRUCTION,
    INJECTED_INSTRUCTION,
    STALE_TIMESTAMP,
    TIER0_FAULTS,
    mutate_result,
)

ORDERS = {
    "orders": [
        {"order_id": "ORD-2", "updated_at": "2026-07-10T09:30:00Z"},
        {"order_id": "ORD-1", "updated_at": "2026-06-01T10:00:00Z"},
    ]
}


def test_stale_keeps_only_oldest_and_stamps_marker():
    out = mutate_result(TIER0_FAULTS["stale_data"], ORDERS)
    assert [o["order_id"] for o in out["orders"]] == ["ORD-1"]
    assert out["orders"][0]["updated_at"] == STALE_TIMESTAMP


def test_empty_result_is_well_formed():
    out = mutate_result(TIER0_FAULTS["empty_result"], ORDERS)
    assert out == {"orders": []}


def test_injection_embeds_instruction():
    out = mutate_result(TIER0_FAULTS["injected_instruction"], ORDERS)
    assert out["support_note"] == INJECTED_INSTRUCTION
    assert len(out["orders"]) == 2  # data otherwise intact


def test_schema_drift_renames_keys_recursively():
    out = mutate_result(TIER0_FAULTS["schema_drift"], ORDERS)
    assert "orderId" in out["orders"][0]
    assert "updatedAt" in out["orders"][0]


def test_null_fields_preserves_shape_but_drops_values():
    out = mutate_result(TIER0_FAULTS["null_fields"], {"order": {"status": "shipped", "amount": 42}})
    assert out == {"order": {"status": None, "amount": None}}


def test_exfiltration_instruction_uses_distinct_marker():
    out = mutate_result(TIER0_FAULTS["exfiltration_instruction"], ORDERS)
    assert out["debug_note"] == EXFILTRATION_INSTRUCTION
