import json
from datetime import datetime, timedelta, timezone

from mf.config import settings
from mf.data import dataset as D
from mf.data import kalshi as K
from mf.data.common import Candidate
from mf.schemas import prompt_fields

UTC = timezone.utc


def cand(i, event="E1", venue="kalshi", vol=10_000, cat="Politics", created=datetime(2026, 3, 1, tzinfo=UTC),
         close=datetime(2026, 5, 1, tzinfo=UTC), actual=None, outcome=1, title="Will something happen by May?"):
    return Candidate(
        qid=f"{venue}:{i}", venue=venue, event_id=f"{venue}:{event}", title=title, description="d",
        category=cat, created_at=created, scheduled_close=close, actual_close=actual or close,
        resolved_at=(actual or close) + timedelta(hours=1), volume=vol, outcome=outcome, source_url="u",
        price_ref={"series": "S", "ticker": str(i), "historical": True} if venue == "kalshi" else {"token_id": "t"})


def test_choose_t0():
    c, e = datetime(2026, 3, 1, 7, 30, tzinfo=UTC), datetime(2026, 3, 31, 7, 30, tzinfo=UTC)
    assert D.choose_t0(c, e) == datetime(2026, 3, 16, 7, tzinfo=UTC)  # midpoint, floored
    long_c, long_e = datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 2, 9, tzinfo=UTC)
    t0 = D.choose_t0(long_c, long_e)
    assert t0 == datetime(2026, 2, 5, tzinfo=UTC)  # min(created+4d, close-3d=02-06)
    assert t0 >= long_c + timedelta(days=1)


def test_static_filters():
    s = settings()
    win = D.windows(s)["main"]
    f = D.Funnel()
    assert D.static_filter(cand(1), win, s, f) is not None
    assert D.static_filter(cand(2, created=datetime(2026, 1, 20, tzinfo=UTC)), win, s, f) is None
    assert D.static_filter(cand(3, close=datetime(2026, 10, 2, tzinfo=UTC)), win, s, f) is None
    assert D.static_filter(cand(4, vol=10), win, s, f) is None
    assert D.static_filter(cand(5, cat="Sports"), win, s, f) is None
    assert D.static_filter(cand(6, close=datetime(2026, 3, 5, tzinfo=UTC)), win, s, f) is None  # <7d
    assert D.static_filter(cand(7, title="short?"), win, s, f) is None
    # closed (resolved) long before scheduled end -> not forecastable at t0
    early = cand(8, actual=datetime(2026, 3, 10, tzinfo=UTC), outcome=1)
    assert D.static_filter(early, win, s, f) is None
    assert f.counts["drop:closed_before_t0_plus_1d"] == 1 and f.dropped_after_t0_outcomes == [1]


class FakeK:
    def candles(self, series, ticker, start, end, historical):
        from mf.data.common import Candle
        if ticker == "nop":
            return []
        p = {"x": 0.995}.get(ticker, 0.40)
        return [Candle(int(end.timestamp()) - 60, p - 0.01, p + 0.01, p, p, 1.0)]


class FakeP:
    def price_history(self, token, start, end):
        return [(int(end.timestamp()) - 60, 0.5)]


def test_sample_max_two_per_event_highest_volume_and_price_filters():
    s = settings()
    win = D.windows(s)["main"]
    f = D.Funnel()
    cs = [cand(1, vol=6000), cand(2, vol=9000), cand(3, vol=8000), cand(4, vol=7000),
          cand("x", event="E2", vol=50_000), cand("nop", event="E3", vol=50_000)]
    pool = [(c, D.static_filter(c, win, s, f)) for c in cs]
    qs = D.sample(pool, 10, s, FakeK(), FakeP(), f, "test", log=lambda m: None)
    ids = sorted(q.qid for q in qs)
    assert ids == ["kalshi:2", "kalshi:3"]  # top-2 by volume of E1; E2 extreme price; E3 no price
    assert f.counts["drop:p_mkt_extreme"] == 1 and f.counts["drop:no_price_within_window"] == 1
    assert all(q.p_mkt_source == "mid" for q in qs)


def test_outcome_text_never_in_prompt_fields(fixtures_dir):
    ev = json.loads((fixtures_dir / "kalshi" / "events_fed_settled.json").read_text(encoding="utf-8"))
    m = ev["events"][0]["markets"][0]
    assert m["expiration_value"]  # e.g. "Hike 25bps" -- the realized outcome
    c = K.market_to_candidate(m, {"ticker": "KXFEDDECISION", "category": "Economics"}, historical=False)
    t0 = D.choose_t0(c.created_at, c.scheduled_close)
    q = D.to_question(c, t0, 0.4, "mid", "test")
    visible = json.dumps(prompt_fields(q))
    assert m["expiration_value"] not in visible
    for leak in ("settlement", "last_price", str(q.outcome) + "\"", "p_mkt"):
        assert leak not in visible
    assert set(prompt_fields(q)) == {"title", "description", "today", "scheduled_close"}
