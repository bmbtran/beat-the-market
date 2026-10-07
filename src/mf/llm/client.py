"""LLM access behind one protocol so tests never touch the network.

anthropic==1.11.0 notes (PLAN.md §3, verified against the claude-api skill):
  * temperature/top_p/top_k were removed in 1.x (and Sonnet 5 400s on them) -> never sent.
  * SDK 1.x is built on httpx2, so respx cannot intercept it -> tests use FakeLLM at this interface.
  * Sonnet 5: thinking {"type": "disabled"} accepted; effort goes in output_config.
  * Haiku 4.5: no effort parameter.
  * stop_reason "refusal" / "max_tokens" -> the sample counts as failed (handled by callers).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

from mf.core.cache import Cache, cached_call, make_key
from mf.core.pricing import anthropic_cost, anthropic_estimate

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LLMRequest:
    model: str
    user: str
    max_tokens: int
    op: str  # ledger op, e.g. "reason", "query_gen"
    system: str | None = None
    effort: str | None = None
    thinking: str | None = None  # "disabled" | None
    prompt_id: str = ""
    prompt_sha: str = ""
    sample_idx: int = 0

    def api_params(self) -> dict:
        p: dict = {"model": self.model, "max_tokens": self.max_tokens,
                   "messages": [{"role": "user", "content": self.user}]}
        if self.system:
            p["system"] = self.system
        if self.thinking == "disabled":
            p["thinking"] = {"type": "disabled"}
        if self.effort:
            p["output_config"] = {"effort": self.effort}
        return p

    def cache_key(self) -> str:
        return make_key("anthropic", "messages", self.model, self.api_params(), self.prompt_sha,
                        self.sample_idx, SCHEMA_VERSION)

    def prompt_chars(self) -> int:
        return len(self.user) + len(self.system or "")


@dataclass
class LLMResult:
    text: str
    stop_reason: str
    input_tokens: int
    output_tokens: int
    model: str
    cost_usd: float
    cache_key: str
    cache_hit: bool = False
    raw: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.stop_reason in ("end_turn", "stop_sequence")


def response_to_dict(msg) -> dict:
    """Normalize an SDK Message (or a dict) to the JSON we cache."""
    d = msg if isinstance(msg, dict) else msg.to_dict()
    return {
        "id": d.get("id"),
        "model": d.get("model"),
        "stop_reason": d.get("stop_reason"),
        "content": [{"type": b.get("type"), "text": b.get("text", "")} for b in d.get("content", [])],
        "usage": {k: (d.get("usage") or {}).get(k) or 0 for k in
                  ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")},
    }


def result_from_cached(entry: dict, key: str, hit: bool, batch: bool = False) -> LLMResult:
    r = entry["response"]
    u = r["usage"]
    text = "".join(b["text"] for b in r["content"] if b["type"] == "text")
    return LLMResult(text=text, stop_reason=r["stop_reason"] or "", input_tokens=u["input_tokens"],
                     output_tokens=u["output_tokens"], model=r.get("model") or "",
                     cost_usd=entry.get("cost_usd", 0.0), cache_key=key, cache_hit=hit, raw=r)


def usage_cost(model: str, resp: dict, batch: bool) -> float:
    u = resp["usage"]
    return anthropic_cost(model, u["input_tokens"], u["output_tokens"], u["cache_read_input_tokens"],
                          u["cache_creation_input_tokens"], batch=batch)


class LLMClient(Protocol):
    """Raw (uncached) access. Implemented by AnthropicClient and FakeLLM."""

    sdk_version: str

    def create(self, params: dict) -> dict: ...
    def batch_create(self, requests: list[tuple[str, dict]]) -> str: ...
    def batch_status(self, batch_id: str) -> str: ...
    def batch_results(self, batch_id: str) -> Iterable[tuple[str, str, dict | None]]: ...


class AnthropicClient:
    def __init__(self, api_key: str | None = None, max_retries: int = 4):
        import anthropic

        from mf.config import require_key

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key or require_key("ANTHROPIC_API_KEY"),
                                          max_retries=max_retries, timeout=300.0)
        self.sdk_version = anthropic.__version__

    def create(self, params: dict) -> dict:
        return response_to_dict(self.client.messages.create(**params))

    def batch_create(self, requests: list[tuple[str, dict]]) -> str:
        b = self.client.messages.batches.create(
            requests=[{"custom_id": cid, "params": params} for cid, params in requests])
        return b.id

    def batch_status(self, batch_id: str) -> str:
        return self.client.messages.batches.retrieve(batch_id).processing_status

    def batch_results(self, batch_id: str):
        """Yield (custom_id, result_type, response_dict|None). Results arrive in any order."""
        for r in self.client.messages.batches.results(batch_id):
            if r.result.type == "succeeded":
                yield r.custom_id, "succeeded", response_to_dict(r.result.message)
            else:
                yield r.custom_id, r.result.type, None


class FakeLLM:
    """Deterministic offline stand-in. `responder(params) -> text` decides the reply."""

    sdk_version = "fake"

    def __init__(self, responder: Callable[[dict], str] | None = None, stop_reason: str = "end_turn"):
        self.responder = responder or (lambda params: "FINAL PROBABILITY: 0.42")
        self.stop_reason = stop_reason
        self.calls: list[dict] = []
        self.batches: dict[str, dict] = {}
        self._n = 0

    def _reply(self, params: dict) -> dict:
        text = self.responder(params)
        n_in = sum(len(m["content"]) for m in params["messages"]) // 4 + len(params.get("system") or "") // 4
        return {"id": f"msg_fake_{len(self.calls)}", "model": params["model"], "stop_reason": self.stop_reason,
                "content": [{"type": "text", "text": text}],
                "usage": {"input_tokens": n_in, "output_tokens": len(text) // 4 + 1,
                          "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}

    def create(self, params: dict) -> dict:
        self.calls.append(params)
        return self._reply(params)

    def batch_create(self, requests):
        self._n += 1
        bid = f"msgbatch_fake_{self._n}"
        self.batches[bid] = {"requests": list(requests), "polls": 0}
        return bid

    def batch_status(self, batch_id):
        b = self.batches[batch_id]
        b["polls"] += 1
        return "ended" if b["polls"] >= 2 else "in_progress"

    def batch_results(self, batch_id):
        for cid, params in reversed(self.batches[batch_id]["requests"]):  # any order
            self.calls.append(params)
            yield cid, "succeeded", self._reply(params)


class CachedLLM:
    """Cache + budget wrapper around an LLMClient. Every paid call goes through here."""

    def __init__(self, client: LLMClient | None, cache: Cache, budget=None, client_factory=None):
        self._client = client
        self._factory = client_factory
        self.cache = cache
        self.budget = budget
        self.n_calls = 0
        self.n_hits = 0
        self.network_calls = 0
        self.cost_log: list[tuple[str, float, bool]] = []  # (op, cost_usd, cache_hit)

    @property
    def client(self) -> LLMClient:
        if self._client is None:
            if self._factory is None:
                raise RuntimeError("no LLM client configured (cache miss needs a live or fake client)")
            self._client = self._factory()
        return self._client

    def estimate(self, req: LLMRequest, batch: bool = False) -> float:
        return anthropic_estimate(req.model, req.prompt_chars(), req.max_tokens, batch=batch)

    def is_cached(self, req: LLMRequest) -> bool:
        return self.cache.exists("anthropic", req.cache_key())

    def complete(self, req: LLMRequest) -> LLMResult:
        key = req.cache_key()
        params = req.api_params()

        def call():
            t = time.monotonic()
            self.network_calls += 1
            resp = self.client.create(params)
            resp["latency_s"] = round(time.monotonic() - t, 2)
            cost = usage_cost(req.model, resp, batch=False)
            return resp, cost, resp["usage"]["input_tokens"], resp["usage"]["output_tokens"]

        entry, hit = cached_call(self.cache, self.budget, "anthropic", key, params, self.estimate(req), call,
                                 op=req.op, model=req.model,
                                 sdk_version=getattr(self._client, "sdk_version", None))
        self.n_calls += 1
        self.n_hits += hit
        self.cost_log.append((req.op, float(entry.get("cost_usd") or 0.0), hit))
        return result_from_cached(entry, key, hit)
