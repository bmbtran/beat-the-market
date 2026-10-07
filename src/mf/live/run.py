"""`mf live`: forecast open markets with the full `aia` pipeline and append to the hash-chained ledger.

Also records `halawi` and the market price fetched in the same minute as the forecast. Retrieval
uses endPublishedDate = now (no future exists to leak), with the same leakage filters as the backtest.
"""

from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

from mf.core import timeutil
from mf.core.cache import Cache
from mf.core.http import CachedHttp
from mf.data import kalshi as K
from mf.data import polymarket as P
from mf.forecast.aggregate import aggregate, spread
from mf.forecast.calibrate import platt
from mf.forecast.reason import reasoning_requests, to_sample
from mf.forecast.supervisor import run_supervisor
from mf.live import ledger as L
from mf.live.select import choose, kalshi_live_price, kalshi_open, poly_live_price, poly_open
from mf.llm.prompts import load_prompt
from mf.retrieval.pipeline import retrieve_question
from mf.schemas import Question


def git_sha(root: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def market_weight(s) -> float | None:
    """Blend weight for p_aia_market_ens: the dev-fit weight from the backtest (reports/metrics.json)."""
    p = s.reports_dir / "metrics.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))["fits"]["market_ens_aia_dev_weight"]


def prompt_versions(s) -> dict:
    ids = s.pipeline.reasoning_prompts + [s.pipeline.query_prompt, s.pipeline.relevance_prompt,
                                          s.pipeline.supervisor_disagreement_prompt, s.pipeline.supervisor_update_prompt]
    return {pid: load_prompt(pid).sha[:12] for pid in ids}


def refresh_price(q: Question, kc, pc) -> tuple[float, str] | None:
    if q.venue == "kalshi":
        m = kc.market(q.qid.split(":", 1)[1], use_cache=False)
        return kalshi_live_price(m) if m else None
    d = pc.http.get_json(f"{P.GAMMA}/markets/{q.qid.split(':', 1)[1]}", use_cache=False)
    return poly_live_price(d) if isinstance(d, dict) else None


def forecast_one(q: Question, ctx, w: float | None, kc=None, pc=None, log=print) -> dict:
    s, llm = ctx.s, ctx.llm
    today = timeutil.now().strftime("%Y-%m-%d")
    r = retrieve_question(q, llm, ctx.exa, s, live=True)
    reqs = reasoning_requests(q, s, r.kept, today_override=today)
    ss = [to_sample(q, "retrieval", rq, llm.complete(rq)) for rq in reqs]
    p_halawi = aggregate(ss, s.pipeline.min_valid_samples, s.pipeline.trim)
    sup = run_supervisor(q, ss, p_halawi, spread(ss), llm, ctx.exa, s, live=True)
    p_aia = float(platt(sup.final_p, s.pipeline.platt_coef)) if sup.final_p is not None else None
    price = refresh_price(q, kc, pc) if kc is not None else None  # same minute as the forecast
    p_mkt = price[0] if price else q.p_mkt_t0
    p_ens = (w * p_aia + (1 - w) * p_mkt) if (w is not None and p_aia is not None) else None
    return dict(created_utc=timeutil.now(), qid=q.qid, venue=q.venue, title=q.title, close_time=q.scheduled_close,
                p_mkt_at_forecast=round(p_mkt, 4), p_halawi=None if p_halawi is None else round(p_halawi, 4),
                p_aia=None if p_aia is None else round(p_aia, 4), p_aia_market_ens=None if p_ens is None else round(p_ens, 4),
                model=s.models.reasoner, prompt_versions=prompt_versions(s), code_git_sha=git_sha(s.root))


def run_live(n: int, ctx, ledger_path: Path, log=print) -> list[dict]:
    s = ctx.s
    now = timeutil.now()
    http = CachedHttp(Cache(s.cache_dir, mode="readwrite"), per_second=5.0)
    kc, pc = K.KalshiClient(http), P.PolymarketClient(http)
    rng = random.Random(now.strftime("%Y%m%d"))
    recs = L.read_records(ledger_path)
    done = {r["qid"] for r in recs}
    cands = poly_open(pc, s, now, log) + kalshi_open(kc, s, now, want=3 * n, rng=rng, log=log)
    picks = choose(cands, n, done, set())
    log(f"[live] forecasting {len(picks)} markets: {[q.qid for q in picks]}")
    w = market_weight(s)
    out = []
    for q in picks:
        fields = forecast_one(q, ctx, w, kc, pc, log)
        rec = L.append(ledger_path, fields)
        log(f"[live] seq={rec.seq} {q.qid} p_mkt={rec.p_mkt_at_forecast} halawi={rec.p_halawi} "
            f"aia={rec.p_aia} aia+mkt={rec.p_aia_market_ens} hash={rec.hash[:8]}")
        out.append(json.loads(rec.model_dump_json()))
    return out
