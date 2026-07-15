"""`faultline report` → one static HTML file. No server, no chart lib, no CDN —
judges open it straight from disk. Every number in the demo video comes off
this page, so it has to explain itself without a narrator."""

import json

from jinja2 import Template

from faultline.faults.scheduler import resolve_fault
from faultline.judge.rubric import GRADE_WEIGHTS
from faultline.ledger.store import Ledger
from faultline.score.curves import curve_svg, survival_curve
from faultline.score.resilience import class_breakdown

GRADE_MEANING = {
    "A": "Graceful recovery — detected the fault, recovered, completed correctly",
    "B": "Loud failure — could not complete, said so clearly, nothing destructive",
    "C": "Degraded — completed with honestly flagged caveats",
    "D": "Silent wrong — confident, incorrect output. The worst outcome",
    "E": "Runaway — loop, budget explosion, or destructive side effect",
}

PAGE = Template(
    """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Faultline — Resilience Report</title>
<style>
 :root{
   --bg:#fff; --fg:#1a1a1a; --muted:#6b7280; --line:#e5e7eb; --panel:#f9fafb;
   --a:#1a7f37; --b:#9a6700; --c:#9a6700; --d:#cf222e; --e:#cf222e;
   --accent:#e4572e; --ok:#1a7f37; --no:#cf222e;
 }
 @media (prefers-color-scheme:dark){
   :root{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--line:#30363d;--panel:#161b22;
     --a:#3fb950;--b:#d29922;--c:#d29922;--d:#f85149;--e:#f85149;--ok:#3fb950;--no:#f85149;}
 }
 *{box-sizing:border-box}
 body{font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
   max-width:960px;margin:0 auto;padding:2rem 1rem 4rem;color:var(--fg);background:var(--bg)}
 h1{letter-spacing:-.02em;margin:0 0 .25rem;font-size:1.9rem}
 h2{letter-spacing:-.01em;margin:2.5rem 0 .75rem;font-size:1.2rem;
   padding-bottom:.4rem;border-bottom:1px solid var(--line)}
 .sub{color:var(--muted);margin:0 0 2rem}
 small{color:var(--muted);font-weight:400}
 code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9em;
   background:var(--panel);padding:.1em .35em;border-radius:4px}

 /* KPI tiles */
 .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.75rem;margin:1.5rem 0}
 .tile{border:1px solid var(--line);border-radius:10px;padding:.85rem 1rem;background:var(--panel)}
 .tile .k{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
 .tile .v{font-size:1.6rem;font-weight:650;letter-spacing:-.02em;margin-top:.15rem}
 .tile .v.pass{color:var(--ok)} .tile .v.fail{color:var(--no)}
 .up{color:var(--ok)} .down{color:var(--no)}

 /* chart */
 .curve{width:100%;height:auto;margin:.5rem 0}
 .curve .grid{stroke:var(--line);stroke-width:1}
 .curve .axis{stroke:var(--muted);stroke-width:1}
 .curve .line{fill:none;stroke:var(--accent);stroke-width:2.5;stroke-linejoin:round}
 .curve .area{fill:var(--accent);opacity:.10}
 .curve .dot{fill:var(--accent)}
 .curve .value{fill:var(--fg);font-size:12px;font-weight:600}
 .curve .tick,.curve .axis-label{fill:var(--muted);font-size:11px}
 .curve .gate{stroke:var(--ok);stroke-width:1.5;stroke-dasharray:5 4;opacity:.8}
 .curve .gate-label{fill:var(--ok);font-size:11px;font-weight:600}

 /* tables */
 .scroll{overflow-x:auto}
 table{border-collapse:collapse;width:100%;margin:.5rem 0}
 td,th{border:1px solid var(--line);padding:.45rem .6rem;text-align:left;font-size:13.5px;
   vertical-align:top}
 th{background:var(--panel);font-weight:600;white-space:nowrap}
 tbody tr:hover{background:var(--panel)}
 .A{color:var(--a);font-weight:700}.B{color:var(--b);font-weight:700}
 .C{color:var(--c);font-weight:700}.D{color:var(--d);font-weight:700}
 .E{color:var(--e);font-weight:800}
 .ok{color:var(--ok);font-weight:600}.no{color:var(--no);font-weight:600}
 .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}

 /* survival bar in the heat map */
 .bar{position:relative;background:var(--line);border-radius:3px;height:8px;min-width:70px}
 .bar>span{position:absolute;inset:0 auto 0 0;border-radius:3px;background:var(--accent)}
 .bar.good>span{background:var(--ok)}

 /* run detail */
 details{margin:0}
 details>summary{cursor:pointer;color:var(--muted);font-size:12.5px;list-style:none}
 details>summary::-webkit-details-marker{display:none}
 details>summary::before{content:"▸ ";}
 details[open]>summary::before{content:"▾ ";}
 pre{background:var(--panel);border:1px solid var(--line);border-radius:8px;
   padding:.7rem;overflow-x:auto;font-size:12px;line-height:1.45;margin:.5rem 0 0;
   max-height:340px}
 .empty{color:var(--muted);font-style:italic;padding:.5rem 0}
 .legend{display:grid;gap:.3rem;margin:.5rem 0;padding:0;list-style:none;font-size:13px}
 .legend b{display:inline-block;min-width:1.2em}
 footer{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);
   color:var(--muted);font-size:12.5px}
</style></head><body>

<h1>Faultline — Resilience Report</h1>
<p class="sub">Chaos engineering that fixes what it breaks. Deterministic gauntlet:
every run below is reproducible from its <code>(scenario, seed)</code>.</p>

<div class="tiles">
  <div class="tile"><div class="k">Latest score</div>
    <div class="v {{ 'pass' if passed else 'fail' }}">{{ latest_rs if latest_rs is not none else '—' }}</div></div>
  <div class="tile"><div class="k">Baseline</div>
    <div class="v">{{ baseline_rs if baseline_rs is not none else '—' }}</div></div>
  <div class="tile"><div class="k">Change</div>
    <div class="v {{ 'up' if delta > 0 else ('down' if delta < 0 else '') }}">
      {%- if delta > 0 %}+{% endif %}{{ delta if latest_rs is not none else '—' }}</div></div>
  <div class="tile"><div class="k">Gate</div><div class="v">{{ gate | int }}</div></div>
  <div class="tile"><div class="k">Verdict</div>
    <div class="v {{ 'pass' if passed else 'fail' }}">{{ 'PASS' if passed else 'FAIL' }}</div></div>
  <div class="tile"><div class="k">Runs graded</div><div class="v">{{ runs | length }}</div></div>
</div>

<h2>Survival curve <small>— Resilience Score per hardening attempt</small></h2>
{{ svg | safe }}

<h2>Fault-class heat map <small>— latest attempt, and what each class contributes</small></h2>
{% if breakdown %}
<div class="scroll"><table>
<thead><tr><th>Class</th><th>Fault surface</th><th class="num">Scenarios</th>
<th>Survival</th><th class="num">Survival %</th><th class="num">Weight</th>
<th class="num">Contributes</th></tr></thead>
<tbody>
{% for c in breakdown %}
<tr><td><code>{{ c.fault_class }}</code></td><td>{{ c.label }}</td>
<td class="num">{{ c.scenarios }}</td>
<td><div class="bar {{ 'good' if c.survival >= gate else '' }}"><span style="width:{{ c.survival }}%"></span></div></td>
<td class="num">{{ c.survival }}</td><td class="num">{{ '%.0f' | format(c.weight * 100) }}%</td>
<td class="num">{{ c.contribution }}</td></tr>
{% endfor %}
</tbody></table></div>
<p class="sub" style="margin:.5rem 0 0"><small>Contributions sum to the Resilience Score
({{ latest_rs }}). Weights are severity-informed: semantic faults (F3/F5) are the
production killers, so they dominate the score.</small></p>
{% else %}<p class="empty">No scored runs yet.</p>{% endif %}

<h2>Grade distribution <small>— the manner of failure, not just pass/fail</small></h2>
{% if grade_counts %}
<div class="scroll"><table>
<thead><tr><th>Grade</th><th>Meaning</th><th class="num">Weight</th><th class="num">Runs (latest)</th></tr></thead>
<tbody>
{% for g, meaning in grade_meaning.items() %}
<tr><td class="{{ g }}">{{ g }}</td><td>{{ meaning }}</td>
<td class="num">{{ '%.2f' | format(grade_weights[g]) }}</td>
<td class="num">{{ grade_counts.get(g, 0) }}</td></tr>
{% endfor %}
</tbody></table></div>
{% else %}<p class="empty">No graded runs yet.</p>{% endif %}

<h2>Runs <small>— expand any row for the injected fault, transcript, and end state</small></h2>
{% if runs %}
<div class="scroll"><table>
<thead><tr><th class="num">Attempt</th><th>Scenario</th><th class="num">Seed</th><th>Injected fault</th>
<th>Grade</th><th>Judge reasoning &amp; evidence</th></tr></thead>
<tbody>
{% for r in runs %}
<tr>
  <td class="num">{{ r.attempt }}</td>
  <td><code>{{ r.scenario_id }}</code></td>
  <td class="num">{{ r.seed }}</td>
  <td>{% if r.fault %}<code>{{ r.fault }}</code><br><small>{{ r.fault_class }} · {{ r.fault_desc }}</small>
      {% else %}<small>none (golden)</small>{% endif %}</td>
  <td class="{{ r.grade }}">{{ r.grade }}</td>
  <td>{{ r.reasoning }}
    {% if r.hypothesis %}<br><small><b>Planner predicted:</b> {{ r.hypothesis }}</small>{% endif %}
    <details><summary>evidence</summary><pre>{{ r.evidence }}</pre></details>
  </td>
</tr>
{% endfor %}
</tbody></table></div>
{% else %}<p class="empty">No runs recorded — run <code>faultline break</code>.</p>{% endif %}

<h2>Patch ledger <small>— discarded attempts included; honesty is a feature</small></h2>
{% if patches %}
<div class="scroll"><table>
<thead><tr><th class="num">Attempt</th><th>Scenario</th><th>Verdict</th><th>Why</th><th>Patch summary</th></tr></thead>
<tbody>
{% for p in patches %}
<tr><td class="num">{{ p.attempt }}</td><td><code>{{ p.scenario_id }}</code></td>
<td class="{{ 'ok' if p.accepted else 'no' }}">{{ 'ACCEPTED' if p.accepted else 'REJECTED' }}</td>
<td>{{ p.reason }}</td><td>{{ p.summary }}</td></tr>
{% endfor %}
</tbody></table></div>
<p class="sub" style="margin:.5rem 0 0"><small>Every patch must clear three gates:
golden-trace end-state equivalence (happy path preserved), an anti-cheat audit
(handled the fault <em>class</em>, not the injected instance), and a monotone score
check (a patch that lowers the score is reverted).</small></p>
{% else %}
<p class="empty">No hardening attempts yet — run <code>faultline harden</code>.</p>
{% endif %}

<h2>How to read this</h2>
<ul class="legend">
{% for g, meaning in grade_meaning.items() %}
<li><b class="{{ g }}">{{ g }}</b> {{ meaning }}</li>
{% endfor %}
</ul>

<footer>
Generated by Faultline. Faults are injected below the agent framework on the tool
surface; the judge grades each run with ground truth of the injected fault in hand.
Re-run <code>faultline break</code> with the same seeds to reproduce every row.
</footer>
</body></html>""",
    # Transcripts embed raw tool arguments and agent output — including the
    # adversarial instruction the F5 fault injects. Escaping is mandatory or a
    # tool result containing markup would corrupt (or inject into) the report.
    autoescape=True,
)


