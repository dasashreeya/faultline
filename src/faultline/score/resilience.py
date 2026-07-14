"""Resilience Score: 100 · Σ_c w_c · mean_s( median_over_seeds(grade_weight) ).

Class weights are severity-informed (F3/F5 highest — semantic faults are the
production killers) and renormalized over the classes actually present.
"""

from collections import defaultdict
from statistics import median

from faultline.faults.library import TIER0_FAULTS

DEFAULT_CLASS_WEIGHTS = {"F1": 0.10, "F2": 0.20, "F3": 0.35, "F4": 0.05, "F5": 0.30}


def _run_fault_class(record: dict) -> str:
    fault_id = record["fault_schedule"]["entries"][0]["fault"]
    return TIER0_FAULTS[fault_id].fault_class


def resilience_score(records: list[dict], class_weights: dict | None = None) -> float:
    """`records` = all runs of one gauntlet attempt, judged."""
    weights = class_weights or DEFAULT_CLASS_WEIGHTS
    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_scenario[r["scenario_id"]].append(r)

    class_scores: dict[str, list[float]] = defaultdict(list)
    for runs in by_scenario.values():
        med = median(r["judge"]["weight"] for r in runs)  # over seeds
        class_scores[_run_fault_class(runs[0])].append(med)

    present = {c: weights[c] for c in class_scores}
    total_w = sum(present.values())
    return round(
        100 * sum(w * (sum(class_scores[c]) / len(class_scores[c])) for c, w in present.items()) / total_w,
        1,
    )
