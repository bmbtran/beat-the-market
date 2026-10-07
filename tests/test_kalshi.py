import json

import pytest

from mf.core import timeutil
from mf.data import kalshi as K


def load(fixtures_dir, name):
    return json.loads((fixtures_dir / "kalshi" / name).read_text(encoding="utf-8"))


def test_both_candle_schemas_normalize_to_same_candle(fixtures_dir):
    hist = [K.normalize_candle(c) for c in load(fixtures_dir, "historical_candles.json")["candlesticks"]]
    live = [K.normalize_candle(c) for c in load(fixtures_dir, "live_candles.json")["candlesticks"]]
    assert hist and live
    for c in hist + live:
        assert isinstance(c.end_ts, int)
        assert c.price_close is None or 0 <= c.price_close <= 1
        assert c.yes_bid is None or 0 <= c.yes_bid <= 1
    # historical uses plain names, live uses *_dollars; both must yield bids/asks
    assert any(c.yes_bid is not None and c.yes_ask is not None for c in hist)
    assert any(c.yes_bid is not None and c.yes_ask is not None for c in live)


def test_synthetic_schema_equivalence():
    h = {"end_period_ts": 10, "price": {"close": "0.4100", "previous": "0.4"}, "volume": "12.00",
         "yes_bid": {"close": "0.4000"}, "yes_ask": {"close": "0.4200"}}
    l = {"end_period_ts": 10, "price": {"close_dollars": "0.4100", "previous_dollars": "0.4"},
         "volume_fp": "12.00", "yes_bid": {"close_dollars": "0.4000"}, "yes_ask": {"close_dollars": "0.4200"}}
    assert K.normalize_candle(h) == K.normalize_candle(l)


def test_empty_trade_candle_has_only_previous():
    c = K.normalize_candle({"end_period_ts": 5, "price": {"previous_dollars": "0.3300"}})
    assert c.price_close is None and c.price_previous == pytest.approx(0.33)


def test_live_endpoint_404_for_historical_is_recorded(fixtures_dir):
    assert load(fixtures_dir, "live_candles_404_for_historical.json") == {"__status__": 404}


def test_market_to_candidate_whitelists_fields(fixtures_dir):
    ev = load(fixtures_dir, "events_fed_settled.json")["events"][0]
    m = ev["markets"][0]
    c = K.market_to_candidate(m, {"ticker": "KXFEDDECISION", "category": "Economics"}, historical=False)
    assert c is not None and c.qid == f"kalshi:{m['ticker']}"
    assert c.outcome == (1 if m["result"] == "yes" else 0)
    # scheduled end = expected_expiration_time, NOT latest_expiration_time (3-month buffer)
    assert c.scheduled_close == timeutil.parse(m["expected_expiration_time"])
    assert c.scheduled_close < timeutil.parse(m["latest_expiration_time"])


def test_can_close_early_keeps_original_schedule(fixtures_dir):
    m = load(fixtures_dir, "can_close_early_market.json")["market"]
    c = K.market_to_candidate(m, {"ticker": "S", "category": "Politics"}, historical=True)
    assert m["can_close_early"] is True
    assert c.actual_close == timeutil.parse(m["close_time"])
    assert c.scheduled_close > c.actual_close  # schedule preserved after the early close


def test_non_binary_and_mve_rejected():
    base = {"ticker": "X-1", "event_ticker": "X", "market_type": "binary", "result": "yes",
            "created_time": "2026-03-01T00:00:00Z", "close_time": "2026-04-01T00:00:00Z"}
    s = {"ticker": "X", "category": "Politics"}
    assert K.market_to_candidate(base, s, False) is not None
    assert K.market_to_candidate(base | {"market_type": "scalar"}, s, False) is None
    assert K.market_to_candidate(base | {"result": "scalar"}, s, False) is None
    assert K.market_to_candidate(base | {"mve_selected_legs": [{"a": 1}]}, s, False) is None


def test_series_filter():
    assert K.series_allowed({"category": "Economics", "frequency": "monthly"})
    assert not K.series_allowed({"category": "Economics", "frequency": "daily"})
    assert not K.series_allowed({"category": "Sports", "frequency": "one_off"})
    assert not K.series_allowed({"category": "Climate and Weather", "frequency": "weekly"})
    assert K.series_allowed({"category": "Climate and Weather", "frequency": "annual"})
