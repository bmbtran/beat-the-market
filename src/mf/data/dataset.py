"""Deterministic dataset construction (PLAN.md §6.3) and validation.

    uv run mf build-dataset
    uv run python -m mf.data.dataset --validate
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from mf.config import Settings, settings
from mf.core import timeutil
from mf.core.cache import Cache
from mf.core.http import CachedHttp
from mf.data import kalshi as K
from mf.data import polymarket as P
from mf.data.common import ALLOWED_CATEGORIES, LOW_PRIORITY_CATEGORIES, Candidate
from mf.data.prices import kalshi_price_at, poly_price_at
from mf.schemas import Question

DAY = timedelta(days=1)


# ---------------------------------------------------------------------------------------------
# t0 choice
# ---------------------------------------------------------------------------------------------
def choose_t0(created: datetime, scheduled_close: datetime) -> datetime:
    """t0 = min(created + lifetime/2, close - 3d), floored to the hour, and >= created + 1d."""
    lifetime = scheduled_close - created
    t0 = timeutil.floor_hour(min(created + lifetime / 2, scheduled_close - 3 * DAY))
    floor = created + DAY
    if t0 < floor:
        t0 = timeutil.floor_hour(floor) + timedelta(hours=1)
    return t0


# ---------------------------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------------------------
@dataclass
class Window:
    name: str  # "main" | "canary"
    resolved_min: datetime | None
    resolved_max: datetime
    created_min: datetime | None
    close_max: datetime


def windows(s: Settings) -> dict[str, Window]:
    w = s.window
    return {
        "main": Window("main", None, w.resolved_max, w.created_min, w.close_max),
        "canary": Window("canary", w.canary_resolved_min, w.canary_resolved_max, None, w.canary_resolved_max),
    }


@dataclass
class Funnel:
    counts: Counter = field(default_factory=Counter)
    dropped_after_t0_outcomes: list = field(default_factory=list)

    def drop(self, reason: str) -> None:
        self.counts[f"drop:{reason}"] += 1

    def as_dict(self) -> dict:
        d = dict(sorted(self.counts.items()))
        n = len(self.dropped_after_t0_outcomes)
        d["closed_before_t0_plus_1d_yes_rate"] = (
            round(sum(self.dropped_after_t0_outcomes) / n, 4) if n else None)
        return d


def static_filter(c: Candidate, win: Window, s: Settings, f: Funnel) -> datetime | None:
    """All filters that need no price data. Returns t0 if the candidate survives."""
    ds = s.dataset
    if c.category not in ALLOWED_CATEGORIES:
        f.drop("category"); return None
    if win.created_min and c.created_at < win.created_min:
        f.drop("created_before_window"); return None
    if c.scheduled_close > win.close_max:
        f.drop("scheduled_close_after_window"); return None
    if c.resolved_at > win.resolved_max or (win.resolved_min and c.resolved_at < win.resolved_min):
        f.drop("resolved_outside_window"); return None
    if timeutil.days(c.scheduled_close, c.created_at) < ds.min_lifetime_days:
        f.drop("lifetime_lt_7d"); return None
    floor = ds.kalshi_min_volume if c.venue == "kalshi" else ds.poly_min_volume
    if c.volume < floor:
        f.drop("volume"); return None
    if len(c.title) < ds.min_title_chars:
        f.drop("title_short"); return None
    if (c.venue == "kalshi" and c.can_close_early and c.expected_expiration
            and c.actual_close < c.expected_expiration - 3 * DAY):
        f.drop("kalshi_closed_early_gt_3d"); return None
    t0 = choose_t0(c.created_at, c.scheduled_close)
    if c.actual_close < t0 + DAY:
        # Trading stopped (usually: outcome became known) before t0+1d -> cannot be forecast at t0.
        f.drop("closed_before_t0_plus_1d")
        f.dropped_after_t0_outcomes.append(c.outcome)
        return None
    f.counts["pass_static"] += 1
    return t0


# ---------------------------------------------------------------------------------------------
# Candidate enumeration
# ---------------------------------------------------------------------------------------------
def kalshi_candidates(kc: K.KalshiClient, s: Settings, log=print) -> tuple[list[Candidate], Counter]:
    counts: Counter = Counter()
    min_close = s.window.canary_resolved_min - 30 * DAY
    series_all = []
    for cat in K.KALSHI_CATEGORIES:
        ss = kc.series(cat)
        counts["series_listed"] += len(ss)
        series_all += [x for x in ss if K.series_allowed(x)]
    seen = set()
    series_all = [x for x in series_all if not (x["ticker"] in seen or seen.add(x["ticker"]))]
    counts["series_allowed"] = len(series_all)
    log(f"[kalshi] {len(series_all)} allowed series (of {counts['series_listed']} listed)")
    out: list[Candidate] = []
    for i, ser in enumerate(series_all):
        if i % 250 == 0:
            log(f"[kalshi] series {i}/{len(series_all)}  markets so far={counts['markets_seen']}  "
                f"http_calls={kc.http.network_calls}")
        events = kc.settled_events(ser["ticker"], min_close)
        if not events:
            continue
        need_hist = set()
        for ev in events:
            ms = ev.get("markets")
            if not ms:
                need_hist.add(ev["event_ticker"])
                continue
            for m in ms:
                counts["markets_seen"] += 1
                c = K.market_to_candidate(m, ser, historical=False)
                if c is None:
                    counts["drop:not_binary_or_unresolved"] += 1
                else:
                    out.append(c)
        if need_hist:
            for m in kc.historical_markets(ser["ticker"]):
                if m.get("event_ticker") not in need_hist:
                    continue
                counts["markets_seen"] += 1
                c = K.market_to_candidate(m, ser, historical=True)
                if c is None:
                    counts["drop:not_binary_or_unresolved"] += 1
                else:
                    out.append(c)
    return out, counts


def poly_candidates(pc: P.PolymarketClient, s: Settings, win: Window, log=print) -> tuple[list[Candidate], Counter]:
    counts: Counter = Counter()
    end_min = (win.created_min + s.dataset.min_lifetime_days * DAY) if win.created_min else win.resolved_min
    events = pc.events_by_volume(True, end_min, win.close_max, s.dataset.poly_min_volume)
    counts["events_listed"] = len(events)
    log(f"[poly:{win.name}] {len(events)} closed events listed")
    out = []
    for ev in events:
        cat = P.classify(ev)
        ms = ev.get("markets") or []
        if cat is None:
            counts["drop:category_or_excluded_tag"] += len(ms)
            continue
        for m in ms:
            counts["markets_seen"] += 1
            c = P.market_to_candidate(m, ev, cat)
            if c is None:
                counts["drop:not_binary_yes_no_or_unresolved"] += 1
            else:
                out.append(c)
    return out, counts


# ---------------------------------------------------------------------------------------------
# Pricing + sampling
# ---------------------------------------------------------------------------------------------
def price_at_t0(c: Candidate, t0: datetime, kc: K.KalshiClient, pc: P.PolymarketClient):
    start = t0 - DAY
    if c.venue == "kalshi":
        r = c.price_ref
        candles = kc.candles(r["series"], r["ticker"], start, t0, historical=r["historical"])
        if candles is None and not r["historical"]:  # tier moved since enumeration
            candles = kc.candles(r["series"], r["ticker"], start, t0, historical=True)
        return kalshi_price_at(candles, t0)
    hist = pc.price_history(c.price_ref["token_id"], start, t0)
    return poly_price_at(hist, t0)


def to_question(c: Candidate, t0: datetime, p: float, src: str, split: str) -> Question:
    return Question(
        qid=c.qid, venue=c.venue, event_id=c.event_id, title=c.title, description=c.description,
        category=c.category, created_at=c.created_at, t0=t0, scheduled_close=c.scheduled_close,
        resolved_at=c.resolved_at, horizon_days=round(timeutil.days(c.scheduled_close, t0), 3),
        p_mkt_t0=round(p, 4), p_mkt_source=src, volume=round(c.volume, 2), outcome=c.outcome,
        split=split, source_url=c.source_url,
    )


def sample(pool: list[tuple[Candidate, datetime]], n: int, s: Settings, kc, pc, f: Funnel,
           split: str, log=print) -> list[Question]:
    """Event-level stratified sampling with lazy price checks.

    Events are visited in a seeded random order (low-priority categories last); within an event,
    markets are tried in descending volume and at most `max_per_event` are accepted. Targets: half
    per venue (the other venue tops up if one runs out), no category above max_category_share.
    """
    ds = s.dataset
    rng = random.Random(ds.seed if split != "canary" else ds.seed + 1)
    by_event: dict[str, list[tuple[Candidate, datetime]]] = defaultdict(list)
    for c, t0 in pool:
        by_event[c.event_id].append((c, t0))
    for v in by_event.values():
        v.sort(key=lambda x: (-x[0].volume, x[0].qid))
    cat_cap = int(ds.max_category_share * n)
    venue_events = {}
    for venue in ("kalshi", "polymarket"):
        evs = sorted(e for e, v in by_event.items() if v[0][0].venue == venue)
        rng.shuffle(evs)
        evs.sort(key=lambda e: by_event[e][0][0].category in LOW_PRIORITY_CATEGORIES)  # stable
        venue_events[venue] = evs

    chosen: list[Question] = []
    cat_n: Counter = Counter()
    venue_n: Counter = Counter()

    def fill(venue: str, target: int) -> None:
        for ev in venue_events[venue]:
            if venue_n[venue] >= target or len(chosen) >= n:
                return
            if ev in done_events:
                continue
            done_events.add(ev)
            taken = 0
            for c, t0 in by_event[ev]:
                if taken >= ds.max_per_event or venue_n[venue] >= target or len(chosen) >= n:
                    break
                if cat_n[c.category] >= cat_cap:
                    f.counts["skip:category_cap"] += 1
                    break
                r = price_at_t0(c, t0, kc, pc)
                f.counts["price_checked"] += 1
                if r is None:
                    f.drop("no_price_within_window"); continue
                p, src = r
                if not (ds.p_mkt_min <= p <= ds.p_mkt_max):
                    f.drop("p_mkt_extreme"); continue
                chosen.append(to_question(c, t0, p, src, split))
                cat_n[c.category] += 1
                venue_n[venue] += 1
                taken += 1
            if len(chosen) % 25 == 0 and taken:
                log(f"[sample:{split}] {len(chosen)}/{n}  {dict(venue_n)}")

    done_events: set[str] = set()
    fill("kalshi", n // 2)
    fill("polymarket", n - venue_n["kalshi"])
    if len(chosen) < n:  # top up from Kalshi if Polymarket ran short
        fill("kalshi", n - venue_n["polymarket"])
    return chosen


# ---------------------------------------------------------------------------------------------
# Build + validate
# ---------------------------------------------------------------------------------------------
def write_jsonl(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(r.model_dump_json() + "\n")


def read_questions(path: Path) -> list[Question]:
    return [Question.model_validate_json(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def build(s: Settings | None = None, log=print, refresh: bool = False) -> dict:
    s = s or settings()
    cache = Cache(s.cache_dir, mode="refresh" if refresh else None)
    http = CachedHttp(cache, per_second=5.0)
    kc, pc = K.KalshiClient(http), P.PolymarketClient(http)
    wins = windows(s)

    kc_all, k_counts = kalshi_candidates(kc, s, log)
    log(f"[kalshi] {len(kc_all)} binary resolved candidates")
    results = {}
    for wname, n in (("main", s.dataset.n_total), ("canary", s.dataset.n_canary)):
        win = wins[wname]
        f = Funnel()
        f.counts.update({f"kalshi:{k}": v for k, v in k_counts.items()})
        p_all, p_counts = poly_candidates(pc, s, win, log)
        f.counts.update({f"poly:{k}": v for k, v in p_counts.items()})
        pool = []
        for c in kc_all + p_all:
            t0 = static_filter(c, win, s, f)
            if t0 is not None:
                pool.append((c, t0))
        f.counts["pool_kalshi"] = sum(c.venue == "kalshi" for c, _ in pool)
        f.counts["pool_polymarket"] = sum(c.venue == "polymarket" for c, _ in pool)
        f.counts["pool_events"] = len({c.event_id for c, _ in pool})
        log(f"[{wname}] pool after static filters: {len(pool)} "
            f"(kalshi={f.counts['pool_kalshi']}, poly={f.counts['pool_polymarket']})")
        qs = sample(pool, n, s, kc, pc, f, "canary" if wname == "canary" else "test", log)
        results[wname] = (qs, f)

    main_qs, main_f = results["main"]
    main_qs.sort(key=lambda q: (q.t0, q.qid))
    for i, q in enumerate(main_qs):
        q.split = "dev" if i < s.dataset.n_dev else "test"
    canary_qs, canary_f = results["canary"]
    canary_qs.sort(key=lambda q: (q.t0, q.qid))

    ddir = s.data_dir / "dataset"
    write_jsonl(ddir / "questions.jsonl", main_qs)
    write_jsonl(ddir / "canary_precutoff.jsonl", canary_qs)
    card = dataset_card(main_qs, canary_qs, main_f, canary_f, kc.cutoff())
    (ddir / "dataset_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n",
                                            encoding="utf-8", newline="\n")
    log(f"[http] network calls this build: {http.network_calls}, cache hits: {cache.hits}")
    return card


def _summ(qs: list[Question]) -> dict:
    return {
        "n": len(qs),
        "by_venue": dict(Counter(q.venue for q in qs)),
        "by_category": dict(sorted(Counter(q.category for q in qs).items())),
        "by_split": dict(Counter(q.split for q in qs)),
        "base_rate_yes": round(sum(q.outcome for q in qs) / len(qs), 4) if qs else None,
        "mean_p_mkt": round(sum(q.p_mkt_t0 for q in qs) / len(qs), 4) if qs else None,
        "p_mkt_source": dict(Counter(q.p_mkt_source for q in qs)),
        "n_events": len({q.event_id for q in qs}),
        "t0_range": [timeutil.iso(min(q.t0 for q in qs)), timeutil.iso(max(q.t0 for q in qs))] if qs else None,
    }


def dataset_card(main_qs, canary_qs, main_f, canary_f, kalshi_cutoff) -> dict:
    dev = [q for q in main_qs if q.split == "dev"]
    test = [q for q in main_qs if q.split == "test"]
    return {
        "built_utc": timeutil.iso(timeutil.now()),
        "kalshi_historical_cutoff": timeutil.iso(kalshi_cutoff),
        "all": _summ(main_qs), "dev": _summ(dev), "test": _summ(test), "canary": _summ(canary_qs),
        "funnel_main": main_f.as_dict(), "funnel_canary": canary_f.as_dict(),
    }


def validate(s: Settings | None = None) -> str:
    s = s or settings()
    ddir = s.data_dir / "dataset"
    qs = read_questions(ddir / "questions.jsonl")
    canary = read_questions(ddir / "canary_precutoff.jsonl")
    ds, w = s.dataset, s.window
    dev = [q for q in qs if q.split == "dev"]
    test = [q for q in qs if q.split == "test"]
    assert len({q.qid for q in qs}) == len(qs), "duplicate qids"
    assert len(dev) == ds.n_dev, f"dev={len(dev)}"
    assert max(q.t0 for q in dev) <= min(q.t0 for q in test), "temporal split violated"
    for q in qs:
        assert q.created_at >= w.created_min, q.qid
        assert q.t0 > q.created_at and q.t0 >= q.created_at + DAY, q.qid
        assert q.scheduled_close <= w.close_max, q.qid
        assert q.resolved_at <= w.resolved_max, q.qid
        assert ds.p_mkt_min <= q.p_mkt_t0 <= ds.p_mkt_max, q.qid
        assert q.outcome in (0, 1)
    for q in canary:
        assert w.canary_resolved_min <= q.resolved_at <= w.canary_resolved_max, q.qid
        assert ds.p_mkt_min <= q.p_mkt_t0 <= ds.p_mkt_max, q.qid
    per_event = Counter(q.event_id for q in qs)
    assert max(per_event.values()) <= ds.max_per_event, per_event.most_common(1)
    venues = Counter(q.venue for q in qs)
    for v in ("kalshi", "polymarket"):
        assert venues[v] / len(qs) >= 0.30, f"venue {v} share {venues[v] / len(qs):.2f} < 0.30"
    cats = Counter(q.category for q in qs)
    top_cat, top_n = cats.most_common(1)[0]
    assert top_n / len(qs) <= ds.max_category_share + 1e-9, f"category {top_cat} share {top_n / len(qs):.2f}"
    assert len(qs) >= 200, f"only {len(qs)} questions"
    return f"OK {len(qs)} questions (dev={len(dev)} test={len(test)}) canary={len(canary)}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    a = ap.parse_args(argv)
    if a.validate:
        print(validate())
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
