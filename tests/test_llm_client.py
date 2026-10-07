import pytest

from mf.config import BudgetCfg
from mf.core.budget import BudgetExceeded, BudgetGuard
from mf.core.cache import Cache, CacheMiss
from mf.llm.client import CachedLLM, FakeLLM, LLMRequest

CAPS = BudgetCfg(anthropic_total_usd=30, anthropic_backtest_usd=23, exa_monthly_usd=9, per_run_default_usd=5)


def req(**kw):
    base = dict(model="claude-sonnet-5", user="Q?", max_tokens=1200, op="reason", effort="medium",
                thinking="disabled", prompt_id="p", prompt_sha="s1", sample_idx=0)
    base.update(kw)
    return LLMRequest(**base)


def test_api_params_never_include_sampling_params():
    p = req().api_params()
    assert p["thinking"] == {"type": "disabled"}
    assert p["output_config"] == {"effort": "medium"}
    for banned in ("temperature", "top_p", "top_k"):
        assert banned not in p
    haiku = req(model="claude-haiku-4-5-20251001", effort=None, thinking=None).api_params()
    assert "output_config" not in haiku and "thinking" not in haiku


def test_cached_llm_pays_once_then_hits(tmp_path):
    fake = FakeLLM(lambda p: "reasoning...\nFINAL PROBABILITY: 0.61")
    budget = BudgetGuard(tmp_path / "ledger.jsonl", CAPS, run_id="t", max_usd=1)
    llm = CachedLLM(fake, Cache(tmp_path / "c", mode="readwrite"), budget)
    r1 = llm.complete(req())
    r2 = llm.complete(req())
    assert (r1.cache_hit, r2.cache_hit) == (False, True)
    assert r1.text == r2.text and "0.61" in r1.text
    assert len(fake.calls) == 1
    assert budget.spent("anthropic") == pytest.approx(r1.cost_usd) and r1.cost_usd > 0
    assert len(budget.entries) == 1


def test_key_changes_with_prompt_sha(tmp_path):
    assert req().cache_key() != req(prompt_sha="s2").cache_key()
    assert req().cache_key() != req(sample_idx=1).cache_key()


def test_readonly_cache_never_calls_client(tmp_path):
    fake = FakeLLM()
    llm = CachedLLM(fake, Cache(tmp_path, mode="readonly"), None)
    with pytest.raises(CacheMiss):
        llm.complete(req())
    assert fake.calls == []


def test_budget_blocks_before_call(tmp_path):
    fake = FakeLLM()
    budget = BudgetGuard(tmp_path / "l.jsonl", CAPS, run_id="t", max_usd=0.001)
    llm = CachedLLM(fake, Cache(tmp_path / "c", mode="readwrite"), budget)
    with pytest.raises(BudgetExceeded):
        llm.complete(req())
    assert fake.calls == []


def test_refusal_is_not_ok(tmp_path):
    llm = CachedLLM(FakeLLM(stop_reason="refusal"), Cache(tmp_path, mode="readwrite"),
                    BudgetGuard(tmp_path / "l.jsonl", CAPS, run_id="t", max_usd=1))
    assert llm.complete(req()).ok is False
