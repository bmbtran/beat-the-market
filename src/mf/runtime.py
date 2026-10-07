"""Builds the shared per-command context: settings, cache, budget guard, LLM + Exa clients.

Without --allow-spend no paid client exists: any cache miss raises SpendNotAllowed.
"""

from __future__ import annotations

from dataclasses import dataclass

from mf.config import Settings, settings
from mf.core import timeutil
from mf.core.budget import BudgetGuard
from mf.core.cache import Cache
from mf.llm.batch import pending_batch_reservations
from mf.llm.client import AnthropicClient, CachedLLM
from mf.retrieval.exa_client import ExaClient


class SpendNotAllowed(RuntimeError):
    pass


@dataclass
class Ctx:
    s: Settings
    cache: Cache
    budget: BudgetGuard
    llm: CachedLLM
    exa: ExaClient
    run_id: str
    allow_spend: bool

    @property
    def state_dir(self):
        return self.s.state_dir


def _deny():
    raise SpendNotAllowed("cache miss requires a paid API call; re-run with --allow-spend "
                          "(or --dry-run to see projected cost)")


class _DenyHttp:
    def post(self, *a, **k):
        _deny()


def make_ctx(prefix: str = "run", max_usd: float | None = None, allow_spend: bool = False,
             llm_client=None, exa_http=None) -> Ctx:
    """run_id = <prefix>-<UTC timestamp>: the per-run --max-usd cap applies to one invocation.
    Prefixes starting with "live" are exempt from the backtest sub-cap (never from the total cap)."""
    s = settings()
    run_id = f"{prefix}-{timeutil.now().strftime('%Y%m%dT%H%M%SZ')}"
    cache = Cache(s.cache_dir)
    budget = BudgetGuard(s.state_dir / "ledger.jsonl", s.budget, run_id=run_id, max_usd=max_usd,
                         pending_fn=lambda: pending_batch_reservations(s.state_dir),
                         run_pending_fn=lambda: pending_batch_reservations(s.state_dir, run_id))
    if llm_client is not None:
        llm = CachedLLM(llm_client, cache, budget)
    elif allow_spend:
        llm = CachedLLM(None, cache, budget, client_factory=AnthropicClient)
    else:
        llm = CachedLLM(None, cache, budget, client_factory=_deny)
    if exa_http is not None:
        exa = ExaClient(cache, budget, http=exa_http)
    elif allow_spend:
        exa = ExaClient(cache, budget)
    else:
        exa = ExaClient(cache, budget, http=_DenyHttp())
    return Ctx(s, cache, budget, llm, exa, run_id, allow_spend)
