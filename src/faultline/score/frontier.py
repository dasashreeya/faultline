"""Fault-intensity frontier experiments built on the normal gauntlet."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from faultline.config import Config
from faultline.run.gauntlet import run_gauntlet


def load_frontier(path: Path) -> list[dict]:
    """Load a frontier artifact defensively for the static report."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    points = payload.get("intensities", []) if isinstance(payload, dict) else []
    return points if isinstance(points, list) else []


def frontier_svg(
    points: list[dict], gate: float | None = None, width: int = 720, height: int = 300
) -> str:
    """Render the intensity frontier as dependency-free inline SVG."""

    if not points:
        return '<p class="empty">No frontier data yet — run <code>faultline frontier</code>.</p>'

    pad_l, pad_r, pad_t, pad_b = 54, 24, 24, 48
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    def y_of(score: float) -> float:
        return pad_t + (1 - score / 100) * plot_h

    intensities = [float(point["intensity"]) for point in points]
    span = max(max(intensities) - min(intensities), 1.0)

    def x_of(intensity: float) -> float:
        return pad_l + (intensity - min(intensities)) / span * plot_w

    grid = "".join(
        f'<line class="grid" x1="{pad_l}" y1="{y_of(value):.1f}" '
        f'x2="{width - pad_r}" y2="{y_of(value):.1f}"/>'
        f'<text class="tick" x="{pad_l - 8}" y="{y_of(value) + 4:.1f}" text-anchor="end">{value}</text>'
        for value in (0, 25, 50, 75, 100)
    )
    coords = [
        (x_of(float(point["intensity"])), y_of(float(point["resilience_score"])))
        for point in points
    ]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area = (
        f"{pad_l},{pad_t + plot_h:.1f} {polyline} "
        f"{coords[-1][0]:.1f},{pad_t + plot_h:.1f}"
    )
    line = f'<polygon class="area" points="{area}"/><polyline class="line" points="{polyline}"/>'

    gate_line = ""
    if gate is not None:
        gy = y_of(gate)
        gate_line = (
            f'<line class="gate" x1="{pad_l}" y1="{gy:.1f}" x2="{width - pad_r}" y2="{gy:.1f}"/>'
            f'<text class="gate-label" x="{pad_l + 6}" y="{gy - 6:.1f}">gate {gate:g}</text>'
        )

    dots = "".join(
        f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="5">'
        f'<title>Intensity {point["intensity"]:.2f}: score {point["resilience_score"]:g}</title></circle>'
        f'<text class="value" x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle">'
        f'{point["resilience_score"]:g}</text>'
        f'<text class="tick" x="{x:.1f}" y="{height - pad_b + 18:.1f}" text-anchor="middle">'
        f'{point["intensity"]:.2f}</text>'
        for (x, y), point in zip(coords, points)
    )

    return (
        f'<svg class="frontier" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Resilience Score by fault intensity" xmlns="http://www.w3.org/2000/svg">'
        f"{grid}{gate_line}{line}{dots}"
        f'<line class="axis" x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height - pad_b}"/>'
        f'<line class="axis" x1="{pad_l}" y1="{height - pad_b}" x2="{width - pad_r}" y2="{height - pad_b}"/>'
        f'<text class="axis-label" x="{pad_l + plot_w / 2:.0f}" y="{height - 5}" text-anchor="middle">'
        "fault intensity (lambda)</text>"
        f'<text class="axis-label" transform="translate(14 {pad_t + plot_h / 2:.0f}) rotate(-90)" '
        'text-anchor="middle">Resilience Score</text>'
        "</svg>"
    )


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
