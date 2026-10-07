"""Helper-model search query generation."""

from __future__ import annotations

from mf.llm.client import LLMRequest
from mf.llm.parse import parse_json
from mf.llm.prompts import load_prompt
from mf.schemas import Question, prompt_fields


def query_request(q: Question, s, today_override: str | None = None) -> LLMRequest:
    p = load_prompt(s.pipeline.query_prompt)
    ctx = prompt_fields(q) | {"n_queries": s.pipeline.queries_per_question}
    if today_override:
        ctx["today"] = today_override
    system, user = p.render(**ctx)
    return LLMRequest(model=s.models.helper, user=user, system=system, max_tokens=300, op="query_gen",
                      prompt_id=p.id, prompt_sha=p.sha)


def parse_queries(text: str, q: Question, n: int) -> list[str]:
    """JSON list of strings; falls back to the question title so retrieval never silently stops."""
    data = parse_json(text)
    out: list[str] = []
    if isinstance(data, list):
        for x in data:
            if isinstance(x, str) and x.strip() and x.strip() not in out:
                out.append(x.strip()[:200])
    if not out:
        out = [q.title[:200]]
    return out[:n]
