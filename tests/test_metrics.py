import math

import numpy as np
import pytest

from mf.eval.calibration import reliability_table
from mf.eval.metrics import accuracy, brier, brier_skill, ece, log_loss, murphy, summary


def test_brier_constant_half():
    y = np.array([0, 1, 1, 0, 1])
    assert brier(np.full(5, 0.5), y) == pytest.approx(0.25)


def test_log_loss_half_is_ln2():
    assert log_loss([0.5, 0.5], [0, 1]) == pytest.approx(math.log(2))


def test_log_loss_clips():
    assert log_loss([0.0], [1]) == pytest.approx(-math.log(0.01))


def test_murphy_identity_exact_with_unique_bins():
    rng = np.random.default_rng(1)
    p = rng.choice([0.1, 0.25, 0.4, 0.6, 0.85], size=500)
    y = (rng.random(500) < p).astype(int)
    m = murphy(p, y, n_bins=None)
    assert m["reliability"] - m["resolution"] + m["uncertainty"] == pytest.approx(brier(p, y), abs=1e-12)


def test_ece_perfectly_calibrated_large_n():
    rng = np.random.default_rng(0)
    p = rng.random(100_000)
    y = (rng.random(100_000) < p).astype(int)
    assert ece(p, y) < 0.02


def test_ece_miscalibrated_is_large():
    rng = np.random.default_rng(0)
    p = rng.random(10_000)
    y = (rng.random(10_000) < 0.5).astype(int)
    assert ece(p, y) > 0.2


def test_skill_accuracy_summary():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.9, 0.1, 0.8, 0.3])
    mkt = np.full(4, 0.5)
    assert brier_skill(p, y, mkt) == pytest.approx(1 - brier(p, y) / 0.25)
    assert accuracy(p, y) == 1.0
    s = summary(p, y, mkt)
    assert s["n"] == 4 and "murphy_reliability" in s and s["mean_abs_diff_vs_market"] == pytest.approx(0.325)


def test_reliability_table_counts():
    rows = reliability_table([0.05, 0.15, 0.95, 1.0], [0, 0, 1, 1])
    assert sum(r["n"] for r in rows) == 4 and rows[9]["n"] == 2 and rows[9]["frac_yes"] == 1.0
