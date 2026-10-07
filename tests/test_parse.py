import pytest

from mf.llm.parse import parse_json, parse_probability


@pytest.mark.parametrize("text,expected", [
    ("blah\nFINAL PROBABILITY: 0.37", 0.37),
    ("FINAL PROBABILITY: .25", 0.25),
    ("FINAL PROBABILITY: 37%", 0.37),
    ("FINAL PROBABILITY: 15%", 0.15),
    ("FINAL PROBABILITY: 100%", 0.99),
    ("FINAL PROBABILITY: 0", 0.01),
    ("FINAL PROBABILITY: 1.0", 0.99),
    ("final probability: **0.6**", 0.6),
    ("FINAL PROBABILITY: 0.2\n...on reflection...\nFINAL PROBABILITY: 0.3", 0.3),
])
def test_parse_probability(text, expected):
    assert parse_probability(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", None, "I think 0.4", "FINAL PROBABILITY: high", "FINAL PROBABILITY: 3.5"])
def test_unparseable_is_none(text):
    assert parse_probability(text) is None


def test_parse_json_variants():
    assert parse_json('```json\n["a", "b"]\n```') == ["a", "b"]
    assert parse_json('Here you go: {"x": 1, "y": [2]} thanks') == {"x": 1, "y": [2]}
    assert parse_json('[{"idx": 0}]') == [{"idx": 0}]
    assert parse_json("no json here") is None
    assert parse_json("```\n{bad json}\n```") is None
