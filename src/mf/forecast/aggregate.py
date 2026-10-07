"""Halawi-style aggregation: trimmed mean of the valid samples; >= min_valid samples required."""

from __future__ import annotations

from mf.schemas import Sample


def trimmed_mean(ps: list[float], trim: int = 1) -> float:
    xs = sorted(ps)
    if len(xs) > 2 * trim:
        xs = xs[trim: len(xs) - trim]
    return sum(xs) / len(xs)


def valid_ps(samples: list[Sample]) -> list[float]:
    return [s.p for s in sorted(samples, key=lambda s: s.sample_idx) if s.p is not None]


def aggregate(samples: list[Sample], min_valid: int = 3, trim: int = 1) -> float | None:
    """None (reported as a failed question, never silently 0.5) if fewer than min_valid samples parse."""
    ps = valid_ps(samples)
    if len(ps) < min_valid:
        return None
    return trimmed_mean(ps, trim)


def spread(samples: list[Sample]) -> float:
    ps = valid_ps(samples)
    return (max(ps) - min(ps)) if ps else 0.0
