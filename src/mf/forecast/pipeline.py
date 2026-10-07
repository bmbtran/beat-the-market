"""Per-question forecasting: K reasoner samples (Batch or sync) -> trimmed mean -> supervisor.

Writes data/runs/<run>/samples.jsonl and forecasts.jsonl (base arms only). Post-hoc arms that cost
$0 (Platt, market ensembles) are computed in eval/arms.py from these files.

Base arms written here:
  retrieval    -> halawi_single (r1 sample), halawi (trimmed mean), halawi_sup (+ supervisor)
  no_retrieval -> noret_single (r1 sample), noret_ens (trimmed mean)
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from mf.forecast.aggregate import aggregate, spread
from mf.forecast.reason import reasoning_requests, to_sample
from mf.forecast.supervisor import run_supervisor
from mf.llm import batch as B
from mf.llm.client import LLMRequest, LLMResult
from mf.retrieval.pipeline import _read_jsonl, _write_jsonl, load_evidence
from mf.schemas import ArmForecast, Question, Sample


def plan_requests(qs: list[Question], s, evidence: dict, want_ret: set[str], want_noret: set[str]
                  ) -> dict[str, dict[str, list[LLMRequest]]]:
    """{qid: {"retrieval": [...], "no_retrieval": [...]}} for questions whose split asks for each arm."""
    out: dict[str, dict[str, list[LLMRequest]]] = {}
    for q in qs:
        d = {}
        if q.split in want_ret:
            d["retrieval"] = reasoning_requests(q, s, evidence.get(q.qid, []))
        if q.split in want_noret:
            d["no_retrieval"] = reasoning_requests(q, s, None)
        out[q.qid] = d
    return out


def uncached_questions(plan: dict, llm) -> list[str]:
    return [qid for qid, d in plan.items() if any(not llm.is_cached(r) for rs in d.values() for r in rs)]


def run_requests(llm, reqs: list[LLMRequest], s, use_batch: bool, log=print) -> dict[str, LLMResult | None]:
    if use_batch:
        res = B.run_batch(llm, reqs, s.state_dir, log=log)
        for r in reqs:
            x = res.get(r.cache_key())
            if x is not None:
                llm.cost_log.append((r.op + "_batch", x.cost_usd, x.cache_hit))
        return res
    out = {}
    for i, r in enumerate(reqs):
        out[r.cache_key()] = llm.complete(r)
        if (i + 1) % 25 == 0:
            log(f"[reason] {i + 1}/{len(reqs)} sync requests")
    return out


def forecast(qs: list[Question], ctx, want_ret: set[str], want_noret: set[str], supervisor: bool,
             use_batch: bool, log=print) -> dict:
    s, llm = ctx.s, ctx.llm
    run_dir = s.run_dir
    retrieved = {m["qid"] for m in _read_jsonl(run_dir / "retrieval_meta.jsonl")}
    missing = [q.qid for q in qs if q.split in want_ret and q.qid not in retrieved]
    if missing:
        raise RuntimeError(f"{len(missing)} questions have no retrieval yet (run `mf retrieve` first): {missing[:3]}")
    evidence = load_evidence(run_dir)
    plan = plan_requests(qs, s, evidence, want_ret, want_noret)
    all_reqs = [r for d in plan.values() for rs in d.values() for r in rs]
    results = run_requests(llm, all_reqs, s, use_batch, log)

    samples: list[Sample] = []
    arms: list[ArmForecast] = []
    stats = Counter()
    qmap = {q.qid: q for q in qs}
    for qid, d in plan.items():
        q = qmap[qid]
        for arm_base, reqs in d.items():
            ss = [to_sample(q, arm_base, r, results.get(r.cache_key())) for r in reqs]
            samples += ss
            stats["samples"] += len(ss)
            stats["samples_failed"] += sum(x.p is None for x in ss)
            agg = aggregate(ss, s.pipeline.min_valid_samples, s.pipeline.trim)
            first = next((x.p for x in ss if x.sample_idx == 0), None)
            comp = {"samples": [x.p for x in sorted(ss, key=lambda x: x.sample_idx)],
                    "n_valid": sum(x.p is not None for x in ss), "spread": round(spread(ss), 4)}
            prefix = "halawi" if arm_base == "retrieval" else "noret"
            arms.append(ArmForecast(qid=qid, arm=f"{prefix}_single", p=first, components={}))
            arms.append(ArmForecast(qid=qid, arm="halawi" if prefix == "halawi" else "noret_ens", p=agg,
                                    components=comp))
            if agg is None:
                stats[f"{prefix}_failed_questions"] += 1
            if arm_base == "retrieval" and supervisor:
                sup = run_supervisor(q, ss, agg, spread(ss), llm, ctx.exa, s)
                stats["supervisor_triggered"] += sup.triggered
                stats["supervisor_replaced"] += sup.triggered and sup.confidence == "high" and sup.probability is not None
                stats["supervisor_failed"] += sup.failed is not None
                arms.append(ArmForecast(qid=qid, arm="halawi_sup", p=sup.final_p, components=sup.components()))
    write_forecast_files(run_dir, samples, arms)
    stats["questions"] = len(plan)
    return dict(stats)


def write_forecast_files(run_dir: Path, samples: list[Sample], arms: list[ArmForecast]) -> None:
    """Merge into existing files (replace rows for the same (qid, arm_base/arm))."""
    run_dir.mkdir(parents=True, exist_ok=True)
    new_s = {(x.qid, x.arm_base, x.sample_idx) for x in samples}
    old_s = [r for r in _read_jsonl(run_dir / "samples.jsonl")
             if (r["qid"], r["arm_base"], r["sample_idx"]) not in new_s]
    rows = old_s + [json.loads(x.model_dump_json()) for x in samples]
    rows.sort(key=lambda r: (r["qid"], r["arm_base"], r["sample_idx"]))
    _write_jsonl(run_dir / "samples.jsonl", rows)
    new_a = {(a.qid, a.arm) for a in arms}
    old_a = [r for r in _read_jsonl(run_dir / "forecasts.jsonl") if (r["qid"], r["arm"]) not in new_a]
    rows = old_a + [json.loads(a.model_dump_json()) for a in arms]
    rows.sort(key=lambda r: (r["qid"], r["arm"]))
    _write_jsonl(run_dir / "forecasts.jsonl", rows)
