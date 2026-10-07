"""Proper scoring rules and decompositions (PLAN.md §12)."""

from __future__ import annotations

import numpy as np

LL_CLIP = (0.01, 0.99)


def _arr(p, y):
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    if p.shape != y.shape:
        raise ValueError("p and y shapes differ")
    return p, y


def brier(p, y) -> float:
    p, y = _arr(p, y)
    return float(np.mean((p - y) ** 2))


def log_loss(p, y) -> float:
    p, y = _arr(p, y)
    p = np.clip(p, *LL_CLIP)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier_skill(p, y, p_ref) -> float:
    """1 - B/B_ref (vs market when p_ref = p_mkt)."""
    return 1.0 - brier(p, y) / brier(p_ref, y)


def accuracy(p, y) -> float:
    p, y = _arr(p, y)
    return float(np.mean((p > 0.5) == (y == 1)))


def mean_abs_diff(p, q) -> float:
    return float(np.mean(np.abs(np.asarray(p, float) - np.asarray(q, float))))


def bin_index(p, n_bins: int = 10) -> np.ndarray:
    """Equal-width bins on [0,1]; p == 1 goes in the last bin."""
    p = np.asarray(p, dtype=float)
    return np.minimum((p * n_bins).astype(int), n_bins - 1)


def ece(p, y, n_bins: int = 10) -> float:
    p, y = _arr(p, y)
    idx = bin_index(p, n_bins)
    tot = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            tot += m.sum() * abs(p[m].mean() - y[m].mean())
    return float(tot / len(p))


def murphy(p, y, n_bins: int | None = None) -> dict:
    """Brier = REL - RES + UNC. Exact when bins are the unique forecast values (n_bins=None);
    with equal-width bins the identity holds up to within-bin forecast variance."""
    p, y = _arr(p, y)
    groups = np.unique(p, return_inverse=True)[1] if n_bins is None else bin_index(p, n_bins)
    obar = y.mean()
    rel = res = 0.0
    for g in np.unique(groups):
        m = groups == g
        n, fk, ok = m.sum(), p[m].mean(), y[m].mean()
        rel += n * (fk - ok) ** 2
        res += n * (ok - obar) ** 2
    N = len(p)
    return {"reliability": float(rel / N), "resolution": float(res / N), "uncertainty": float(obar * (1 - obar))}


def summary(p, y, p_mkt=None) -> dict:
    out = {"n": int(len(p)), "brier": brier(p, y), "log_loss": log_loss(p, y), "ece": ece(p, y),
           "accuracy": accuracy(p, y), **{f"murphy_{k}": v for k, v in murphy(p, y, n_bins=10).items()}}
    if p_mkt is not None:
        out["bss_vs_market"] = brier_skill(p, y, p_mkt)
        out["mean_abs_diff_vs_market"] = mean_abs_diff(p, p_mkt)
    return out
