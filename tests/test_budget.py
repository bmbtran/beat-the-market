from datetime import datetime, timezone

import pytest

from mf.config import BudgetCfg
from mf.core.budget import BudgetExceeded, BudgetGuard

CAPS = BudgetCfg(anthropic_total_usd=30.0, anthropic_backtest_usd=23.0, exa_monthly_usd=9.0,
                 per_run_default_usd=5.0)


class Clock:
    def __init__(self, dt):
        self.dt = dt

    def __call__(self):
        return self.dt


def spend(g, provider, usd, op="x"):
    r = g.charge(provider, usd, op)
    g.settle(r, actual_usd=usd, model=None, cache_key="k")


def test_raises_when_estimate_would_cross_backtest_cap(tmp_path):
    g = BudgetGuard(tmp_path / "l.jsonl", CAPS, run_id="bt1", max_usd=100)
    spend(g, "anthropic", 22.5)
    with pytest.raises(BudgetExceeded, match="backtest cap"):
        g.charge("anthropic", 0.6, "reason")
    g.charge("anthropic", 0.4, "reason")  # still fits


def test_total_cap_applies_to_live_runs(tmp_path):
    led = tmp_path / "l.jsonl"
    spend(BudgetGuard(led, CAPS, run_id="bt", max_usd=100), "anthropic", 22.0)
    live = BudgetGuard(led, CAPS, run_id="live-2026-10-06", max_usd=100)
    spend(live, "anthropic", 7.5)  # live is exempt from the 23 backtest cap
    with pytest.raises(BudgetExceeded, match="total cap"):
        live.charge("anthropic", 0.6, "reason")


def test_open_reservations_count(tmp_path):
    g = BudgetGuard(tmp_path / "l.jsonl", CAPS, run_id="r", max_usd=1.0)
    g.charge("anthropic", 0.6, "a")
    with pytest.raises(BudgetExceeded, match="per-run"):
        g.charge("anthropic", 0.5, "b")


def test_per_run_cap(tmp_path):
    g = BudgetGuard(tmp_path / "l.jsonl", CAPS, run_id="r", max_usd=0.05)
    spend(g, "exa", 0.04)
    with pytest.raises(BudgetExceeded, match="per-run"):
        g.charge("exa", 0.02, "search")


def test_exa_month_rollover(tmp_path):
    led = tmp_path / "l.jsonl"
    clock = Clock(datetime(2026, 10, 30, tzinfo=timezone.utc))
    g = BudgetGuard(led, CAPS, run_id="r", max_usd=100, now_fn=clock)
    spend(g, "exa", 8.9)
    with pytest.raises(BudgetExceeded, match="2026-10"):
        g.charge("exa", 0.2, "search")
    clock.dt = datetime(2026, 11, 1, tzinfo=timezone.utc)
    g.charge("exa", 0.2, "search")  # new calendar month -> allowed


def test_ledger_sums_and_persistence(tmp_path):
    led = tmp_path / "l.jsonl"
    g = BudgetGuard(led, CAPS, run_id="r1", max_usd=100)
    spend(g, "anthropic", 1.25, "reason")
    spend(g, "anthropic", 0.75, "helper")
    spend(g, "exa", 0.30, "search")
    g2 = BudgetGuard(led, CAPS, run_id="r2", max_usd=100)  # re-reads ledger from disk
    assert g2.spent("anthropic") == pytest.approx(2.0)
    assert g2.spent("exa") == pytest.approx(0.30)
    assert g2.spent(run_id="r1") == pytest.approx(2.30)
    assert g2.run_spent() == 0
    s = g2.summary()
    assert s["n_paid_calls"] == 3 and g2.caps_ok()


def test_release_frees_reservation(tmp_path):
    g = BudgetGuard(tmp_path / "l.jsonl", CAPS, run_id="r", max_usd=1.0)
    r = g.charge("exa", 0.9, "s")
    g.release(r)
    g.charge("exa", 0.9, "s")
