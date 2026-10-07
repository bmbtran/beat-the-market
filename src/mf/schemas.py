"""Pydantic v2 schemas (PLAN.md §7). All datetimes are aware UTC."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from mf.core import timeutil


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def _parse_dt(cls, v, info):
        field = cls.model_fields.get(info.field_name)
        if field is not None and field.annotation in (datetime, datetime | None) and v is not None:
            return timeutil.parse(v)
        return v

    @field_serializer("*", when_used="json")
    def _ser(self, v):
        if isinstance(v, datetime):
            return timeutil.iso(v)
        return v


class Question(_Base):
    qid: str
    venue: Literal["kalshi", "polymarket"]
    event_id: str
    title: str
    description: str
    category: str
    created_at: datetime
    t0: datetime
    scheduled_close: datetime
    resolved_at: datetime
    horizon_days: float
    p_mkt_t0: float
    p_mkt_source: Literal["mid", "last_trade", "previous"]
    volume: float
    outcome: int
    split: Literal["dev", "test", "canary", "live"]
    source_url: str


def prompt_fields(q: Question) -> dict:
    """The ONLY question data any prompt template may see. Never outcome, p_mkt, resolution
    dates, volume or URLs (leakage guard, tested in tests/test_dataset.py and tests/test_reason.py)."""
    return {
        "title": q.title,
        "description": q.description,
        "today": q.t0.strftime("%Y-%m-%d"),
        "scheduled_close": q.scheduled_close.strftime("%Y-%m-%d"),
    }


class Evidence(_Base):
    qid: str
    query: str
    url: str
    title: str
    published_date: datetime | None
    relevance: int
    leak_flag: bool
    leak_reason: str | None
    summary: str
    kept: bool


class Sample(_Base):
    qid: str
    arm_base: Literal["retrieval", "no_retrieval"]
    prompt_id: str
    prompt_sha: str
    sample_idx: int
    model: str
    p: float | None
    rationale: str
    stop_reason: str
    input_tokens: int
    output_tokens: int
    cache_key: str


class ArmForecast(_Base):
    qid: str
    arm: str
    p: float | None
    components: dict


class LiveRecord(_Base):
    seq: int
    created_utc: datetime
    qid: str
    venue: str
    title: str
    close_time: datetime
    p_mkt_at_forecast: float
    p_halawi: float | None
    p_aia: float | None
    p_aia_market_ens: float | None
    model: str
    prompt_versions: dict
    code_git_sha: str
    prev_hash: str
    hash: str


class LedgerEntry(_Base):
    ts: datetime
    provider: Literal["anthropic", "exa"]
    op: str
    model: str | None
    cache_key: str
    cache_hit: bool
    est_usd: float
    actual_usd: float
    input_tokens: int | None
    output_tokens: int | None
    run_id: str
