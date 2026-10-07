"""BudgetGuard + append-only spend ledger (PLAN.md §10).

`charge()` is called BEFORE every paid call (only on a cache miss). It sums actual spend in
state/ledger.jsonl + open reservations + the new estimate, and raises BudgetExceeded if any cap
would be crossed:
  * Anthropic total cap (all runs)                       -> budget.anthropic_total_usd
  * Anthropic backtest cap (runs not prefixed "live")    -> budget.anthropic_backtest_usd
  * Exa calendar-month cap (UTC month of the call)       -> budget.exa_monthly_usd
  * Per-run cap (--max-usd, all providers)               -> max_usd
After the call, `settle()` replaces the reservation with the actual cost and appends a LedgerEntry.
"""

from __future__ import annotations

import itertools
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from mf.core import timeutil
from mf.schemas import LedgerEntry

EPS = 1e-9


class BudgetExceeded(Exception):
    pass


@dataclass
class Reservation:
    rid: int
    provider: str
    op: str
    est_usd: float
    month: str


def is_live_run(run_id: str) -> bool:
    return run_id.startswith("live")


def read_ledger(path: str | Path) -> list[LedgerEntry]:
    path = Path(path)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(LedgerEntry.model_validate_json(line))
    return out


class BudgetGuard:
    def __init__(self, ledger_path: str | Path, caps, run_id: str, max_usd: float | None = None,
                 now_fn: Callable = timeutil.now, pending_fn: Callable[[], float] | None = None,
                 run_pending_fn: Callable[[], float] | None = None):
        """caps: a BudgetCfg (anthropic_total_usd, anthropic_backtest_usd, exa_monthly_usd, ...)."""
        self.ledger_path = Path(ledger_path)
        self.caps = caps
        self.run_id = run_id
        self.max_usd = caps.per_run_default_usd if max_usd is None else max_usd
        self.now_fn = now_fn
        # $ of submitted-but-uncollected batches (durable reservations kept in state/batches/)
        self.pending_fn = pending_fn or (lambda: 0.0)
        # pending batches submitted by THIS run only (per-run cap must not count other runs' batches)
        self.run_pending_fn = run_pending_fn or (lambda: 0.0)
        self._open: dict[int, Reservation] = {}
        self._ids = itertools.count(1)
        self.entries = read_ledger(self.ledger_path)

    # ---- sums --------------------------------------------------------------------------------
    def spent(self, provider: str | None = None, month: str | None = None, run_id: str | None = None,
              backtest_only: bool = False) -> float:
        total = 0.0
        for e in self.entries:
            if provider and e.provider != provider:
                continue
            if month and timeutil.month_key(e.ts) != month:
                continue
            if run_id and e.run_id != run_id:
                continue
            if backtest_only and is_live_run(e.run_id):
                continue
            total += e.actual_usd
        return total

    def reserved(self, provider: str | None = None, month: str | None = None) -> float:
        tot = sum(r.est_usd for r in self._open.values()
                  if (provider is None or r.provider == provider) and (month is None or r.month == month))
        if provider in (None, "anthropic"):
            tot += self.pending_fn()
        return tot

    def run_spent(self) -> float:
        return self.spent(run_id=self.run_id)

    # ---- guard -------------------------------------------------------------------------------
    def check(self, provider: str, est_usd: float) -> None:
        """Raise BudgetExceeded if reserving est_usd now would cross any cap."""
        month = timeutil.month_key(self.now_fn())
        if provider == "anthropic":
            tot = self.spent("anthropic") + self.reserved("anthropic") + est_usd
            if tot > self.caps.anthropic_total_usd + EPS:
                raise BudgetExceeded(
                    f"Anthropic total cap ${self.caps.anthropic_total_usd:.2f} would be exceeded "
                    f"(spent+reserved+est = ${tot:.4f})")
            if not is_live_run(self.run_id):
                bt = self.spent("anthropic", backtest_only=True) + self.reserved("anthropic") + est_usd
                if bt > self.caps.anthropic_backtest_usd + EPS:
                    raise BudgetExceeded(
                        f"Anthropic backtest cap ${self.caps.anthropic_backtest_usd:.2f} would be exceeded "
                        f"(spent+reserved+est = ${bt:.4f})")
        elif provider == "exa":
            tot = self.spent("exa", month=month) + self.reserved("exa", month=month) + est_usd
            if tot > self.caps.exa_monthly_usd + EPS:
                raise BudgetExceeded(
                    f"Exa monthly cap ${self.caps.exa_monthly_usd:.2f} for {month} would be exceeded "
                    f"(spent+reserved+est = ${tot:.4f})")
        else:
            raise ValueError(f"unknown provider {provider!r}")
        own_open = sum(r.est_usd for r in self._open.values())
        run_tot = self.run_spent() + own_open + self.run_pending_fn() + est_usd
        if run_tot > self.max_usd + EPS:
            raise BudgetExceeded(
                f"per-run cap --max-usd ${self.max_usd:.2f} would be exceeded "
                f"(run spent+reserved+est = ${run_tot:.4f})")

    def charge(self, provider: str, est_usd: float, op: str) -> Reservation:
        self.check(provider, est_usd)
        r = Reservation(next(self._ids), provider, op, est_usd, timeutil.month_key(self.now_fn()))
        self._open[r.rid] = r
        return r

    def release(self, res: Reservation) -> None:
        self._open.pop(res.rid, None)

    def settle(self, res: Reservation, actual_usd: float, model: str | None, cache_key: str,
               input_tokens: int | None = None, output_tokens: int | None = None) -> LedgerEntry:
        self._open.pop(res.rid, None)
        entry = LedgerEntry(
            ts=self.now_fn(), provider=res.provider, op=res.op, model=model, cache_key=cache_key,
            cache_hit=False, est_usd=res.est_usd, actual_usd=actual_usd,
            input_tokens=input_tokens, output_tokens=output_tokens, run_id=self.run_id,
        )
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ledger_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(entry.model_dump_json() + "\n")
        self.entries.append(entry)
        return entry

    def record(self, provider: str, op: str, model: str | None, cache_key: str, actual_usd: float,
               input_tokens: int | None = None, output_tokens: int | None = None,
               est_usd: float = 0.0) -> LedgerEntry:
        """Ledger entry for spend already covered by a durable reservation (batch results)."""
        r = Reservation(-1, provider, op, est_usd, timeutil.month_key(self.now_fn()))
        return self.settle(r, actual_usd, model, cache_key, input_tokens, output_tokens)

    # ---- reporting ---------------------------------------------------------------------------
    def summary(self) -> dict:
        by = defaultdict(lambda: {"usd": 0.0, "calls": 0})
        for e in self.entries:
            k = (e.provider, e.op, timeutil.month_key(e.ts))
            by[k]["usd"] += e.actual_usd
            by[k]["calls"] += 1
        months = sorted({timeutil.month_key(e.ts) for e in self.entries})
        return {
            "anthropic_total_usd": round(self.spent("anthropic"), 6),
            "anthropic_backtest_usd": round(self.spent("anthropic", backtest_only=True), 6),
            "anthropic_cap_usd": self.caps.anthropic_total_usd,
            "anthropic_backtest_cap_usd": self.caps.anthropic_backtest_usd,
            "exa_by_month_usd": {m: round(self.spent("exa", month=m), 6) for m in months},
            "exa_monthly_cap_usd": self.caps.exa_monthly_usd,
            "by_provider_op_month": [
                {"provider": p, "op": o, "month": m, "usd": round(v["usd"], 6), "calls": v["calls"]}
                for (p, o, m), v in sorted(by.items())
            ],
            "n_paid_calls": len(self.entries),
        }

    def caps_ok(self) -> bool:
        s = self.summary()
        return (s["anthropic_total_usd"] <= self.caps.anthropic_total_usd + EPS
                and all(v <= self.caps.exa_monthly_usd + EPS for v in s["exa_by_month_usd"].values()))


def dump_summary(summary: dict) -> str:
    return json.dumps(summary, indent=2, sort_keys=True)
