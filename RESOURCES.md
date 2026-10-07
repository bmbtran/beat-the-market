# RESOURCES — market-forecaster

Checked 2026-10-06. "Verified" = fetched/probed on that date.

## Papers

### Base
- **Halawi, Zhang, Chen, Steinhardt (2024). Approaching Human-Level Forecasting with Language Models.** NeurIPS 2024. https://arxiv.org/abs/2402.18563 — The base pipeline: query generation → retrieval → relevance filtering → summarization → scratchpad reasoning → ensemble (trimmed mean).
  - Code: https://github.com/dannyallover/llm_forecasting (verified public; **no license file**, so adapt the ideas and prompts with attribution, don't copy code verbatim). Prompts are in `llm_forecasting/prompts/{search_query,relevance,summarization,base_reasoning,ensemble_reasoning}.py`; their data pickles are in `notebooks/results/data/`.

### Headline improvement (chosen)
- **AIA Forecaster: Technical Report** (Bridgewater AIA Labs, Nov 2025). https://arxiv.org/abs/2511.07678 (HTML: https://arxiv.org/html/2511.07678v1) — Supervisor reconciliation (0.1199→0.1125 Brier), fixed Platt √3 extremization (→0.1076), and LLM+market ensemble that beats market alone on MarketLiquid. Supplies all three headline components.
- Neyman & Roughgarden (2022). Are You Smarter Than a Random Expert? The Robust Aggregation of Substitutable Signals. https://arxiv.org/abs/2111.03153 — Source of the √3 extremization coefficient AIA uses.

### Shortlist (not chosen, cited)
- Dai, Teehan, Torabian, Ren (May 2026). Aligning LLMs with Human Uncertainty: A Beta-Bernoulli Calibrator for LLM Forecasting. https://arxiv.org/abs/2605.27668 — Runner-up; lightweight calibrator using crowd signal; needs a bigger fit split (stretch S3).
- Paleka et al. (Dec 2024). Consistency Checks for Language Model Forecasters. https://arxiv.org/abs/2412.18544 — Arbitrage/consistency metric; rejected (×3–5 calls).
- Turtel et al. (2025). LLMs Can Teach Themselves to Better Predict the Future. https://arxiv.org/abs/2502.05253 — Self-play + DPO; training, excluded.
- Turtel et al. (2025). Outcome-based Reinforcement Learning to Predict the Future. https://arxiv.org/abs/2505.17989 — RL; training, excluded.
- How Proper Scoring Rules Shape LLM Forecasting (Aug 2026). https://arxiv.org/abs/2608.28482 — Training with scoring rules; excluded; good LEARNING.md material.

### Evaluation methodology (adopted)
- Paleka, Goel, Geiping, Tramèr (2025). Pitfalls in Evaluating Language Model Forecasters. ICLR 2026. https://arxiv.org/abs/2506.00723 — Temporal-leakage taxonomy and selection bias; drives §6.3 and §12 leakage checks.
- Ye et al. (Jul 2026). Hindcast: Replaying Prediction Markets to Evaluate LLM Forecasters. https://arxiv.org/abs/2607.14051 — Score vs. outcome AND market price at t0; retrieval helps only when prior discussion existed.
- Mostafa, Shastri, Lee (Apr 2026). TimeSeek: Temporal Reliability of Agentic Forecasters. https://arxiv.org/abs/2604.04220 — 150 Kalshi markets × 5 checkpoints; LLMs best early/high-uncertainty; ensembles don't beat market. Motivates horizon breakdown.
- Nechepurenko & Shuvalov (May 2026). Foresight Arena. https://arxiv.org/abs/2605.00420 — Power analysis: ~350 predictions to detect α=0.02 edge vs market; grounds our sample-size honesty.
- Karger et al. (2024). ForecastBench. https://arxiv.org/abs/2409.19839 ; code https://github.com/forecastingresearch/forecastbench — Standard benchmark, leakage-free by construction; context for AIA's claims.
- Prediction Arena (Apr 2026). https://arxiv.org/abs/2604.07355 — Frontier models trading live on Kalshi/Polymarket lost money (−16% to −31%); sobering context.

### Context / LEARNING.md material
- Beyond Forecasting: The Belief-to-Trade Layer in Prediction-Market Agents (Jul 2026). https://arxiv.org/abs/2607.03015 ; code https://github.com/Alchemist-X/predict-raven — Forecast accuracy ≠ trading P&L.
- When do prophets profit in prediction markets? (Jul 2026). https://arxiv.org/abs/2607.06166 — Same theme.
- Preference Optimization Drives Monoculture in LLM Prediction Markets (Jun 2026). https://arxiv.org/abs/2606.26583 — Correlated LLM errors (ρ≈0.70); why multi-prompt ensembles of one model give limited diversity.
- Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets (Feb 2026). https://arxiv.org/abs/2602.19520 — Market calibration varies by domain; motivates category breakdown.
- LLM-based Agents for Forecasting and Prediction (survey, Aug 2026). https://arxiv.org/abs/2608.23058 — Survey for background reading.
- Schoenegger et al. (2024). Wisdom of the Silicon Crowd. https://arxiv.org/abs/2402.19379 — LLM ensembles rival human crowds.

