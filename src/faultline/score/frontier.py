"""Fault-intensity frontier experiments built on the normal gauntlet."""

from __future__ import annotations

from collections.abc import Iterable

from faultline.config import Config
from faultline.run.gauntlet import run_gauntlet


def validate_intensities(intensities: Iterable[float]) -> list[float]:
    values = [round(float(value), 4) for value in intensities]
    if not values:
        raise ValueError("at least one fault intensity is required")
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("fault intensity must be between 0 and 1")
    return values


async def run_frontier(
    cfg: Config,
    intensities: Iterable[float],
    *,
    attempt: int = 0,
    plan: dict | None = None,
) -> list[dict]:
    """Run clean-to-full chaos points without touching the hardening ledger."""

    points = []
    for intensity in validate_intensities(intensities):
        score, records = await run_gauntlet(
            cfg,
            attempt=attempt,
            plan=plan,
            persist=False,
            intensity=intensity,
        )
        points.append(
            {
                "intensity": intensity,
                "resilience_score": score,
                "critical_failures": sum(
                    record["judge"]["grade"] in ("D", "E") for record in records
                ),
                "faulted_runs": sum(
                    bool(record["fault_schedule"].get("entries")) for record in records
                ),
                "total_runs": len(records),
            }
        )
    return points
