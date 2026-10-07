import json

import httpx
import pytest

from mf.config import BudgetCfg, settings
from mf.core.budget import BudgetGuard
from mf.core.cache import Cache
from mf.forecast.supervisor import decide, run_supervisor, should_trigger
from mf.llm.client import CachedLLM, FakeLLM
from mf.retrieval.exa_client import ExaClient
from mf.schemas import Question, Sample

CAPS = BudgetCfg(anthropic_total_usd=30, anthropic_backtest_usd=23, exa_monthly_usd=9, per_run_default_usd=5)
Q = Question(qid="poly:1", venue="polymarket", event_id="poly:e1", title="Will the treaty be ratified by August?",
             description="Resolves Yes if ratified before Aug 31, 2026.", category="World",
             created_at="2026-04-01T00:00:00Z", t0="2026-06-01T00:00:00Z", scheduled_close="2026-08-31T00:00:00Z",
             resolved_at="2026-08-31T01:00:00Z", horizon_days=91, p_mkt_t0=0.3, p_mkt_source="last_trade",
             volume=9e4, outcome=0, split="test", source_url="u")


def samples(ps):
    return [Sample(qid=Q.qid, arm_base="retrieval", prompt_id=f"r{i}", prompt_sha="s", sample_idx=i,
                   model="claude-sonnet-5", p=p, rationale=f"rationale {i} says {p}", stop_reason="end_turn",
                   input_tokens=1, output_tokens=1, cache_key=f"k{i}") for i, p in enumerate(ps)]


def make(tmp_path, confidence="high", prob=0.12):
    def responder(params):
        u = params["messages"][0]["content"]
        if "disagreements that explain" in u:
            return json.dumps({"disagreements": ["whether the vote is scheduled"], "queries": ["treaty vote schedule senate", "x"]})
        if "Excerpts:" in u:
            return json.dumps([{"idx": 0, "relevance": 6, "mentions_events_after_t0": False,
                                "reveals_outcome": False, "summary": "Vote postponed to autumn."}])
        return json.dumps({"probability": prob, "confidence": confidence, "reason": "vote postponed"})

    def exa_t(req):
        return httpx.Response(200, json={"results": [{"url": "https://n.com/a", "title": "Vote postponed",
                                                      "publishedDate": "2026-05-20T00:00:00.000Z",
                                                      "highlights": ["The vote was postponed."]}],
                                         "costDollars": {"total": 0.004}})

    cache = Cache(tmp_path / "c", mode="readwrite")
    budget = BudgetGuard(tmp_path / "l.jsonl", CAPS, run_id="t", max_usd=1)
    fake = FakeLLM(responder)
    return fake, CachedLLM(fake, cache, budget), ExaClient(cache, budget, http=httpx.Client(transport=httpx.MockTransport(exa_t)))


def test_not_triggered_when_spread_small(tmp_path):
    s = settings()
    fake, llm, exa = make(tmp_path)
    ss = samples([0.30, 0.32, 0.35, 0.38, 0.40])  # spread 0.10 -> not > 0.10
    r = run_supervisor(Q, ss, 0.35, 0.10, llm, exa, s)
    assert not r.triggered and r.final_p == 0.35 and fake.calls == []
    assert not should_trigger(0.10, 0.10) and should_trigger(0.1001, 0.10)


def test_high_confidence_replaces_mean(tmp_path):
    s = settings()
    fake, llm, exa = make(tmp_path, "high", 0.12)
    r = run_supervisor(Q, samples([0.1, 0.2, 0.3, 0.5, 0.6]), 0.33, 0.5, llm, exa, s)
    assert r.triggered and r.confidence == "high" and r.final_p == pytest.approx(0.12)
    assert r.queries == ["treaty vote schedule senate", "x"] and r.new_evidence_urls == ["https://n.com/a"]
    update_prompt = fake.calls[-1]["messages"][0]["content"]
    assert "Vote postponed to autumn." in update_prompt and "0.33" in update_prompt


@pytest.mark.parametrize("conf", ["medium", "low"])
def test_lower_confidence_keeps_mean(tmp_path, conf):
    s = settings()
    _, llm, exa = make(tmp_path, conf, 0.12)
    r = run_supervisor(Q, samples([0.1, 0.2, 0.3, 0.5, 0.6]), 0.33, 0.5, llm, exa, s)
    assert r.triggered and r.final_p == pytest.approx(0.33) and r.probability == pytest.approx(0.12)


def test_decide():
    assert decide(0.4, 0.2, "high") == 0.2
    assert decide(0.4, 0.2, "medium") == 0.4
    assert decide(0.4, None, "high") == 0.4
