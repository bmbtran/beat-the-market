# market-forecaster — Implementation Plan

> Planning date: 2026-10-06. This file plus `RESOURCES.md` is the full spec. The implementer
> (a fresh Claude Code session) must build from these files alone. Every fact about external
> APIs below was checked on 2026-10-06 (live probes of the free Kalshi/Polymarket endpoints,
> docs pages for Anthropic and Exa). Where something is NOT verified it says **UNVERIFIED**
> and there is a mechanical check that settles it before money is spent.

---

## 0. TL;DR

An LLM forecasting agent that reproduces the **Halawi et al. 2024** retrieval + scratchpad +
ensemble pipeline, adds the **AIA Forecaster (Bridgewater AIA Labs, arXiv 2511.07678, Nov 2025)**
improvements (supervisor reconciliation + fixed Platt extremization + market-consensus ensemble)
as the headline, and evaluates everything **leak-free** against **real Kalshi + Polymarket prices
at the same timestamp**, then keeps a **forward, hash-chained, append-only live track record**.

- Reasoner: `claude-sonnet-5` (training-data cutoff **Jan 2026**, $2/$10 per MTok, Batch API −50%).
- Helper (query gen, relevance, leakage judge, summaries): `claude-haiku-4-5-20251001`
  (training-data cutoff **Jul 2025**, $1/$5 per MTok).
- Question window: created ≥ 2026-02-01, scheduled close & resolved ≤ 2026-09-30.
- Dataset: 250 binary questions (50 dev / 200 test) + 30-question pre-cutoff "leak canary" set.
- Budget: Exa ≈ $6.5 (hard cap $9/calendar month); Anthropic ≈ $23 backtest + ≈ $4.4 for 8 weeks
  of live (hard cap $30 total). Every external call cached to disk; reruns cost $0.
- Honest expectation: the agent will probably **not** beat the market price alone. The likely
  positive result is (a) AIA components beat the Halawi baseline, and (b) LLM ⊕ market beats
  market alone by a small margin. Whatever happens gets reported in `RESULTS.md`.

---

## 1. Goal and non-goals

### Goal
1. Build a reproducible forecasting system that outputs P(YES) for a binary prediction-market
   question at a historical timestamp `t0`, using only information available before `t0`.
2. Measure it against: the market price at `t0`, 0.5, the dev-set base rate, and its own ablations.
3. Show a measurable delta from one 2025–2026 method (AIA Forecaster) over the Halawi baseline,
   with paired cluster-bootstrap 95% CIs.
4. Run a forward live mode on open markets; log forecasts with timestamps in a tamper-evident,
   committed ledger; score them as they resolve.
5. Ship a blog-style README with charts, a static HTML report, and `RESULTS.md` containing real
   verify-script output.

### Non-goals
- No model training / fine-tuning / RL. API models only.
- No real-money trading, no order placement, no authenticated exchange APIs.
- No web app / server / database. Static HTML report only (no Streamlit).
- No multi-outcome (non-binary) markets, no scalar markets, no sports, no crypto-price or
  15-min/hourly/daily markets.
- Not trying to beat ForecastBench SOTA. Not claiming "superhuman".
- No GPU, no local models.

---

## 2. Headline paper decision (ranked shortlist)

| Rank | Paper | Implementable w/o training? | Expected measurable delta over Halawi | Verdict |
|---|---|---|---|---|
| **1** | **AIA Forecaster: Technical Report** (Bridgewater AIA Labs, arXiv 2511.07678, Nov 2025) | Yes — all prompting + statistics | Paper ablations: supervisor 0.1199→0.1125 Brier; fixed Platt √3 → 0.1076; market ensemble beats market alone on MarketLiquid (0.106 with weights ≈0.33 LLM / 0.67 market). Each component is a separate, cheap ablation arm. | **CHOSEN** |
| 2 | Beta-Bernoulli Calibrator (Dai, Teehan, Torabian, Ren; arXiv 2605.27668, May 2026) | Yes (lightweight calibrator), but needs fitting on outcomes + crowd forecasts | 0.146→0.125 Brier for Claude Sonnet 4 in their setup | Runner-up. Needs a training split larger than our 50 dev questions; high overfit risk at our N. Listed as stretch goal S3. |
| 3 | Consistency Checks for LM Forecasters / ArbitrageForecaster (Paleka et al., arXiv 2412.18544, Dec 2024) | Yes | Small, and needs many extra calls per question (related-question generation) | Dated (2024), cost multiplier ×3–5. Rejected. |
| 4 | Hindcast (arXiv 2607.14051, Jul 2026), TimeSeek (arXiv 2604.04220, Apr 2026), Pitfalls in Evaluating LM Forecasters (Paleka et al., arXiv 2506.00723, ICLR 2026), Foresight Arena (arXiv 2605.00420) | N/A — evaluation methodology | No accuracy delta; they improve trust in the numbers | **Adopted as eval protocol**, not headline (leakage controls, market-at-t0 scoring, horizon checkpoints, power analysis). |
| 5 | LLMs Can Teach Themselves to Better Predict the Future (arXiv 2502.05253), Outcome-based RL (arXiv 2505.17989), How Proper Scoring Rules Shape LLM Forecasting (arXiv 2608.28482) | No — training | — | Rejected (training). Mentioned in LEARNING.md. |

**Why AIA:** (1) It is a direct descendant of Halawi (same pipeline shape), so the delta is a clean
ablation, not a different system. (2) Every component is implementable with API calls and
~20 lines of statistics. (3) Two of its three components (Platt √3, market ensemble) cost **$0**
extra because they are post-hoc transforms of cached forecasts. (4) It is the only candidate that
explicitly studies "LLM vs. market consensus" on liquid prediction markets — exactly the
Kalshi/Polymarket story. (5) Bridgewater-authored → resonates with trading-firm readers.

**What we implement from AIA (and what we skip):**
- ✅ Ensembling of independent runs (K=5) — Halawi also does this; AIA confirms it is "not optional".
- ✅ **Supervisor agent**: reads the K rationales, names the disagreements, issues ≤2 new search
  queries, reads results, emits an updated forecast + confidence {high, medium, low}. If `high`,
  it replaces the trimmed mean; otherwise trimmed mean is kept.
- ✅ **Fixed Platt scaling / extremization**: `p' = sigmoid(√3 · logit(p))`, coefficient **not fit**
  (AIA used a fixed √3 following Neyman & Roughgarden 2022). Fitted variant reported only as a
  secondary row, fit on dev.
- ✅ **Market-consensus ensemble**: `p_ens = w·p_llm + (1−w)·p_mkt`, w ∈ [0,1] chosen by grouped
  5-fold cross-fitting on the test set (grouped by event) AND separately fit on dev; both reported.
- ❌ Fully agentic multi-step adaptive search (too many Exa calls for budget). We keep Halawi's
  fixed query-generation search; the supervisor provides the only adaptive search step.
- ❌ Their proprietary benchmarks.

---

## 3. Models, cutoffs, leakage window

Source: Anthropic Models overview + Sonnet 5 model page + Model deprecations page (fetched
2026-10-06; links in RESOURCES.md).

