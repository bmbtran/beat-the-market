import pytest

from mf.core.cache import Cache, CacheMiss, cached_call, make_key
from mf.core.hashing import canonical_json


def test_canonical_json_is_order_independent():
    assert canonical_json({"b": 1, "a": [1, 2]}) == canonical_json({"a": [1, 2], "b": 1})


def test_cache_hit_returns_identical_object(tmp_path):
    c = Cache(tmp_path, mode="readwrite")
    k = make_key("anthropic", "messages", "m", {"x": 1}, "sha", 0)
    resp = {"text": "hello ü", "nested": {"a": [1, 2.5, None]}}
    c.put("anthropic", k, {"req": 1}, resp, 0.01)
    got = c.get("anthropic", k)
    assert got["response"] == resp
    assert Cache(tmp_path, mode="readonly").get("anthropic", k) == got


def test_readwrite_miss_returns_none(tmp_path):
    assert Cache(tmp_path, mode="readwrite").get("exa", "ab" * 32) is None


def test_readonly_miss_raises(tmp_path):
    with pytest.raises(CacheMiss):
        Cache(tmp_path, mode="readonly").get("exa", "cd" * 32)


def test_default_mode_in_tests_is_readonly(tmp_path):
    assert Cache(tmp_path).mode == "readonly"


def test_refresh_ignores_reads(tmp_path):
    c = Cache(tmp_path, mode="readwrite")
    k = make_key("exa", "search", params={"q": 1})
    c.put("exa", k, {}, {"v": 1})
    assert Cache(tmp_path, mode="refresh").get("exa", k) is None


def test_key_changes_with_prompt_sha_and_sample_idx():
    base = dict(provider="anthropic", endpoint="messages", model="m", params={"p": 1})
    k1 = make_key(**base, prompt_sha="aaa", sample_idx=0)
    assert k1 != make_key(**base, prompt_sha="bbb", sample_idx=0)
    assert k1 != make_key(**base, prompt_sha="aaa", sample_idx=1)
    assert k1 == make_key(**base, prompt_sha="aaa", sample_idx=0)


def test_cached_call_only_pays_on_miss(tmp_path):
    c = Cache(tmp_path / "c", mode="readwrite")
    calls = []

    class FakeBudget:
        def charge(self, provider, est, op):
            calls.append(("charge", est))
            return object()

        def settle(self, res, **kw):
            calls.append(("settle", kw["actual_usd"]))

        def release(self, res):
            calls.append(("release",))

    k = make_key("exa", "search", params={"q": "x"})

    def fn():
        return {"r": 1}, 0.005, None, None

    e1, hit1 = cached_call(c, FakeBudget(), "exa", k, {"q": "x"}, 0.01, fn, "search")
    e2, hit2 = cached_call(c, FakeBudget(), "exa", k, {"q": "x"}, 0.01, fn, "search")
    assert (hit1, hit2) == (False, True)
    assert e1["response"] == e2["response"] == {"r": 1}
    assert calls == [("charge", 0.01), ("settle", 0.005)]


def test_cached_call_releases_reservation_on_error(tmp_path):
    c = Cache(tmp_path, mode="readwrite")
    log = []

    class B:
        def charge(self, *a):
            log.append("charge")
            return 1

        def release(self, r):
            log.append("release")

    def boom():
        raise RuntimeError("api down")

    with pytest.raises(RuntimeError):
        cached_call(c, B(), "exa", "ee" * 32, {}, 0.01, boom, "search")
    assert log == ["charge", "release"]
    assert not c.exists("exa", "ee" * 32)
