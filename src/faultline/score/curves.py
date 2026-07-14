"""Survival curve: RS per hardening attempt. The demo's money shot."""

from faultline.ledger.store import Ledger


def survival_curve(ledger: Ledger) -> list[dict]:
    return [{"attempt": a, "rs": rs} for a, rs in ledger.scores()]


def curve_svg(points: list[dict], width: int = 640, height: int = 240) -> str:
    """Inline-SVG survival curve — no chart lib, no deploy dependency for judges."""
    if not points:
        return "<svg/>"
    pad = 36
    xs = [p["attempt"] for p in points]
    span = max(max(xs) - min(xs), 1)
    coords = [
        (
            pad + (p["attempt"] - min(xs)) / span * (width - 2 * pad),
            height - pad - p["rs"] / 100 * (height - 2 * pad),
        )
        for p in points
    ]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#e4572e"/>'
        f'<text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" font-size="12">{p["rs"]}</text>'
        for (x, y), p in zip(coords, points)
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        f'<line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" stroke="#999"/>'
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height - pad}" stroke="#999"/>'
        f'<polyline points="{polyline}" fill="none" stroke="#e4572e" stroke-width="2.5"/>{dots}</svg>'
    )