| Role | Model ID | Reliable knowledge cutoff | Training data cutoff | Price in/out per MTok | Status |
|---|---|---|---|---|---|
| Reasoner (backtest + live) | `claude-sonnet-5` | Jan 2026 | **Jan 2026** | $2 / $10 (Batch: $1 / $5) | Active (legacy), retirement not before 2027-06-30 |
| Helper | `claude-haiku-4-5-20251001` | Feb 2025 | **Jul 2025** | $1 / $5 | Active, retirement "not sooner than 2026-10-15" — **no deprecation notice yet**; Anthropic gives ≥60 days notice |
| Fallback helper | `claude-sonnet-5` (effort low) | Jan 2026 | Jan 2026 | $2 / $10 | used only if Haiku 4.5 is deprecated |
| Optional live-only arm (stretch) | `claude-sonnet-5-5` | Jun 2026 | Jun 2026 | $2 / $10 | NOT usable for backtest (cutoff inside window) |

Why not Sonnet 5.5 / Opus 5.5: their **training cutoff is Jun 2026**, leaving only ~3 months
(Jul–Sep 2026) of resolved questions — too few. Sonnet 5 gives an 8-month leak-free window
(Feb–Sep 2026) at the same price as Sonnet 5.5.

**Leak-free window rule (hard filter in code, tested):**
- `question.created_at >= 2026-02-01T00:00:00Z` (strictly after Sonnet 5's Jan 2026 training cutoff)
- `t0 >= question.created_at + 1 day`
- `question.scheduled_close <= 2026-09-30T23:59:59Z` and `resolved_at <= 2026-10-05`
- Haiku's earlier cutoff (Jul 2025) is automatically inside this window.

**API behavior facts the implementer MUST respect (from the claude-api skill / docs):**
- Python SDK is `anthropic==1.11.0` (1.x). In 1.x `temperature`, `top_p`, `top_k` are **removed**
  (passing them raises `TypeError`); Sonnet 5 also 400s on non-default sampling params.
  → Ensemble diversity comes from **5 different prompt variants** + default sampling randomness.
- SDK 1.x uses `httpx2` internally → `respx` will NOT intercept SDK traffic. Tests must mock at
  our own `LLMClient` interface (FakeLLM), never at HTTP level for Anthropic.
- Sonnet 5: thinking is adaptive by default; `thinking={"type":"disabled"}` is accepted. We use
  **thinking disabled + visible Halawi-style scratchpad**, `output_config={"effort":"medium"}`,
  `max_tokens=1200`. This makes output length (cost) predictable and the reasoning auditable.
- Haiku 4.5: no `effort` support; no thinking needed; `max_tokens` small.
- Always check `stop_reason`; treat `"refusal"` and `"max_tokens"` as a failed sample.
- Message Batches: `client.messages.batches.create/retrieve/results`; results arrive in any order,
  key by `custom_id` (we use the cache key hash, truncated to 64 chars).
- Prefill is not allowed (400) on Sonnet 5 → parse the final line instead.

---

## 4. Architecture

```
                         ┌───────────────────────── configs/default.toml ─────────────────────────┐
                         │ models, prices, budgets, filters, K, search params, prompt versions     │
                         └──────────────────────────────────────────────────────────────────────────┘
   FREE (public, no auth)                                       PAID (cached + budget-guarded)
 ┌────────────────────┐   ┌────────────────────┐
 │ Kalshi trade-api v2│   │ Polymarket Gamma + │
 │ /markets /series   │   │ CLOB /prices-history│
 │ /historical/*      │   └─────────┬──────────┘
 └─────────┬──────────┘             │
           ▼                        ▼
   data/kalshi.py            data/polymarket.py        (httpx, rate-limited, cached in cache/http/)
           └──────────┬─────────────┘
                      ▼
            data/dataset.py  ── filters, leak-window, t0 choice, price@t0, dedupe, split
                      │
                      ▼  data/dataset/questions.jsonl  (COMMITTED)
 ┌────────────────────────────────────────── per question ─────────────────────────────────────────┐
 │ retrieval/queries.py   Haiku: 2 search queries                         ─┐                         │
 │ retrieval/exa_client.py Exa /search (instant, n=5, endPublishedDate=t0−1d, highlights)          │
 │ retrieval/leakage.py   regex date scan + domain blocklist                │  all via              │
 │ retrieval/summarize.py Haiku (1 call): relevance 1–6, leak flag, summary │  core/cache.py        │
 │ forecast/reason.py     Sonnet 5 × K=5 prompt variants (Batch API)       │  core/budget.py       │
 │ forecast/aggregate.py  trimmed mean  ──────────────► ARM halawi          │  core/ledger.jsonl    │
 │ forecast/supervisor.py Sonnet 5 + ≤2 Exa queries (if spread>0.10) ──► ARM +supervisor          │
 │ forecast/calibrate.py  sigmoid(√3·logit p)  ($0) ──────────────────────► ARM +platt             │
 │ forecast/market_ensemble.py  w·p + (1−w)·p_mkt, grouped CV ($0) ───────► ARM ⊕market            │
 └──────────────────────────────────────────────────────────────────────────────────────────────────┘
                      ▼  data/runs/<run_id>/{evidence,samples,forecasts}.jsonl  (COMMITTED)
            eval/metrics.py  eval/bootstrap.py  eval/calibration.py
                      ▼
            eval/report.py → reports/metrics.json, reports/figures/*.png, reports/index.html,
                             README.md + RESULTS.md metric blocks (auto-inserted)

 LIVE:  live/select.py (open markets) → same pipeline (no date filter) → live/ledger.py
        → data/live/forecasts.jsonl (append-only, SHA-256 hash chain, COMMITTED)
        → mf score-live → data/live/scores.jsonl → report
```

---

## 5. Repository layout

```
market-forecaster/
  PLAN.md  RESOURCES.md  README.md  RESULTS.md  LEARNING.md
  pyproject.toml  uv.lock  .python-version (3.12)  .env.example  .gitignore
  configs/
    default.toml          # all knobs (see §9)
    pricing.toml          # $ per MTok per model; $ per Exa op (see §10)
  prompts/
    CHANGELOG.md
    lockfile.json         # {prompt_id: sha256} — test fails if a released prompt changes
    retrieval/query_gen_v1.md
    retrieval/relevance_summary_v1.md      # relevance + leak flag + summary, JSON out
    reasoning/r1_halawi_scratchpad_v1.md
    reasoning/r2_base_rates_v1.md
    reasoning/r3_inside_outside_view_v1.md
    reasoning/r4_premortem_both_sides_v1.md
    reasoning/r5_superforecaster_checklist_v1.md
    supervisor/disagreement_v1.md
    supervisor/update_v1.md
  src/mf/
    __init__.py
    cli.py                # typer app `mf`
    config.py             # pydantic Settings, loads toml + .env
    schemas.py            # pydantic models (§7)
    core/
      cache.py            # content-addressed JSON cache (§10)
      budget.py           # BudgetGuard + ledger (§10)
      pricing.py
      http.py             # httpx client w/ rate limiter + retries (tenacity) + http cache
      hashing.py          # canonical JSON + sha256
      timeutil.py         # all times UTC, ISO-8601 'Z'
    data/
      kalshi.py           # normalize live vs historical schemas
      polymarket.py
      prices.py           # price_at(t0) for both venues
      dataset.py          # build, filter, split, validate
    llm/
      client.py           # LLMClient protocol, AnthropicClient, FakeLLM
      batch.py            # Message Batches submit/poll/collect, cache-aware
      parse.py            # extract probability + JSON robustly
      prompts.py          # load prompt files, render (jinja2 StrictUndefined), hash
    retrieval/
      queries.py  exa_client.py  leakage.py  summarize.py  pipeline.py
    forecast/
      reason.py  aggregate.py  supervisor.py  calibrate.py  market_ensemble.py  pipeline.py
    eval/
      metrics.py  bootstrap.py  calibration.py  arms.py  report.py
    live/
      select.py  ledger.py  run.py  score.py
  scripts/
    verify.py             # the one command that proves the project works (§13)
    live_weekly.ps1       # Windows Task Scheduler helper (optional)
  tests/
    fixtures/{kalshi,polymarket,exa,anthropic}/...   # recorded real responses (small)
    test_*.py
  data/
    dataset/questions.jsonl          # committed
    dataset/canary_precutoff.jsonl   # committed
    runs/<run_id>/...                # committed (no raw article text)
    live/forecasts.jsonl  live/scores.jsonl   # committed, append-only
  reports/
    metrics.json  figures/*.png  index.html  leakage_audit.csv   # committed
  cache/                  # GITIGNORED (raw Exa text, raw LLM responses, HTTP)
  state/ledger.jsonl      # GITIGNORED raw spend ledger; summary copied to reports/spend.json (committed)
```

---

## 6. Data sources (verified 2026-10-06 by live probes)

### 6.1 Kalshi — base `https://api.elections.kalshi.com/trade-api/v2`, **no auth needed for reads**
| Endpoint | Use | Notes (verified) |
|---|---|---|
| `GET /series?category=<Cat>` | enumerate series by category | returned 868 Economics series; fields: `ticker, frequency, category, tags, title, settlement_sources` |
| `GET /markets?series_ticker=&status=settled&min_settled_ts=&max_settled_ts=&mve_filter=exclude&limit=1000&cursor=` | settled markets after the historical cutoff | Only one `status` per request; `min/max_settled_ts` only with `status=settled`; `min/max_close_ts` only with `status=closed` |
| `GET /historical/cutoff` | boundary | returned `market_settled_ts: 2026-08-07T00:00:00Z`. Markets settled before this are ONLY at `/historical/*` |
| `GET /historical/markets?series_ticker=&mve_filter=exclude&limit=1000&cursor=` | older settled markets | `security: []` (no auth) |
| `GET /historical/markets/{ticker}/candlesticks?start_ts=&end_ts=&period_interval=60` | price history for historical markets | candle fields: `price.{open,high,low,close,mean,previous}`, `yes_bid.{...}`, `yes_ask.{...}`, `volume`, `open_interest` — **plain names, dollar strings** e.g. `"0.2000"` |
| `GET /series/{series}/markets/{ticker}/candlesticks?start_ts=&end_ts=&period_interval=60` | price history for recent markets | candle fields use **`_dollars` / `_fp` suffixes**: `yes_bid.close_dollars`, `price.close_dollars`, `volume_fp`, `open_interest_fp`. Returns 404 for historical-tier markets. Empty-trade candles may contain only `price.previous_dollars`. |
| `GET /events?status=settled` | event metadata (`category`, `mutually_exclusive`) | |

Market object fields (verified): `ticker, event_ticker, title, yes_sub_title, no_sub_title, rules_primary,
rules_secondary, open_time, close_time, created_time, expected_expiration_time, latest_expiration_time,
settlement_ts, status ("finalized"), result ("yes"/"no"), market_type ("binary"), volume_fp,
open_interest_fp, last_price_dollars, can_close_early, expiration_value, mve_selected_legs, ...`

⚠ **LEAKAGE TRAP:** `expiration_value` holds the realized outcome text (e.g. `"Fed maintains rate"`),
`result`, `settlement_*`, `last_price_dollars`, `rules_secondary` (can be amended) must NEVER be
rendered into any prompt. The `Question` schema only carries whitelisted fields; a test asserts
that rendered prompts never contain the outcome string.

Rate limits: Basic tier 200 tokens/s, most requests cost 10 tokens → ~20 req/s. We throttle to
**5 req/s**, retry on 429 with exponential backoff (no retry header is sent).
Period intervals: 1, 60, 1440 minutes (60 used). **UNVERIFIED:** max candles per request — request
in ≤ 7-day windows at 60-min resolution to stay safe.
Categories to include (series `category`): Politics, Elections, Economics, World, Science and
Technology, Companies, Financials (non-intraday only), Climate and Weather (monthly/annual only),
Health. Exclude: Sports, Crypto, Entertainment-awards? (keep, low priority), any series with
`frequency` in {`fifteen_min`, `hourly`, `daily`} and all MVE (`mve_filter=exclude`).

### 6.2 Polymarket — no auth for reads
| Endpoint | Use | Notes (verified) |
|---|---|---|
| `GET https://gamma-api.polymarket.com/markets?closed=true&end_date_min=&end_date_max=&order=volumeNum&ascending=false&limit=&offset=` | resolved markets | returns a JSON **list**. Fields: `id, question, conditionId, slug, description, startDate, endDate, createdAt, closedTime, outcomes` (JSON-encoded string `"[\"Yes\", \"No\"]"`), `outcomePrices` (JSON-encoded string `"[\"0\", \"1\"]"`), `clobTokenIds` (JSON-encoded string, index 0 = first outcome), `volumeNum, umaResolutionStatus ("resolved"), negRisk, events[]` |
| `GET https://clob.polymarket.com/prices-history?market=<clobTokenId>&startTs=&endTs=&fidelity=60` | price history | returns `{"history":[{"t":unix,"p":float}]}`; both `startTs/endTs` and `interval=max` verified working on a resolved market |
Rate limits (docs): Gamma `/markets` 300 req/10s, `/events` 500 req/10s, CLOB `/prices-history` 1000 req/10s. We throttle to 5 req/s.
Resolution parse: only `outcomes == ["Yes","No"]`; YES won iff `outcomePrices == ["1","0"]`; skip anything else
(e.g. 50/50 splits). `category` is often null → classify via `events[].title`/tags or a keyword map, not required for filtering.
⚠ Leakage trap: `description` can get post-hoc clarifications. Strip paragraphs that contain
"Update"/"Clarification"/"UPDATE" (case-insensitive) before rendering; test it.

### 6.3 Dataset construction (deterministic; `mf build-dataset`)
1. Pull candidates from both venues within the window (§3). Kalshi needs BOTH `/historical/markets`
   (settled before 2026-08-07) and `/markets?status=settled` (after).
2. Filters: binary; Yes/No; created ≥ 2026-02-01; lifetime ≥ 7 days; scheduled close ≤ 2026-09-30;
   resolved cleanly; Kalshi `volume_fp ≥ 5,000` contracts, Polymarket `volumeNum ≥ $50,000`;
   allowed categories; not MVE; title length ≥ 15 chars.
3. **Scheduled vs. early close (selection-bias guard, Paleka "pitfalls"):** keep a market only if
   its *scheduled* end is inside the window. Polymarket: `endDate`. Kalshi: use
   `latest_expiration_time`/`expected_expiration_time` — **UNVERIFIED which field preserves the
   original schedule after an early close**; M2 includes a fixture test on a `can_close_early`
   market; if indistinguishable, exclude `can_close_early=true` markets whose `close_time` is
   >3 days before `expected_expiration_time`, and report the residual bias in RESULTS.md.
4. **Forecast time t0** = `min(created + 0.5·lifetime, close − 3 days)`, floored to the hour,
   and ≥ created + 1 day. (Single checkpoint per question to save budget; TimeSeek shows
   horizon matters → we record `horizon_days = close − t0` and report Brier by horizon bucket.)
5. **Market price at t0** (`p_mkt`): Kalshi = midpoint of `yes_bid.close` and `yes_ask.close` of
   the last 60-min candle ending ≤ t0 (fallback: `price.close`, then `price.previous`); require
   spread ≤ 0.10 else use last trade. Polymarket = last `p` with `t ≤ t0` within 6 h.
   Drop question if no price within 24 h before t0.
6. Drop if `p_mkt < 0.03` or `p_mkt > 0.97` (near-certain questions add noise, no signal).
7. **Correlation control:** at most 2 markets per `event_ticker` / Polymarket event; keep the
   two with highest volume. Bootstrap clusters by event.
8. Stratified sample to N=250 (target mix ≈ 50% Kalshi / 50% Polymarket, no category > 35%),
   seed 20261006. **Temporal split:** dev = 50 questions with earliest t0; test = remaining 200.
9. Canary set: 30 questions with the same filters but resolved **2025-03-01..2025-06-30**
   (before both models' training cutoffs). Used only for the no-retrieval arm as a leakage
   **detector**: if the model "knows" outcomes, canary Brier will be far below test Brier.
10. Write `questions.jsonl` + `dataset_card.json` (counts by venue/category/split, base rates,
    filter funnel counts).

---

## 7. Data schemas (pydantic v2, `src/mf/schemas.py`; JSONL on disk)

```python
class Question(BaseModel):            # data/dataset/questions.jsonl
    qid: str                          # "kalshi:KXFEDDECISION-26SEP-H25" | "poly:2252244"
    venue: Literal["kalshi","polymarket"]
    event_id: str                     # cluster id for bootstrap / dedupe
    title: str                        # question text shown to LLM
    description: str                  # rules_primary (Kalshi) or sanitized description (Poly)
    category: str
    created_at: datetime; t0: datetime; scheduled_close: datetime; resolved_at: datetime
    horizon_days: float
    p_mkt_t0: float                   # market baseline at t0 (never shown to LLM)
    p_mkt_source: Literal["mid","last_trade","previous"]
    volume: float
    outcome: int                      # 1 = YES, 0 = NO (never shown to LLM)
    split: Literal["dev","test","canary","live"]
    source_url: str

class Evidence(BaseModel):            # data/runs/<run>/evidence.jsonl  (no raw text committed)
    qid: str; query: str; url: str; title: str; published_date: datetime | None
    relevance: int                    # 1..6
    leak_flag: bool; leak_reason: str | None
    summary: str                      # ≤ 80 words, Haiku-written
    kept: bool

class Sample(BaseModel):              # data/runs/<run>/samples.jsonl
    qid: str; arm_base: Literal["retrieval","no_retrieval"]
    prompt_id: str; prompt_sha: str; sample_idx: int
    model: str; p: float | None; rationale: str
    stop_reason: str; input_tokens: int; output_tokens: int; cache_key: str

class ArmForecast(BaseModel):         # data/runs/<run>/forecasts.jsonl (one row per qid × arm)
    qid: str; arm: str; p: float; components: dict   # e.g. {"trimmed_mean":0.41,"supervisor":{...}}

class LiveRecord(BaseModel):          # data/live/forecasts.jsonl (append-only)
    seq: int; created_utc: datetime; qid: str; venue: str; title: str
    close_time: datetime; p_mkt_at_forecast: float
    p_halawi: float; p_aia: float; p_aia_market_ens: float
    model: str; prompt_versions: dict; code_git_sha: str
    prev_hash: str; hash: str         # sha256(canonical_json(record_without_hash) + prev_hash)

class LedgerEntry(BaseModel):         # state/ledger.jsonl
    ts: datetime; provider: Literal["anthropic","exa"]; op: str; model: str | None
    cache_key: str; cache_hit: bool; est_usd: float; actual_usd: float
    input_tokens: int | None; output_tokens: int | None; run_id: str
```

---

## 8. Prompt strategy

- All prompts live in `prompts/**.md` as Jinja2 templates with YAML front matter:
  `id, version, purpose, model_role, output_format`. Rendered with `StrictUndefined`.
- The **sha256 of the prompt file** is part of every LLM cache key → editing a prompt
  automatically invalidates only the affected cached calls.
- **Versioning rule:** a prompt that has been used in a committed run is frozen. Change = new file
  `_v2.md` + CHANGELOG entry + config switch. `prompts/lockfile.json` stores hashes;
  `tests/test_prompts.py` fails if a locked file's hash changes.
- Prompt content adapted (not copied — repo has no license) from Halawi's
  `llm_forecasting/prompts/{search_query,relevance,summarization,base_reasoning}.py`:
  - query_gen: given question + t0 → 2 diverse search queries (JSON list).
  - relevance_summary: given question, t0, and up to 10 article highlights → JSON array:
    `{idx, relevance 1–6, mentions_events_after_t0: bool, reveals_outcome: bool, summary}`.
  - reasoning r1..r5: all receive the same `QUESTION`, `RESOLUTION CRITERIA`, `TODAY = t0 date`,
    `EVIDENCE` (kept summaries sorted by date). Each ends with an exact final line
    `FINAL PROBABILITY: 0.xx`. r1 = Halawi scratchpad (rephrase, reasons for/against, aggregate,
    calibrate); r2 = base rates first; r3 = outside view then inside view; r4 = pre-mortem both
    directions; r5 = superforecaster checklist (Fermi-ize, update incrementally, avoid extremes
    unless warranted).
  - Every reasoning prompt states: "Today is {t0}. You have no information after this date. Do not
    assume the question has resolved."
  - supervisor/disagreement: input the K rationales + probabilities → JSON
    `{disagreements:[...], queries:[≤2 strings]}`; supervisor/update: input rationales + new
    evidence → JSON `{probability, confidence: "high"|"medium"|"low", reason}`.
- Parsing (`llm/parse.py`): regex `FINAL PROBABILITY:\s*([01](?:\.\d+)?|\.\d+)(%?)`, last match
  wins, percentages converted, clamp to [0.01, 0.99]; JSON parse tolerant of ```json fences.
  Unparseable → `p=None` (sample dropped; ≥3 of 5 valid required, else arm value = NaN and the
  question is reported as failed, never silently filled with 0.5).

---

## 9. Configuration (`configs/default.toml`, values the implementer should use)

```toml
[window]
created_min = "2026-02-01T00:00:00Z"
close_max   = "2026-09-30T23:59:59Z"
canary_resolved_min = "2025-03-01T00:00:00Z"
canary_resolved_max = "2025-06-30T23:59:59Z"

[models]
reasoner = "claude-sonnet-5"
helper   = "claude-haiku-4-5-20251001"
reasoner_effort = "medium"
reasoner_thinking = "disabled"
reasoner_max_tokens = 1200
helper_max_tokens = 1500

[pipeline]
k_samples = 5
reasoning_prompts = ["r1_halawi_scratchpad_v1","r2_base_rates_v1","r3_inside_outside_view_v1","r4_premortem_both_sides_v1","r5_superforecaster_checklist_v1"]
queries_per_question = 2
exa_type = "instant"          # fallback "fast" if M3 date-filter check fails
exa_num_results = 5
exa_highlight_max_chars = 1500
exa_end_offset_hours = 24      # endPublishedDate = t0 - 24h
exa_max_age_hours = -1         # prefer cached index copy (no live re-crawl of updated pages)
min_relevance = 4
max_evidence = 6
supervisor_spread_threshold = 0.10
supervisor_max_queries = 2
platt_coef = 1.7320508          # sqrt(3), fixed
trim = 1                       # drop 1 min + 1 max of 5
use_batch_api = true

[dataset]
n_total = 250
n_dev = 50
n_canary = 30
seed = 20261006
kalshi_min_volume = 5000
poly_min_volume = 50000
max_per_event = 2
p_mkt_min = 0.03
p_mkt_max = 0.97

[budget]
anthropic_total_usd = 30.0
anthropic_backtest_usd = 23.0
exa_monthly_usd = 9.0
per_run_default_usd = 5.0     # every CLI command also takes --max-usd

[exa_blocklist]
domains = ["polymarket.com","kalshi.com","manifold.markets","metaculus.com","predictit.org",
           "wikipedia.org","x.com","twitter.com","reddit.com","polymarketanalytics.com",
           "electionbettingodds.com","oddschecker.com"]
```

---

## 10. Caching + budget guard design

### Cache (`core/cache.py`)
- Content-addressed JSON files: `cache/<provider>/<key[:2]>/<key>.json`,
  `key = sha256(canonical_json({provider, endpoint, model, params, prompt_sha, sample_idx, schema_version}))`.
  Canonical JSON = `json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False, default=iso)`.
- Stored value: `{request, response, cost_usd, created_utc, sdk_version}`. Atomic write
  (write `*.tmp` then `os.replace`) — safe on Windows. UTF-8 explicitly.
- Modes via `MF_CACHE_MODE`: `readwrite` (default), `readonly` (cache miss → `CacheMiss` exception,
  **guarantees $0**; used by all tests and by `verify.py` reproduction), `refresh` (ignore reads; never
  used in normal flow).
- Free HTTP (Kalshi/Polymarket) also cached under `cache/http/` so dataset rebuilds are offline.
- Batch API: before submission each request's cache key is checked; only misses are submitted;
  `custom_id = key[:64]`; results are written to cache by key; batch id + status stored in
  `state/batches/<batch_id>.json` so a crashed poll can resume (`mf batch resume`).

### Budget guard (`core/budget.py`)
- `BudgetGuard.charge(provider, est_usd)` is called **before** every paid call (inside the cache
  wrapper, only on a miss). It sums `state/ledger.jsonl` (actual) + open reservations + `est_usd`
  and raises `BudgetExceeded` if it would exceed any of: provider total cap, Exa calendar-month cap,
  per-run `--max-usd`. After the call, the reservation is replaced by the actual cost.
- Estimates: Anthropic `est = (len(prompt_chars)/3.0)/1e6·in_price + max_tokens/1e6·out_price`
  (×0.5 if batch) — deliberately pessimistic. Actual = `usage.input_tokens`, `usage.output_tokens`,
  `usage.cache_read_input_tokens` × `pricing.toml`. Exa est from pricing table
  (`search[type] + num_results·$0.001` for highlights); actual = response `costDollars.total`.
- Batch: reserve the full batch's worst-case before `batches.create`.
- `mf budget` prints spend by provider/op/month, remaining, call counts. `reports/spend.json` is
  regenerated by `mf report` (committed, so readers see real cost).
- `--dry-run` on every paid command: renders all prompts, counts cache hits/misses, prints projected
  $ — makes **zero** network calls to paid APIs.
- **Pilot gate:** `mf forecast` on > 20 uncached questions refuses to run unless
  `state/pilot.json` exists (written by `mf pilot`, which runs 10 dev questions and records mean
  measured $/question) **and** `projected = mean_cost × n_uncached ≤ remaining budget`.

### `configs/pricing.toml` (verified 2026-10-06)
```toml
[anthropic."claude-sonnet-5"]        # $/MTok
input = 2.00
output = 10.00
cache_read = 0.20
cache_write_5m = 2.50
batch_discount = 0.5
[anthropic."claude-haiku-4-5-20251001"]
input = 1.00
output = 5.00
cache_read = 0.10
cache_write_5m = 1.25
batch_discount = 0.5
[anthropic."claude-sonnet-5-5"]
input = 2.00
output = 10.00
[exa]                                # $ per request / per page
search_instant = 0.004               # $4 / 1k requests (≤10 results)
search_fast = 0.007                  # $7 / 1k
search_auto = 0.007
extra_result = 0.001                 # per result above 10
contents_per_page_per_type = 0.001   # text / highlights / summary each
```
(Haiku cache-write price is the usual 1.25× rule — **UNVERIFIED**, irrelevant because we don't
write caches on Haiku.)

---

## 11. Budget table (estimates; pilot re-measures)

Token assumptions: helper call ≈ 5.6k in / 1.0k out per question (one batched relevance call) +
0.6k/0.15k query-gen; reasoner sample ≈ 1.8k in / 0.7k out (with retrieval), 1.0k / 0.7k (without);
supervisor ≈ 5k/0.4k + 6k/0.6k + one Haiku summary call, triggered on ~40% of questions.

| Stage | Questions | Exa calls | Exa $ | Anthropic $ |
|---|---|---|---|---|
| Smoke tests (M3) | 1 | 2 | 0.02 | 0.05 |
| Pilot (10 dev q, full pipeline, sync) | 10 | ~28 | 0.25 | 0.70 |
| Retrieval helpers (Haiku) | 250 | 500 searches × 5 highlights | 4.50 | 3.00 |
| Reasoning K=5 w/ retrieval (Batch) | 250 | – | – | 6.60 |
| No-retrieval K=5 (Batch), test only | 200 | – | – | 4.50 |
| Supervisor (≈40%, sync) | ~100 | 200 | 1.80 | 4.00 |
| Canary no-retrieval K=5 (Batch) | 30 | – | – | 0.70 |
| Dev prompt iterations (≤2 reruns of dev 50) | 100 | 0 (cached) | 0 | 4.00 |
| **Backtest subtotal** | | **≈730** | **≈$6.6** | **≈$23.5** |
| Live: 10 q/week × 8 weeks | 80 | ≈225 | ≈$2.0 (≈$1/month) | ≈$4.4 |
| **Total** | | | **≈$8.6 over 2+ months; ≤$9/month cap** | **≈$27.9 (cap $30)** |

Exa note: Exa gives new/free accounts **$10 credits per month** (pricing page, 2026-10-06), which
may cover all of this at $0. If `instant` fails the date-filter check and `fast` ($7/1k) is
needed, Exa rises to ≈$8.8 for the backtest → split the test-set retrieval across two calendar
months (the guard enforces this automatically).
Power note: N_test=200 → if paired ΔBrier SD ≈ 0.06, SE ≈ 0.0042 and the minimal detectable
effect (80% power, α=0.05) ≈ 0.012 before cluster correction. AIA's component deltas are
0.005–0.008 → **some ablations will likely be inconclusive; say so.** Stretch S1 expands to N=400
next month for ≈$5 Exa + ≈$12 Anthropic.
Fallback levers if pilot projects over cap (apply in order): K 5→4; `exa_num_results` 5→4;
N_test 200→175; drop canary to 20.

---

## 12. Evaluation protocol

**Arms** (all derived from cached samples; only rows marked $ cost money):
| Arm id | Description |
|---|---|
| `const_0.5` | 0.5 |
| `base_rate` | dev-set YES rate (fixed before looking at test) |
| `market` | `p_mkt_t0` |
| `noret_single` | no retrieval, r1 sample only ($) |
| `noret_ens` | no retrieval, K=5 trimmed mean ($) |
| `halawi_single` | retrieval, r1 sample only ($) |
| **`halawi`** | retrieval, K=5 trimmed mean — **the baseline system** ($) |
| `halawi_platt` | `halawi` + fixed √3 Platt |
| `halawi_sup` | `halawi` + supervisor ($) |
| **`aia`** | `halawi` + supervisor + fixed Platt — **the headline system** |
| `aia_platt_fit` | Platt coefficient fit on dev (secondary) |
| `market_ens_halawi` | grouped-CV blend of `halawi` with market |
| **`market_ens_aia`** | grouped-CV blend of `aia` with market |
| `market_ens_aia_devw` | blend weight fit on dev only |

**Metrics** (`eval/metrics.py`): Brier; log loss (probabilities clipped to [0.01,0.99]); Brier skill
score vs market `1 − B/B_mkt`; ECE (10 equal-width bins); Murphy decomposition
(reliability, resolution, uncertainty); accuracy@0.5; mean |p − p_mkt|.
**Uncertainty:** paired **cluster bootstrap** (resample events with replacement, B=10,000,
seed 0) for each arm's Brier and for Δ vs `halawi` and Δ vs `market`; report 95% percentile CIs
and the fraction of bootstrap draws with Δ<0.
**Breakdowns:** by venue, by category, by horizon bucket (<7d, 7–30d, >30d), by supervisor-triggered.
**Figures** (`reports/figures/`): reliability diagrams (aia, halawi, market) with bin counts;
Brier bar chart with CIs per arm; ΔBrier forest plot; scatter p_llm vs p_mkt colored by outcome;
Brier by horizon; cumulative live Brier vs market over time.
**Leakage checks (must all be reported):**
1. Canary: `noret_ens` Brier on canary vs on test. Expected: canary noticeably lower (model knows
   2025 outcomes). If test `noret_ens` is also suspiciously good (better than market), flag
   possible leakage in RESULTS.md.
2. `mf audit-leakage --n 50`: random 50 kept evidence items → CSV with url, published_date, summary,
   Haiku flags; implementer reviews by reading summaries and fills `human_verdict`; report leak rate
   (AIA found ≈1.65%).
3. Count of evidence dropped by each filter (null date, date > t0−24h, regex post-t0 date in text,
   blocklisted domain, Haiku leak flag).
4. Robustness row: `aia` re-scored after removing every question with any Haiku-flagged-but-kept
   item (should be ≈ unchanged).

---

## 13. Milestones (ordered; each has a mechanical acceptance check)

Convention: `uv run` everywhere. All tests run with `MF_CACHE_MODE=readonly` and must cost $0.
A milestone is done only when its check passes AND its output is pasted into `RESULTS.md`
under "Milestone log".

**M0 — Scaffold.** `uv init` (package `mf`, src layout), `.python-version`=3.12, pinned deps (RESOURCES.md),
`git init`, `.gitignore`, `.env.example`, empty `RESULTS.md` skeleton, typer `mf --help`.
✔ Check: `uv run python -c "import sys,mf;print(sys.version_info[:2])"` → `(3, 12)`;
`uv run mf --help` lists `build-dataset retrieve forecast evaluate report live score-live budget pilot audit-leakage verify-ledger`;
`git check-ignore .env cache/x state/x` prints all three paths.

**M1 — Core: hashing, cache, budget, pricing.**
✔ Check: `uv run pytest tests/test_cache.py tests/test_budget.py tests/test_pricing.py -q` → all pass, including:
cache hit returns identical object; readonly miss raises `CacheMiss`; key changes when prompt_sha
changes; `BudgetGuard` raises `BudgetExceeded` when est would cross cap; month rollover for Exa;
ledger sums correct; cost of `usage(in=1e6,out=1e6)` on sonnet-5 = 12.00, batch = 6.00.

**M2 — Market data + dataset (free APIs).**
Record fixtures: `uv run mf fixtures record` (saves ≤ 15 small real JSON responses to
`tests/fixtures/{kalshi,polymarket}` — includes one historical candle response, one live candle
response, one `can_close_early` market, one Polymarket negRisk market, one non-Yes/No market).
✔ Check 1: `uv run pytest tests/test_kalshi.py tests/test_polymarket.py tests/test_prices.py tests/test_dataset.py -q` passes
(both candle schemas normalize to the same `Candle`; price_at uses mid; outcome-text never in rendered prompt;
description "Update:" paragraphs stripped; non-Yes/No skipped; max 2 per event).
✔ Check 2: `uv run mf build-dataset` → prints filter funnel; writes `data/dataset/questions.jsonl`
with **250** rows and `canary_precutoff.jsonl` with **30**; then
`uv run python -m mf.data.dataset --validate` prints `OK 250 questions (dev=50 test=200) canary=30`
and asserts: all `created_at ≥ 2026-02-01`, `t0 > created_at`, `scheduled_close ≤ 2026-09-30`,
`0.03 ≤ p_mkt_t0 ≤ 0.97`, ≤2 per event, both venues ≥ 30%, no category > 35%.
If fewer than 250 candidates survive: relax `poly_min_volume` → $20k, `kalshi_min_volume` → 2,000,
then accept N ≥ 200 and record the deviation.

**M3 — LLM + Exa clients (first money: ≈ $0.07).**
`AnthropicClient` (sync + batch) and `FakeLLM` share a `LLMClient` protocol; `ExaClient` uses
`exa-py` (`exa.search(query, type=..., num_results=..., end_published_date=..., exclude_domains=..., contents={"highlights": {"max_characters": 1500}})`
— **UNVERIFIED** exact exa-py 2.x kwarg names; if they differ, call REST `POST https://api.exa.ai/search`
with `x-api-key` via httpx using the documented camelCase params; the REST shape is verified).
✔ Check 1: `uv run pytest tests/test_llm_client.py tests/test_exa_client.py tests/test_parse.py -q` (FakeLLM + recorded fixtures).
✔ Check 2 (spends ≈$0.07, requires `--allow-spend`): `uv run mf smoke --allow-spend` makes 1 Haiku call,
1 Sonnet 5 call, 1 tiny Batch (1 request), 2 Exa searches with `endPublishedDate=2026-03-01`;
prints each result; **asserts every Exa result has `publishedDate` ≤ endPublishedDate or null**;
saves responses as fixtures. If assertion fails with `instant`, re-run with `--exa-type fast` and set config.
Second run of the same command prints `cache_hit=True` for all 5 and `$0.00 spent`.

