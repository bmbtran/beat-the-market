"""Polymarket Gamma (metadata) + CLOB (price history). No auth for reads.

Verified 2026-10-06: gamma /events returns a JSON list with nested `markets` and `tags`;
market `outcomes`, `outcomePrices`, `clobTokenIds` are JSON-encoded strings; page size max 100.
`endDate` keeps the scheduled end after an early close (closedTime moves instead).
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from mf.core import timeutil
from mf.core.http import CachedHttp
from mf.data.common import Candidate, to_float

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

EXCLUDE_TAGS = {
    "sports", "soccer", "football", "nfl", "nba", "mlb", "nhl", "tennis", "golf", "ufc", "mma", "boxing",
    "f1", "formula-1", "cricket", "esports", "basketball", "baseball", "hockey", "olympics", "chess",
    "crypto", "bitcoin", "ethereum", "solana", "crypto-prices", "xrp", "dogecoin", "memecoins", "airdrops",
    "up-or-down", "hide-from-new-crypto",
}
# Ordered: first matching rule wins.
TAG_CATEGORY_RULES: list[tuple[set[str], str]] = [
    ({"elections", "global-elections", "us-elections", "main-election", "primaries", "midterms",
      "us-presidential-election", "mayoral-elections"}, "Elections"),
    ({"fed", "fed-rates", "fomc", "economy", "economic-policy", "inflation", "cpi", "gdp", "jobs",
      "unemployment", "recession", "tariffs", "trade-war", "interest-rates"}, "Economics"),
    ({"stocks", "finance", "commodities", "ipos", "ipo", "earnings", "indices", "s-p-500", "gold",
      "oil"}, "Financials"),
    ({"ai", "openai", "tech", "technology", "science", "space", "spacex", "nasa"}, "Science and Technology"),
    ({"business", "companies", "elon-musk", "tesla", "apple", "big-tech"}, "Companies"),
    ({"climate", "weather", "hurricanes", "natural-disasters", "earthquakes", "climate-science"},
     "Climate and Weather"),
    ({"health", "pandemics", "covid", "measles", "bird-flu", "fda"}, "Health"),
    ({"geopolitics", "world", "middle-east", "ukraine", "russia", "china", "israel", "iran",
      "foreign-policy", "world-affairs"}, "World"),
    ({"politics", "us-politics", "trump", "congress", "supreme-court", "courts", "scotus"}, "Politics"),
    ({"pop-culture", "entertainment", "movies", "music", "awards", "oscars", "grammys", "tv",
      "box-office", "celebrities", "culture"}, "Entertainment"),
]
_UPDATE_RE = re.compile(r"\b(update|clarification)\b", re.IGNORECASE)


def tag_slugs(event: dict) -> set[str]:
    return {str(t.get("slug", "")).lower() for t in (event.get("tags") or []) if t.get("slug")}


def classify(event: dict) -> str | None:
    """Unified category, or None if excluded (sports/crypto) or unknown."""
    slugs = tag_slugs(event)
    if slugs & EXCLUDE_TAGS:
        return None
    for tags, cat in TAG_CATEGORY_RULES:
        if slugs & tags:
            return cat
    return None


def sanitize_description(text: str) -> str:
    """Drop paragraphs that look like post-hoc updates/clarifications (they can leak the outcome)."""
    paras = re.split(r"\n\s*\n", text or "")
    kept = [p.strip() for p in paras if p.strip() and not _UPDATE_RE.search(p)]
    return "\n\n".join(kept)


def _jlist(x) -> list:
    if isinstance(x, list):
        return x
    try:
        v = json.loads(x or "[]")
        return v if isinstance(v, list) else []
    except (TypeError, ValueError):
        return []


def parse_resolution(m: dict) -> int | None:
    """1/0 for a cleanly resolved Yes/No market; None otherwise (non-Yes/No, 50/50, unresolved)."""
    if [str(o) for o in _jlist(m.get("outcomes"))] != ["Yes", "No"]:
        return None
    prices = [str(p) for p in _jlist(m.get("outcomePrices"))]
    if prices == ["1", "0"]:
        return 1
    if prices == ["0", "1"]:
        return 0
    return None


class PolymarketClient:
    def __init__(self, http: CachedHttp):
        self.http = http

    def events_page(self, closed: bool, end_min: datetime | None, end_max: datetime | None,
                    offset: int, limit: int = 100, use_cache: bool = True) -> list[dict]:
        params = {
            "closed": "true" if closed else "false", "order": "volume", "ascending": "false",
            "limit": limit, "offset": offset,
            "end_date_min": timeutil.iso(end_min) if end_min else None,
            "end_date_max": timeutil.iso(end_max) if end_max else None,
        }
        if not closed:
            params["active"] = "true"
        d = self.http.get_json(f"{GAMMA}/events", params, use_cache=use_cache)
        return d if isinstance(d, list) else []

    def events_by_volume(self, closed: bool, end_min, end_max, min_volume: float,
                         max_pages: int = 300, use_cache: bool = True) -> list[dict]:
        out = []
        for page in range(max_pages):
            evs = self.events_page(closed, end_min, end_max, offset=page * 100, use_cache=use_cache)
            if not evs:
                break
            out.extend(evs)
            if (to_float(evs[-1].get("volume")) or 0.0) < min_volume:
                break
        return out

    def price_history(self, token_id: str, start: datetime, end: datetime,
                      use_cache: bool = True) -> list[tuple[int, float]]:
        d = self.http.get_json(f"{CLOB}/prices-history", {
            "market": token_id, "startTs": timeutil.to_unix(start), "endTs": timeutil.to_unix(end),
            "fidelity": 60}, use_cache=use_cache)
        return [(int(h["t"]), float(h["p"])) for h in (d.get("history") or [])]


def market_to_candidate(m: dict, event: dict, category: str) -> Candidate | None:
    outcome = parse_resolution(m)
    if outcome is None or str(m.get("umaResolutionStatus", "")).lower() != "resolved":
        return None
    tokens = _jlist(m.get("clobTokenIds"))
    if len(tokens) != 2:
        return None
    created = max(t for t in (timeutil.parse(m.get("createdAt")), timeutil.parse(m.get("startDate"))) if t)
    end = timeutil.parse(m.get("endDate"))
    closed = timeutil.parse(m.get("closedTime")) or end
    if end is None or closed is None:
        return None
    return Candidate(
        qid=f"poly:{m['id']}",
        venue="polymarket",
        event_id=f"poly:{event['id']}",
        title=(m.get("question") or "").strip(),
        description=sanitize_description(m.get("description") or ""),
        category=category,
        created_at=created,
        scheduled_close=end,
        actual_close=closed,
        resolved_at=closed,
        volume=to_float(m.get("volumeNum", m.get("volume"))) or 0.0,
        outcome=outcome,
        source_url=f"https://polymarket.com/event/{event.get('slug', '')}",
        can_close_early=False,
        expected_expiration=end,
        price_ref={"token_id": str(tokens[0])},  # index 0 = "Yes"
    )


def open_market_ok(m: dict) -> bool:
    return [str(o) for o in _jlist(m.get("outcomes"))] == ["Yes", "No"] and len(_jlist(m.get("clobTokenIds"))) == 2
