import json
import re
from datetime import datetime, timezone

import httpx

from mf.config import BudgetCfg, settings
from mf.core.budget import BudgetGuard
from mf.core.cache import Cache
from mf.llm.client import CachedLLM, FakeLLM
from mf.retrieval.exa_client import ExaClient
from mf.retrieval.pipeline import load_evidence, project_question, retrieve_question, write_results
from mf.schemas import Question

UTC = timezone.utc
CAPS = BudgetCfg(anthropic_total_usd=30, anthropic_backtest_usd=23, exa_monthly_usd=9, per_run_default_usd=5)

Q = Question(qid="kalshi:TEST-1", venue="kalshi", event_id="kalshi:TEST", title="Will the Senate pass the bill by July?",
             description="Resolves YES if the Senate passes the bill before July 31, 2026.", category="Politics",
             created_at="2026-04-01T00:00:00Z", t0="2026-06-01T00:00:00Z", scheduled_close="2026-07-31T00:00:00Z",
             resolved_at="2026-07-31T01:00:00Z", horizon_days=60, p_mkt_t0=0.4, p_mkt_source="mid", volume=1e4,
             outcome=1, split="dev", source_url="u")


def article(i, date, text="Senators debated the bill.", url=None, title=None):
    return {"url": url or f"https://news{i}.com/a{i}", "title": title or f"Article {i}", "publishedDate": date,
            "highlights": [text]}


ARTICLES = {
    "q one": [article(1, "2026-05-20T00:00:00.000Z"), article(2, None),  # null date
              article(3, "2026-05-10T00:00:00.000Z", "Vote delayed. Updated September 3, 2026"),  # text leak
              article(4, "2026-05-02T00:00:00.000Z", url="https://en.wikipedia.org/wiki/Bill"),  # blocklist
              article(5, "2026-04-15T00:00:00.000Z"), article(6, "2026-05-25T00:00:00.000Z")],
    "q two": [article(1, "2026-05-20T00:00:00.000Z"),  # duplicate URL
              article(7, "2026-05-28T00:00:00.000Z"), article(8, "2026-04-20T00:00:00.000Z"),
              article(9, "2026-04-21T00:00:00.000Z"), article(10, "2026-04-22T00:00:00.000Z"),
              article(11, "2026-04-23T00:00:00.000Z"), article(12, "2026-04-24T00:00:00.000Z")],
}


def exa_transport(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["endPublishedDate"] == "2026-05-31T00:00:00.000Z"  # t0 - 24h
    return httpx.Response(200, json={"results": ARTICLES[body["query"]], "costDollars": {"total": 0.004}})


def responder(params):
    user = params["messages"][0]["content"]
    if "search queries" in user:
        return '["q one", "q two"]'
    idxs = [int(x) for x in re.findall(r"^\[(\d+)\]", user, flags=re.M)]
    rows = []
    for i in idxs:
        title = re.search(rf"^\[{i}\] \"Article (\d+)\"", user, flags=re.M).group(1)
        n = int(title)
        rows.append({"idx": i, "relevance": 2 if n == 8 else 5 + (n % 2),
                     "mentions_events_after_t0": n == 9, "reveals_outcome": False,
                     "summary": f"summary of article {n} " + "word " * 100})
    return "```json\n" + json.dumps(rows) + "\n```"


def make(tmp_path):
    cache = Cache(tmp_path / "c", mode="readwrite")
    budget = BudgetGuard(tmp_path / "l.jsonl", CAPS, run_id="t", max_usd=1)
    llm = CachedLLM(FakeLLM(responder), cache, budget)
    exa = ExaClient(cache, budget, http=httpx.Client(transport=httpx.MockTransport(exa_transport)))
    return llm, exa


def test_pipeline_filters_and_selects(tmp_path):
    s = settings()
    llm, exa = make(tmp_path)
    r = retrieve_question(Q, llm, exa, s)
    assert r.queries == ["q one", "q two"]
    reasons = {e.url: (e.kept, e.leak_reason) for e in r.evidence}
    assert reasons["https://news2.com/a2"] == (False, "null_date")
    assert reasons["https://news3.com/a3"] == (False, "text_post_t0_date")
    assert reasons["https://en.wikipedia.org/wiki/Bill"] == (False, "blocklisted_domain")
    assert reasons["https://news8.com/a8"] == (False, None)  # relevance 2 < 4
    assert reasons["https://news9.com/a9"][1] == "haiku_leak_flag:mentions_events_after_t0"
    assert r.haiku_flagged_any
    assert len([e for e in r.evidence if e.url == "https://news1.com/a1"]) == 1  # deduped
    kept = r.kept
    assert 0 < len(kept) <= 6
    dates = [e.published_date for e in kept]
    assert dates == sorted(dates)
    assert all(e.relevance >= 4 and not e.leak_flag for e in kept)
    assert all(len(e.summary.split()) <= 80 for e in r.evidence)
    assert r.drop_counts["over_max_evidence"] >= 1  # 8 survivors scored >=4 -> top 6 kept


def test_pipeline_is_cached_second_time(tmp_path):
    s = settings()
    llm, exa = make(tmp_path)
    retrieve_question(Q, llm, exa, s)
    n_llm, n_exa = llm.network_calls, exa.network_calls
    r2 = retrieve_question(Q, llm, exa, s)
    assert (llm.network_calls, exa.network_calls) == (n_llm, n_exa)
    assert len(r2.kept) > 0


def test_dry_run_projection_makes_no_network_calls(tmp_path):
    s = settings()
    llm, exa = make(tmp_path)
    proj = project_question(Q, llm, exa, s)
    assert llm.network_calls == 0 and exa.network_calls == 0
    assert proj["llm_misses"] == 2 and proj["exa_misses"] == 2 and proj["anthropic_usd"] > 0
    retrieve_question(Q, llm, exa, s)
    before = (llm.network_calls, exa.network_calls)
    proj2 = project_question(Q, llm, exa, s)
    assert (llm.network_calls, exa.network_calls) == before
    assert proj2["anthropic_usd"] == 0 and proj2["exa_usd"] == 0 and proj2["llm_hits"] == 2


def test_write_and_load_evidence_roundtrip(tmp_path):
    s = settings()
    llm, exa = make(tmp_path)
    r = retrieve_question(Q, llm, exa, s)
    write_results(tmp_path / "run", [r])
    loaded = load_evidence(tmp_path / "run")
    assert [e.url for e in loaded[Q.qid]] == [e.url for e in r.kept]
    raw = (tmp_path / "run" / "evidence.jsonl").read_text(encoding="utf-8")
    assert "Senators debated the bill." not in raw  # no raw article text committed