**M4 — Retrieval pipeline.** queries → Exa → dedupe → leakage filters → Haiku relevance/leak/summary → top-6 evidence.
✔ Check 1: `uv run pytest tests/test_retrieval.py tests/test_leakage.py -q`: synthetic article whose text says
"Updated September 3, 2026" with t0=2026-06-01 is dropped; blocklisted domain dropped; null-date dropped;
relevance < 4 dropped; FakeLLM pipeline produces ≤ 6 evidence items sorted by date.
✔ Check 2: `uv run mf retrieve --split dev --limit 10 --dry-run` prints projected $ and 0 network calls.

**M5 — Reasoning + Halawi aggregation + Batch path.**
✔ Check 1: `uv run pytest tests/test_reason.py tests/test_aggregate.py tests/test_batch.py -q`:
trimmed mean of [0.1,0.2,0.3,0.4,0.9] = 0.3; ≥3 valid samples rule; batch path with FakeLLM writes
cache keyed by custom_id and is resumable after simulated crash.
✔ Check 2 (pilot, ≈$1): `uv run mf pilot --n 10 --allow-spend` → writes `state/pilot.json` with
measured `usd_per_question`; prints `PROJECTED backtest: $X anthropic, $Y exa` and **exits non-zero if
projection > caps**. Paste output into RESULTS.md.

