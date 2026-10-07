import pytest

from mf.core.pricing import anthropic_cost, anthropic_estimate, exa_search_estimate


def test_sonnet5_million_tokens():
    assert anthropic_cost("claude-sonnet-5", 1_000_000, 1_000_000) == pytest.approx(12.00)
    assert anthropic_cost("claude-sonnet-5", 1_000_000, 1_000_000, batch=True) == pytest.approx(6.00)


def test_haiku_and_cache_read():
    assert anthropic_cost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000) == pytest.approx(6.00)
    assert anthropic_cost("claude-sonnet-5", 0, 0, cache_read_tokens=1_000_000) == pytest.approx(0.20)


def test_estimate_is_pessimistic():
    # 3000 chars -> 1001 input tokens; full 1200 output tokens
    est = anthropic_estimate("claude-sonnet-5", 3000, 1200)
    assert est == pytest.approx((1001 * 2 + 1200 * 10) / 1e6)
    assert anthropic_estimate("claude-sonnet-5", 3000, 1200, batch=True) == pytest.approx(est / 2)


def test_exa_estimates():
    assert exa_search_estimate("instant", 5) == pytest.approx(0.004 + 5 * 0.001)
    assert exa_search_estimate("fast", 12) == pytest.approx(0.007 + 2 * 0.001 + 12 * 0.001)


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        anthropic_cost("claude-nope", 1, 1)
