"""`mf smoke --allow-spend`: 1 Haiku call, 1 Sonnet 5 call, 1 one-request Batch, 2 Exa searches.

Asserts every Exa result has publishedDate <= endPublishedDate (or null). Saves the real responses
as fixtures (Exa highlights truncated to 1,500 chars; no headers/keys). A second run is all cache hits.
"""

from __future__ import annotations

import json
from datetime import datetime

from mf.core import timeutil
from mf.llm import batch as B
from mf.llm.client import LLMRequest
from mf.llm.parse import parse_json, parse_probability
from mf.llm.prompts import load_prompt
from mf.runtime import make_ctx

SMOKE_END = timeutil.parse("2026-03-01T00:00:00Z")
SMOKE_QUERIES = ["Federal Reserve interest rate decision outlook", "US government shutdown negotiations Congress"]


def _req(prompt_id: str, model: str, max_tokens: int, op: str, sample_idx: int = 0, **ctx) -> LLMRequest:
    p = load_prompt(prompt_id)
    system, user = p.render(**ctx)
    return LLMRequest(model=model, user=user, system=system, max_tokens=max_tokens, op=op,
                      prompt_id=prompt_id, prompt_sha=p.sha, sample_idx=sample_idx)


def run(allow_spend: bool, exa_type: str | None = None, log=print) -> int:
    ctx = make_ctx(run_id="smoke", max_usd=0.50, allow_spend=allow_spend)
    s = ctx.s
    exa_type = exa_type or s.pipeline.exa_type
    spent0 = ctx.budget.spent()
    fx = s.root / "tests" / "fixtures"
    ok = True

    # 1. Haiku (sync)
    r = ctx.llm.complete(_req("smoke_helper_v1", s.models.helper, 50, "smoke_helper", word="hello"))
    log(f"[haiku]  cache_hit={r.cache_hit} stop={r.stop_reason} in={r.input_tokens} out={r.output_tokens} "
        f"text={r.text.strip()!r} parsed={parse_json(r.text)}")
    ok &= r.ok and parse_json(r.text) == ["hello", "ok"]

    # 2. Sonnet 5 (sync, thinking disabled, effort medium)
    sreq = _req("smoke_reasoner_v1", s.models.reasoner, 300, "smoke_reasoner")
    sreq = LLMRequest(**{**sreq.__dict__, "effort": s.models.reasoner_effort, "thinking": s.models.reasoner_thinking})
    r2 = ctx.llm.complete(sreq)
    p = parse_probability(r2.text)
    log(f"[sonnet] cache_hit={r2.cache_hit} stop={r2.stop_reason} in={r2.input_tokens} out={r2.output_tokens} "
        f"p={p} text={r2.text.strip()[:200]!r}")
    ok &= r2.ok and p is not None and 0.05 <= p <= 0.4

    # 3. Batch with one (Haiku) request
    breq = _req("smoke_helper_v1", s.models.helper, 50, "smoke_batch", word="batch")
    res = B.run_batch(ctx.llm, [breq], s.state_dir, log=log, poll_seconds=20)[breq.cache_key()]
    log(f"[batch]  cache_hit={'yes' if res and ctx.cache.exists('anthropic', breq.cache_key()) else 'no'} "
        f"stop={res and res.stop_reason} text={res and res.text.strip()!r}")
    ok &= res is not None and parse_json(res.text) == ["batch", "ok"]

    # 4. Exa x2 with endPublishedDate
    for i, q in enumerate(SMOKE_QUERIES):
        resp, hit = ctx.exa.search(q, SMOKE_END, num_results=s.pipeline.exa_num_results, search_type=exa_type,
                                   exclude_domains=s.exa_blocklist, highlight_chars=s.pipeline.exa_highlight_max_chars,
                                   max_age_hours=s.pipeline.exa_max_age_hours)
        bad = []
        for item in resp.get("results", []):
            pd = timeutil.parse(item.get("publishedDate"))
            if pd is not None and pd > SMOKE_END:
                bad.append((item.get("url"), item.get("publishedDate")))
        log(f"[exa:{exa_type}] cache_hit={hit} q={q!r} n={len(resp.get('results', []))} "
            f"cost={resp.get('costDollars', {}).get('total')} dates={[x.get('publishedDate') for x in resp.get('results', [])]}")
        if bad:
            log(f"  !! results AFTER endPublishedDate: {bad}")
            ok = False
        body = ctx.exa.build_body(q, SMOKE_END, s.pipeline.exa_num_results, exa_type, s.exa_blocklist,
                                  s.pipeline.exa_highlight_max_chars, s.pipeline.exa_max_age_hours)
        trimmed = dict(resp)
        trimmed["results"] = [dict(x, highlights=[h[:1500] for h in (x.get("highlights") or [])], text=None)
                              for x in resp.get("results", [])]
        trimmed.pop("text", None)
        _save(fx / "exa" / f"smoke_{exa_type}_{i}.json", {"request": body, "response": trimmed})

    _save(fx / "anthropic" / "smoke_haiku.json", r.raw)
    _save(fx / "anthropic" / "smoke_sonnet5.json", r2.raw)
    spent = ctx.budget.spent() - spent0
    log(f"spent this run: ${spent:.4f}  (anthropic total ${ctx.budget.spent('anthropic'):.4f}, "
        f"exa {timeutil.month_key(timeutil.now())} ${ctx.budget.spent('exa', month=timeutil.month_key(timeutil.now())):.4f})")
    log("SMOKE OK" if ok else "SMOKE FAILED")
    return 0 if ok else 1


def _save(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
