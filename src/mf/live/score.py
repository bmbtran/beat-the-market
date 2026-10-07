"""`mf score-live`: resolve closed live markets and append scores to data/live/scores.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

from mf.core import timeutil
from mf.core.cache import Cache
from mf.core.hashing import canonical_json
from mf.core.http import CachedHttp
from mf.data import kalshi as K
from mf.data import polymarket as P
from mf.live import ledger as L


def resolve(rec: dict, kc: K.KalshiClient, pc: P.PolymarketClient) -> int | None:
    venue, mid = rec["venue"], rec["qid"].split(":", 1)[1]
    if venue == "kalshi":
        m = kc.market(mid, use_cache=False)
        if m and m.get("status") in ("finalized", "settled", "determined") and m.get("result") in ("yes", "no"):
            return 1 if m["result"] == "yes" else 0
        return None
    m = pc.http.get_json(f"{P.GAMMA}/markets/{mid}", use_cache=False)
    if isinstance(m, dict) and m.get("closed") and str(m.get("umaResolutionStatus", "")).lower() == "resolved":
        return P.parse_resolution(m)
    return None


def score_live(ledger_path: Path, scores_path: Path, s, log=print) -> list[dict]:
    recs = L.read_records(ledger_path)
    scored = {json.loads(l)["seq"] for l in (scores_path.read_text(encoding="utf-8").splitlines()
                                              if scores_path.exists() else []) if l.strip()}
    http = CachedHttp(Cache(s.cache_dir, mode="readwrite"), per_second=5.0)
    kc, pc = K.KalshiClient(http), P.PolymarketClient(http)
    now = timeutil.now()
    new = []
    for r in recs:
        if r["seq"] in scored or timeutil.parse(r["close_time"]) > now:
            continue
        y = resolve(r, kc, pc)
        if y is None:
            continue
        row = {"seq": r["seq"], "qid": r["qid"], "outcome": y, "scored_utc": timeutil.iso(now)}
        for k in ("p_mkt_at_forecast", "p_halawi", "p_aia", "p_aia_market_ens"):
            row[f"brier_{k[2:]}"] = None if r[k] is None else round((r[k] - y) ** 2, 6)
        new.append(row)
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    with open(scores_path, "a", encoding="utf-8", newline="\n") as f:
        for row in new:
            f.write(canonical_json(row) + "\n")
    log(f"[score-live] {len(new)} newly resolved; {len(scored) + len(new)} scored of {len(recs)} forecasts")
    return new
