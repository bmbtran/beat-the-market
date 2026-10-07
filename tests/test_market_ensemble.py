import numpy as np
import pytest

from mf.forecast.market_ensemble import blend, cross_fit, fit_weight, grouped_folds


def synth(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    truth = rng.uniform(0.05, 0.95, n)
    y = (rng.random(n) < truth).astype(int)
    noise = rng.uniform(0.01, 0.99, n)
    return truth, y, noise


def test_w_near_one_when_market_is_noise():
    truth, y, noise = synth()
    assert fit_weight(truth, noise, y) >= 0.9


def test_w_near_zero_when_llm_is_noise():
    truth, y, noise = synth()
    assert fit_weight(noise, truth, y) <= 0.1


def test_blend():
    assert blend([0.2], [0.6], 0.25)[0] == pytest.approx(0.5)


def test_grouped_cv_never_splits_an_event():
    groups = np.repeat(np.arange(37), 3)[:100]
    for tr, te in grouped_folds(groups, 5):
        assert set(groups[tr]).isdisjoint(set(groups[te]))
    assert sorted(np.concatenate([te for _, te in grouped_folds(groups, 5)])) == list(range(100))


def test_cross_fit_out_of_fold_predictions_complete():
    truth, y, noise = synth(300)
    groups = np.arange(300) // 2
    p, ws = cross_fit(truth, noise, y, groups)
    assert not np.isnan(p).any() and len(ws) == 5 and all(w >= 0.7 for w in ws)
