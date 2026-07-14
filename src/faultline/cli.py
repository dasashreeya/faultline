"""Faultline CLI. The demo *is* the terminal."""

import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(no_args_is_help=True, help="Chaos engineering that fixes what it breaks.")
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
def init() -> None:
    """Detect the target framework and write faultline.yaml."""
    console.print("[yellow]TODO[/yellow] tier-0: see examples/support_bot/faultline.yaml for the shape")
    raise typer.Exit(1)


@app.command()
def plan() -> None:
    """Emit attack_plan.json (tier 0: curated file; add-back 3: GPT-5.6 planner-lite)."""
    console.print("[yellow]TODO[/yellow] add-back 3: planner-lite (tier 0 aims faults via scenarios.yaml)")
    raise typer.Exit(1)


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
    out.write_text(render_report(Ledger(cfg.state_dir / "ledger.sqlite3")))
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
