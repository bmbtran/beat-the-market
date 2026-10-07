import json
from datetime import datetime, timezone

import pytest

from mf.core import timeutil
from mf.data.common import Candle
from mf.data.kalshi import normalize_candle
from mf.data.prices import kalshi_price_at, poly_price_at

T0 = datetime(2026, 6, 1, 12, tzinfo=timezone.utc)
T = int(T0.timestamp())


def C(end, bid=None, ask=None, close=None, prev=None):
    return Candle(end, bid, ask, close, prev, 0.0)


def test_uses_mid_of_last_candle_before_t0():
    cs = [C(T - 7200, 0.30, 0.34, 0.31), C(T - 3600, 0.40, 0.44, 0.41), C(T + 3600, 0.9, 0.95, 0.9)]
    assert kalshi_price_at(cs, T0) == (pytest.approx(0.42), "mid")


def test_wide_spread_falls_back_to_last_trade_then_previous():
    assert kalshi_price_at([C(T - 60, 0.10, 0.60, 0.33)], T0) == (0.33, "last_trade")
    assert kalshi_price_at([C(T - 60, 0.0, 1.0, None, 0.27)], T0) == (0.27, "previous")


def test_no_candle_within_24h_returns_none():
    assert kalshi_price_at([C(T - 25 * 3600, 0.4, 0.42, 0.41)], T0) is None
    assert kalshi_price_at([], T0) is None
    assert kalshi_price_at(None, T0) is None


def test_real_fixture_candles(fixtures_dir):
    d = json.loads((fixtures_dir / "kalshi" / "historical_candles.json").read_text(encoding="utf-8"))
    cs = [normalize_candle(c) for c in d["candlesticks"]]
    r = kalshi_price_at(cs, timeutil.parse(d["_request"]["end"]))
    assert r is not None and 0 <= r[0] <= 1


def test_poly_last_point_within_6h():
    hist = [(T - 8 * 3600, 0.2), (T - 3600, 0.35), (T + 60, 0.99)]
    assert poly_price_at(hist, T0) == (0.35, "last_trade")
    assert poly_price_at([(T - 7 * 3600, 0.2)], T0) is None


def test_poly_real_fixture(fixtures_dir):
    d = json.loads((fixtures_dir / "polymarket" / "prices_history.json").read_text(encoding="utf-8"))
    hist = [(h["t"], h["p"]) for h in d["history"]]
    r = poly_price_at(hist, timeutil.parse(d["_request"]["end"]))
    assert r is not None and 0 <= r[0] <= 1
