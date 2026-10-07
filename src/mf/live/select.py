"""Pick open markets for live forecasting: both venues, close in 7-60 days, same category filters and
volume floors as the backtest, at most one market per event, skipping qids already in the ledger."""

from __future__ import annotations

import random
from datetime import timedelta

from mf.core import timeutil
from mf.data import kalshi as K
from mf.data import polymarket as P
from mf.data.common import ALLOWED_CATEGORIES, to_float
from mf.schemas import Question

MIN_DAYS, MAX_DAYS = 7, 60
MAX_SPREAD = 0.10


def kalshi_live_price(m: dict) -> tuple[float, str] | None:
    bid, ask = to_float(m.get("yes_bid_dollars")), to_float(m.get("yes_ask_dollars"))
    if bid is not None and ask is not None and 0 < ask and 0 <= ask - bid <= MAX_SPREAD:
        return (bid + ask) / 2, "mid"
    last = to_float(m.get("last_price_dollars"))
    return (last, "last_trade") if last else None


def poly_live_price(m: dict) -> tuple[float, str] | None:
    bid, ask = to_float(m.get("bestBid")), to_float(m.get("bestAsk"))
    if bid is not None and ask is not None and 0 < ask and 0 <= ask - bid <= MAX_SPREAD:
        return (bid + ask) / 2, "mid"
    last = to_float(m.get("lastTradePrice"))
    return (last, "last_trade") if last else None


def _q(qid, venue, event_id, title, desc, cat, created, close, p, src, vol, url, now) -> Question:
    return Question(qid=qid, venue=venue, event_id=event_id, title=title, description=desc, category=cat,
                    created_at=created, t0=now, scheduled_close=close, resolved_at=close,
                    horizon_days=round(timeutil.days(close, now), 3), p_mkt_t0=round(p, 4), p_mkt_source=src,
                    volume=round(vol, 2), outcome=-1, split="live", source_url=url)


def kalshi_open(kc: K.KalshiClient, s, now, want: int, rng: random.Random, log=print) -> list[Question]:
    """Series that were active in the backtest window (cached settled-events lookups) -> open events."""
    min_close = s.window.canary_resolved_min - timedelta(days=30)
    series = []
    for cat in K.KALSHI_CATEGORIES:
        series += [x for x in kc.series(cat) if K.series_allowed(x)]
    rng.shuffle(series)
    out, checked = [], 0
    for ser in series:
        if len(out) >= want or checked >= 400:
            break
        try:
            if not kc.settled_events(ser["ticker"], min_close):  # cached by the dataset build
                continue
        except Exception:  # noqa: BLE001 - cache miss in readonly mode etc.
            continue
        checked += 1
        for ev in kc._paginate(f"{K.BASE}/events", {"series_ticker": ser["ticker"], "status": "open",
                                                    "with_nested_markets": "true", "limit": 200}, "events"):
            best = None
            for m in ev.get("markets") or []:
                close = timeutil.parse(m.get("expected_expiration_time") or m.get("close_time"))
                if (m.get("market_type") != "binary" or m.get("status") not in ("active", "open")
                        or m.get("mve_selected_legs") or close is None):
                    continue
                d = timeutil.days(close, now)
                vol = to_float(m.get("volume_fp")) or 0.0
                title = K.market_title(m)
                if not (MIN_DAYS <= d <= MAX_DAYS) or vol < s.dataset.kalshi_min_volume or len(title) < s.dataset.min_title_chars:
                    continue
                pr = kalshi_live_price(m)
                if pr is None or not (s.dataset.p_mkt_min <= pr[0] <= s.dataset.p_mkt_max):
                    continue
                if best is None or vol > best[1]:
                    best = (m, vol, pr, close)
            if best:
                m, vol, (p, src), close = best
                created = timeutil.parse(m.get("open_time") or m["created_time"])
                out.append(_q(f"kalshi:{m['ticker']}", "kalshi", f"kalshi:{m['event_ticker']}", K.market_title(m),
                              (m.get("rules_primary") or "").strip(), ser["category"], created, close, p, src, vol,
                              f"https://kalshi.com/markets/{m['event_ticker'].lower()}", now))
    log(f"[live:kalshi] {len(out)} candidates from {checked} active series")
    return out


def poly_open(pc: P.PolymarketClient, s, now, log=print) -> list[Question]:
    evs = pc.events_by_volume(False, now + timedelta(days=MIN_DAYS), now + timedelta(days=MAX_DAYS),
                              s.dataset.poly_min_volume, max_pages=10, use_cache=False)
    out = []
    for ev in evs:
        cat = P.classify(ev)
        if cat is None or cat not in ALLOWED_CATEGORIES:
            continue
        best = None
        for m in ev.get("markets") or []:
            if m.get("closed") or not m.get("active") or not P.open_market_ok(m):
                continue
            close = timeutil.parse(m.get("endDate"))
            vol = to_float(m.get("volumeNum", m.get("volume"))) or 0.0
            title = (m.get("question") or "").strip()
            if close is None or not (MIN_DAYS <= timeutil.days(close, now) <= MAX_DAYS):
                continue
            if vol < s.dataset.poly_min_volume or len(title) < s.dataset.min_title_chars:
                continue
            pr = poly_live_price(m)
            if pr is None or not (s.dataset.p_mkt_min <= pr[0] <= s.dataset.p_mkt_max):
                continue
            if best is None or vol > best[1]:
                best = (m, vol, pr, close)
        if best:
            m, vol, (p, src), close = best
            created = max(t for t in (timeutil.parse(m.get("createdAt")), timeutil.parse(m.get("startDate"))) if t)
            out.append(_q(f"poly:{m['id']}", "polymarket", f"poly:{ev['id']}", m["question"].strip(),
                          P.sanitize_description(m.get("description") or ""), cat, created, close, p, src, vol,
                          f"https://polymarket.com/event/{ev.get('slug', '')}", now))
    log(f"[live:poly] {len(out)} candidates")
    return out


def choose(cands: list[Question], n: int, skip_qids: set[str], skip_events: set[str]) -> list[Question]:
    """Highest volume first, alternating venues, <= 1 per event, category share <= 50%."""
    by_venue = {v: sorted([q for q in cands if q.venue == v and q.qid not in skip_qids and q.event_id not in skip_events],
                          key=lambda q: (-q.volume, q.qid)) for v in ("kalshi", "polymarket")}
    chosen, events, cats = [], set(), {}
    while len(chosen) < n and any(by_venue.values()):
        for v in ("polymarket", "kalshi"):
            while by_venue[v]:
                q = by_venue[v].pop(0)
                if q.event_id in events or cats.get(q.category, 0) >= max(1, n // 2):
                    continue
                chosen.append(q)
                events.add(q.event_id)
                cats[q.category] = cats.get(q.category, 0) + 1
                break
            if len(chosen) >= n:
                break
    return chosen
