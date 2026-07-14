"""Faultline CLI. The demo *is* the terminal."""

import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(no_args_is_help=True, help="Chaos engineering that fixes what it breaks.")

# Windows consoles default to a legacy codepage (cp1252) that cannot encode
# the emoji rich renders for :white_check_mark:/:skull: — reconfigure stdout
# to UTF-8 so `faultline break`/`harden` don't crash on a stock Windows shell.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

console = Console()

PathOpt = typer.Option(".", "--path", help="Directory containing faultline.yaml")


def _load(path: Path):
    from faultline.config import load_config

    root = path.resolve()
    # target agents are imported by module path relative to the repo, so make
    # the invocation cwd importable (e.g. `examples.support_bot.naive_agent`)
    sys.path.insert(0, str(Path.cwd().resolve()))
    return load_config(root)


def _grade_cell(grade: str) -> str:
    color = {"A": "green", "B": "yellow", "C": "yellow", "D": "red", "E": "bold red"}[grade]
    return f"[{color}]{grade}[/{color}]"


@app.command()
def init(
    path: Path = PathOpt,
    force: bool = typer.Option(False, "--force", help="Overwrite an existing faultline.yaml"),
) -> None:
    """Write a starter faultline.yaml and scenarios.yaml for a target repo."""
    root = path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    cfg_path = root / "faultline.yaml"
    scenarios_path = root / "scenarios.yaml"
    if cfg_path.exists() and not force:
        console.print(f"[green]found[/green] {cfg_path}")
        console.print("Use [bold]--force[/bold] to replace it.")
        return

    cfg_text = """# Faultline target config.
# Replace the entrypoints below with importable functions from your agent repo.
target:
  agent: your_package.agent:run_task
  tools: your_package.tools:build_tools
  reset: your_package.tools:reset_backend
  snapshot: your_package.tools:snapshot
  scenarios: scenarios.yaml
  model: gpt-5.6

judge:
  mode: detectors # use "llm" with OPENAI_API_KEY for GPT-5.6 grading
  model: gpt-5.6

seeds: [1, 3]
run_timeout_s: 30
isolation: asyncio # use "subprocess" to hard-kill stuck sync tools

gate:
  min_score: 85

harden:
  max_attempts: 3
"""
    scenarios_text = """# Replace this with the task/tool/end-state contract for your agent.
scenarios:
  - id: happy-path-hardening-01
    task: "Describe the task the agent must complete."
    tools: [lookup_records]
    fault_pool: [empty_result, stale_data, injected_instruction]
    fault_targets: [lookup_records]
    max_steps: 6
    end_state: {}
"""
    cfg_path.write_text(cfg_text, encoding="utf-8")
    if not scenarios_path.exists() or force:
        scenarios_path.write_text(scenarios_text, encoding="utf-8")
    console.print(f"[green]wrote[/green] {cfg_path}")
    console.print(f"[green]wrote[/green] {scenarios_path}")
    console.print("Edit the entrypoints, then run [bold]faultline plan[/bold] and [bold]faultline break[/bold].")


