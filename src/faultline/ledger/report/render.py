"""`faultline report` → one static HTML file. No server, no chart lib —
judges open it from disk. Every number in the demo video comes off this page."""

from jinja2 import Template

from faultline.ledger.store import Ledger
from faultline.score.curves import curve_svg, survival_curve

PAGE = Template(
    """<!doctype html><html><head><meta charset="utf-8"><title>Faultline Report</title>
<style>
 body{font:15px/1.5 -apple-system,Segoe UI,sans-serif;max-width:880px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
 h1{letter-spacing:-.02em} table{border-collapse:collapse;width:100%;margin:1rem 0}
 td,th{border:1px solid #ddd;padding:.4rem .6rem;text-align:left;font-size:14px}
 th{background:#f6f6f6} .A{color:#1a7f37}.B{color:#9a6700}.C{color:#9a6700}.D{color:#cf222e}.E{color:#cf222e;font-weight:700}
 .ok{color:#1a7f37}.no{color:#cf222e}
</style></head><body>
<h1>⚡ Faultline — Resilience Report</h1>
<h2>Survival curve</h2>{{ svg }}
<h2>Runs</h2>
<table><tr><th>Attempt</th><th>Scenario</th><th>Seed</th><th>Fault</th><th>Grade</th><th>Judge</th></tr>
{% for r in runs %}<tr><td>{{ r.attempt }}</td><td>{{ r.scenario_id }}</td><td>{{ r.seed }}</td>
<td>{{ r.fault_schedule.entries[0].fault if r.fault_schedule.entries else '—' }}</td>
<td class="{{ r.judge.grade }}">{{ r.judge.grade }}</td><td>{{ r.judge.reasoning }}</td></tr>{% endfor %}
</table>
<h2>Patch ledger <small>(discarded attempts included — honesty is a feature)</small></h2>
<table><tr><th>Attempt</th><th>Scenario</th><th>Verdict</th><th>Reason</th><th>Patch</th></tr>
{% for p in patches %}<tr><td>{{ p.attempt }}</td><td>{{ p.scenario_id }}</td>
<td class="{{ 'ok' if p.accepted else 'no' }}">{{ 'accepted' if p.accepted else 'REJECTED' }}</td>
<td>{{ p.reason }}</td><td>{{ p.summary }}</td></tr>{% endfor %}
</table></body></html>"""
)


def render_report(ledger: Ledger) -> str:
    runs = []
    for attempt, _ in ledger.scores():
        runs.extend(ledger.runs_for_attempt(attempt))
    return PAGE.render(
        svg=curve_svg(survival_curve(ledger)),
        runs=sorted(runs, key=lambda r: (r["attempt"], r["scenario_id"], r["seed"])),
        patches=ledger.patches(),
    )