**M6 — Evaluation module.**
✔ Check: `uv run pytest tests/test_metrics.py tests/test_bootstrap.py -q`: Brier of all-0.5 = 0.25;
log loss of p=0.5 = ln 2; Murphy decomposition `REL − RES + UNC == Brier` (exact when bins = unique values);
bootstrap with seed is deterministic; cluster bootstrap resamples whole events; ECE of perfectly
calibrated synthetic data < 0.02 at n=100k.

**M7 — AIA components (headline).**
✔ Check: `uv run pytest tests/test_calibrate.py tests/test_supervisor.py tests/test_market_ensemble.py -q`:
`platt(0.5)=0.5`, `platt(0.7)≈0.8127` (±1e-3), monotone, symmetric; supervisor not triggered when
spread ≤ 0.10; on `confidence=high` replaces mean, else keeps it; market-ensemble grid search
recovers w≈1 when market is noise and w≈0 when LLM is noise on synthetic data; grouped CV never
puts the same event in train and test fold.

**M8 — Full backtest (main spend ≈ $20 + Exa ≈ $6).**
`uv run mf retrieve --split all --allow-spend` → `uv run mf forecast --split all --arms all --allow-spend`
→ `uv run mf evaluate` → `uv run mf report`.
✔ Check 1: `reports/metrics.json` exists with every arm in §12, `n_test=200` (or documented N), CIs present.
✔ Check 2 (reproducibility, $0): `MF_CACHE_MODE=readonly uv run mf evaluate --out reports/metrics_repro.json`
then `uv run python -c "import json;a=json.load(open('reports/metrics.json'));b=json.load(open('reports/metrics_repro.json'));assert a==b;print('REPRO OK')"`.
✔ Check 3: `uv run mf budget` shows Anthropic total ≤ $30 and Exa month ≤ $9.

