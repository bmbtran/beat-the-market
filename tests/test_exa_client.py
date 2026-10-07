import json
from datetime import datetime, timezone

import httpx
import pytest
import respx

from mf.config import BudgetCfg
from mf.core.budget import BudgetGuard
from mf.core.cache import Cache, CacheMiss
from mf.retrieval.exa_client import EXA_URL, ExaClient

CAPS = BudgetCfg(anthropic_total_usd=30, anthropic_backtest_usd=23, exa_monthly_usd=9, per_run_default_usd=5)
END = datetime(2026, 3, 1, tzinfo=timezone.utc)


def fixture(fixtures_dir, name="search_synthetic.json"):
    return json.loads((fixtures_dir / "exa" / name).read_text(encoding="utf-8"))


def test_request_body_uses_documented_camelcase():
    body = ExaClient.build_body("fed rates", END, 5, "instant", ["x.com", "kalshi.com"], 1500, -1)
    assert body == {
        "query": "fed rates", "type": "instant", "numResults": 5,
        "excludeDomains": ["kalshi.com", "x.com"],
        "endPublishedDate": "2026-03-01T00:00:00.000Z",
        "contents": {"highlights": {"maxCharacters": 1500}, "maxAgeHours": -1},
    }


@respx.mock
def test_search_caches_and_records_actual_cost(tmp_path, fixtures_dir):
    route = respx.post(EXA_URL).mock(return_value=httpx.Response(200, json=fixture(fixtures_dir)))
    budget = BudgetGuard(tmp_path / "l.jsonl", CAPS, run_id="t", max_usd=1)
    exa = ExaClient(Cache(tmp_path / "c", mode="readwrite"), budget, http=httpx.Client())
    r1, hit1 = exa.search("fed", END)
    r2, hit2 = exa.search("fed", END)
    assert (hit1, hit2) == (False, True) and route.call_count == 1
    assert r1 == r2 and len(r1["results"]) == 2
    assert budget.spent("exa") == pytest.approx(0.009)
    sent = json.loads(route.calls[0].request.content)
    assert sent["endPublishedDate"] == "2026-03-01T00:00:00.000Z"


@respx.mock
def test_retries_on_429(tmp_path, fixtures_dir):
    route = respx.post(EXA_URL).mock(side_effect=[httpx.Response(429, json={}),
                                                  httpx.Response(200, json=fixture(fixtures_dir))])
    exa = ExaClient(Cache(tmp_path, mode="readwrite"),
                    BudgetGuard(tmp_path / "l.jsonl", CAPS, run_id="t", max_usd=1), http=httpx.Client())
    resp, _ = exa.search("fed", END)
    assert route.call_count == 2 and resp["results"]


def test_readonly_miss_makes_no_request(tmp_path):
    exa = ExaClient(Cache(tmp_path, mode="readonly"), None, http=httpx.Client(transport=httpx.MockTransport(
        lambda r: (_ for _ in ()).throw(AssertionError("network used")))))
    with pytest.raises(CacheMiss):
        exa.search("fed", END)


def test_recorded_smoke_fixtures_respect_date_filter(fixtures_dir):
    """Real responses saved by `mf smoke` (if present) must honour endPublishedDate."""
    files = sorted((fixtures_dir / "exa").glob("smoke_*.json"))
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        end = datetime.fromisoformat(d["request"]["endPublishedDate"].replace("Z", "+00:00"))
        for r in d["response"]["results"]:
            if r.get("publishedDate"):
                assert datetime.fromisoformat(r["publishedDate"].replace("Z", "+00:00")) <= end
