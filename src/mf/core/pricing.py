"""Cost arithmetic from configs/pricing.toml. Anthropic prices are $/MTok; Exa $/request."""

from __future__ import annotations

from mf.config import settings


def _model_prices(model: str, pricing: dict | None = None) -> dict:
    pricing = pricing or settings().pricing
    try:
        return pricing["anthropic"][model]
    except KeyError as e:
        raise KeyError(f"no pricing for model {model!r} in configs/pricing.toml") from e


def anthropic_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    batch: bool = False,
    pricing: dict | None = None,
) -> float:
    p = _model_prices(model, pricing)
    usd = (
        input_tokens * p["input"]
        + output_tokens * p["output"]
        + cache_read_tokens * p.get("cache_read", p["input"])
        + cache_write_tokens * p.get("cache_write_5m", p["input"] * 1.25)
    ) / 1e6
    if batch:
        usd *= p.get("batch_discount", 0.5)
    return usd


def anthropic_estimate(model: str, prompt_chars: int, max_tokens: int, batch: bool = False,
                       pricing: dict | None = None) -> float:
    """Deliberately pessimistic: chars/3 input tokens and the full max_tokens of output."""
    return anthropic_cost(model, int(prompt_chars / 3.0) + 1, max_tokens, batch=batch, pricing=pricing)


def exa_search_estimate(search_type: str, num_results: int, content_types: int = 1,
                        pricing: dict | None = None) -> float:
    p = (pricing or settings().pricing)["exa"]
    base = p[f"search_{search_type}"]
    extra = max(0, num_results - 10) * p["extra_result"]
    contents = num_results * content_types * p["contents_per_page_per_type"]
    return base + extra + contents
