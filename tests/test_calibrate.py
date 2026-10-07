import numpy as np
import pytest

from mf.forecast.calibrate import SQRT3, fit_platt, platt


def test_fixed_platt_values():
    assert platt(0.5) == pytest.approx(0.5)
    assert platt(0.7) == pytest.approx(0.8127, abs=1e-3)
    assert SQRT3 == pytest.approx(1.7320508)


def test_monotone_and_symmetric():
    xs = np.linspace(0.01, 0.99, 99)
    ys = platt(xs)
    assert np.all(np.diff(ys) > 0)
    assert np.allclose(platt(1 - xs), 1 - ys)
    assert np.all(np.abs(ys - 0.5) >= np.abs(xs - 0.5) - 1e-12)  # extremizes


def test_fit_recovers_coefficient():
    rng = np.random.default_rng(0)
    true_p = rng.uniform(0.05, 0.95, 20_000)
    y = (rng.random(20_000) < true_p).astype(int)
    shrunk = platt(true_p, coef=1 / 1.8)  # under-confident forecasts
    a, b = fit_platt(shrunk, y)
    assert a == pytest.approx(1.8, abs=0.1) and b == 0.0
