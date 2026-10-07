import pytest

from mf.forecast.aggregate import aggregate, spread, trimmed_mean
from mf.schemas import Sample


def S(i, p):
    return Sample(qid="q", arm_base="retrieval", prompt_id=f"r{i}", prompt_sha="s", sample_idx=i, model="m",
                  p=p, rationale="", stop_reason="end_turn", input_tokens=1, output_tokens=1, cache_key="k")


def test_trimmed_mean_plan_example():
    assert trimmed_mean([0.1, 0.2, 0.3, 0.4, 0.9]) == pytest.approx(0.3)
    assert trimmed_mean([0.9, 0.1, 0.4, 0.3, 0.2]) == pytest.approx(0.3)  # order-free


def test_min_valid_rule():
    assert aggregate([S(0, 0.2), S(1, 0.4), S(2, 0.6), S(3, None), S(4, None)]) == pytest.approx(0.4)
    assert aggregate([S(0, 0.2), S(1, 0.4), S(2, None), S(3, None), S(4, None)]) is None  # never 0.5
    assert aggregate([S(0, 0.2), S(1, 0.4), S(2, 0.5), S(3, 0.9)]) == pytest.approx(0.45)


def test_spread():
    assert spread([S(0, 0.2), S(1, None), S(2, 0.35)]) == pytest.approx(0.15)
    assert spread([S(0, None)]) == 0.0
