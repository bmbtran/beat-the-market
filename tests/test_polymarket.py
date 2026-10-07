import json

from mf.data import polymarket as P


def load(fixtures_dir, name):
    return json.loads((fixtures_dir / "polymarket" / name).read_text(encoding="utf-8"))


def test_parse_resolution():
    yn = '["Yes", "No"]'
    assert P.parse_resolution({"outcomes": yn, "outcomePrices": '["1", "0"]'}) == 1
    assert P.parse_resolution({"outcomes": yn, "outcomePrices": '["0", "1"]'}) == 0
    assert P.parse_resolution({"outcomes": yn, "outcomePrices": '["0.5", "0.5"]'}) is None
    assert P.parse_resolution({"outcomes": '["Spain", "Argentina"]', "outcomePrices": '["1", "0"]'}) is None


def test_non_yes_no_market_skipped(fixtures_dir):
    ev = load(fixtures_dir, "event_non_yes_no.json")
    assert P.market_to_candidate(ev["markets"][0], ev, "World") is None


def test_negrisk_market_parses_with_yes_token(fixtures_dir):
    ev = load(fixtures_dir, "event_negrisk.json")
    assert ev["negRisk"] is True
    cat = P.classify(ev)
    assert cat is not None
    m = ev["markets"][0]
    c = P.market_to_candidate(m, ev, cat)
    assert c is not None
    assert c.price_ref["token_id"] == json.loads(m["clobTokenIds"])[0]
    assert c.event_id == f"poly:{ev['id']}"


def test_update_paragraphs_stripped():
    desc = ("This market resolves YES if X happens by June 30.\n\n"
            "Resolution source: official statements.\n\n"
            "Update: As of June 2, X has happened, this market will resolve YES.\n\n"
            "CLARIFICATION - the deadline is ET.\n\nFinal paragraph.")
    out = P.sanitize_description(desc)
    assert "Update" not in out and "CLARIFICATION" not in out and "has happened" not in out
    assert out.startswith("This market resolves YES") and out.endswith("Final paragraph.")


def test_classify_excludes_sports_and_crypto():
    assert P.classify({"tags": [{"slug": "sports"}, {"slug": "politics"}]}) is None
    assert P.classify({"tags": [{"slug": "crypto"}]}) is None
    assert P.classify({"tags": [{"slug": "fed-rates"}, {"slug": "politics"}]}) == "Economics"
    assert P.classify({"tags": [{"slug": "elections"}, {"slug": "politics"}]}) == "Elections"
    assert P.classify({"tags": [{"slug": "zzz-unknown"}]}) is None
