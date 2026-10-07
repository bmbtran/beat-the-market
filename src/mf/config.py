"""Settings: configs/default.toml + configs/pricing.toml + .env (keys only, never logged)."""

from __future__ import annotations

import os
import tomllib
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, field_validator

from mf.core import timeutil


def project_root() -> Path:
    env = os.environ.get("MF_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


class WindowCfg(BaseModel):
    created_min: datetime
    close_max: datetime
    resolved_max: datetime
    canary_resolved_min: datetime
    canary_resolved_max: datetime

    @field_validator("*", mode="before")
    @classmethod
    def _utc(cls, v):
        return timeutil.parse(v)


class ModelsCfg(BaseModel):
    reasoner: str
    helper: str
    reasoner_effort: str
    reasoner_thinking: str
    reasoner_max_tokens: int
    helper_max_tokens: int


class PipelineCfg(BaseModel):
    run_name: str
    k_samples: int
    reasoning_prompts: list[str]
    query_prompt: str
    relevance_prompt: str
    supervisor_disagreement_prompt: str
    supervisor_update_prompt: str
    queries_per_question: int
    exa_type: str
    exa_num_results: int
    exa_highlight_max_chars: int
    exa_end_offset_hours: int
    exa_max_age_hours: int
    min_relevance: int
    max_evidence: int
    supervisor_spread_threshold: float
    supervisor_max_queries: int
    platt_coef: float
    trim: int
    min_valid_samples: int
    use_batch_api: bool


class DatasetCfg(BaseModel):
    n_total: int
    n_dev: int
    n_canary: int
    seed: int
    kalshi_min_volume: float
    poly_min_volume: float
    max_per_event: int
    p_mkt_min: float
    p_mkt_max: float
    min_lifetime_days: float
    min_title_chars: int
    max_category_share: float


class BudgetCfg(BaseModel):
    anthropic_total_usd: float
    anthropic_backtest_usd: float
    exa_monthly_usd: float
    per_run_default_usd: float


class Settings(BaseModel):
    root: Path
    window: WindowCfg
    models: ModelsCfg
    pipeline: PipelineCfg
    dataset: DatasetCfg
    budget: BudgetCfg
    exa_blocklist: list[str]
    pricing: dict

    @property
    def cache_dir(self) -> Path:
        return Path(os.environ.get("MF_CACHE_DIR", self.root / "cache"))

    @property
    def state_dir(self) -> Path:
        return Path(os.environ.get("MF_STATE_DIR", self.root / "state"))

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def run_dir(self) -> Path:
        return self.data_dir / "runs" / self.pipeline.run_name


def load_settings(root: Path | None = None) -> Settings:
    root = root or project_root()
    with open(root / "configs" / "default.toml", "rb") as f:
        cfg = tomllib.load(f)
    with open(root / "configs" / "pricing.toml", "rb") as f:
        pricing = tomllib.load(f)
    return Settings(
        root=root,
        window=cfg["window"],
        models=cfg["models"],
        pipeline=cfg["pipeline"],
        dataset=cfg["dataset"],
        budget=cfg["budget"],
        exa_blocklist=cfg["exa_blocklist"]["domains"],
        pricing=pricing,
    )


@lru_cache(maxsize=1)
def settings() -> Settings:
    return load_settings()


def load_env() -> None:
    """Load API keys from .env into os.environ (never printed)."""
    from dotenv import load_dotenv

    load_dotenv(project_root() / ".env", override=False)


def require_key(name: str) -> str:
    load_env()
    val = os.environ.get(name, "").strip()
    if not val:
        raise RuntimeError(f"{name} is not set (put it in .env; see .env.example)")
    return val
