"""Reliability-diagram data (equal-width bins with counts)."""

from __future__ import annotations

import numpy as np

from mf.eval.metrics import bin_index


def reliability_table(p, y, n_bins: int = 10) -> list[dict]:
    p = np.asarray(p, float)
    y = np.asarray(y, float)
    idx = bin_index(p, n_bins)
    rows = []
    for b in range(n_bins):
        m = idx == b
        rows.append({"bin_low": b / n_bins, "bin_high": (b + 1) / n_bins, "n": int(m.sum()),
                     "mean_p": float(p[m].mean()) if m.any() else None,
                     "frac_yes": float(y[m].mean()) if m.any() else None})
    return rows
