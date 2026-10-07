"""`mf` command-line interface. Each command is a thin wrapper; logic lives in submodules."""

from __future__ import annotations

from typing import Optional

import typer

app = typer.Typer(help="market-forecaster: leak-free LLM forecasting vs Kalshi/Polymarket", no_args_is_help=True)
fixtures_app = typer.Typer(help="Record small real API responses as test fixtures")
batch_app = typer.Typer(help="Message Batches helpers")
app.add_typer(fixtures_app, name="fixtures")
app.add_typer(batch_app, name="batch")


def _todo(name: str) -> None:
    typer.echo(f"`mf {name}` is not implemented yet", err=True)
    raise typer.Exit(2)


@app.command("build-dataset")
def build_dataset(refresh: bool = typer.Option(False, help="Ignore cached HTTP responses")) -> None:
    """Pull Kalshi + Polymarket candidates, filter, pick t0, price@t0, split, write questions.jsonl."""
    _todo("build-dataset")


@app.command()
def retrieve(
    split: str = typer.Option("dev", help="dev|test|canary|all"),
    limit: Optional[int] = typer.Option(None),
    dry_run: bool = typer.Option(False, "--dry-run"),
    allow_spend: bool = typer.Option(False, "--allow-spend"),
    max_usd: Optional[float] = typer.Option(None, "--max-usd"),
) -> None:
    """Query generation -> Exa -> leakage filters -> Haiku relevance/summary."""
    _todo("retrieve")


@app.command()
def forecast(
    split: str = typer.Option("dev"),
    arms: str = typer.Option("all"),
    limit: Optional[int] = typer.Option(None),
    dry_run: bool = typer.Option(False, "--dry-run"),
    allow_spend: bool = typer.Option(False, "--allow-spend"),
    max_usd: Optional[float] = typer.Option(None, "--max-usd"),
) -> None:
    """Reasoner samples (K prompt variants), aggregation, supervisor."""
    _todo("forecast")


@app.command()
def evaluate(out: str = typer.Option("reports/metrics.json")) -> None:
    """Compute all arms + metrics + cluster-bootstrap CIs."""
    _todo("evaluate")


@app.command()
def report() -> None:
    """Figures, reports/index.html, README/RESULTS metric blocks."""
    _todo("report")


@app.command()
def live(
    n: int = typer.Option(10),
    dry_run: bool = typer.Option(False, "--dry-run"),
    allow_spend: bool = typer.Option(False, "--allow-spend"),
    max_usd: Optional[float] = typer.Option(None, "--max-usd"),
) -> None:
    """Forecast open markets and append to the hash-chained live ledger."""
    _todo("live")


@app.command("score-live")
def score_live() -> None:
    """Score resolved live forecasts."""
    _todo("score-live")


@app.command()
def budget() -> None:
    """Print spend by provider/op/month and remaining caps."""
    _todo("budget")


@app.command()
def pilot(
    n: int = typer.Option(10),
    allow_spend: bool = typer.Option(False, "--allow-spend"),
    max_usd: Optional[float] = typer.Option(None, "--max-usd"),
) -> None:
    """Run the full pipeline on N dev questions and project total cost."""
    _todo("pilot")


@app.command("audit-leakage")
def audit_leakage(
    n: int = typer.Option(50),
    summarize: bool = typer.Option(False, "--summarize"),
) -> None:
    """Sample kept evidence for human leakage review, or summarize the filled CSV."""
    _todo("audit-leakage")


@app.command("verify-ledger")
def verify_ledger() -> None:
    """Verify the live forecast hash chain."""
    _todo("verify-ledger")


@app.command()
def smoke(
    allow_spend: bool = typer.Option(False, "--allow-spend"),
    exa_type: Optional[str] = typer.Option(None, "--exa-type"),
) -> None:
    """Tiny paid smoke test of Haiku, Sonnet, Batch and Exa (~$0.07)."""
    _todo("smoke")


@fixtures_app.command("record")
def fixtures_record() -> None:
    _todo("fixtures record")


@batch_app.command("resume")
def batch_resume() -> None:
    _todo("batch resume")


if __name__ == "__main__":
    app()
