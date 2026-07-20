"""Survival curve: RS per hardening attempt. The demo's money shot."""

from faultline.ledger.store import Ledger


def survival_curve(ledger: Ledger) -> list[dict]:
    return [{"attempt": a, "rs": rs} for a, rs in ledger.scores()]


def curve_svg(
    points: list[dict], gate: float | None = None, width: int = 720, height: int = 300
) -> str:
    """Inline-SVG survival curve — no chart lib, no deploy dependency for judges.

    Renders correctly for a single attempt too (a lone polyline point draws
    nothing, so the dot carries the baseline case).
    """
    if not points:
        return '<p class="empty">No scored attempts yet — run <code>faultline break</code>.</p>'

    pad_l, pad_r, pad_t, pad_b = 48, 24, 24, 40
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    def y_of(rs: float) -> float:
        return pad_t + (1 - rs / 100) * plot_h

    xs = [p["attempt"] for p in points]
    span = max(max(xs) - min(xs), 1)

    def x_of(attempt: int) -> float:
        return pad_l + (attempt - min(xs)) / span * plot_w

    if len(points) == 1:
        # A lone baseline would sit on the y-axis with its label colliding with
        # the axis ticks. Centre it instead.
        coords = [(pad_l + plot_w / 2, y_of(points[0]["rs"]))]
    else:
        coords = [(x_of(p["attempt"]), y_of(p["rs"])) for p in points]

    # horizontal gridlines every 25 RS
    grid = "".join(
        f'<line class="grid" x1="{pad_l}" y1="{y_of(v):.1f}" x2="{width - pad_r}" y2="{y_of(v):.1f}"/>'
        f'<text class="tick" x="{pad_l - 8}" y="{y_of(v) + 4:.1f}" text-anchor="end">{v}</text>'
        for v in (0, 25, 50, 75, 100)
    )

    gate_line = ""
    if gate is not None:
        gy = y_of(gate)
        # Anchored left: the right edge is where a passing curve ends up, and the
        # label would sit on top of the winning data point.
        gate_line = (
            f'<line class="gate" x1="{pad_l}" y1="{gy:.1f}" x2="{width - pad_r}" y2="{gy:.1f}"/>'
            f'<text class="gate-label" x="{pad_l + 6}" y="{gy - 6:.1f}" text-anchor="start">'
            f"gate {gate:g}</text>"
        )

    line = ""
    if len(coords) > 1:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        area = (
            f"{pad_l},{pad_t + plot_h:.1f} "
            + pts
            + f" {coords[-1][0]:.1f},{pad_t + plot_h:.1f}"
        )
        line = f'<polygon class="area" points="{area}"/><polyline class="line" points="{pts}"/>'

    dots = "".join(
        f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="5"/>'
        f'<text class="value" x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle">{p["rs"]:g}</text>'
        f'<text class="tick" x="{x:.1f}" y="{height - pad_b + 18:.1f}" text-anchor="middle">#{p["attempt"]}</text>'
        for (x, y), p in zip(coords, points)
    )

    return (
        f'<svg class="curve" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="Resilience Score per hardening attempt" xmlns="http://www.w3.org/2000/svg">'
        f"{grid}{gate_line}{line}{dots}"
        f'<line class="axis" x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height - pad_b}"/>'
        f'<line class="axis" x1="{pad_l}" y1="{height - pad_b}" x2="{width - pad_r}" y2="{height - pad_b}"/>'
        f'<text class="axis-label" x="{pad_l + plot_w / 2:.0f}" y="{height - 4}" text-anchor="middle">'
        f"hardening attempt</text>"
        f"</svg>"
    )
