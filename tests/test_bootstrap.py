import numpy as np
import pytest

from mf.eval.bootstrap import ClusterBootstrap, draw_counts


def test_seeded_bootstrap_is_deterministic():
    g = np.repeat(np.arange(30), 2)
    losses = np.random.default_rng(3).random(60)
    a = ClusterBootstrap(g, B=2000, seed=0).ci(losses)
    b = ClusterBootstrap(g, B=2000, seed=0).ci(losses)
    assert a == b
    assert ClusterBootstrap(g, B=2000, seed=1).ci(losses) != a


def test_resamples_whole_events():
    # each event has 2 items with identical losses within the event; per-event means are 0 or 1.
    g = np.array([0, 0, 1, 1, 2, 2, 3, 3])
    losses = np.array([0, 0, 1, 1, 0, 0, 1, 1], dtype=float)
    bs = ClusterBootstrap(g, B=5000, seed=0)
    d = bs.draws(losses)
    # every draw is a multiple of 1/4 (4 events, each contributing 2 items of 0 or 1)
    assert np.allclose(np.round(d * 4), d * 4)
    # the multiplicity of a cluster scales all of its items: counts sum to n_clusters per draw
    assert (bs.counts.sum(axis=1) == 4).all()


def test_unequal_cluster_sizes_weighted_by_items():
    g = np.array([0, 1, 1, 1])
    losses = np.array([1.0, 0, 0, 0])
    bs = ClusterBootstrap(g, B=1, seed=0)
    bs.counts = np.array([[1.0, 1.0]])
    bs.denom = bs.counts @ bs.n_per
    assert bs.draws(losses)[0] == pytest.approx(0.25)


def test_paired_delta():
    rng = np.random.default_rng(0)
    g = np.arange(200)
    a = rng.random(200) * 0.2
    b = a + 0.05 + rng.normal(0, 0.01, 200)
    d = ClusterBootstrap(g, B=3000).delta(a, b)
    assert d["delta"] == pytest.approx(-0.05, abs=0.005)
    assert d["ci_high"] < 0 and d["frac_draws_below_0"] == 1.0


def test_draw_counts_shape():
    c = draw_counts(7, B=11, seed=0)
    assert c.shape == (11, 7) and (c.sum(axis=1) == 7).all()