**M9 — Leakage audit.**
✔ Check: `uv run mf audit-leakage --n 50` writes `reports/leakage_audit.csv` (50 rows); implementer fills
`human_verdict` ∈ {clean, leak, unsure} for all 50 (reading the summaries/urls — no extra API spend);
`uv run mf audit-leakage --summarize` prints leak rate; canary vs test numbers present in metrics.json.

**M10 — Live mode.**
`mf live --n 10 --allow-spend`: select open markets (both venues; close in 7–60 days; same category
filters and volume floors; skip already-forecast qids), run `aia` pipeline (Exa without date filter but
`endPublishedDate=now`), also record `halawi` and `p_mkt_at_forecast` (fetched in the same minute),
append to ledger with hash chain. `mf score-live` resolves closed ones → `data/live/scores.jsonl`.
✔ Check 1: `uv run pytest tests/test_live_ledger.py -q`: tampering any field of record i breaks
`verify` at i; append-only (writer opens with `"a"`, never rewrites).
✔ Check 2: `uv run mf live --n 3 --dry-run` (FakeLLM fixtures) works offline;
`uv run mf verify-ledger` → `LEDGER OK n=<count> head=<hash>`.
✔ Check 3: first real live run committed: `git log --oneline -- data/live/forecasts.jsonl` shows a commit.

