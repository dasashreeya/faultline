"""Survival curve: RS per hardening attempt. The demo's money shot."""

from faultline.ledger.store import Ledger


def survival_curve(ledger: Ledger) -> list[dict]:
    return [{"attempt": a, "rs": rs} for a, rs in ledger.scores()]


def _spaced_indices(coords: list[tuple[float, float]], minimum_gap: float) -> set[int]:
    """Choose x-axis labels with enough room to remain legible."""

    if not coords:
        return set()
    selected = [0]
    for index in range(1, len(coords) - 1):
        if coords[index][0] - coords[selected[-1]][0] >= minimum_gap:
            selected.append(index)
    if len(coords) > 1:
        if coords[-1][0] - coords[selected[-1]][0] < minimum_gap and len(selected) > 1:
            selected[-1] = len(coords) - 1
        else:
            selected.append(len(coords) - 1)
    return set(selected)


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

    if len(points) == 1:
        # A lone baseline would sit on the y-axis with its label colliding with
        # the axis ticks. Centre it instead.
        coords = [(pad_l + plot_w / 2, y_of(points[0]["rs"]))]
    else:
        # Attempts are an ordered history, not a continuous numeric axis. Using
        # their raw IDs can create a huge visual gap when a later run uses an
        # intentionally distinct attempt number.
        coords = [
            (pad_l + index / (len(points) - 1) * plot_w, y_of(point["rs"]))
            for index, point in enumerate(points)
        ]

    if len(points) <= 8:
        value_indices = set(range(len(points)))
        tick_indices = value_indices
    else:
        value_indices = {
            0,
            len(points) - 1,
            len(points) // 2,
            min(range(len(points)), key=lambda index: points[index]["rs"]),
            max(range(len(points)), key=lambda index: points[index]["rs"]),
        }
        tick_indices = _spaced_indices(coords, minimum_gap=72)

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
        f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="5">'
        f'<title>Attempt {p["attempt"]}: resilience score {p["rs"]:g}</title></circle>'
        + (
            f'<text class="value" x="{x:.1f}" y="{max(y - 12, 15):.1f}" '
            f'text-anchor="middle">{p["rs"]:g}</text>'
            if index in value_indices
            else ""
        )
        + (
            f'<text class="tick" x="{x:.1f}" y="{height - pad_b + 18:.1f}" '
            f'text-anchor="middle">#{p["attempt"]}</text>'
            if index in tick_indices
            else ""
        )
        for index, ((x, y), p) in enumerate(zip(coords, points))
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