## APIs — market data (free, no auth for reads)
- Kalshi API docs: https://docs.kalshi.com — base `https://api.elections.kalshi.com/trade-api/v2` (verified).
  - Get Markets: https://docs.kalshi.com/api-reference/market/get-markets — filter params and which combinations are allowed.
  - Historical data guide: https://docs.kalshi.com/getting_started/historical_data — `/historical/cutoff`, `/historical/markets`, `/historical/markets/{ticker}/candlesticks` (cutoff was 2026-08-07 when probed).
  - Get Historical Markets: https://docs.kalshi.com/api-reference/historical/get-historical-markets — `security: []` (no auth).
  - Rate limits: https://docs.kalshi.com/getting_started/rate_limits — Basic 200 read tokens/s, 10 tokens per request.
  - Doc index for anything else: https://docs.kalshi.com/llms.txt
- Polymarket docs: https://docs.polymarket.com
  - Gamma markets: `https://gamma-api.polymarket.com/markets` (verified fields: outcomes / outcomePrices / clobTokenIds are JSON-encoded strings).
  - CLOB price history: `https://clob.polymarket.com/prices-history?market=<token_id>&startTs=&endTs=&fidelity=` (verified).
  - Rate limits: https://docs.polymarket.com/quickstart/introduction/rate-limits — Gamma /markets 300 req/10s; CLOB /prices-history 1000 req/10s.

## APIs — paid
- Exa search reference: https://exa.ai/docs/reference/search — `type` (instant|fast|auto|deep-lite|deep|deep-reasoning), `numResults` 1–100, `startPublishedDate`/`endPublishedDate` (ISO 8601), `includeDomains`/`excludeDomains`, `category`, `contents.{text,highlights,summary,maxAgeHours}`; auth header `x-api-key`; response has `costDollars`.
- Exa pricing: https://exa.ai/pricing — instant $4/1k, fast/auto $7/1k (≤10 results), +$1/1k extra results, contents $1/1k pages per content type, $10 free credits monthly (verified 2026-10-06).
- Exa Python SDK: https://pypi.org/project/exa-py/ (2.25.0) and https://github.com/exa-labs/exa-py — check kwarg names; REST fallback is fine.
- Anthropic Models overview (IDs, prices, cutoffs): https://platform.claude.com/docs/en/about-claude/models/overview — Sonnet 5.5/Opus 5.5 cutoff Jun 2026; Haiku 4.5 training cutoff Jul 2025.
- Claude Sonnet 5 page: https://platform.claude.com/docs/en/models/sonnet-5/overview — training/reliable cutoff Jan 2026; $2/$10; Batch −50%; non-default temperature → 400.
- Claude Haiku 4.5 page: https://platform.claude.com/docs/en/models/haiku-4-5/overview
- Model deprecations: https://platform.claude.com/docs/en/about-claude/model-deprecations — Haiku 4.5 "not sooner than Oct 15 2026", Sonnet 5 "not sooner than Jun 30 2027"; ≥60 days notice.
- Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Anthropic Transparency Hub (cutoff definitions): https://www.anthropic.com/transparency
- Batch processing: https://platform.claude.com/docs/en/build-with-claude/batch-processing
- Prompt caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Effort / thinking: https://platform.claude.com/docs/en/build-with-claude/effort , https://platform.claude.com/docs/en/build-with-claude/thinking
- Anthropic Python SDK: https://github.com/anthropics/anthropic-sdk-python (see MIGRATION.md for 0.x→1.x: httpx→httpx2, `temperature/top_p/top_k` removed).

## Pinned versions (PyPI, 2026-10-06)
| Package | Version | Why |
|---|---|---|
| Python | 3.12 (via `uv python pin 3.12`) | numpy/scipy 3.12+; avoid 3.14 wheel gaps |
| uv | ≥ 0.11 (local 0.11.2) | env + lockfile |
| anthropic | 1.11.0 | Claude API, Batches |
| exa-py | 2.25.0 | Exa search (REST fallback allowed) |
| httpx | 0.28.1 | Kalshi/Polymarket/Exa REST |
| tenacity | 9.1.4 | retries/backoff |
| pydantic | 2.13.5 | schemas, config |
| python-dotenv | 1.2.4 | `.env` |
| typer | 0.27.3 | CLI |
| jinja2 | 3.1.6 | prompts + HTML report |
| numpy | 2.5.3 | metrics |
| pandas | 3.0.6 | tables |
| scipy | 1.18.1 | stats helpers |
| scikit-learn | 1.9.1 | GroupKFold, LogisticRegression (Platt-fit secondary) |
| matplotlib | 3.11.2 | figures |
| pytest | 9.1.1 | tests |
| respx | 0.23.1 | mock httpx for Kalshi/Polymarket/Exa only (NOT Anthropic SDK, which uses httpx2) |

Pin exact versions in `pyproject.toml`; if any fails to resolve on Python 3.12/Windows, take the
newest version that works and record it in RESULTS.md.
