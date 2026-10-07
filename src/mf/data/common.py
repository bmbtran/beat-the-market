"""Venue-neutral candidate + candle types used while building the dataset."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Unified category names (Kalshi's names; Polymarket tags are mapped onto these).
ALLOWED_CATEGORIES = {
    "Politics", "Elections", "Economics", "World", "Science and Technology", "Companies",
    "Financials", "Climate and Weather", "Health", "Entertainment",
}
LOW_PRIORITY_CATEGORIES = {"Entertainment"}


@dataclass
class Candle:
    end_ts: int
    yes_bid: float | None
    yes_ask: float | None
    price_close: float | None
    price_previous: float | None
    volume: float | None


@dataclass
class Candidate:
    qid: str
    venue: str  # "kalshi" | "polymarket"
    event_id: str
    title: str
    description: str
    category: str
    created_at: datetime
    scheduled_close: datetime
    actual_close: datetime
    resolved_at: datetime
    volume: float
    outcome: int
    source_url: str
    can_close_early: bool = False
    expected_expiration: datetime | None = None
    price_ref: dict = field(default_factory=dict)  # venue-specific handle for price history


def to_float(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
