"""Content-addressed JSON cache (PLAN.md §10).

cache/<provider>/<key[:2]>/<key>.json; key = sha256(canonical_json(key-material)).
Modes (env MF_CACHE_MODE): readwrite (default) | readonly (miss -> CacheMiss, guarantees $0) | refresh.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from mf.core import timeutil
from mf.core.hashing import canonical_json, hash_obj

SCHEMA_VERSION = 1
MODES = ("readwrite", "readonly", "refresh")


class CacheMiss(Exception):
    """Raised on a cache miss in readonly mode (a paid/network call would have been needed)."""


def make_key(provider: str, endpoint: str, model: str | None = None, params: Any = None,
             prompt_sha: str | None = None, sample_idx: int | None = None,
             schema_version: int = SCHEMA_VERSION) -> str:
    return hash_obj({
        "provider": provider, "endpoint": endpoint, "model": model, "params": params,
        "prompt_sha": prompt_sha, "sample_idx": sample_idx, "schema_version": schema_version,
    })


def current_mode() -> str:
    mode = os.environ.get("MF_CACHE_MODE", "readwrite").strip().lower()
    if mode not in MODES:
        raise ValueError(f"MF_CACHE_MODE must be one of {MODES}, got {mode!r}")
    return mode


class Cache:
    def __init__(self, root: str | Path, mode: str | None = None):
        self.root = Path(root)
        self.mode = mode or current_mode()
        if self.mode not in MODES:
            raise ValueError(f"bad cache mode {self.mode!r}")
        self.hits = 0
        self.misses = 0

    def path(self, provider: str, key: str) -> Path:
        return self.root / provider / key[:2] / f"{key}.json"

    def exists(self, provider: str, key: str) -> bool:
        return self.path(provider, key).exists()

    def get(self, provider: str, key: str) -> dict | None:
        """Return the stored entry, None on a miss (readwrite/refresh), or raise CacheMiss (readonly)."""
        p = self.path(provider, key)
        if self.mode != "refresh" and p.exists():
            self.hits += 1
            return json.loads(p.read_text(encoding="utf-8"))
        self.misses += 1
        if self.mode == "readonly":
            raise CacheMiss(f"{provider}/{key[:16]}… not cached (MF_CACHE_MODE=readonly)")
        return None

    def put(self, provider: str, key: str, request: Any, response: Any, cost_usd: float = 0.0,
            sdk_version: str | None = None) -> dict:
        if self.mode == "readonly":
            raise CacheMiss("refusing to write in readonly mode")
        entry = {
            "request": request, "response": response, "cost_usd": cost_usd,
            "created_utc": timeutil.iso(timeutil.now()), "sdk_version": sdk_version,
        }
        p = self.path(provider, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(canonical_json(entry), encoding="utf-8")
        os.replace(tmp, p)
        return json.loads(canonical_json(entry))


def cached_call(
    cache: Cache,
    budget,  # BudgetGuard | None
    provider: str,
    key: str,
    request: Any,
    est_usd: float,
    call_fn: Callable[[], tuple[Any, float, int | None, int | None]],
    op: str,
    model: str | None = None,
    sdk_version: str | None = None,
) -> tuple[dict, bool]:
    """Return (entry, cache_hit). On a miss: reserve budget, call, store, settle actual cost.

    call_fn returns (response_jsonable, actual_usd, input_tokens, output_tokens).
    """
    hit = cache.get(provider, key)
    if hit is not None:
        return hit, True
    if budget is None and est_usd > 0:
        raise RuntimeError("paid call attempted without a BudgetGuard")
    res = budget.charge(provider, est_usd, op) if budget is not None else None
    try:
        response, actual, in_tok, out_tok = call_fn()
    except BaseException:
        if res is not None:
            budget.release(res)
        raise
    entry = cache.put(provider, key, request, response, actual, sdk_version)
    if res is not None:
        budget.settle(res, actual_usd=actual, model=model, cache_key=key,
                      input_tokens=in_tok, output_tokens=out_tok)
    return entry, False
