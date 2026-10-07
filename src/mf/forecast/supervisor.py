"""AIA Forecaster supervisor (arXiv 2511.07678): reconcile disagreeing ensemble members.

Triggered only when the sample spread exceeds `supervisor_spread_threshold`. Steps:
  1. reasoner names disagreements + proposes <= 2 search queries (JSON)
  2. Exa search with the same date cutoff + helper relevance/leak/summary (shared retrieval code)
  3. reasoner issues an updated probability with confidence {high, medium, low}
If confidence == "high" the supervisor probability replaces the trimmed mean; otherwise it is kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mf.llm.client import LLMRequest
from mf.llm.parse import clamp, parse_json
from mf.llm.prompts import load_prompt
from mf.retrieval.pipeline import cutoff_for, judge_and_select, search_all
from mf.schemas import Evidence, Question, Sample, prompt_fields
from mf.forecast.reason import evidence_ctx
from mf.core import timeutil


@dataclass
class SupervisorResult:
    triggered: bool
    final_p: float | None
    trimmed_mean: float | None
    spread: float
    probability: float | None = None
    confidence: str | None = None
    reason: str = ""
    disagreements: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    new_evidence_urls: list[str] = field(default_factory=list)
    failed: str | None = None

    def components(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def should_trigger(spread: float, threshold: float) -> bool:
    return spread > threshold


def decide(trimmed: float, sup_p: float | None, confidence: str | None) -> float:
    if sup_p is not None and confidence == "high":
        return sup_p
    return trimmed


def _req(prompt_id: str, s, max_tokens: int, op: str, **ctx) -> LLMRequest:
    p = load_prompt(prompt_id)
    system, user = p.render(**ctx)
    return LLMRequest(model=s.models.reasoner, user=user, system=system, max_tokens=max_tokens, op=op,
                      effort=s.models.reasoner_effort, thinking=s.models.reasoner_thinking,
                      prompt_id=prompt_id, prompt_sha=p.sha)


def run_supervisor(q: Question, samples: list[Sample], trimmed: float | None, spread: float, llm, exa, s,
                   live: bool = False) -> SupervisorResult:
    if trimmed is None or not should_trigger(spread, s.pipeline.supervisor_spread_threshold):
        return SupervisorResult(False, trimmed, trimmed, spread)
    today_override = timeutil.now().strftime("%Y-%m-%d") if live else None
    base = prompt_fields(q)
    if today_override:
        base["today"] = today_override
    forecasts = [{"p": x.p, "rationale": x.rationale} for x in sorted(samples, key=lambda x: x.sample_idx)
                 if x.p is not None]
    r1 = llm.complete(_req(s.pipeline.supervisor_disagreement_prompt, s, 800, "supervisor_disagree",
                           **base, forecasts=forecasts, max_queries=s.pipeline.supervisor_max_queries))
    d = parse_json(r1.text) if r1.ok else None
    if not isinstance(d, dict):
        return SupervisorResult(True, trimmed, trimmed, spread, failed="disagreement_unparseable")
    disagreements = [str(x)[:400] for x in (d.get("disagreements") or []) if str(x).strip()][:6]
    queries = [str(x).strip()[:200] for x in (d.get("queries") or []) if str(x).strip()][: s.pipeline.supervisor_max_queries]
    new_ev: list[Evidence] = []
    if queries:
        cutoff = cutoff_for(q, s, live)
        t0 = timeutil.now() if live else q.t0
        cands = search_all(exa, queries, cutoff, s)
        rows, _, _ = judge_and_select(q, llm, cands, t0, cutoff, s, today_override)
        new_ev = [e for e in rows if e.kept]
    r2 = llm.complete(_req(s.pipeline.supervisor_update_prompt, s, 600, "supervisor_update", **base,
                           forecasts=forecasts, trimmed_mean=trimmed, disagreements=disagreements,
                           new_evidence=evidence_ctx(new_ev) or []))
    u = parse_json(r2.text) if r2.ok else None
    sup_p, conf, reason = None, None, ""
    if isinstance(u, dict):
        try:
            sup_p = clamp(float(u.get("probability")))
        except (TypeError, ValueError):
            sup_p = None
        conf = str(u.get("confidence", "")).lower() or None
        if conf not in ("high", "medium", "low"):
            conf = None
        reason = str(u.get("reason", ""))[:500]
    res = SupervisorResult(True, decide(trimmed, sup_p, conf), trimmed, spread, sup_p, conf, reason,
                           disagreements, queries, [e.url for e in new_ev])
    if sup_p is None or conf is None:
        res.failed = "update_unparseable"
    return res
