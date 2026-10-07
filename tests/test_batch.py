import json

import pytest

from mf.config import BudgetCfg
from mf.core.budget import BudgetGuard
from mf.core.cache import Cache
from mf.llm import batch as B
from mf.llm.client import CachedLLM, FakeLLM, LLMRequest

CAPS = BudgetCfg(anthropic_total_usd=30, anthropic_backtest_usd=23, exa_monthly_usd=9, per_run_default_usd=5)


def reqs(n=3):
    return [LLMRequest(model="claude-sonnet-5", user=f"question {i}", max_tokens=1200, op="reason",
                       prompt_id="r", prompt_sha="s", sample_idx=i) for i in range(n)]


def setup(tmp_path, fake=None):
    fake = fake or FakeLLM(lambda p: f"ans to {p['messages'][0]['content']}\nFINAL PROBABILITY: 0.3")
    budget = BudgetGuard(tmp_path / "ledger.jsonl", CAPS, run_id="t", max_usd=5,
                         pending_fn=lambda: B.pending_batch_reservations(tmp_path / "state"))
    return fake, CachedLLM(fake, Cache(tmp_path / "cache", mode="readwrite"), budget), budget


def test_batch_writes_cache_keyed_by_custom_id(tmp_path):
    fake, llm, budget = setup(tmp_path)
    rs = reqs()
    out = B.run_batch(llm, rs, tmp_path / "state", log=lambda m: None, poll_seconds=0)
    for r in rs:
        res = out[r.cache_key()]
        assert res is not None and res.text.startswith(f"ans to {r.user}")  # matched by id, not order
        assert llm.cache.exists("anthropic", r.cache_key())
    st = json.loads(next((tmp_path / "state" / "batches").glob("*.json")).read_text())
    assert set(st["requests"]) == {r.cache_key()[:64] for r in rs} and st["status"] == "collected"
    assert len(budget.entries) == 3 and all(e.op == "reason_batch" for e in budget.entries)
    assert budget.spent("anthropic") > 0


def test_only_misses_are_submitted(tmp_path):
    fake, llm, _ = setup(tmp_path)
    rs = reqs()
    llm.complete(rs[0])  # pre-cached via sync
    B.run_batch(llm, rs, tmp_path / "state", log=lambda m: None, poll_seconds=0)
    (bid,) = fake.batches
    assert len(fake.batches[bid]["requests"]) == 2
    assert B.submit(llm, rs, tmp_path / "state") is None  # nothing left to submit


def test_resumable_after_crash(tmp_path):
    fake, llm, _ = setup(tmp_path)
    rs = reqs()
    bid = B.submit(llm, rs, tmp_path / "state")  # ... process crashes before collect
    assert B.pending_batch_reservations(tmp_path / "state") > 0  # still counted against the budget
    _, llm2, budget2 = setup(tmp_path, fake=fake)  # fresh process, same remote batch
    assert not any(llm2.cache.exists("anthropic", r.cache_key()) for r in rs)
    done = B.resume_all(llm2, tmp_path / "state", log=lambda m: None, poll_seconds=0)
    assert done == [bid]
    assert all(llm2.cache.exists("anthropic", r.cache_key()) for r in rs)
    assert B.pending_batch_reservations(tmp_path / "state") == 0
    assert B.resume_all(llm2, tmp_path / "state", log=lambda m: None, poll_seconds=0) == []  # idempotent


def test_pending_batch_counts_toward_caps(tmp_path):
    fake, llm, budget = setup(tmp_path)
    B.submit(llm, reqs(), tmp_path / "state")
    assert budget.reserved("anthropic") == pytest.approx(B.pending_batch_reservations(tmp_path / "state"))