**M11 — Report, README, RESULTS.**
`mf report` writes `reports/index.html` (single file, figures embedded as base64 PNG, tables via
jinja2), and replaces content between `<!-- METRICS:START -->`/`<!-- METRICS:END -->` in README.md
and RESULTS.md from metrics.json.
✔ Check: `uv run pytest tests/test_report.py -q` (README numbers == metrics.json numbers);
`uv run python scripts/verify.py` ends with `VERIFY: PASS metrics_sha=<sha>`.

Stretch (only after DoD): S1 expand to N=400 next month; S2 `claude-sonnet-5-5` live-only arm;
S3 Beta-Bernoulli calibrator on dev→test; S4 toy trading backtest (bet $1 when |p−p_mkt|>0.10,
include Kalshi fee formula, report with heavy caveats); S5 GitHub Pages for `reports/index.html`.

---

## 14. `scripts/verify.py` (the anti-premature-done gate)

Runs, in order, printing each command and its full output:
1. `pytest -q` with `MF_CACHE_MODE=readonly` (must pass, 0 network).
2. `python -m mf.data.dataset --validate`.
3. Reproduce metrics in readonly mode and compare to `reports/metrics.json` (byte-equal after canonical JSON).
4. `mf verify-ledger`.
5. `mf budget` (prints spend; fails if any cap exceeded).
6. Checks that `RESULTS.md` contains no `TODO`/`TBD`/`XX` placeholders and that every number
   between METRICS markers matches metrics.json.
