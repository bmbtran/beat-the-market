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
    import json

    from mf.data.dataset import build

    card = build(refresh=refresh, log=lambda m: typer.echo(m))
    typer.echo("FILTER FUNNEL (main):")
    typer.echo(json.dumps(card["funnel_main"], indent=2))
    typer.echo("FILTER FUNNEL (canary):")
    typer.echo(json.dumps(card["funnel_canary"], indent=2))
    for k in ("all", "dev", "test", "canary"):
        typer.echo(f"{k}: {json.dumps(card[k])}")


@app.command()
def retrieve(
    split: str = typer.Option("dev", help="dev|test|canary|all"),
    limit: Optional[int] = typer.Option(None),
    dry_run: bool = typer.Option(False, "--dry-run"),
    allow_spend: bool = typer.Option(False, "--allow-spend"),
    max_usd: Optional[float] = typer.Option(None, "--max-usd"),
) -> None:
    """Query generation -> Exa -> leakage filters -> Haiku relevance/summary."""
    from mf.commands import retrieve as run

    raise typer.Exit(run(split, limit, dry_run, allow_spend, max_usd, log=lambda m: typer.echo(m)))


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
    from mf.commands import forecast_cmd

    raise typer.Exit(forecast_cmd(split, arms, limit, dry_run, allow_spend, max_usd, log=lambda m: typer.echo(m)))


@app.command()
def evaluate(out: str = typer.Option("reports/metrics.json")) -> None:
    """Compute all arms + metrics + cluster-bootstrap CIs (from committed run files; $0)."""
    from pathlib import Path

    from mf.config import settings
    from mf.eval.arms import evaluate as run_eval, write_metrics

    s = settings()
    res = run_eval(s)
    path = Path(out) if Path(out).is_absolute() else s.root / out
    write_metrics(res, path)
    a = res["arms"]
    typer.echo(f"wrote {out}: n_test_scored={res['n_test_scored']} events={res['n_events_scored']} "
               f"failed={res['failed_questions_by_arm']}")
    for arm in ("const_0.5", "base_rate", "market", "noret_ens", "halawi", "halawi_sup", "aia", "market_ens_aia"):
        ci = a[arm]["brier_ci"]
        typer.echo(f"  {arm:<16} Brier {a[arm]['brier']:.4f}  95% CI [{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]")
    for k, v in res["primary_comparisons"].items():
        typer.echo(f"  PRIMARY {k}: dBrier {v['delta']:+.4f} [{v['ci_low']:+.4f}, {v['ci_high']:+.4f}] "
                   f"P(d<0)={v['frac_draws_below_0']:.3f}")


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
    from mf.commands import live_cmd

    raise typer.Exit(live_cmd(n, dry_run, allow_spend, max_usd, log=lambda m: typer.echo(m)))


@app.command("score-live")
def score_live() -> None:
    """Score resolved live forecasts."""
    from mf.config import settings
    from mf.live.score import score_live as run

    s = settings()
    run(s.data_dir / "live" / "forecasts.jsonl", s.data_dir / "live" / "scores.jsonl", s,
        log=lambda m: typer.echo(m))


@app.command()
def budget() -> None:
    """Print spend by provider/op/month and remaining caps (exit 1 if any cap is exceeded)."""
    from mf.config import settings
    from mf.core.budget import BudgetGuard, dump_summary

    s = settings()
    g = BudgetGuard(s.state_dir / "ledger.jsonl", s.budget, run_id="budget-view")
    summ = g.summary()
    typer.echo(dump_summary(summ))
    typer.echo(f"Anthropic: ${summ['anthropic_total_usd']:.4f} of ${s.budget.anthropic_total_usd:.2f} total "
               f"(backtest ${summ['anthropic_backtest_usd']:.4f} of ${s.budget.anthropic_backtest_usd:.2f})")
    for m, v in summ["exa_by_month_usd"].items():
        typer.echo(f"Exa {m}: ${v:.4f} of ${s.budget.exa_monthly_usd:.2f}")
    ok = g.caps_ok()
    typer.echo("BUDGET OK: all caps respected" if ok else "BUDGET EXCEEDED")
    raise typer.Exit(0 if ok else 1)


@app.command()
def pilot(
    n: int = typer.Option(10),
    allow_spend: bool = typer.Option(False, "--allow-spend"),
    max_usd: Optional[float] = typer.Option(None, "--max-usd"),
) -> None:
    """Run the full pipeline on N dev questions and project total cost."""
    from mf.commands import pilot_cmd

    raise typer.Exit(pilot_cmd(n, allow_spend, max_usd, log=lambda m: typer.echo(m)))


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
    from mf.config import settings
    from mf.live.ledger import verify

    v = verify(settings().data_dir / "live" / "forecasts.jsonl")
    if v.ok:
        typer.echo(f"LEDGER OK n={v.n} head={v.head}")
    else:
        typer.echo(f"LEDGER BROKEN at record {v.bad_index}: {v.reason}")
    raise typer.Exit(0 if v.ok else 1)


@app.command()
def smoke(
    allow_spend: bool = typer.Option(False, "--allow-spend"),
    exa_type: Optional[str] = typer.Option(None, "--exa-type"),
) -> None:
    """Tiny paid smoke test of Haiku, Sonnet, Batch and Exa (~$0.07)."""
    from mf.smoke import run

    raise typer.Exit(run(allow_spend, exa_type, log=lambda m: typer.echo(m)))


@fixtures_app.command("record")
def fixtures_record() -> None:
    from mf.data.fixtures import record

    paths = record(log=lambda m: typer.echo(m))
    typer.echo(f"{len(paths)} fixtures recorded")


@batch_app.command("resume")
def batch_resume() -> None:
    from mf.llm.batch import resume_all
    from mf.runtime import make_ctx

    ctx = make_ctx(prefix="bt-batch-resume", allow_spend=True)
    done = resume_all(ctx.llm, ctx.s.state_dir, log=lambda m: typer.echo(m))
    typer.echo(f"resumed {len(done)} batch(es): {done}")


if __name__ == "__main__":
    app()
