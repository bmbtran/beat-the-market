from datetime import datetime, timezone

from mf.config import settings
from mf.forecast.reason import reasoning_requests, to_sample
from mf.llm.client import LLMResult
from mf.schemas import Evidence, Question

Q = Question(qid="kalshi:KXFEDDECISION-26SEP-C26", venue="kalshi", event_id="kalshi:KXFEDDECISION-26SEP",
             title="Will the Federal Reserve Cut rates by >25bps at their September 2026 meeting?",
             description="If the Fed cuts by more than 25bps at the September 2026 meeting, resolves Yes.",
             category="Economics", created_at="2026-03-01T00:00:00Z", t0="2026-06-15T13:00:00Z",
             scheduled_close="2026-09-16T18:05:00Z", resolved_at="2026-09-16T19:00:00Z", horizon_days=93,
             p_mkt_t0=0.0731, p_mkt_source="mid", volume=123456, outcome=0, split="test",
             source_url="https://kalshi.com/markets/kxfeddecision-26sep")
EV = [Evidence(qid=Q.qid, query="q", url="https://n.com/2", title="Later piece", published_date="2026-06-10T00:00:00Z",
               relevance=5, leak_flag=False, leak_reason=None, summary="Officials signal patience.", kept=True),
      Evidence(qid=Q.qid, query="q", url="https://n.com/1", title="Earlier piece", published_date="2026-05-01T00:00:00Z",
               relevance=6, leak_flag=False, leak_reason=None, summary="Inflation cooled in April.", kept=True)]


def test_five_distinct_prompt_variants():
    s = settings()
    reqs = reasoning_requests(Q, s, EV)
    assert len(reqs) == 5
    assert len({r.prompt_id for r in reqs}) == 5 and len({r.cache_key() for r in reqs}) == 5
    assert [r.sample_idx for r in reqs] == list(range(5))
    for r in reqs:
        assert r.model == "claude-sonnet-5" and r.thinking == "disabled" and r.effort == "medium"
        assert r.max_tokens == 1200


def test_rendered_prompt_contents_and_leakage_guards():
    s = settings()
    for r in reasoning_requests(Q, s, EV):
        full = (r.system or "") + "\n" + r.user
        assert "Today is 2026-06-15. You have no information after this date. Do not assume the question has resolved." in full
        assert "FINAL PROBABILITY:" in full
        assert full.index("Earlier piece") < full.index("Later piece")  # evidence sorted by date
        for leak in ("0.0731", "Hike 25bps", "123456", "kalshi.com/markets", "2026-09-16T19"):
            assert leak not in full


def test_no_retrieval_variant_differs():
    s = settings()
    ret = reasoning_requests(Q, s, EV)
    nor = reasoning_requests(Q, s, None)
    assert all("no news articles" in r.user for r in nor)
    assert all("Inflation cooled" not in r.user for r in nor)
    assert {r.cache_key() for r in ret}.isdisjoint({r.cache_key() for r in nor})
    assert all(r.op == "reason_noret" for r in nor)


def test_to_sample_parses_and_handles_failures():
    s = settings()
    req = reasoning_requests(Q, s, EV)[0]
    ok = LLMResult("...\nFINAL PROBABILITY: 0.12", "end_turn", 10, 5, "claude-sonnet-5", 0.0, "k")
    assert to_sample(Q, "retrieval", req, ok).p == 0.12
    cut = LLMResult("...\nFINAL PROBABILITY: 0.12", "max_tokens", 10, 5, "claude-sonnet-5", 0.0, "k")
    assert to_sample(Q, "retrieval", req, cut).p is None
    refusal = LLMResult("", "refusal", 10, 0, "claude-sonnet-5", 0.0, "k")
    assert to_sample(Q, "retrieval", req, refusal).p is None
    assert to_sample(Q, "retrieval", req, None).stop_reason == "missing"
