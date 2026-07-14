"""Resilience Score: 100 * sum_c w_c * mean_s(median_over_seeds(grade_weight)).

Class weights default F3/F5-heavy; configurable in faultline.yaml.
Owner: Person B, Day 2.
"""

DEFAULT_CLASS_WEIGHTS = {"F1": 0.15, "F2": 0.20, "F3": 0.35, "F4": 0.0, "F5": 0.30}
