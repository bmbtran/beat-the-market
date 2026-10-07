"""Kalshi public trade-api v2 (no auth for reads).

Two data tiers (verified 2026-10-06):
  * markets settled before GET /historical/cutoff -> /historical/markets, /historical/markets/{t}/candlesticks
    (candle fields: plain names, dollar strings: price.close, yes_bid.close, volume)
  * newer markets -> /events?with_nested_markets=true, /series/{s}/markets/{t}/candlesticks
    (candle fields: *_dollars / *_fp suffixes; 404 for historical-tier markets)
/events with with_nested_markets omits `markets` for historical-tier events, which is how we route.

LEAKAGE: market objects carry result/expiration_value/settlement_*/last_price_*; only whitelisted
fields are copied into a Candidate (see `market_to_candidate`).
"""

from __future__ import annotations

from datetime import datetime

from mf.core import timeutil
from mf.core.http import CachedHttp
from mf.data.common import Candidate, Candle, to_float

BASE = "https://api.elections.kalshi.com/trade-api/v2"

KALSHI_CATEGORIES = [
    "Politics", "Elections", "Economics", "World", "Science and Technology", "Companies",
    "Financials", "Climate and Weather", "Health", "Entertainment",
]
EXCLUDED_FREQUENCIES = {"fifteen_min", "hourly", "daily"}
CLIMATE_FREQUENCIES = {"monthly", "annual"}


def series_allowed(series: dict) -> bool:
    cat = series.get("category")
    freq = series.get("frequency")
    if cat not in KALSHI_CATEGORIES or freq in EXCLUDED_FREQUENCIES:
        return False
    if cat == "Climate and Weather" and freq not in CLIMATE_FREQUENCIES:
        return False
    return True


class KalshiClient:
    def __init__(self, http: CachedHttp):
        self.http = http

    def cutoff(self) -> datetime:
        d = self.http.get_json(f"{BASE}/historical/cutoff")
        return timeutil.parse(d["market_settled_ts"])

    def series(self, category: str) -> list[dict]:
        return self.http.get_json(f"{BASE}/series", {"category": category}).get("series") or []

    def _paginate(self, url: str, params: dict, key: str, max_pages: int = 50) -> list[dict]:
        out, cursor = [], None
        for _ in range(max_pages):
            p = dict(params)
            if cursor:
                p["cursor"] = cursor
            d = self.http.get_json(url, p)
            out.extend(d.get(key) or [])
            cursor = d.get("cursor")
            if not cursor:
                break
        return out

    def settled_events(self, series_ticker: str, min_close: datetime) -> list[dict]:
        return self._paginate(f"{BASE}/events", {
            "series_ticker": series_ticker, "status": "settled", "with_nested_markets": "true",
            "min_close_ts": timeutil.to_unix(min_close), "limit": 200}, "events")

    def historical_markets(self, series_ticker: str) -> list[dict]:
        return self._paginate(f"{BASE}/historical/markets", {
            # NB: the API rejects series_ticker combined with mve_filter (mutually exclusive);
            # MVE markets live in KXMVE* series and are also dropped in market_to_candidate.
            "series_ticker": series_ticker, "limit": 1000}, "markets")

    def open_events(self, series_ticker: str) -> list[dict]:
        return self._paginate(f"{BASE}/events", {
            "series_ticker": series_ticker, "status": "open", "with_nested_markets": "true",
            "limit": 200}, "events")

    def candles(self, series_ticker: str, ticker: str, start: datetime, end: datetime,
                historical: bool, use_cache: bool = True) -> list[Candle] | None:
        params = {"start_ts": timeutil.to_unix(start), "end_ts": timeutil.to_unix(end), "period_interval": 60}
        url = (f"{BASE}/historical/markets/{ticker}/candlesticks" if historical
               else f"{BASE}/series/{series_ticker}/markets/{ticker}/candlesticks")
        d = self.http.get_json(url, params, use_cache=use_cache)
        if d.get("__status__") == 404:
            return None
        return [normalize_candle(c) for c in d.get("candlesticks") or []]

    def market(self, ticker: str, use_cache: bool = False) -> dict | None:
        d = self.http.get_json(f"{BASE}/markets/{ticker}", use_cache=use_cache)
        if d.get("__status__") == 404:
            d = self.http.get_json(f"{BASE}/historical/markets/{ticker}", use_cache=use_cache)
            if d.get("__status__") == 404:
                return None
        return d.get("market")


def _num(group: dict | None, name: str) -> float | None:
    """Read a candle sub-field from either schema: `close` (historical) or `close_dollars` (live)."""
    if not group:
        return None
    for k in (f"{name}_dollars", name):
        if k in group and group[k] is not None:
            return to_float(group[k])
    return None


def normalize_candle(c: dict) -> Candle:
    vol = c.get("volume_fp", c.get("volume"))
    return Candle(
        end_ts=int(c["end_period_ts"]),
        yes_bid=_num(c.get("yes_bid"), "close"),
        yes_ask=_num(c.get("yes_ask"), "close"),
        price_close=_num(c.get("price"), "close"),
        price_previous=_num(c.get("price"), "previous"),
        volume=to_float(vol),
    )


def market_title(m: dict) -> str:
    title = (m.get("title") or "").strip()
    sub = (m.get("yes_sub_title") or "").strip()
    if sub and sub.lower() not in title.lower():
        return f"{title} — this market resolves YES for: {sub}"
    return title


def market_to_candidate(m: dict, series: dict, historical: bool) -> Candidate | None:
    """Whitelist conversion. Returns None if the market is not a clean binary yes/no."""
    if m.get("market_type") != "binary" or m.get("result") not in ("yes", "no"):
        return None
    if m.get("mve_selected_legs") or str(m.get("ticker", "")).startswith("KXMVE"):
        return None
    created = max(timeutil.parse(m["created_time"]), timeutil.parse(m.get("open_time") or m["created_time"]))
    expected_exp = timeutil.parse(m.get("expected_expiration_time"))
    latest_exp = timeutil.parse(m.get("latest_expiration_time"))
    close = timeutil.parse(m["close_time"])
    # Scheduled end (selection-bias guard): an early close moves close_time only; the expiration
    # fields keep the original schedule (verified on KXGOVSHUTLENGTH-26FEB28-4D, closed 02-04,
    # expected/latest expiration still 03-01). latest_expiration_time carries a long buffer
    # (KXFEDDECISION-26SEP: expected 09-16, latest 12-16), so expected_expiration_time is used.
    scheduled = expected_exp or latest_exp or close
    return Candidate(
        qid=f"kalshi:{m['ticker']}",
        venue="kalshi",
        event_id=f"kalshi:{m['event_ticker']}",
        title=market_title(m),
        description=(m.get("rules_primary") or "").strip(),
        category=series.get("category") or "",
        created_at=created,
        scheduled_close=scheduled,
        actual_close=close,
        resolved_at=timeutil.parse(m.get("settlement_ts")) or close,
        volume=to_float(m.get("volume_fp", m.get("volume"))) or 0.0,
        outcome=1 if m["result"] == "yes" else 0,
        source_url=f"https://kalshi.com/markets/{m['event_ticker'].lower()}",
        can_close_early=bool(m.get("can_close_early")),
        expected_expiration=expected_exp,
        price_ref={"series": series["ticker"], "ticker": m["ticker"], "historical": historical},
    )
