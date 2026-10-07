"""Market price at a timestamp t0 (PLAN.md §6.3 step 5). Never shown to the LLM."""

from __future__ import annotations

from datetime import datetime

from mf.core import timeutil
from mf.data.common import Candle

MAX_SPREAD = 0.10
KALSHI_MAX_AGE_H = 24
POLY_MAX_AGE_H = 6


def kalshi_price_at(candles: list[Candle] | None, t0: datetime,
                    max_age_hours: float = KALSHI_MAX_AGE_H) -> tuple[float, str] | None:
    """Last 60-min candle ending <= t0 (and within max_age): mid if spread <= 0.10,
    else last trade (price.close), else price.previous. Returns (p, source) or None."""
    if not candles:
        return None
    t = timeutil.to_unix(t0)
    eligible = [c for c in candles if c.end_ts <= t and t - c.end_ts <= max_age_hours * 3600]
    if not eligible:
        return None
    c = max(eligible, key=lambda c: c.end_ts)
    if c.yes_bid is not None and c.yes_ask is not None and 0 < c.yes_ask and c.yes_ask - c.yes_bid <= MAX_SPREAD \
            and c.yes_ask >= c.yes_bid:
        return (c.yes_bid + c.yes_ask) / 2.0, "mid"
    if c.price_close is not None:
        return c.price_close, "last_trade"
    if c.price_previous is not None:
        return c.price_previous, "previous"
    return None


def poly_price_at(history: list[tuple[int, float]] | None, t0: datetime,
                  max_age_hours: float = POLY_MAX_AGE_H) -> tuple[float, str] | None:
    """Last CLOB price-history point with t <= t0 within max_age hours."""
    if not history:
        return None
    t = timeutil.to_unix(t0)
    pts = [(ts, p) for ts, p in history if ts <= t and t - ts <= max_age_hours * 3600]
    if not pts:
        return None
    return max(pts)[1], "last_trade"
