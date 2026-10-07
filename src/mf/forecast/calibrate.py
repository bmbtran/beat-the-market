"""Extremization / Platt scaling. AIA uses a FIXED coefficient sqrt(3) (Neyman & Roughgarden 2022):
p' = sigmoid(a * logit(p)). A fitted variant (fit on dev, applied to test) is reported as secondary."""

from __future__ import annotations

import math

import numpy as np

SQRT3 = math.sqrt(3.0)
EPS = 1e-6


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


def platt(p, coef: float = SQRT3, intercept: float = 0.0):
    out = sigmoid(coef * logit(p) + intercept)
    return float(out) if np.ndim(out) == 0 else out


def fit_platt(p, y, fit_intercept: bool = False) -> tuple[float, float]:
    """Fit a (and optionally b) in sigmoid(a*logit(p)+b) by maximum likelihood (Newton / L-BFGS)."""
    from scipy.optimize import minimize

    x = logit(p)
    y = np.asarray(y, dtype=float)

    def nll(theta):
        a, b = theta[0], (theta[1] if fit_intercept else 0.0)
        q = np.clip(sigmoid(a * x + b), EPS, 1 - EPS)
        return -np.sum(y * np.log(q) + (1 - y) * np.log(1 - q))

    res = minimize(nll, x0=np.array([1.0, 0.0] if fit_intercept else [1.0]), method="L-BFGS-B")
    a = float(res.x[0])
    b = float(res.x[1]) if fit_intercept else 0.0
    return a, b
