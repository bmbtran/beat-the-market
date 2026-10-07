"""httpx client for the free public APIs: rate limit, retries (tenacity), on-disk cache (cache/http/)."""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from mf.core.cache import Cache, make_key

USER_AGENT = "market-forecaster/0.1 (research; read-only)"


class HttpStatusError(Exception):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"HTTP {status} for {url}: {body[:200]}")
        self.status = status


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, HttpStatusError):
        return exc.status == 429 or exc.status >= 500
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


class RateLimiter:
    def __init__(self, per_second: float):
        self.min_interval = 1.0 / per_second
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            sleep = self._last + self.min_interval - now
            if sleep > 0:
                time.sleep(sleep)
            self._last = time.monotonic()


class CachedHttp:
    """GET JSON with caching. 404 responses are cached too (as {"__status__": 404})."""

    def __init__(self, cache: Cache, per_second: float = 5.0, timeout: float = 60.0,
                 client: httpx.Client | None = None):
        self.cache = cache
        self.limiter = RateLimiter(per_second)
        self.client = client or httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT},
                                             follow_redirects=True)
        self.network_calls = 0

    @retry(retry=retry_if_exception(_retryable), wait=wait_exponential_jitter(initial=1, max=60),
           stop=stop_after_attempt(8), reraise=True)
    def _fetch(self, url: str, params: dict | None) -> Any:
        self.limiter.wait()
        self.network_calls += 1
        r = self.client.get(url, params=params)
        if r.status_code == 404:
            return {"__status__": 404}
        if r.status_code != 200:
            raise HttpStatusError(r.status_code, str(r.url), r.text)
        return r.json()

    def get_json(self, url: str, params: dict | None = None, use_cache: bool = True) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        key = make_key("http", url, params=params)
        if use_cache:
            hit = self.cache.get("http", key)
            if hit is not None:
                return hit["response"]
        data = self._fetch(url, params)
        if use_cache:
            self.cache.put("http", key, {"url": url, "params": params}, data)
        return data
