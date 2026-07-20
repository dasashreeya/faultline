"""Resilience Score: 100 · Σ_c w_c · mean_s( median_over_seeds(grade_weight) ).

Class weights are severity-informed (F3/F5 highest — semantic faults are the
production killers) and renormalized over the classes actually present.
"""

from collections import defaultdict
from statistics import median

from faultline.faults.scheduler import resolve_fault

DEFAULT_CLASS_WEIGHTS = {"F1": 0.10, "F2": 0.20, "F3": 0.35, "F4": 0.05, "F5": 0.30}

CLASS_LABELS = {
    "F1": "LLM transport",
    "F2": "Tool transport",
    "F3": "Tool semantics",
    "F4": "Schema / contract",
    "F5": "Context / cognitive",
}


def _run_fault_class(record: dict) -> str:
    schedule = record["fault_schedule"]
    entries = schedule.get("entries", [])
    fault_id = entries[0]["fault"] if entries else schedule.get("potential_fault")
    fault = resolve_fault(fault_id)
    return fault.fault_class if fault else "F3"


def _class_scores(records: list[dict]) -> dict[str, list[float]]:
    """Per fault class, the median-over-seeds grade weight of each scenario."""
    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_scenario[r["scenario_id"]].append(r)

    class_scores: dict[str, list[float]] = defaultdict(list)
    for runs in by_scenario.values():
        med = median(r["judge"]["weight"] for r in runs)  # over seeds
        class_scores[_run_fault_class(runs[0])].append(med)
    return class_scores


def resilience_score(records: list[dict], class_weights: dict | None = None) -> float:
    """`records` = all runs of one gauntlet attempt, judged."""
    weights = class_weights or DEFAULT_CLASS_WEIGHTS
    class_scores = _class_scores(records)
    if not class_scores:
        return 0.0

    present = {c: weights[c] for c in class_scores}
    total_w = sum(present.values())
    return round(
        100 * sum(w * (sum(class_scores[c]) / len(class_scores[c])) for c, w in present.items()) / total_w,
        1,
    )


def class_breakdown(records: list[dict], class_weights: dict | None = None) -> list[dict]:
    """Per-fault-class survival, for the report's heat map.

    Shares `_class_scores` with `resilience_score`, so the breakdown can never
    disagree with the headline number it explains.
    """
    weights = class_weights or DEFAULT_CLASS_WEIGHTS
    class_scores = _class_scores(records)
    present = {c: weights[c] for c in class_scores}
    total_w = sum(present.values()) or 1.0

    rows = []
    for cls in sorted(class_scores):
        scores = class_scores[cls]
        survival = sum(scores) / len(scores)
        norm_w = present[cls] / total_w
        rows.append(
            {
                "fault_class": cls,
                "label": CLASS_LABELS.get(cls, cls),
                "scenarios": len(scores),
                "survival": round(100 * survival, 1),
                "weight": round(norm_w, 3),
                "contribution": round(100 * norm_w * survival, 1),
            }
        )
    return rows