7. `git status --porcelain` must not list `.env` or anything under `cache/`.
8. Prints `VERIFY: PASS metrics_sha=<sha256 of metrics.json>` or `VERIFY: FAIL <reason>` and exits 1.

### Anti-premature-done protocol (implementer MUST follow)
- Never write a metric by hand. All numbers come from `reports/metrics.json` via `mf report`.
- After each milestone, paste the **verbatim** check output into `RESULTS.md → Milestone log`.
- Do not mark the project done until `uv run python scripts/verify.py` prints `VERIFY: PASS` and that
  output is pasted (verbatim, including the sha) at the top of `RESULTS.md`.
- If a check fails, fix the cause; do not weaken a test or delete an assertion to make it pass. If an
  assertion is genuinely wrong, change it in a separate commit with a message explaining why.
- If the agent does not beat the market (likely), `RESULTS.md` must say so in the first paragraph and
  include a **"What didn't work"** section: which arms lost, by how much, CIs, and hypotheses
  (market efficiency, small N, retrieval quality, horizon mix). No cherry-picking subsets after the
  fact: the only breakdowns allowed in the headline are those pre-registered in §12.
- Pre-registration: before running M8 on the test split, commit `configs/default.toml`, all prompts,
  and a file `PREREGISTRATION.md` (copy of §12 arms + primary metric = Brier on test, primary
  comparisons = `aia` vs `halawi` and `market_ens_aia` vs `market`). Dev split may be used freely
  for prompt iteration; **test split is run once**. Any rerun on test must be logged in RESULTS.md.

---

## 15. Definition of Done (each item verifiable)

- [ ] `uv run python scripts/verify.py` → `VERIFY: PASS ...` (pasted in RESULTS.md).
- [ ] `uv run pytest -q` → ≥ 40 tests, all pass, $0 (readonly cache).
- [ ] `data/dataset/questions.jsonl` has 250 rows (or documented ≥200), validated by `--validate`.
- [ ] `reports/metrics.json` contains all arms in §12 with bootstrap CIs; `metrics_repro.json` identical.
- [ ] `reports/figures/` contains ≥ 5 PNGs: reliability, brier_bars, delta_forest, scatter_vs_market, brier_by_horizon.
- [ ] `reports/index.html` opens offline (no external URLs: `grep -c "http" reports/index.html` only in links section).
- [ ] `reports/leakage_audit.csv` 50 rows with `human_verdict` filled; leak rate in RESULTS.md.
- [ ] Canary vs test no-retrieval comparison present in RESULTS.md.
- [ ] `PREREGISTRATION.md` committed before the first test-split forecast commit (`git log --follow` order).
- [ ] `data/live/forecasts.jsonl` ≥ 10 records, `mf verify-ledger` OK, committed.
- [ ] `uv run mf budget` → Anthropic ≤ $30, Exa ≤ $9 in every month; `reports/spend.json` committed.
- [ ] `git ls-files | grep -E "^\.env$|^cache/|^state/"` → empty.
- [ ] README has the METRICS block, ≥ 3 embedded charts, a "Limitations" section, and reproduction commands.
- [ ] RESULTS.md has: headline table, "What didn't work", leakage section, cost section, milestone log.
- [ ] LEARNING.md written per outline (§18).

