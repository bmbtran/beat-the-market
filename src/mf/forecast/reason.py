"""Reasoner samples: K prompt variants (no sampling params exist in SDK 1.x; diversity = prompts)."""

from __future__ import annotations

from mf.llm.client import LLMRequest, LLMResult
from mf.llm.parse import parse_probability
from mf.llm.prompts import load_prompt
from mf.schemas import Evidence, Question, Sample, prompt_fields


def evidence_ctx(evidence: list[Evidence] | None) -> list[dict] | None:
    if evidence is None:
        return None
    evs = sorted(evidence, key=lambda e: (e.published_date, e.url))
    return [{"date": e.published_date.strftime("%Y-%m-%d") if e.published_date else "undated",
             "title": e.title, "summary": e.summary} for e in evs]


def reasoning_requests(q: Question, s, evidence: list[Evidence] | None,
                       today_override: str | None = None) -> list[LLMRequest]:
    """One request per prompt variant. evidence=None -> no-retrieval arm."""
    reqs = []
    ctx = prompt_fields(q) | {"evidence": evidence_ctx(evidence)}
    if today_override:
        ctx["today"] = today_override
    for i, pid in enumerate(s.pipeline.reasoning_prompts[: s.pipeline.k_samples]):
        p = load_prompt(pid)
        system, user = p.render(**ctx)
        reqs.append(LLMRequest(
            model=s.models.reasoner, user=user, system=system, max_tokens=s.models.reasoner_max_tokens,
            op="reason" if evidence is not None else "reason_noret", effort=s.models.reasoner_effort,
            thinking=s.models.reasoner_thinking, prompt_id=pid, prompt_sha=p.sha, sample_idx=i))
    return reqs


def to_sample(q: Question, arm_base: str, req: LLMRequest, res: LLMResult | None) -> Sample:
    if res is None:
        return Sample(qid=q.qid, arm_base=arm_base, prompt_id=req.prompt_id, prompt_sha=req.prompt_sha,
                      sample_idx=req.sample_idx, model=req.model, p=None, rationale="", stop_reason="missing",
                      input_tokens=0, output_tokens=0, cache_key=req.cache_key())
    p = parse_probability(res.text) if res.ok else None
    return Sample(qid=q.qid, arm_base=arm_base, prompt_id=req.prompt_id, prompt_sha=req.prompt_sha,
                  sample_idx=req.sample_idx, model=req.model, p=p, rationale=res.text,
                  stop_reason=res.stop_reason, input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                  cache_key=res.cache_key)