@app.command()
def plan(
    path: Path = PathOpt,
    mode: str = typer.Option("curated", "--mode", help="Planner mode: curated, random, or gpt"),
    seed: int = typer.Option(0, "--seed", help="Seed for --mode random"),
) -> None:
    """Emit a ranked attack_plan.json for the target repo."""
    from faultline.plan.planner import build_plan, save_plan

    cfg = _load(path)
    try:
        attack_plan = build_plan(cfg, mode=mode, seed=seed)
    except Exception as exc:
        console.print(f"[red]planner failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    out = cfg.state_dir / "attack_plan.json"
    save_plan(attack_plan, out)
    table = Table(title=f"Faultline attack plan ({attack_plan['generated_by']})")
    for col in ("rank", "scenario", "fault", "target", "why"):
        table.add_column(col)
    for attack in attack_plan["attacks"][:12]:
        table.add_row(
            str(attack["rank"]),
            attack["scenario_id"],
            attack["fault"],
            attack["target"],
            attack["hypothesis"],
        )
    console.print(table)
    console.print(f"attack plan -> [bold]{out}[/bold]")


@app.command(name="break")
def break_(path: Path = PathOpt, attempt: int = typer.Option(0, help="Hardening attempt index")) -> None:
    """Run the gauntlet: scenarios × seeds, grade every run, print the Resilience Score."""
    from faultline.run.gauntlet import run_gauntlet

    cfg = _load(path)
    table = Table(title=f"Faultline gauntlet — attempt {attempt}")
    for col in ("scenario", "seed", "fault", "grade", "judge"):
        table.add_column(col)

    def on_run(rec: dict) -> None:
        entries = rec["fault_schedule"]["entries"]
        table.add_row(
            rec["scenario_id"],
            str(rec["seed"]),
            entries[0]["fault"] if entries else "—",
            _grade_cell(rec["judge"]["grade"]),
            rec["judge"]["reasoning"],
        )

    rs, _ = asyncio.run(run_gauntlet(cfg, attempt, on_run=on_run))
    console.print(table)
    mark = ":white_check_mark:" if rs >= cfg.gate_min_score else ":skull:"
    console.print(f"\n[bold]Resilience Score: {rs}/100[/bold] {mark}")


@app.command()
def harden(path: Path = PathOpt) -> None:
    """Codex loop: dossier → patch → gatekeeper → re-break, until gate clears or budget out."""
    from faultline.config import load_scenarios
    from faultline.gate.gatekeeper import evaluate_patch
    from faultline.harden.codex_loop import run_codex
    from faultline.harden.dossier import build_dossiers
    from faultline.ledger.store import Ledger
    from faultline.run.gauntlet import run_gauntlet

    cfg = _load(path)
    ledger = Ledger(cfg.state_dir / "ledger.sqlite3")
    scenarios = load_scenarios(cfg.scenarios_path)
    repo_hints = [cfg.agent_entrypoint, cfg.tools_entrypoint]

    scores = ledger.scores()
    if not scores:
        console.print("No baseline — running [bold]faultline break[/bold] first (attempt 0)")
        rs, _ = asyncio.run(run_gauntlet(cfg, 0))
        scores = [(0, rs)]
    attempt, rs = scores[-1]
    console.print(f"Baseline RS: [bold]{rs}[/bold] · gate: {cfg.gate_min_score}")

    for attempt in range(attempt + 1, attempt + 1 + cfg.max_attempts):
        if rs >= cfg.gate_min_score:
            break
        dossiers = build_dossiers(ledger.runs_for_attempt(attempt - 1), scenarios, repo_hints)
        if not dossiers:
            break
        dossier = dossiers[0]
        console.print(f"\n[bold]attempt {attempt}[/bold] → codex exec on {dossier['scenario_id']} "
                      f"(grade {dossier['judge_grade']})")
        patch = run_codex(cfg, dossier)
        if patch is None:
            console.print("[red]codex produced no parseable patch; see .faultline/codex_last_error.log[/red]")
            ledger.add_patch(attempt, dossier["scenario_id"], False, "codex exec failed", "")
            continue
        accepted, reason, rs = asyncio.run(
            evaluate_patch(cfg, ledger, attempt, rs, f"{patch['summary']} [scenario {dossier['scenario_id']}]")
        )
        ledger.add_patch(attempt, dossier["scenario_id"], accepted, reason, patch["summary"])
        style = "green" if accepted else "red"
        console.print(f"[{style}]{reason}[/{style}]")

    curve = " → ".join(str(s[1]) for s in ledger.scores())
    mark = ":white_check_mark:" if rs >= cfg.gate_min_score else ":warning: budget exhausted"
    console.print(f"\n[bold]Survival curve: {curve}[/bold] {mark}")


@app.command()
def report(path: Path = PathOpt) -> None:
    """Render the static HTML report (survival curve, run grades, patch ledger)."""
    from faultline.ledger.report.render import render_report
    from faultline.ledger.store import Ledger

    cfg = _load(path)
    out = cfg.state_dir / "report.html"
    out.write_text(render_report(Ledger(cfg.state_dir / "ledger.sqlite3")), encoding="utf-8")
    console.print(f"report → [bold]{out}[/bold]")


@app.command()
def gate(path: Path = PathOpt, min_score: float = typer.Option(None, "--min-score")) -> None:
    """CI gate: exit non-zero if the latest Resilience Score is below the gate."""
    from faultline.ledger.store import Ledger

    cfg = _load(path)
    threshold = min_score if min_score is not None else cfg.gate_min_score
    scores = Ledger(cfg.state_dir / "ledger.sqlite3").scores()
    if not scores:
        console.print("[red]no scores in ledger — run `faultline break` first[/red]")
        raise typer.Exit(2)
    rs = scores[-1][1]
    if rs < threshold:
        console.print(f"[red]RS {rs} < {threshold} — gate failed[/red]")
        raise typer.Exit(1)
    console.print(f"[green]RS {rs} ≥ {threshold} — gate passed[/green]")


if __name__ == "__main__":
    app()