---

## 16. Git hygiene

`.gitignore`:
```
.env
.venv/
__pycache__/
*.pyc
cache/
state/
reports/metrics_repro.json
.pytest_cache/
*.tmp
```
- Commit: code, prompts, configs, `data/dataset/*.jsonl`, `data/runs/<run_id>/*.jsonl` (no raw
  article text — URLs, titles, dates, Haiku summaries ≤80 words only), `data/live/*`, `reports/*`,
  small `tests/fixtures/` (strip any headers/keys; Exa fixtures truncated to ≤ 1,500 chars per highlight).
- Do NOT commit: `.env`, `cache/` (raw Exa text = copyrighted third-party content + size), `state/`.
- `.env.example`: `ANTHROPIC_API_KEY=` and `EXA_API_KEY=` (empty). Code reads via python-dotenv;
  never logs keys; fixture recorder scrubs `x-api-key`/`authorization`.
- Commit style: one commit per milestone minimum; live runs commit as `live: <date> n=<k> head=<hash8>`.

---

## 17. README outline (blog-style)

1. **Title + one-line claim** (filled from metrics: e.g. "Claude Sonnet 5 forecaster vs. Kalshi &
   Polymarket: Brier X vs market Y on 200 leak-free questions").
2. Hero chart: Brier bars with CIs (const 0.5, base rate, halawi, aia, market, market⊕aia).
3. **Why this is hard**: markets are efficient; leakage makes most backtests lie.
4. **What I built**: architecture diagram; Halawi pipeline; AIA additions (one paragraph each).
5. **Leakage, taken seriously**: model cutoffs table, window, Exa date filters, blocklist, Haiku leak
   judge, canary result, human audit rate, `expiration_value` trap story.
6. **Results**: METRICS block, reliability diagram, ΔBrier forest plot, horizon chart, scatter vs market.
7. **What didn't work** (honest).
8. **Live track record**: table + cumulative chart, how the hash chain works, how to verify.
9. **Cost engineering**: cache design, budget guard, Batch API; real spend from `reports/spend.json`.
10. Reproduce: `uv sync`, `.env`, `MF_CACHE_MODE=readonly` caveat (cache not shipped → reruns need keys;
    committed run files allow re-evaluation for $0: `mf evaluate --from-runs`).
11. Limitations & future work; references (link RESOURCES.md).

## 18. LEARNING.md outline

Concepts: proper scoring rules (Brier, log loss, why proper); Murphy decomposition; calibration vs
resolution/sharpness; reliability diagrams & ECE pitfalls; extremization/Platt scaling and why
averaging pulls toward 0.5; trimmed mean vs median vs log-odds pooling; wisdom of crowds &
correlated errors (DPO monoculture paper 2606.26583); efficient-market hypothesis for prediction
markets, favorite–longshot bias; bid/ask mid vs last trade; temporal leakage taxonomy (model
cutoff, retrieval, question-text, selection/"resolved-early" bias); bootstrap and cluster bootstrap,
paired tests, statistical power/MDE; pre-registration; RAG design (query gen, reranking,
summarization); LLM-as-judge; prompt versioning & content-addressed caching; Batch API economics;
hash chains for tamper-evident logs.
Likely interview questions (with short model answers to write): "Why Brier and not accuracy?";
"Your model beats the market by 0.003 — is it real?"; "How do you know there's no leakage?";
"Why does averaging LLM samples under-confide and how does extremizing fix it?";
"How would you turn forecasts into trades — what about fees, spread, Kelly sizing, adverse
selection?"; "How would you scale to 10k questions within budget?"; "What's the difference
between calibration and sharpness?"; "Why cluster the bootstrap by event?"; "How would you detect
that a provider silently changed a model?"; "Design a live eval that can't be backfilled."

---

## 19. Risks and where a one-shot implementation is most likely to fail

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| 1 | **Kalshi schema split** (historical candles `close` vs live `close_dollars`; fixed-point strings; 404 from live endpoint on historical markets) | High | Fixtures for both in M2; single `normalize_candle()` with tests; route by `/historical/cutoff`. |
| 2 | **Candidate scarcity after filters** (Kalshi volume is dominated by sports/crypto/MVE) | Medium | Funnel printout; documented relaxation ladder (M2); Polymarket share can rise to 70%. |
| 3 | **Outcome leakage via question fields** (`expiration_value`, amended rules, Polymarket "Update:" text) | Medium | Whitelisted schema; sanitizer; test that rendered prompts never contain outcome text. |
| 4 | **Retrieval leakage** (Exa `publishedDate` wrong/missing; pages updated after publish; index embeddings may reflect later content) | Medium | endPublishedDate = t0−24h; drop null dates; regex post-t0 date scan; blocklist (markets, Wikipedia, social); Haiku leak judge; `maxAgeHours=-1`; human audit of 50; canary; robustness row. Residual risk acknowledged in README. |
| 5 | **Cost overrun** (output tokens larger than assumed; supervisor triggering more often; rerunning test) | Medium | Thinking disabled + max_tokens 1200; pessimistic pre-call estimates; hard caps; pilot gate; Batch API; cache. |
| 6 | **SDK drift**: anthropic 1.x removed `temperature`; `httpx2` breaks respx; exa-py kwarg names | High for a one-shot | Explicit in §3; FakeLLM at protocol level; Exa REST fallback with verified camelCase params. |
| 7 | Batch API complexity (polling, partial failures, resuming) | Medium | Cache-keyed custom_ids; `state/batches/`; resume command; sync fallback flag `use_batch_api=false` (costs 2× on reasoning — budget guard will catch it). |
| 8 | **Small N / inconclusive deltas** | High | Pre-registered primary comparisons; power note; honest reporting; S1 expansion. |
| 9 | Haiku 4.5 deprecation mid-project | Low-Med | Config switch to `claude-sonnet-5` helper; costs +~$3. |
| 10 | Refusals / unparseable outputs on political questions | Low | `stop_reason` handling; ≥3/5 rule; failure counts reported. |
| 11 | Windows issues (path length, cp1252 encoding, `os.replace` on open files, PowerShell env vars) | Medium | UTF-8 everywhere; short hashed paths; `MF_CACHE_MODE` documented as `$env:MF_CACHE_MODE="readonly"`. |
| 12 | Public API changes / rate limits (429 without retry header) | Low-Med | Throttle 5 req/s; tenacity backoff; HTTP cache makes rebuild offline. |
| 13 | Implementer fudging "done" | Medium | §14 protocol; verify.py; README numbers machine-inserted and tested. |
| 14 | Selection bias (questions that resolved early) | Medium | Scheduled-close filter (§6.3 step 3); report residual bias. |

## 20. What the user must provide
- `.env` with `ANTHROPIC_API_KEY` and `EXA_API_KEY` (never committed).
- Confirm acceptance of spend caps ($30 Anthropic total, $9/month Exa) — they are config values.
- ~10 minutes to fill `human_verdict` in the 50-row leakage audit CSV (or let the implementer do it and say so).
- Run `mf live` weekly (or register `scripts/live_weekly.ps1` in Task Scheduler) and `git push`.
