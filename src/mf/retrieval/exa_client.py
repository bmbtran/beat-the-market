"""Exa search over REST (POST https://api.exa.ai/search, header x-api-key).

exa-py 2.25.0 exposes the same options (end_published_date, exclude_domains, contents=...),
verified by inspecting its signature; REST is used so the exact request body is visible, cost is
read from `costDollars.total`, and tests can mock with respx.
"""

from __future__ import annotations

from datetime import datetime

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from mf.core import timeutil
from mf.core.cache import Cache, cached_call, make_key
from mf.core.pricing import exa_search_estimate

EXA_URL = "https://api.exa.ai/search"


def _retryable(e: BaseException) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code == 429 or e.response.status_code >= 500
    return isinstance(e, (httpx.TransportError, httpx.TimeoutException))


class ExaClient:
    def __init__(self, cache: Cache, budget=None, api_key: str | None = None,
                 http: httpx.Client | None = None):
        self.cache = cache
        self.budget = budget
        self._api_key = api_key
        self._http = http
        self.n_calls = 0
        self.n_hits = 0

    def _client(self) -> httpx.Client:
        if self._http is None:
            from mf.config import require_key

            key = self._api_key or require_key("EXA_API_KEY")
            self._http = httpx.Client(timeout=60, headers={"x-api-key": key, "content-type": "application/json"})
        return self._http

    @staticmethod
    def build_body(query: str, end_published: datetime | None, num_results: int, search_type: str,
                   exclude_domains: list[str], highlight_chars: int, max_age_hours: int | None) -> dict:
        body: dict = {
            "query": query,
            "type": search_type,
            "numResults": num_results,
            "excludeDomains": sorted(exclude_domains),
            "contents": {"highlights": {"maxCharacters": highlight_chars}},
        }
        if end_published is not None:
            body["endPublishedDate"] = timeutil.iso(end_published).replace("Z", ".000Z")
        if max_age_hours is not None:
            body["contents"]["maxAgeHours"] = max_age_hours
        return body

    @retry(retry=retry_if_exception(_retryable), wait=wait_exponential_jitter(initial=1, max=30),
           stop=stop_after_attempt(5), reraise=True)
    def _post(self, body: dict) -> dict:
        r = self._client().post(EXA_URL, json=body)
        r.raise_for_status()
        return r.json()

    def search(self, query: str, end_published: datetime | None, num_results: int = 5,
               search_type: str = "instant", exclude_domains: list[str] | None = None,
               highlight_chars: int = 1500, max_age_hours: int | None = -1) -> tuple[dict, bool]:
        """Returns (response_json, cache_hit)."""
        body = self.build_body(query, end_published, num_results, search_type, exclude_domains or [],
                               highlight_chars, max_age_hours)
        key = make_key("exa", "search", params=body)
        est = exa_search_estimate(search_type, num_results)

        def call():
            resp = self._post(body)
            actual = float(((resp.get("costDollars") or {}).get("total")) or est)
            return resp, actual, None, None

        entry, hit = cached_call(self.cache, self.budget, "exa", key, body, est, call, op=f"search_{search_type}")
        self.n_calls += 1
        self.n_hits += hit
        return entry["response"], hit

    def is_cached(self, body: dict) -> bool:
        return self.cache.exists("exa", make_key("exa", "search", params=body))
