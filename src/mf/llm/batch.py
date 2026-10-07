"""Message Batches: submit only cache misses, poll, write results to the cache by key; resumable.

custom_id = cache key (64 hex chars, within the API's 64-char limit). Batch state lives in
state/batches/<batch_id>.json so a crashed poll can be resumed with `mf batch resume`.
The worst-case cost of the whole batch is reserved before batches.create.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from mf.core import timeutil
from mf.llm.client import CachedLLM, LLMRequest, LLMResult, result_from_cached, usage_cost

POLL_SECONDS = 30


def _state_path(state_dir: Path, batch_id: str) -> Path:
    return state_dir / "batches" / f"{batch_id}.json"


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    tmp.replace(path)


def submit(llm: CachedLLM, reqs: list[LLMRequest], state_dir: Path) -> str | None:
    """Submit the uncached subset. Returns batch id, or None if everything is cached."""
    todo: dict[str, LLMRequest] = {}
    for r in reqs:
        k = r.cache_key()
        if k not in todo and not llm.cache.exists("anthropic", k):
            todo[k] = r
    if not todo:
        return None
    if llm.cache.mode == "readonly":
        from mf.core.cache import CacheMiss
        raise CacheMiss(f"{len(todo)} batch requests not cached (readonly)")
    est = sum(llm.estimate(r, batch=True) for r in todo.values())
    res = llm.budget.charge("anthropic", est, "batch") if llm.budget else None
    try:
        batch_id = llm.client.batch_create([(k[:64], r.api_params()) for k, r in todo.items()])
    except BaseException:
        if res is not None:
            llm.budget.release(res)
        raise
    if res is not None:
        llm.budget.release(res)  # replaced by a durable reservation recorded in the state file
    _write_state(_state_path(state_dir, batch_id), {
        "batch_id": batch_id, "created_utc": timeutil.iso(timeutil.now()), "status": "submitted",
        "est_usd": est, "run_id": getattr(llm.budget, "run_id", None),
        "requests": {k[:64]: {"key": k, "model": r.model, "op": r.op, "params": r.api_params(),
                              "est": llm.estimate(r, batch=True)}
                     for k, r in todo.items()},
    })
    return batch_id


def pending_batch_reservations(state_dir: Path) -> float:
    """Estimated $ of submitted-but-uncollected batches (counted by the budget guard)."""
    total = 0.0
    for p in (state_dir / "batches").glob("*.json"):
        st = json.loads(p.read_text(encoding="utf-8"))
        if st.get("status") != "collected":
            total += st.get("est_usd", 0.0)
    return total


def collect(llm: CachedLLM, batch_id: str, state_dir: Path, poll_seconds: float = POLL_SECONDS,
            log=print, max_wait_s: float = 26 * 3600) -> dict:
    """Poll until ended, write succeeded results into the cache, record actual spend."""
    path = _state_path(state_dir, batch_id)
    state = json.loads(path.read_text(encoding="utf-8"))
    if state["status"] == "collected":
        return state.get("summary", {})
    t_start = time.monotonic()
    while True:
        status = llm.client.batch_status(batch_id)
        if status == "ended":
            break
        if time.monotonic() - t_start > max_wait_s:
            raise TimeoutError(f"batch {batch_id} not ended after {max_wait_s}s; resume later")
        log(f"[batch] {batch_id} status={status}; sleeping {poll_seconds}s")
        time.sleep(poll_seconds)
    counts = {"succeeded": 0, "errored": 0, "canceled": 0, "expired": 0, "unknown_id": 0}
    spent = 0.0
    for cid, rtype, resp in llm.client.batch_results(batch_id):
        meta = state["requests"].get(cid)
        if meta is None:
            counts["unknown_id"] += 1
            continue
        counts[rtype] = counts.get(rtype, 0) + 1
        if rtype != "succeeded" or resp is None:
            continue
        key = meta["key"]
        cost = usage_cost(meta["model"], resp, batch=True)
        if not llm.cache.exists("anthropic", key):
            llm.cache.put("anthropic", key, meta["params"], resp, cost, getattr(llm.client, "sdk_version", None))
            if llm.budget is not None:
                llm.budget.record("anthropic", meta["op"] + "_batch", meta["model"], key, cost,
                                  resp["usage"]["input_tokens"], resp["usage"]["output_tokens"],
                                  est_usd=meta.get("est", 0.0))
            spent += cost
    state["status"] = "collected"
    state["summary"] = {"counts": counts, "actual_usd": round(spent, 6)}
    _write_state(path, state)
    log(f"[batch] {batch_id} collected: {counts} actual=${spent:.4f}")
    return state["summary"]


def run_batch(llm: CachedLLM, reqs: list[LLMRequest], state_dir: Path, log=print,
              poll_seconds: float = POLL_SECONDS) -> dict[str, LLMResult | None]:
    """Submit misses, wait, and return {cache_key: LLMResult|None (failed)} for every request."""
    bid = submit(llm, reqs, state_dir)
    if bid:
        log(f"[batch] submitted {bid}")
        collect(llm, bid, state_dir, poll_seconds=poll_seconds, log=log)
    out: dict[str, LLMResult | None] = {}
    for r in reqs:
        k = r.cache_key()
        if llm.cache.exists("anthropic", k):
            out[k] = result_from_cached(llm.cache.get("anthropic", k), k, hit=True, batch=True)
        else:
            out[k] = None
    return out


def resume_all(llm: CachedLLM, state_dir: Path, log=print, poll_seconds: float = POLL_SECONDS) -> list[str]:
    done = []
    for p in sorted((state_dir / "batches").glob("*.json")):
        st = json.loads(p.read_text(encoding="utf-8"))
        if st.get("status") != "collected":
            collect(llm, st["batch_id"], state_dir, poll_seconds=poll_seconds, log=log)
            done.append(st["batch_id"])
    return done
