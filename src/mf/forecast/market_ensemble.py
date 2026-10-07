"""LLM + market consensus ensemble (AIA): p_ens = w * p_llm + (1 - w) * p_mkt.

w is chosen by grid search minimizing Brier. Two variants are reported:
  * grouped 5-fold cross-fitting on the test set (folds grouped by event: no event in both train and test)
  * w fit on the dev set only, applied to test
"""

from __future__ import annotations

import numpy as np
from sklearn.model_selection import GroupKFold

GRID = np.round(np.linspace(0.0, 1.0, 101), 2)


def blend(p_llm, p_mkt, w: float):
    return w * np.asarray(p_llm, dtype=float) + (1 - w) * np.asarray(p_mkt, dtype=float)


def fit_weight(p_llm, p_mkt, y) -> float:
    p_llm, p_mkt, y = (np.asarray(a, dtype=float) for a in (p_llm, p_mkt, y))
    briers = [np.mean((blend(p_llm, p_mkt, w) - y) ** 2) for w in GRID]
    return float(GRID[int(np.argmin(briers))])  # argmin -> smallest w on ties (deterministic)


def grouped_folds(groups, n_splits: int = 5):
    groups = np.asarray(groups)
    n = min(n_splits, len(np.unique(groups)))
    return list(GroupKFold(n_splits=n).split(np.zeros(len(groups)), groups=groups))


def cross_fit(p_llm, p_mkt, y, groups, n_splits: int = 5) -> tuple[np.ndarray, list[float]]:
    """Out-of-fold blended predictions and the per-fold weights."""
    p_llm, p_mkt, y = (np.asarray(a, dtype=float) for a in (p_llm, p_mkt, y))
    out = np.full(len(y), np.nan)
    ws = []
    for tr, te in grouped_folds(groups, n_splits):
        w = fit_weight(p_llm[tr], p_mkt[tr], y[tr])
        ws.append(w)
        out[te] = blend(p_llm[te], p_mkt[te], w)
    return out, ws
