"""`mf fixtures record`: save <= 15 small real API responses to tests/fixtures/{kalshi,polymarket}."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from mf.config import settings
from mf.core import timeutil
from mf.core.cache import Cache
from mf.core.http import CachedHttp
from mf.data import kalshi as K
from mf.data import polymarket as P


def _save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def record(log=print) -> list[Path]:
    s = settings()
    http = CachedHttp(Cache(s.cache_dir, mode="readwrite"))
    fx = s.root / "tests" / "fixtures"
    saved: list[Path] = []

    def save(rel: str, obj) -> None:
        p = fx / rel
        _save(p, obj)
        saved.append(p)
        log(f"saved {p.relative_to(s.root).as_posix()}")

    # --- Kalshi -------------------------------------------------------------------------------
    hist = http.get_json(f"{K.BASE}/historical/markets",
                         {"series_ticker": "KXFEDDECISION", "limit": 1000})
    hm = [m for m in hist["markets"] if m["event_ticker"] == "KXFEDDECISION-26JUL"]
    save("kalshi/historical_markets_fed_jul26.json", {"cursor": "", "markets": hm[:3]})
    m = hm[0]
    end = timeutil.parse(m["close_time"]) - timedelta(days=10)
    save("kalshi/historical_candles.json", http.get_json(
        f"{K.BASE}/historical/markets/{m['ticker']}/candlesticks",
        {"start_ts": timeutil.to_unix(end - timedelta(hours=12)), "end_ts": timeutil.to_unix(end),
         "period_interval": 60}) | {"_request": {"ticker": m["ticker"], "end": timeutil.iso(end)}})

    evs = http.get_json(f"{K.BASE}/events", {"series_ticker": "KXFEDDECISION", "status": "settled",
                                            "with_nested_markets": "true", "limit": 200})
    live_ev = next(e for e in evs["events"] if e.get("markets"))
    save("kalshi/events_fed_settled.json",
         {"cursor": "", "events": [dict(live_ev, markets=live_ev["markets"][:3])] +
          [dict(e) for e in evs["events"] if not e.get("markets")][:2]})
    lm = live_ev["markets"][0]
    lend = timeutil.parse(lm["close_time"]) - timedelta(days=10)
    save("kalshi/live_candles.json", http.get_json(
        f"{K.BASE}/series/KXFEDDECISION/markets/{lm['ticker']}/candlesticks",
        {"start_ts": timeutil.to_unix(lend - timedelta(hours=12)), "end_ts": timeutil.to_unix(lend),
         "period_interval": 60}) | {"_request": {"ticker": lm["ticker"], "end": timeutil.iso(lend)}})
    save("kalshi/live_candles_404_for_historical.json", http.get_json(
        f"{K.BASE}/series/KXFEDDECISION/markets/{m['ticker']}/candlesticks",
        {"start_ts": timeutil.to_unix(end - timedelta(hours=2)), "end_ts": timeutil.to_unix(end),
         "period_interval": 60}))

    # A can_close_early market that actually closed early (non-sports series).
    early = None
    for ser in ("KXGOVSHUTLENGTH", "KXTRUMPPUTIN", "KXRECOGPERSONIRAN", "KXIRANDEMOCRACY", "KXFEDDECISION"):
        for mm in http.get_json(f"{K.BASE}/historical/markets",
                                {"series_ticker": ser, "limit": 1000}).get("markets") or []:
            if mm.get("can_close_early") and mm.get("latest_expiration_time") and \
                    timeutil.parse(mm["close_time"]) < timeutil.parse(mm["latest_expiration_time"]) - timedelta(days=3):
                early = mm
                break
        if early:
            break
    if early is None:
        hm_all = http.get_json(f"{K.BASE}/historical/markets", {"mve_filter": "exclude", "limit": 200})["markets"]
        early = next(mm for mm in hm_all if mm.get("can_close_early"))
    save("kalshi/can_close_early_market.json", {"market": early})
    save("kalshi/cutoff.json", http.get_json(f"{K.BASE}/historical/cutoff"))

    # --- Polymarket ---------------------------------------------------------------------------
    evs = P.PolymarketClient(http).events_page(True, timeutil.parse("2026-02-08T00:00:00Z"),
                                               timeutil.parse("2026-09-30T23:59:59Z"), offset=0)
    neg = next(e for e in evs if e.get("negRisk") and P.classify(e))
    save("polymarket/event_negrisk.json", dict(neg, markets=(neg.get("markets") or [])[:3]))
    nonyn = None
    for e in evs:
        for mk in e.get("markets") or []:
            if P._jlist(mk.get("outcomes")) not in (["Yes", "No"], []):
                nonyn = dict(e, markets=[mk])
                break
        if nonyn:
            break
    if nonyn:
        save("polymarket/event_non_yes_no.json", nonyn)
    mk = neg["markets"][0]
    tok = P._jlist(mk["clobTokenIds"])[0]
    t_end = timeutil.parse(mk["endDate"]) - timedelta(days=10)
    save("polymarket/prices_history.json", http.get_json(f"{P.CLOB}/prices-history", {
        "market": tok, "startTs": timeutil.to_unix(t_end - timedelta(hours=12)),
        "endTs": timeutil.to_unix(t_end), "fidelity": 60}) | {"_request": {"token": tok, "end": timeutil.iso(t_end)}})
    return saved
