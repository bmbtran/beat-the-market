# Pre-registration — market-forecaster backtest

Committed **before** the first forecast on the test split (dev pilot measured on 2026-10-07; spend so far $1.60) (verify with
`git log --follow --format="%h %ad %s" -- PREREGISTRATION.md data/runs/backtest_v1/forecasts.jsonl`).
The dev split (50 earliest-t0 questions) may be used freely for prompt iteration; **the test split
(200 questions) is run once**. Any re-run on test is logged in RESULTS.md with the reason.

## Frozen at registration
- `configs/default.toml` and `configs/pricing.toml` as committed with this file.
- All prompts under `prompts/` (hashes in `prompts/lockfile.json`, enforced by `tests/test_prompts.py`).
- Dataset: `data/dataset/questions.jsonl` (dev/test split) and `data/dataset/canary_precutoff.jsonl`.
- Retrieval: Exa `instant`, `category: "news"`, 10 results per query, 2 queries per question,
  `endPublishedDate = t0 − 24h`, undated results dropped, blocklist as in config, helper relevance ≥ 4, top 6 kept.
  (Changed from the plan's 5 non-news results after the dev pilot; see RESULTS.md deviations.)
- Reasoner `claude-sonnet-5` (thinking disabled, effort medium, max_tokens 1200), helper
  `claude-haiku-4-5-20251001`, K = 5 prompt variants, trimmed mean (drop 1 min + 1 max),
  ≥ 3 valid samples required, supervisor trigger spread > 0.10, Platt coefficient √3 (fixed).

## Primary metric
Brier score on the **test** split.

## Primary comparisons (paired cluster bootstrap by event, B = 10,000, seed 0, 95% percentile CI)
1. `aia` vs `halawi` — does the AIA recipe (supervisor + fixed Platt √3) improve on the Halawi baseline?
2. `market_ens_aia` vs `market` — does blending AIA with the market price beat the market alone?

Everything else is secondary and reported as such.

## Arms (PLAN.md §12)
| Arm id | Description |
|---|---|
| `const_0.5` | 0.5 |
| `base_rate` | dev-set YES rate (fixed before looking at test) |
| `market` | `p_mkt_t0` |
| `noret_single` | no retrieval, r1 sample only |
| `noret_ens` | no retrieval, K=5 trimmed mean |
| `halawi_single` | retrieval, r1 sample only |
| `halawi` | retrieval, K=5 trimmed mean — the baseline system |
| `halawi_platt` | `halawi` + fixed √3 Platt |
| `halawi_sup` | `halawi` + supervisor |
| `aia` | `halawi` + supervisor + fixed Platt — the headline system |
| `aia_platt_fit` | Platt coefficient fit on dev (secondary) |
| `market_ens_halawi` | grouped 5-fold cross-fitted blend of `halawi` with market |
| `market_ens_aia` | grouped 5-fold cross-fitted blend of `aia` with market |
| `market_ens_aia_devw` | blend weight fit on dev only |

## Scoring set and failures
Arms are scored on the test questions where **every** LLM base arm (`noret_single`, `noret_ens`,
`halawi_single`, `halawi`, `halawi_sup`) produced a probability. Questions where an arm failed
(< 3 parseable samples, refusals) are counted per arm and reported; they are never filled with 0.5.

## Pre-registered breakdowns (the only subsets allowed in the headline)
Venue; category; horizon bucket (< 7 d, 7–30 d, > 30 d); supervisor triggered vs not.

## Leakage checks (all reported regardless of outcome)
1. Canary: `noret_ens` Brier on the 30 pre-cutoff canary questions vs on test.
2. Human audit of 50 random kept evidence items → leak rate.
3. Evidence drop counts per filter.
4. Robustness: `aia` re-scored excluding questions whose retrieval surfaced any helper-flagged item.

## Expected result (stated in advance)
The agent will probably **not** beat the market price alone. Plausible positive results are a small
`aia` < `halawi` improvement (likely inconclusive at N≈200; MDE ≈ 0.012) and `market_ens_aia` ≤ `market`.
