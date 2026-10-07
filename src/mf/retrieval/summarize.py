"""One helper call per question: relevance 1-6, leak flags, <=80-word summary for each article."""

from __future__ import annotations

from mf.llm.client import LLMRequest
from mf.llm.parse import parse_json
from mf.llm.prompts import load_prompt
from mf.schemas import Question, prompt_fields

MAX_ARTICLES = 10
MAX_SUMMARY_WORDS = 80


def relevance_request(q: Question, articles: list[dict], s, today_override: str | None = None) -> LLMRequest:
    """articles: [{idx, title, published (YYYY-MM-DD), text}] (at most MAX_ARTICLES)."""
    p = load_prompt(s.pipeline.relevance_prompt)
    ctx = prompt_fields(q) | {"articles": articles[:MAX_ARTICLES]}
    if today_override:
        ctx["today"] = today_override
    system, user = p.render(**ctx)
    return LLMRequest(model=s.models.helper, user=user, system=system, max_tokens=s.models.helper_max_tokens,
                      op="relevance_summary", prompt_id=p.id, prompt_sha=p.sha)


def _truncate_words(text: str, n: int = MAX_SUMMARY_WORDS) -> str:
    words = (text or "").split()
    return " ".join(words[:n])


def parse_judgements(text: str, idxs: list[int]) -> dict[int, dict]:
    """{idx: {relevance, mentions_events_after_t0, reveals_outcome, summary}}; missing idx -> absent."""
    data = parse_json(text)
    out: dict[int, dict] = {}
    if not isinstance(data, list):
        return out
    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            idx = int(row.get("idx"))
            rel = int(row.get("relevance"))
        except (TypeError, ValueError):
            continue
        if idx not in idxs:
            continue
        out[idx] = {
            "relevance": max(1, min(6, rel)),
            "mentions_events_after_t0": bool(row.get("mentions_events_after_t0")),
            "reveals_outcome": bool(row.get("reveals_outcome")),
            "summary": _truncate_words(str(row.get("summary") or "")),
        }
    return out
