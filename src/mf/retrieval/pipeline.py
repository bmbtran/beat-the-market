"""queries -> Exa -> dedupe -> deterministic leakage filters -> helper relevance/leak/summary -> top-k.

Every candidate article becomes an Evidence row (kept or not, with the drop reason) so the filter
funnel is auditable. Raw article text is never written outside cache/ (only <=80-word summaries).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from mf.core import timeutil
from mf.core.cache import make_key
from mf.core.pricing import anthropic_estimate, exa_search_estimate
from mf.retrieval.exa_client import ExaClient
from mf.retrieval.leakage import deterministic_drop_reason
from mf.retrieval.queries import parse_queries, query_request
from mf.retrieval.summarize import MAX_ARTICLES, parse_judgements, relevance_request
from mf.schemas import Evidence, Question

LEAK_REASONS = {"date_after_cutoff", "text_post_t0_date", "haiku_leak_flag"}
# Pessimistic typical relevance-call size used only for dry-run projections when inputs are uncached.
TYPICAL_RELEVANCE_PROMPT_CHARS = 17_000


@dataclass
class RetrievalResult:
    qid: str
    queries: list[str]
    evidence: list[Evidence]
    drop_counts: Counter = field(default_factory=Counter)
    n_results: int = 0
    haiku_flagged_any: bool = False

    @property
    def kept(self) -> list[Evidence]:
        return sorted([e for e in self.evidence if e.kept],
                      key=lambda e: (e.published_date or datetime.min.replace(tzinfo=timeutil.UTC), e.url))

    def meta(self) -> dict:
        return {"qid": self.qid, "queries": self.queries, "n_results": self.n_results,
                "n_kept": len(self.kept), "drop_counts": dict(sorted(self.drop_counts.items())),
                "haiku_flagged_any": self.haiku_flagged_any}


def cutoff_for(q: Question, s, live: bool = False) -> datetime:
    if live:
        return timeutil.now()
    return q.t0 - timedelta(hours=s.pipeline.exa_end_offset_hours)


def _norm_url(u: str) -> str:
    return u.split("#")[0].rstrip("/").lower()


def search_all(exa: ExaClient, queries: list[str], cutoff: datetime, s) -> list[tuple[str, dict]]:
    """Run each query; return deduped [(query, result)] in first-seen order."""
    seen, out = set(), []
    for qtext in queries:
        resp, _ = exa.search(qtext, cutoff, num_results=s.pipeline.exa_num_results, search_type=s.pipeline.exa_type,
                             exclude_domains=s.exa_blocklist, highlight_chars=s.pipeline.exa_highlight_max_chars,
                             max_age_hours=s.pipeline.exa_max_age_hours, category=s.pipeline.exa_category)
        for r in resp.get("results") or []:
            u = _norm_url(r.get("url") or "")
            if u and u not in seen:
                seen.add(u)
                out.append((qtext, r))
    return out


def judge_and_select(q: Question, llm, candidates: list[tuple[str, dict]], t0: datetime, cutoff: datetime,
                     s, today_override: str | None = None) -> tuple[list[Evidence], Counter, bool]:
    """Deterministic filters, then one helper call for survivors, then top-k selection."""
    counts: Counter = Counter()
    rows: list[Evidence] = []
    survivors: list[tuple[str, dict, datetime]] = []
    for qtext, r in candidates:
        pub = timeutil.parse(r.get("publishedDate"))
        text = "\n".join(r.get("highlights") or [])[: s.pipeline.exa_highlight_max_chars]
        reason = deterministic_drop_reason(r.get("url", ""), r.get("title") or "", pub, text, t0, cutoff,
                                           s.exa_blocklist)
        if reason:
            counts[reason] += 1
            rows.append(Evidence(qid=q.qid, query=qtext, url=r.get("url", ""), title=(r.get("title") or "")[:300],
                                 published_date=pub, relevance=0, leak_flag=reason in LEAK_REASONS,
                                 leak_reason=reason, summary="", kept=False))
        elif len(survivors) >= MAX_ARTICLES:
            counts["over_max_articles"] += 1
            rows.append(Evidence(qid=q.qid, query=qtext, url=r.get("url", ""), title=(r.get("title") or "")[:300],
                                 published_date=pub, relevance=0, leak_flag=False, leak_reason="over_max_articles",
                                 summary="", kept=False))
        else:
            survivors.append((qtext, r, pub))
    flagged_any = False
    if survivors:
        arts = [{"idx": i, "title": (r.get("title") or "").strip()[:300], "published": pub.strftime("%Y-%m-%d"),
                 "text": "\n".join(r.get("highlights") or [])[: s.pipeline.exa_highlight_max_chars]}
                for i, (_, r, pub) in enumerate(survivors)]
        res = llm.complete(relevance_request(q, arts, s, today_override))
        judged = parse_judgements(res.text, list(range(len(survivors)))) if res.ok else {}
        scored = []
        for i, (qtext, r, pub) in enumerate(survivors):
            j = judged.get(i)
            base = dict(qid=q.qid, query=qtext, url=r.get("url", ""), title=(r.get("title") or "")[:300],
                        published_date=pub)
            if j is None:
                counts["judge_missing"] += 1
                rows.append(Evidence(**base, relevance=0, leak_flag=False, leak_reason="judge_missing",
                                     summary="", kept=False))
                continue
            if j["reveals_outcome"] or j["mentions_events_after_t0"]:
                flagged_any = True
                counts["haiku_leak_flag"] += 1
                why = "reveals_outcome" if j["reveals_outcome"] else "mentions_events_after_t0"
                rows.append(Evidence(**base, relevance=j["relevance"], leak_flag=True,
                                     leak_reason=f"haiku_leak_flag:{why}", summary=j["summary"], kept=False))
                continue
            if j["relevance"] < s.pipeline.min_relevance:
                counts["low_relevance"] += 1
                rows.append(Evidence(**base, relevance=j["relevance"], leak_flag=False, leak_reason=None,
                                     summary=j["summary"], kept=False))
                continue
            scored.append(Evidence(**base, relevance=j["relevance"], leak_flag=False, leak_reason=None,
                                   summary=j["summary"], kept=True))
        scored.sort(key=lambda e: (-e.relevance, -(e.published_date.timestamp()), e.url))
        for k, e in enumerate(scored):
            if k >= s.pipeline.max_evidence:
                counts["over_max_evidence"] += 1
                e = e.model_copy(update={"kept": False})
            else:
                counts["kept"] += 1
            rows.append(e)
    return rows, counts, flagged_any


def retrieve_question(q: Question, llm, exa: ExaClient, s, live: bool = False) -> RetrievalResult:
    cutoff = cutoff_for(q, s, live)
    t0 = timeutil.now() if live else q.t0
    today_override = t0.strftime("%Y-%m-%d") if live else None
    qr = llm.complete(query_request(q, s, today_override))
    queries = parse_queries(qr.text if qr.ok else "", q, s.pipeline.queries_per_question)
    cands = search_all(exa, queries, cutoff, s)
    rows, counts, flagged = judge_and_select(q, llm, cands, t0, cutoff, s, today_override)
    return RetrievalResult(q.qid, queries, rows, counts, len(cands), flagged)


# ---------------------------------------------------------------------------------------------
# Dry-run projection: no network, no client construction.
# ---------------------------------------------------------------------------------------------
def project_question(q: Question, llm, exa: ExaClient, s) -> dict:
    """Projected $ for retrieving q, using cache contents where available."""
    out = {"anthropic_usd": 0.0, "exa_usd": 0.0, "llm_misses": 0, "exa_misses": 0, "llm_hits": 0, "exa_hits": 0}
    cutoff = cutoff_for(q, s)
    qreq = query_request(q, s)
    queries = None
    if llm.is_cached(qreq):
        out["llm_hits"] += 1
        entry = llm.cache.get("anthropic", qreq.cache_key())
        text = "".join(b["text"] for b in entry["response"]["content"] if b["type"] == "text")
        queries = parse_queries(text, q, s.pipeline.queries_per_question)
    else:
        out["llm_misses"] += 1
        out["anthropic_usd"] += llm.estimate(qreq)
    all_exa_cached = queries is not None
    for qtext in queries or [None] * s.pipeline.queries_per_question:
        body = None if qtext is None else exa.build_body(
            qtext, cutoff, s.pipeline.exa_num_results, s.pipeline.exa_type, s.exa_blocklist,
            s.pipeline.exa_highlight_max_chars, s.pipeline.exa_max_age_hours, s.pipeline.exa_category)
        if body is not None and exa.cache.exists("exa", make_key("exa", "search", params=body)):
            out["exa_hits"] += 1
        else:
            all_exa_cached = False
            out["exa_misses"] += 1
            out["exa_usd"] += exa_search_estimate(s.pipeline.exa_type, s.pipeline.exa_num_results)
    rel_cached = False
    if all_exa_cached:
        cands = search_all(exa, queries, cutoff, s)  # all cache hits
        rows_needed = [c for c in cands if deterministic_drop_reason(
            c[1].get("url", ""), c[1].get("title") or "", timeutil.parse(c[1].get("publishedDate")),
            "\n".join(c[1].get("highlights") or []), q.t0, cutoff, s.exa_blocklist) is None][:MAX_ARTICLES]
        if not rows_needed:
            rel_cached = True
        else:
            arts = [{"idx": i, "title": (r.get("title") or "").strip()[:300],
                     "published": timeutil.parse(r.get("publishedDate")).strftime("%Y-%m-%d"),
                     "text": "\n".join(r.get("highlights") or [])[: s.pipeline.exa_highlight_max_chars]}
                    for i, (_, r) in enumerate(rows_needed)]
            rreq = relevance_request(q, arts, s)
            rel_cached = llm.is_cached(rreq)
            if not rel_cached:
                out["anthropic_usd"] += llm.estimate(rreq)
    if rel_cached:
        out["llm_hits"] += 1
    elif not all_exa_cached:
        out["llm_misses"] += 1
        out["anthropic_usd"] += anthropic_estimate(s.models.helper, TYPICAL_RELEVANCE_PROMPT_CHARS,
                                                   s.models.helper_max_tokens)
    else:
        out["llm_misses"] += 1
    return out


# ---------------------------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------------------------
def write_results(run_dir: Path, results: list[RetrievalResult]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    existing_ev = _read_jsonl(run_dir / "evidence.jsonl")
    existing_meta = _read_jsonl(run_dir / "retrieval_meta.jsonl")
    new_ids = {r.qid for r in results}
    ev = [e for e in existing_ev if e["qid"] not in new_ids]
    meta = [m for m in existing_meta if m["qid"] not in new_ids]
    for r in results:
        ev += [json.loads(e.model_dump_json()) for e in r.evidence]
        meta.append(r.meta())
    ev.sort(key=lambda e: (e["qid"], e["url"]))
    meta.sort(key=lambda m: m["qid"])
    _write_jsonl(run_dir / "evidence.jsonl", ev)
    _write_jsonl(run_dir / "retrieval_meta.jsonl", meta)


def load_evidence(run_dir: Path) -> dict[str, list[Evidence]]:
    out: dict[str, list[Evidence]] = {}
    for row in _read_jsonl(run_dir / "evidence.jsonl"):
        e = Evidence.model_validate(row)
        if e.kept:
            out.setdefault(e.qid, []).append(e)
    for v in out.values():
        v.sort(key=lambda e: (e.published_date, e.url))
    return out


def _read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _write_jsonl(p: Path, rows: list[dict]) -> None:
    from mf.core.hashing import canonical_json

    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(canonical_json(r) + "\n")
