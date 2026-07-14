from faultline.judge.detectors import check_end_state, run_detectors

SCENARIO = {"max_steps": 4, "end_state": {"refunded_order": "ORD-1", "refund_count": 1}}


def _call(tool="t", h="x"):
    return {"type": "tool_call", "tool": tool, "args_hash": h}


def test_loop_detector_trips_on_three_identical_calls():
    det = run_detectors([_call(), _call(), _call()], {"refunds": []}, SCENARIO)
    assert det["loop"] and not det["budget_overrun"]


def test_budget_overrun():
    calls = [_call(h=str(i)) for i in range(5)]
    assert run_detectors(calls, {"refunds": []}, SCENARIO)["budget_overrun"]


def test_end_state_double_refund_caught():
    good = {"refunds": [{"order_id": "ORD-1", "amount": 1.0}]}
    double = {"refunds": [{"order_id": "ORD-1", "amount": 1.0}] * 2}
    assert check_end_state(SCENARIO["end_state"], good)
    assert not check_end_state(SCENARIO["end_state"], double)


def test_end_state_null_means_no_refunds():
    assert check_end_state({"refunded_order": None}, {"refunds": []})
    assert not check_end_state({"refunded_order": None}, {"refunds": [{"order_id": "X", "amount": 1}]})