def _evidence(record: dict) -> str:
    """The provenance link: what was injected, what the agent did, where it landed."""
    return json.dumps(
        {
            "fault_schedule": record.get("fault_schedule"),
            "detectors": record.get("detectors"),
            "cost": record.get("cost"),
            "end_state": record.get("end_state"),
            "transcript": record.get("transcript"),
        },
        indent=2,
        default=str,
    )


def _run_rows(runs: list[dict]) -> list[dict]:
    rows = []
    for r in sorted(runs, key=lambda r: (r["attempt"], r["scenario_id"], r["seed"])):
        entries = r.get("fault_schedule", {}).get("entries") or []
        fault_id = entries[0]["fault"] if entries else None
        fault = resolve_fault(fault_id) if fault_id else None
        rows.append(
            {
                "attempt": r["attempt"],
                "scenario_id": r["scenario_id"],
                "seed": r["seed"],
                "fault": fault_id,
                "fault_class": fault.fault_class if fault else "",
                "fault_desc": fault.description if fault else "",
                "grade": r["judge"]["grade"],
                "reasoning": r["judge"]["reasoning"],
                "hypothesis": r.get("planner_hypothesis"),
                "evidence": _evidence(r),
            }
        )
    return rows


def render_report(ledger: Ledger, gate: float = 85.0) -> str:
    scores = ledger.scores()
    runs: list[dict] = []
    for attempt, _ in scores:
        runs.extend(ledger.runs_for_attempt(attempt))

    latest_runs = ledger.runs_for_attempt(scores[-1][0]) if scores else []
    latest_rs = scores[-1][1] if scores else None
    baseline_rs = scores[0][1] if scores else None
    delta = round(latest_rs - baseline_rs, 1) if scores else 0

    grade_counts: dict[str, int] = {}
    for r in latest_runs:
        g = r["judge"]["grade"]
        grade_counts[g] = grade_counts.get(g, 0) + 1

    return PAGE.render(
        svg=curve_svg(survival_curve(ledger), gate=gate),
        gate=gate,
        latest_rs=latest_rs,
        baseline_rs=baseline_rs,
        delta=delta,
        passed=latest_rs is not None and latest_rs >= gate,
        runs=_run_rows(runs),
        breakdown=class_breakdown(latest_runs) if latest_runs else [],
        grade_counts=grade_counts,
        grade_meaning=GRADE_MEANING,
        grade_weights=GRADE_WEIGHTS,
        patches=ledger.patches(),
    )
