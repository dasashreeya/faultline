from faultline.score.resilience import resilience_score


def _rec(scenario, fault, weight, seed=1):
    return {
        "scenario_id": scenario,
        "seed": seed,
        "fault_schedule": {"entries": [{"fault": fault}]},
        "judge": {"weight": weight},
    }


def test_all_graceful_is_100():
    records = [_rec("s1", "stale_data", 1.0), _rec("s2", "tool_flapping", 1.0)]
    assert resilience_score(records) == 100.0


def test_median_over_seeds_and_class_weighting():
    records = [
        _rec("s1", "stale_data", 0.0, seed=1),
        _rec("s1", "stale_data", 0.0, seed=2),  # F3 median 0
        _rec("s2", "tool_flapping", 1.0, seed=1),
        _rec("s2", "tool_flapping", 1.0, seed=2),  # F2 median 1
    ]
    # weights renormalized over F2 (.20) and F3 (.35): RS = 100 * .20/.55
    assert resilience_score(records) == round(100 * 0.20 / 0.55, 1)
