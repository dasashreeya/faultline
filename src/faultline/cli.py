"""Faultline CLI. The demo *is* the terminal."""

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, help="Chaos engineering that fixes what it breaks.")
console = Console()


@app.command()
def init() -> None:
    """Detect the target framework and write faultline.yaml."""
    console.print("[yellow]TODO[/yellow] tier-0: write faultline.yaml for the target repo")
    raise typer.Exit(1)


@app.command()
def plan(random: bool = typer.Option(False, "--random", help="Uniform sampling instead of a plan")) -> None:
    """Emit attack_plan.json (tier 0: curated file; add-back 3: GPT-5.6 planner-lite)."""
    console.print("[yellow]TODO[/yellow] tier-0: load curated attack plan")
    raise typer.Exit(1)


@app.command(name="break")
def break_(seeds: int = typer.Option(2, help="Seeds per scenario")) -> None:
    """Run the gauntlet: scenarios x seeds, grade every run, print the Resilience Score."""
    console.print("[yellow]TODO[/yellow] day 2: gauntlet → judge → score")
    raise typer.Exit(1)


@app.command()
def harden(max_attempts: int = typer.Option(3, help="Codex attempt budget")) -> None:
    """Codex loop: dossier → patch → gatekeeper → re-break, until gate clears or budget out."""
    console.print("[yellow]TODO[/yellow] day 3: the loop. The loop is the project.")
    raise typer.Exit(1)


@app.command()
def report() -> None:
    """Render the survival curve + fault matrix (tier 0: terminal/PNG; add-back 4: HTML)."""
    console.print("[yellow]TODO[/yellow] tier-0: survival curve")
    raise typer.Exit(1)


@app.command()
def gate(min_score: float = typer.Option(85.0, "--min-score")) -> None:
    """CI gate: exit non-zero if the latest Resilience Score is below --min-score."""
    console.print("[yellow]TODO[/yellow] add-back 6: read latest score from the ledger")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
