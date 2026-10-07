import inspect
import json

import pytest

from mf.live import ledger as L


def fields(i):
    return dict(created_utc=f"2026-10-0{i + 1}T12:00:00Z", qid=f"poly:{i}", venue="polymarket", title=f"Q{i}?",
                close_time="2026-11-30T00:00:00Z", p_mkt_at_forecast=0.4, p_halawi=0.35, p_aia=0.3,
                p_aia_market_ens=0.37, model="claude-sonnet-5", prompt_versions={"r1": "abc"},
                code_git_sha="deadbeef")


def build(tmp_path, n=4):
    p = tmp_path / "forecasts.jsonl"
    for i in range(n):
        L.append(p, fields(i))
    return p


def test_chain_verifies(tmp_path):
    p = build(tmp_path)
    v = L.verify(p)
    assert v.ok and v.n == 4 and v.head == L.read_records(p)[-1]["hash"]
    recs = L.read_records(p)
    assert recs[0]["prev_hash"] == L.GENESIS and recs[1]["prev_hash"] == recs[0]["hash"]


@pytest.mark.parametrize("field,value", [("p_aia", 0.99), ("title", "edited"), ("created_utc", "2026-09-01T00:00:00Z"),
                                         ("qid", "poly:999"), ("p_mkt_at_forecast", 0.1)])
def test_tampering_any_field_breaks_verify_at_that_record(tmp_path, field, value):
    p = build(tmp_path)
    lines = p.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[2])
    rec[field] = value
    lines[2] = json.dumps(rec)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    v = L.verify(p)
    assert not v.ok and v.bad_index == 2


def test_deleting_or_reordering_breaks_verify(tmp_path):
    p = build(tmp_path)
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join([lines[0], lines[2], lines[3]]) + "\n", encoding="utf-8")
    assert not L.verify(p).ok


def test_rehashing_a_tampered_record_still_fails_downstream(tmp_path):
    p = build(tmp_path)
    recs = L.read_records(p)
    recs[1]["p_aia"] = 0.9
    recs[1]["hash"] = L.record_hash(recs[1], recs[1]["prev_hash"])  # attacker recomputes record 1
    p.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    v = L.verify(p)
    assert not v.ok and v.bad_index == 2  # record 2's prev_hash no longer matches


def test_writer_is_append_only(tmp_path):
    src = inspect.getsource(L.append)
    assert 'open(path, "a"' in src and '"w"' not in src
    p = build(tmp_path, 2)
    before = p.read_bytes()
    L.append(p, fields(2))
    assert p.read_bytes().startswith(before)
