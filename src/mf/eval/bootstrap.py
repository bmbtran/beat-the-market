"""Paired cluster bootstrap (resample whole events with replacement), B=10,000, seed 0.

Per-event loss sums are precomputed, so each draw's mean loss is (counts @ S) / (counts @ n):
one matrix product for all B draws. Deltas between arms reuse the same draws (paired).
"""

from __future__ import annotations

import numpy as np

B_DEFAULT = 10_000
SEED = 0


def draw_counts(n_clusters: int, B: int = B_DEFAULT, seed: int = SEED) -> np.ndarray:
    """B x n_clusters matrix: how many times each cluster appears in each bootstrap draw."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_clusters, size=(B, n_clusters))
    counts = np.zeros((B, n_clusters), dtype=np.int32)
    np.add.at(counts, (np.repeat(np.arange(B), n_clusters), idx.ravel()), 1)
    return counts


class ClusterBootstrap:
    def __init__(self, groups, B: int = B_DEFAULT, seed: int = SEED):
        groups = np.asarray(groups)
        self.clusters, self.inv = np.unique(groups, return_inverse=True)
        self.n_per = np.bincount(self.inv).astype(float)
        self.counts = draw_counts(len(self.clusters), B, seed).astype(float)
        self.denom = self.counts @ self.n_per

    def draws(self, losses) -> np.ndarray:
        """Bootstrap distribution of the mean of per-item `losses`."""
        s = np.bincount(self.inv, weights=np.asarray(losses, dtype=float), minlength=len(self.clusters))
        return (self.counts @ s) / self.denom

    def ci(self, losses, alpha: float = 0.05) -> dict:
        d = self.draws(losses)
        lo, hi = np.percentile(d, [100 * alpha / 2, 100 * (1 - alpha / 2)])
        return {"mean": float(np.mean(losses)), "ci_low": float(lo), "ci_high": float(hi)}

    def delta(self, losses_a, losses_b, alpha: float = 0.05) -> dict:
        """a - b (negative = a better for losses)."""
        diff = np.asarray(losses_a, float) - np.asarray(losses_b, float)
        d = self.draws(diff)
        lo, hi = np.percentile(d, [100 * alpha / 2, 100 * (1 - alpha / 2)])
        return {"delta": float(np.mean(diff)), "ci_low": float(lo), "ci_high": float(hi),
                "frac_draws_below_0": float(np.mean(d < 0))}
