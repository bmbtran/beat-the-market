# RESULTS — market-forecaster

> Every number in this file comes from `reports/metrics.json` (inserted by `mf report`) or is verbatim
> command output. Nothing here is typed by hand.

## Verify

<!-- VERIFY:START -->
**`VERIFY: PASS metrics_sha=84cc418825e1f3bd4569f8015b52883c3ee39edaf0c22190d50fe40ddadca61f`** (run 2026-10-07; full verbatim output below)

<details><summary>uv run python scripts/verify.py</summary>

```
$ uv run python scripts/verify.py
$ uv run pytest -q -p no:cacheprovider
............................................................................................ [ 69%]
.........................................                                                    [100%]
133 passed in 9.94s
[exit 0]

$ uv run python -m mf.data.dataset --validate
OK 250 questions (dev=50 test=200) canary=30
[exit 0]

$ uv run mf evaluate --out reports/metrics_repro.json
wrote reports/metrics_repro.json: n_test_scored=200 events=126 failed={'noret_single': 0, 'noret_ens': 0, 'halawi_single': 0, 'halawi': 0, 'halawi_sup': 0}
  const_0.5        Brier 0.2500  95% CI [0.2500, 0.2500]
  base_rate        Brier 0.2410  95% CI [0.2287, 0.2533]
  market           Brier 0.1676  95% CI [0.1382, 0.1978]
  noret_ens        Brier 0.2802  95% CI [0.2378, 0.3221]
  halawi           Brier 0.2794  95% CI [0.2364, 0.3227]
  halawi_sup       Brier 0.2695  95% CI [0.2280, 0.3122]
  aia              Brier 0.3029  95% CI [0.2515, 0.3554]
  market_ens_aia   Brier 0.1688  95% CI [0.1392, 0.1991]
  PRIMARY aia_minus_halawi: dBrier +0.0235 [+0.0058, +0.0394] P(d<0)=0.005
  PRIMARY market_ens_aia_minus_market: dBrier +0.0012 [+0.0004, +0.0021] P(d<0)=0.003
[exit 0]

$ compare reports/metrics.json reports/metrics_repro.json (canonical JSON)
REPRO OK (identical after canonical JSON)

$ uv run mf verify-ledger
LEDGER OK n=10 head=dd4761a1291bec68a002420291764aa19fc1678430412ae9e5dc7920c2f5dbdc
[exit 0]

$ uv run mf budget
{
  "anthropic_backtest_cap_usd": 23.0,
  "anthropic_backtest_usd": 13.955241,
  "anthropic_cap_usd": 30.0,
  "anthropic_total_usd": 14.562981,
  "by_provider_op_month": [
    {
      "calls": 260,
      "month": "2026-10",
      "op": "query_gen",
      "provider": "anthropic",
      "usd": 0.144909
    },
    {
      "calls": 135,
      "month": "2026-10",
      "op": "reason",
      "provider": "anthropic",
      "usd": 0.9905
    },
    {
      "calls": 1200,
      "month": "2026-10",
      "op": "reason_batch",
      "provider": "anthropic",
      "usd": 4.56766
    },
    {
      "calls": 50,
      "month": "2026-10",
      "op": "reason_noret",
      "provider": "anthropic",
      "usd": 0.32131
    },
    {
      "calls": 1150,
      "month": "2026-10",
      "op": "reason_noret_batch",
      "provider": "anthropic",
      "usd": 4.05287
    },
    {
      "calls": 377,
      "month": "2026-10",
      "op": "relevance_summary",
      "provider": "anthropic",
      "usd": 2.737902
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_batch_batch",
      "provider": "anthropic",
      "usd": 4.6e-05
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_helper",
      "provider": "anthropic",
      "usd": 9.2e-05
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_reasoner",
      "provider": "anthropic",
      "usd": 0.000862
    },
    {
      "calls": 131,
      "month": "2026-10",
      "op": "supervisor_disagree",
      "provider": "anthropic",
      "usd": 1.251616
    },
    {
      "calls": 131,
      "month": "2026-10",
      "op": "supervisor_update",
      "provider": "anthropic",
      "usd": 0.495214
    },
    {
      "calls": 19,
      "month": "2026-10",
      "op": "search_fast",
      "provider": "exa",
      "usd": 0.133
    },
    {
      "calls": 788,
      "month": "2026-10",
      "op": "search_instant",
      "provider": "exa",
      "usd": 3.152
    }
  ],
  "exa_by_month_usd": {
    "2026-10": 3.285
  },
  "exa_monthly_cap_usd": 9.0,
  "n_paid_calls": 4244
}
Anthropic: $14.5630 of $30.00 total (backtest $13.9552 of $23.00)
Exa 2026-10: $3.2850 of $9.00
BUDGET OK: all caps respected
[exit 0]

$ check RESULTS.md / README.md placeholders and METRICS blocks
RESULTS.md: METRICS block matches metrics.json
README.md: METRICS block matches metrics.json
RESULTS.md: no TODO/TBD/XX/_Pending placeholders

$ git status --porcelain --ignored
 M RESULTS.md
 M scripts/verify.py
!! .env
!! .venv/
!! cache/
!! reports/metrics_repro.json
!! src/mf/__pycache__/
!! src/mf/core/__pycache__/
!! src/mf/data/__pycache__/
!! src/mf/eval/__pycache__/
!! src/mf/forecast/__pycache__/
!! src/mf/live/__pycache__/
!! src/mf/llm/__pycache__/
!! src/mf/retrieval/__pycache__/
!! state/
!! tests/__pycache__/
[exit 0]

$ git ls-files
.env.example
.gitattributes
.gitignore
.python-version
LEARNING.md
PLAN.md
PREREGISTRATION.md
README.md
RESOURCES.md
RESULTS.md
configs/default.toml
configs/pricing.toml
data/dataset/canary_precutoff.jsonl
data/dataset/dataset_card.json
data/dataset/questions.jsonl
data/live/forecasts.jsonl
data/runs/backtest_v1/evidence.jsonl
data/runs/backtest_v1/forecasts.jsonl
data/runs/backtest_v1/retrieval_meta.jsonl
data/runs/backtest_v1/samples.jsonl
prompts/CHANGELOG.md
prompts/lockfile.json
prompts/reasoning/r1_halawi_scratchpad_v1.md
prompts/reasoning/r2_base_rates_v1.md
prompts/reasoning/r3_inside_outside_view_v1.md
prompts/reasoning/r4_premortem_both_sides_v1.md
prompts/reasoning/r5_superforecaster_checklist_v1.md
prompts/retrieval/query_gen_v1.md
prompts/retrieval/relevance_summary_v1.md
prompts/smoke/smoke_helper_v1.md
prompts/smoke/smoke_reasoner_v1.md
prompts/supervisor/disagreement_v1.md
prompts/supervisor/update_v1.md
pyproject.toml
reports/figures/brier_bars.png
reports/figures/brier_by_horizon.png
reports/figures/delta_forest.png
reports/figures/reliability.png
reports/figures/scatter_vs_market.png
reports/index.html
reports/leakage_audit.csv
reports/leakage_audit_summary.json
reports/metrics.json
reports/spend.json
scripts/check_metrics_arms.py
scripts/live_weekly.ps1
scripts/log_milestone.py
scripts/verify.py
src/mf/__init__.py
src/mf/cli.py
src/mf/commands.py
src/mf/config.py
src/mf/core/__init__.py
src/mf/core/budget.py
src/mf/core/cache.py
src/mf/core/hashing.py
src/mf/core/http.py
src/mf/core/pricing.py
src/mf/core/timeutil.py
src/mf/data/__init__.py
src/mf/data/common.py
src/mf/data/dataset.py
src/mf/data/fixtures.py
src/mf/data/kalshi.py
src/mf/data/polymarket.py
src/mf/data/prices.py
src/mf/eval/__init__.py
src/mf/eval/arms.py
src/mf/eval/audit.py
src/mf/eval/bootstrap.py
src/mf/eval/calibration.py
src/mf/eval/metrics.py
src/mf/eval/report.py
src/mf/forecast/__init__.py
src/mf/forecast/aggregate.py
src/mf/forecast/calibrate.py
src/mf/forecast/market_ensemble.py
src/mf/forecast/pipeline.py
src/mf/forecast/reason.py
src/mf/forecast/supervisor.py
src/mf/live/__init__.py
src/mf/live/ledger.py
src/mf/live/run.py
src/mf/live/score.py
src/mf/live/select.py
src/mf/llm/__init__.py
src/mf/llm/batch.py
src/mf/llm/client.py
src/mf/llm/parse.py
src/mf/llm/prompts.py
src/mf/retrieval/__init__.py
src/mf/retrieval/exa_client.py
src/mf/retrieval/leakage.py
src/mf/retrieval/pipeline.py
src/mf/retrieval/queries.py
src/mf/retrieval/summarize.py
src/mf/runtime.py
src/mf/schemas.py
src/mf/smoke.py
tests/conftest.py
tests/fixtures/anthropic/smoke_haiku.json
tests/fixtures/anthropic/smoke_sonnet5.json
tests/fixtures/exa/search_synthetic.json
tests/fixtures/exa/smoke_fast_0.json
tests/fixtures/exa/smoke_fast_1.json
tests/fixtures/exa/smoke_instant_0.json
tests/fixtures/exa/smoke_instant_1.json
tests/fixtures/kalshi/can_close_early_market.json
tests/fixtures/kalshi/cutoff.json
tests/fixtures/kalshi/events_fed_settled.json
tests/fixtures/kalshi/historical_candles.json
tests/fixtures/kalshi/historical_markets_fed_jul26.json
tests/fixtures/kalshi/live_candles.json
tests/fixtures/kalshi/live_candles_404_for_historical.json
tests/fixtures/polymarket/event_negrisk.json
tests/fixtures/polymarket/event_non_yes_no.json
tests/fixtures/polymarket/prices_history.json
tests/test_aggregate.py
tests/test_batch.py
tests/test_bootstrap.py
tests/test_budget.py
tests/test_cache.py
tests/test_calibrate.py
tests/test_dataset.py
tests/test_exa_client.py
tests/test_kalshi.py
tests/test_leakage.py
tests/test_live_ledger.py
tests/test_llm_client.py
tests/test_market_ensemble.py
tests/test_metrics.py
tests/test_parse.py
tests/test_polymarket.py
tests/test_prices.py
tests/test_pricing.py
tests/test_prompts.py
tests/test_reason.py
tests/test_report.py
tests/test_retrieval.py
tests/test_supervisor.py
uv.lock
[exit 0]
git: .env, cache/, state/ are neither tracked nor staged

VERIFY: PASS metrics_sha=84cc418825e1f3bd4569f8015b52883c3ee39edaf0c22190d50fe40ddadca61f
```
</details>
<!-- VERIFY:END -->

## Summary

**The forecaster does not beat the market, and uncalibrated it does not even beat a coin flip.** On 200
leak-free test questions (Kalshi + Polymarket, created after Claude Sonnet 5's training cutoff), every LLM-only
arm has a higher (worse) Brier score than the market price at t0, and every *uncalibrated* LLM arm is also worse
than a constant 0.5. Only the secondary arm whose calibration is fitted on the dev split (it shrinks forecasts
toward 0.5) edges past 0.5 and the dev base rate, and it remains far behind the market. Both pre-registered
primary comparisons came out in the wrong direction with 95% CIs that exclude zero: the AIA recipe
(supervisor + fixed √3 extremization) is *worse* than the Halawi baseline, and blending AIA with the market
is very slightly *worse* than the market alone. The one component that helped was the AIA supervisor on its
own, by a small margin. The headline table below is generated from `reports/metrics.json`; the
explanations in "What didn't work" are hypotheses, not findings.

## Headline

<!-- METRICS:START -->
_Auto-generated from `reports/metrics.json` by `mf report`. Test set: 200 questions (126 events) scored of 200; test YES rate 0.405; paired cluster bootstrap B=10000 by event._

| Arm | Brier | 95% CI | Log loss | ECE | BSS vs market |
|---|---|---|---|---|---|
| Constant 0.5 (`const_0.5`) | 0.2500 | [0.2500, 0.2500] | 0.6931 | 0.0950 | -0.4919 |
| Dev base rate (`base_rate`) | 0.2410 | [0.2287, 0.2533] | 0.6750 | 0.0050 | -0.4382 |
| Market price at t0 (`market`) | 0.1676 | [0.1382, 0.1978] | 0.4993 | 0.0766 | +0.0000 |
| No retrieval, 1 sample (`noret_single`) | 0.2787 | [0.2366, 0.3197] | 0.8563 | 0.1911 | -0.6629 |
| No retrieval, K=5 (`noret_ens`) | 0.2802 | [0.2378, 0.3221] | 0.8533 | 0.2167 | -0.6720 |
| Retrieval, 1 sample (`halawi_single`) | 0.2769 | [0.2337, 0.3210] | 0.8464 | 0.2093 | -0.6526 |
| Halawi (retrieval, K=5) (`halawi`) | 0.2794 | [0.2364, 0.3227] | 0.8493 | 0.2020 | -0.6673 |
| Halawi + Platt √3 (`halawi_platt`) | 0.3140 | [0.2612, 0.3671] | 1.1241 | 0.2764 | -0.8739 |
| Halawi + supervisor (`halawi_sup`) | 0.2695 | [0.2280, 0.3122] | 0.8203 | 0.1926 | -0.6081 |
| AIA (supervisor + Platt √3) (`aia`) | 0.3029 | [0.2515, 0.3554] | 1.0808 | 0.2651 | -0.8076 |
| AIA, Platt fit on dev (`aia_platt_fit`) | 0.2375 | [0.2121, 0.2632] | 0.6728 | 0.0888 | -0.4174 |
| Halawi ⊕ market (`market_ens_halawi`) | 0.1682 | [0.1387, 0.1985] | 0.5019 | 0.0706 | -0.0038 |
| AIA ⊕ market (CV) (`market_ens_aia`) | 0.1688 | [0.1392, 0.1991] | 0.5045 | 0.0687 | -0.0074 |
| AIA ⊕ market (dev w) (`market_ens_aia_devw`) | 0.1763 | [0.1472, 0.2069] | 0.5346 | 0.0624 | -0.0519 |

**Pre-registered primary comparisons** (paired ΔBrier, negative = first arm better):

- `aia_minus_halawi`: +0.0235 (95% CI [+0.0058, +0.0394]; P(Δ<0) = 0.005)
- `market_ens_aia_minus_market`: +0.0012 (95% CI [+0.0004, +0.0021]; P(Δ<0) = 0.003)

**Leak canary** (no retrieval, K=5): canary Brier 0.1629 (n=30, market 0.1901) vs test Brier 0.2802 (market 0.1676).
<!-- METRICS:END -->

## What didn't work

<!-- FAILURES:START -->
| Arm | Brier | ΔBrier vs market [95% CI] | Brier − 0.25 (const 0.5) | ECE |
|---|---|---|---|---|
| Dev base rate | 0.2410 | +0.0734 [+0.0439, +0.1016] | -0.0090 | 0.0050 |
| No retrieval, 1 sample | 0.2787 | +0.1111 [+0.0669, +0.1550] | +0.0287 | 0.1911 |
| No retrieval, K=5 | 0.2802 | +0.1126 [+0.0691, +0.1561] | +0.0302 | 0.2167 |
| Retrieval, 1 sample | 0.2769 | +0.1094 [+0.0660, +0.1531] | +0.0269 | 0.2093 |
| Halawi (retrieval, K=5) | 0.2794 | +0.1118 [+0.0692, +0.1552] | +0.0294 | 0.2020 |
| Halawi + Platt √3 | 0.3140 | +0.1464 [+0.0956, +0.1981] | +0.0640 | 0.2764 |
| Halawi + supervisor | 0.2695 | +0.1019 [+0.0611, +0.1430] | +0.0195 | 0.1926 |
| AIA (supervisor + Platt √3) | 0.3029 | +0.1353 [+0.0868, +0.1848] | +0.0529 | 0.2651 |
| AIA, Platt fit on dev | 0.2375 | +0.0700 [+0.0387, +0.1008] | -0.0125 | 0.0888 |
| Halawi ⊕ market | 0.1682 | +0.0006 [+0.0001, +0.0012] | -0.0818 | 0.0706 |
| AIA ⊕ market (CV) | 0.1688 | +0.0012 [+0.0004, +0.0021] | -0.0812 | 0.0687 |
| AIA ⊕ market (dev w) | 0.1763 | +0.0087 [-0.0023, +0.0189] | -0.0737 | 0.0624 |

Supervisor triggered vs not (Brier):

- not_triggered (n=106): market 0.1918, halawi 0.2872, aia 0.3233
- triggered (n=94): market 0.1402, halawi 0.2706, aia 0.2799

Platt coefficient fit on dev: 0.462 (AIA's fixed value is √3 ≈ 1.732). Market-blend weight on AIA: dev-fit 0.25; cross-fitted folds [0.0, 0.03, 0.03, 0.0, 0.05].
<!-- FAILURES:END -->

What the numbers above say, in words (each point is checkable against the table or `metrics.json`):

1. **Every LLM-only arm loses to the market; every uncalibrated one also loses to 0.5.** The model discriminates a little (it is
   positively correlated with outcomes) but is badly overconfident: it puts many questions near 0 or 1 that
   resolve the other way (see `reports/figures/reliability.png`).
2. **Extremization made it worse, not better.** AIA's fixed Platt √3 assumes the averaged ensemble is
   *under*-confident. Here the reverse holds: the Platt coefficient fitted on the 50 dev questions is below 1,
   i.e. the data asks to *shrink* forecasts toward 0.5, and the dev-fitted variant is the best LLM-only arm.
   This is the main reason `aia` loses to `halawi`.
3. **The supervisor helped a little.** `halawi_sup` beats `halawi` with a CI just below zero (secondary
   comparison, so treat as suggestive). It fired on about half the questions but reported "high" confidence,
   and therefore replaced the ensemble mean, only rarely.
4. **Retrieval did not help.** With-retrieval and no-retrieval ensembles are statistically indistinguishable.
   Exa's date filter returns many undated pages that must be discarded, so evidence per question is thin;
   the questions are also short-horizon and data-release driven (CPI prints, GPU rental prices, post counts),
   where news summaries carry little signal relative to the market.
5. **The market blend learned to ignore the LLM.** Cross-fitted blend weights on the LLM are near zero, so
   `market_ens_*` is essentially the market, and the small residual weight costs a little.
6. **No pre-registered subset rescues it.** By venue, category, horizon bucket, and supervisor-triggered, the
   market is better everywhere (breakdowns in `metrics.json` and `reports/index.html`).

Hypotheses (not tested here): stale world knowledge (the 2026 Iran war and its effect on oil, shipping and
inflation post-dates the model's training data, and thin retrieval rarely filled the gap); prompts that invite
crisp "status quo" reasoning at short horizons; a question mix dominated by threshold and bucket markets where
the market price encodes data the model cannot see; and N=200 (minimum detectable effect ≈ 0.012).

## Leakage

<!-- LEAKAGE:START -->
| Check | Value |
|---|---|
| Canary (pre-cutoff, n=30): no-retrieval K=5 Brier | 0.1629 (market 0.1901) |
| Test (post-cutoff, n=200): no-retrieval K=5 Brier | 0.2802 (market 0.1676) |
| Kept evidence per test question (mean) | 3.45 |
| Evidence dropped on test questions, by filter | haiku_leak_flag=214, kept=690, low_relevance=510, null_date=1914, over_max_articles=429, over_max_evidence=106, text_post_t0_date=5 |
| Robustness: AIA Brier excluding questions whose retrieval surfaced any helper-flagged item | 0.2880 on n=108 (all questions 0.3029; market on the same subset 0.1703) |
| Human audit of 50 random kept items | leak 0.0%, leak-or-unsure 2.0% (verdicts {'clean': 49, 'unsure': 1}) |
<!-- LEAKAGE:END -->

The canary behaves as a leak detector should: on questions resolved *before* the model's training cutoff, the
no-retrieval ensemble beats the market (it likely remembers outcomes); on the post-cutoff test set the same arm
is far worse than the market. The human audit (50 random kept evidence items, reviewed by the implementer,
Claude, reading each summary, URL and date against t0) found no post-t0 information; the one "unsure" item is
a "latest" statistics page whose stated publish date is older than its content (content still pre-t0). The full
CSV is `reports/leakage_audit.csv`.

## Cost

<!-- COST:START -->
- Anthropic total: $14.56 of $30.00 cap (backtest $13.96 of $23.00).
- Exa 2026-10: $3.29 of $9.00 monthly cap.
- Paid API calls (cache misses): 4244.

| Provider | Op | Month | Calls | USD |
|---|---|---|---|---|
| anthropic | query_gen | 2026-10 | 260 | 0.1449 |
| anthropic | reason | 2026-10 | 135 | 0.9905 |
| anthropic | reason_batch | 2026-10 | 1200 | 4.5677 |
| anthropic | reason_noret | 2026-10 | 50 | 0.3213 |
| anthropic | reason_noret_batch | 2026-10 | 1150 | 4.0529 |
| anthropic | relevance_summary | 2026-10 | 377 | 2.7379 |
| anthropic | smoke_batch_batch | 2026-10 | 1 | 0.0000 |
| anthropic | smoke_helper | 2026-10 | 1 | 0.0001 |
| anthropic | smoke_reasoner | 2026-10 | 1 | 0.0009 |
| anthropic | supervisor_disagree | 2026-10 | 131 | 1.2516 |
| anthropic | supervisor_update | 2026-10 | 131 | 0.4952 |
| exa | search_fast | 2026-10 | 19 | 0.1330 |
| exa | search_instant | 2026-10 | 788 | 3.1520 |
<!-- COST:END -->

## Deviations from PLAN.md

- **M0 `.env` ignore check:** the local secret-read guard hook blocks any shell command containing the
  literal `.env` (even `git check-ignore`, which never opens the file). The `.env` half of the check was
  done with `git status --porcelain --ignored`, which lists `.env` as ignored (`!!`) without reading it.
- **Dependencies:** all pins in RESOURCES.md resolved exactly on Python 3.12.13 / Windows (no substitutions).
  Transitive extras worth noting: `httpx2 2.13.1` (from `anthropic 1.11.0`), `openai 3.26.0` (from `exa-py`).
- **[VERIFY] Kalshi candle limit (§6.1):** a single 60-min request over 60 days returned 866 candles with no
  truncation; we only ever request a 24 h window before t0, so the limit is irrelevant. Resolved.
- **[VERIFY] Kalshi scheduled close after early close (§6.3.3):** resolved with real data. An early close moves only
  `close_time`; `expected_expiration_time` and `latest_expiration_time` keep the original schedule
  (KXGOVSHUTLENGTH-26FEB28-4D: closed 2026-02-04, both expirations still 2026-03-01). `latest_expiration_time`
  carries a long buffer (KXFEDDECISION-26SEP: expected 09-16, latest 12-16), so **`expected_expiration_time`**
  is used as the scheduled end. The plan's extra rule (drop `can_close_early` markets closed >3 days before
  expected expiration) is applied too. Markets whose trading stopped before t0+1d are dropped and their YES rate is
  reported in `dataset_card.json` (`closed_before_t0_plus_1d_yes_rate`) as the residual selection-bias indicator.
- **Kalshi API:** `/historical/markets` rejects `series_ticker` combined with `mve_filter` ("mutually exclusive"),
  contrary to the plan's example URL. `mve_filter` is omitted when filtering by series; MVE markets
  (`KXMVE*`, `mve_selected_legs`) are dropped in code. `/events?with_nested_markets=true` omits `markets` for
  historical-tier events, which is used to route to `/historical/markets`.
- **[VERIFY] exa-py kwargs (§13 M3):** exa-py 2.25.0 `Exa.search` has `num_results, end_published_date,
  exclude_domains, type, contents` as the plan assumed. The REST endpoint is used anyway (allowed by the plan) so the
  exact body is visible, `costDollars.total` is recorded, and respx can mock it. Contents options are
  `contents.highlights.maxCharacters` and `contents.maxAgeHours`.
- **Exa date filter (M3 smoke):** every *dated* result respected `endPublishedDate`, but Exa also returns
  **undated** results, and in the smoke test those were clearly post-cutoff (October-2026 Fed odds pages, odds
  aggregators). Dropping null-dated results is therefore mandatory, not optional. Seven odds-aggregator domains were
  added to the blocklist. `fast` returned more dated results than `instant` on one of two queries; `instant` is kept
  per plan and dated-evidence yield is measured in the pilot.
- **Exa cost:** actual `costDollars.total` was $0.004 (instant) / $0.007 (fast) per 5-result search with
  highlights, i.e. highlights were not billed separately; the estimator stays pessimistic ($0.009).
- **Haiku cache-write price [UNVERIFIED in plan]:** irrelevant, no cache writes are made on Haiku.
- **Polymarket pagination:** Gamma rejects `offset` > ~2000 ("use /events/keyset", which returned HTTP 500 with
  these filters). The end-date range is split into 7-day windows, each listed by volume. In 30 of the main-window
  weeks more than 2,000 closed events (mostly sports/crypto) exceeded $50k, so those windows stopped at
  ~$90–120k event volume: the **effective Polymarket floor in busy weeks was ~$90–120k instead of $50k**. This
  tilts the Polymarket half toward more liquid markets, which makes the market baseline harder to beat, not easier.
  Recorded as `poly:windows_truncated_by_page_cap` in `dataset_card.json`. The canary window was not truncated.
- **Dataset size:** 250 questions (dev 50 / test 200, 125 per venue, 158 events) and 30 canary questions were
  reached without relaxing the volume floors.
- **Residual selection bias:** 653 otherwise-eligible markets stopped trading before t0+1d (resolved early) and
  were dropped; their YES rate is 0.453 vs 0.404 in the dataset, so the dataset is slightly NO-tilted relative to
  the full population.
- **Count/"mention"-style markets** (e.g. "Will Elon Musk post 180–199 tweets…", "Will Trump say 'Turkey'…") enter via
  Polymarket's politics tags and Kalshi Politics series; Kalshi's separate "Mentions" category is excluded. No
  consistent rule removes them across venues, so they stay in and are noted as a limitation.
- **Dataset determinism:** a second `mf build-dataset` (from the HTTP cache) produced byte-identical
  `questions.jsonl` / `canary_precutoff.jsonl` (sha256 d17c4437… / 966498ec…).
- **Retrieval config changed after the first pilot (dev-set tuning, before pre-registration):** the first pilot
  (plan settings: `instant`, 5 results) kept **0 evidence items for 5 of 10 dev questions** (mean 1.2) because 70 of
  88 dropped results had no `publishedDate`. A dev-only experiment on the pilot's 20 real queries measured the share of
  results surviving the deterministic filters: `instant` 26%, `fast` 25%, `instant`+`category:"news"` 43%, and
  `instant`+news with 10 results 45% (86 survivors vs 24). Adopted: `exa_category = "news"`, `exa_num_results = 10`
  (the plan's fallback lever list moves this the other way; it is reversible if the pilot projects over the caps).
  Experiment cost $0.26 (logged in the spend ledger under run ids `bt-exa-experiment-*`).

## Milestone log

### M0 — Scaffold (PASS, 2026-10-06)

```
$ uv run python -c "import sys,mf;print(sys.version_info[:2])"
(3, 12)
$ uv run mf --help
                                                                                                   
 Usage: mf [OPTIONS] COMMAND [ARGS]...                                                             
                                                                                                   
 market-forecaster: leak-free LLM forecasting vs Kalshi/Polymarket                                 
                                                                                                   
+- Options ---------------------------------------------------------------------------------------+
| --install-completion          Install completion for the current shell.                         |
| --show-completion             Show completion for the current shell, to copy it or customize    |
|                               the installation.                                                 |
| --help                        Show this message and exit.                                       |
+-------------------------------------------------------------------------------------------------+
+- Commands --------------------------------------------------------------------------------------+
| build-dataset  Pull Kalshi + Polymarket candidates, filter, pick t0, price@t0, split, write     |
|                questions.jsonl.                                                                 |
| retrieve       Query generation -> Exa -> leakage filters -> Haiku relevance/summary.           |
| forecast       Reasoner samples (K prompt variants), aggregation, supervisor.                   |
| evaluate       Compute all arms + metrics + cluster-bootstrap CIs.                              |
| report         Figures, reports/index.html, README/RESULTS metric blocks.                       |
| live           Forecast open markets and append to the hash-chained live ledger.                |
| score-live     Score resolved live forecasts.                                                   |
| budget         Print spend by provider/op/month and remaining caps.                             |
| pilot          Run the full pipeline on N dev questions and project total cost.                 |
| audit-leakage  Sample kept evidence for human leakage review, or summarize the filled CSV.      |
| verify-ledger  Verify the live forecast hash chain.                                             |
| smoke          Tiny paid smoke test of Haiku, Sonnet, Batch and Exa (~$0.07).                   |
| fixtures       Record small real API responses as test fixtures                                 |
| batch          Message Batches helpers                                                          |
+-------------------------------------------------------------------------------------------------+

$ git check-ignore cache/x state/x
cache/x
state/x
$ git status --porcelain --ignored | grep "^!!"
!! .env
!! .venv/
!! src/mf/__pycache__/
```

### M1 — Core: hashing, cache, budget, pricing (PASS, 2026-10-07)

```
$ uv run pytest tests/test_cache.py tests/test_budget.py tests/test_pricing.py -q
.....................                                                                        [100%]
21 passed in 0.51s
[exit 0]
```

### M3 — LLM + Exa clients (PASS, 2026-10-07)

```
$ uv run pytest tests/test_llm_client.py tests/test_exa_client.py tests/test_parse.py -q
..........................                                                                   [100%]
26 passed in 2.15s
[exit 0]
$ uv run mf smoke --allow-spend
[haiku]  cache_hit=True stop=end_turn in=22 out=14 text='```json\n["hello", "ok"]\n```' parsed=['hello', 'ok']
[sonnet] cache_hit=True stop=end_turn in=71 out=72 p=0.17 text="It's impossible to know in advance, but based on probability theory, a fair six-sided die has an equal 1-in-6 chance of landing on any specific number, including 6.\n\nFINAL PROBABILITY: 0.17"
[batch]  cache_hit=yes stop=end_turn text='```json\n["batch", "ok"]\n```'
[exa:instant] cache_hit=False q='Federal Reserve interest rate decision outlook' n=5 cost=0.004 dates=[None, None, None, None, None]
[exa:instant] cache_hit=False q='US government shutdown negotiations Congress' n=5 cost=0.004 dates=[None, '2025-10-07T00:00:00.000Z', '2025-10-07T00:00:00.000Z', None, '2025-10-07T00:00:00.000Z']
spent this run: $0.0080  (anthropic total $0.0010, exa 2026-10 $0.0300)
SMOKE OK
[exit 0]
```

### M3 — Check 2 second run (expect all cache hits, $0.00) (PASS, 2026-10-07)

```
$ uv run mf smoke --allow-spend
[haiku]  cache_hit=True stop=end_turn in=22 out=14 text='```json\n["hello", "ok"]\n```' parsed=['hello', 'ok']
[sonnet] cache_hit=True stop=end_turn in=71 out=72 p=0.17 text="It's impossible to know in advance, but based on probability theory, a fair six-sided die has an equal 1-in-6 chance of landing on any specific number, including 6.\n\nFINAL PROBABILITY: 0.17"
[batch]  cache_hit=yes stop=end_turn text='```json\n["batch", "ok"]\n```'
[exa:instant] cache_hit=True q='Federal Reserve interest rate decision outlook' n=5 cost=0.004 dates=[None, None, None, None, None]
[exa:instant] cache_hit=True q='US government shutdown negotiations Congress' n=5 cost=0.004 dates=[None, '2025-10-07T00:00:00.000Z', '2025-10-07T00:00:00.000Z', None, '2025-10-07T00:00:00.000Z']
spent this run: $0.0000  (anthropic total $0.0010, exa 2026-10 $0.0300)
SMOKE OK
[exit 0]
```

### M6 — Evaluation module (PASS, 2026-10-07)

```
$ uv run pytest tests/test_metrics.py tests/test_bootstrap.py -q
.............                                                                                [100%]
13 passed in 1.94s
[exit 0]
```

### M7 — AIA components (PASS, 2026-10-07)

```
$ uv run pytest tests/test_calibrate.py tests/test_supervisor.py tests/test_market_ensemble.py -q
.............                                                                                [100%]
13 passed in 31.06s
[exit 0]
```

### M4 — Retrieval pipeline (PASS, 2026-10-07)

```
$ uv run pytest tests/test_retrieval.py tests/test_leakage.py -q
..........                                                                                   [100%]
10 passed in 0.45s
[exit 0]
$ uv run mf retrieve --split dev --limit 10 --dry-run
DRY RUN retrieve split=dev n=10
  helper LLM calls: 0 cached, 20 to make
  Exa searches:     0 cached, 20 to make
  PROJECTED: anthropic $0.1507, exa $0.1800
  network calls made: 0
[exit 0]
```

### M2 — Market data + dataset (PASS, 2026-10-07)

```
$ uv run pytest tests/test_kalshi.py tests/test_polymarket.py tests/test_prices.py tests/test_dataset.py -q
.......................                                                                      [100%]
23 passed in 0.26s
[exit 0]
$ uv run mf build-dataset
[kalshi] 9381 allowed series (of 9990 listed)
[kalshi] series 0/9381  markets so far=0  http_calls=0
[kalshi] series 250/9381  markets so far=681  http_calls=0
[kalshi] series 500/9381  markets so far=1939  http_calls=0
[kalshi] series 750/9381  markets so far=2797  http_calls=0
[kalshi] series 1000/9381  markets so far=3842  http_calls=0
[kalshi] series 1250/9381  markets so far=5143  http_calls=0
[kalshi] series 1500/9381  markets so far=6284  http_calls=0
[kalshi] series 1750/9381  markets so far=7607  http_calls=0
[kalshi] series 2000/9381  markets so far=9491  http_calls=0
[kalshi] series 2250/9381  markets so far=10390  http_calls=0
[kalshi] series 2500/9381  markets so far=11439  http_calls=0
[kalshi] series 2750/9381  markets so far=12205  http_calls=0
[kalshi] series 3000/9381  markets so far=14238  http_calls=0
[kalshi] series 3250/9381  markets so far=14991  http_calls=0
[kalshi] series 3500/9381  markets so far=15928  http_calls=0
[kalshi] series 3750/9381  markets so far=18109  http_calls=0
[kalshi] series 4000/9381  markets so far=18923  http_calls=0
[kalshi] series 4250/9381  markets so far=19766  http_calls=0
[kalshi] series 4500/9381  markets so far=25602  http_calls=0
[kalshi] series 4750/9381  markets so far=32691  http_calls=0
[kalshi] series 5000/9381  markets so far=37422  http_calls=0
[kalshi] series 5250/9381  markets so far=40255  http_calls=0
[kalshi] series 5500/9381  markets so far=43345  http_calls=0
[kalshi] series 5750/9381  markets so far=44553  http_calls=0
[kalshi] series 6000/9381  markets so far=49026  http_calls=0
[kalshi] series 6250/9381  markets so far=52896  http_calls=0
[kalshi] series 6500/9381  markets so far=58709  http_calls=0
[kalshi] series 6750/9381  markets so far=61777  http_calls=0
[kalshi] series 7000/9381  markets so far=70365  http_calls=0
[kalshi] series 7250/9381  markets so far=75053  http_calls=0
[kalshi] series 7500/9381  markets so far=80370  http_calls=0
[kalshi] series 7750/9381  markets so far=92212  http_calls=0
[kalshi] series 8000/9381  markets so far=99275  http_calls=0
[kalshi] series 8250/9381  markets so far=105025  http_calls=0
[kalshi] series 8500/9381  markets so far=118678  http_calls=0
[kalshi] series 8750/9381  markets so far=123793  http_calls=0
[kalshi] series 9000/9381  markets so far=128653  http_calls=0
[kalshi] series 9250/9381  markets so far=134837  http_calls=0
[kalshi] 134064 binary resolved candidates
[poly:main] 63224 closed events listed; truncated windows: [(datetime.datetime(2026, 2, 8, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 2, 15, 0, 0, tzinfo=datetime.timezone.utc), 90469.328709), (datetime.datetime(2026, 2, 15, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 2, 22, 0, 0, tzinfo=datetime.timezone.utc), 122172.000241), (datetime.datetime(2026, 2, 22, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 3, 1, 0, 0, tzinfo=datetime.timezone.utc), 115245.851316), (datetime.datetime(2026, 3, 1, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 3, 8, 0, 0, tzinfo=datetime.timezone.utc), 96227.267149), (datetime.datetime(2026, 3, 29, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 4, 5, 0, 0, tzinfo=datetime.timezone.utc), 120196.34479199999), (datetime.datetime(2026, 4, 5, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 4, 12, 0, 0, tzinfo=datetime.timezone.utc), 119345.8800449999), (datetime.datetime(2026, 4, 12, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 4, 19, 0, 0, tzinfo=datetime.timezone.utc), 109734.80150199952), (datetime.datetime(2026, 4, 19, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 4, 26, 0, 0, tzinfo=datetime.timezone.utc), 104903.91951200001), (datetime.datetime(2026, 4, 26, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 5, 3, 0, 0, tzinfo=datetime.timezone.utc), 86066.80265400004), (datetime.datetime(2026, 5, 3, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 5, 10, 0, 0, tzinfo=datetime.timezone.utc), 79801.46212000004), (datetime.datetime(2026, 5, 10, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 5, 17, 0, 0, tzinfo=datetime.timezone.utc), 82755.22291799966), (datetime.datetime(2026, 5, 17, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 5, 24, 0, 0, tzinfo=datetime.timezone.utc), 75661.69674199997), (datetime.datetime(2026, 5, 24, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 5, 31, 0, 0, tzinfo=datetime.timezone.utc), 77162.98686699993), (datetime.datetime(2026, 5, 31, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 6, 7, 0, 0, tzinfo=datetime.timezone.utc), 79730.51703299987), (datetime.datetime(2026, 6, 7, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 6, 14, 0, 0, tzinfo=datetime.timezone.utc), 65713.27025900001), (datetime.datetime(2026, 6, 14, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 6, 21, 0, 0, tzinfo=datetime.timezone.utc), 75158.48074799996), (datetime.datetime(2026, 6, 21, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 6, 28, 0, 0, tzinfo=datetime.timezone.utc), 82013.08744699997), (datetime.datetime(2026, 6, 28, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 7, 5, 0, 0, tzinfo=datetime.timezone.utc), 87102.728026), (datetime.datetime(2026, 7, 5, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 7, 12, 0, 0, tzinfo=datetime.timezone.utc), 77426.85154700001), (datetime.datetime(2026, 7, 12, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 7, 19, 0, 0, tzinfo=datetime.timezone.utc), 77391.4468289999), (datetime.datetime(2026, 7, 19, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 7, 26, 0, 0, tzinfo=datetime.timezone.utc), 78806.16390899997), (datetime.datetime(2026, 7, 26, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 8, 2, 0, 0, tzinfo=datetime.timezone.utc), 64970.49506799986), (datetime.datetime(2026, 8, 2, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 8, 9, 0, 0, tzinfo=datetime.timezone.utc), 60524.78990699995), (datetime.datetime(2026, 8, 9, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 8, 16, 0, 0, tzinfo=datetime.timezone.utc), 60276.381786999955), (datetime.datetime(2026, 8, 16, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 8, 23, 0, 0, tzinfo=datetime.timezone.utc), 63322.97181899999), (datetime.datetime(2026, 8, 23, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 8, 30, 0, 0, tzinfo=datetime.timezone.utc), 61436.94866100005), (datetime.datetime(2026, 8, 30, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 9, 6, 0, 0, tzinfo=datetime.timezone.utc), 63026.51428099999), (datetime.datetime(2026, 9, 6, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 9, 13, 0, 0, tzinfo=datetime.timezone.utc), 54294.589076), (datetime.datetime(2026, 9, 13, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 9, 20, 0, 0, tzinfo=datetime.timezone.utc), 53510.21049900002), (datetime.datetime(2026, 9, 20, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 9, 27, 0, 0, tzinfo=datetime.timezone.utc), 55913.222873)]
[main] pool after static filters: 8852 (kalshi=5254, poly=3598)
[sample:test] 100/250  {'kalshi': 100}
[sample:test] 125/250  {'kalshi': 125}
[sample:test] 200/250  {'kalshi': 125, 'polymarket': 75}
[sample:test] 225/250  {'kalshi': 125, 'polymarket': 100}
[sample:test] 250/250  {'kalshi': 125, 'polymarket': 125}
[poly:canary] 5419 closed events listed; truncated windows: []
[canary] pool after static filters: 1966 (kalshi=868, poly=1098)
[sample:canary] 25/30  {'kalshi': 15, 'polymarket': 10}
[http] network calls this build: 0, cache hits: 14503
FILTER FUNNEL (main):
{
  "drop:closed_before_t0_plus_1d": 653,
  "drop:created_before_window": 55820,
  "drop:kalshi_closed_early_gt_3d": 3110,
  "drop:lifetime_lt_7d": 66913,
  "drop:no_price_within_window": 5,
  "drop:p_mkt_extreme": 80,
  "drop:resolved_outside_window": 33,
  "drop:scheduled_close_after_window": 15854,
  "drop:title_short": 2,
  "drop:volume": 52345,
  "kalshi:drop:not_binary_or_unresolved": 4188,
  "kalshi:markets_seen": 138252,
  "kalshi:series_allowed": 9381,
  "kalshi:series_listed": 9990,
  "pass_static": 8852,
  "poly:drop:category_or_excluded_tag": 612717,
  "poly:drop:not_binary_yes_no_or_unresolved": 745,
  "poly:events_listed": 63224,
  "poly:markets_seen": 70263,
  "poly:windows_truncated_by_page_cap": 30,
  "pool_events": 2036,
  "pool_kalshi": 5254,
  "pool_polymarket": 3598,
  "price_checked": 335,
  "closed_before_t0_plus_1d_yes_rate": 0.4533
}
FILTER FUNNEL (canary):
{
  "drop:closed_before_t0_plus_1d": 120,
  "drop:kalshi_closed_early_gt_3d": 56,
  "drop:lifetime_lt_7d": 5820,
  "drop:no_price_within_window": 3,
  "drop:p_mkt_extreme": 3,
  "drop:resolved_outside_window": 4717,
  "drop:scheduled_close_after_window": 122819,
  "drop:volume": 5138,
  "kalshi:drop:not_binary_or_unresolved": 4188,
  "kalshi:markets_seen": 138252,
  "kalshi:series_allowed": 9381,
  "kalshi:series_listed": 9990,
  "pass_static": 1966,
  "poly:drop:category_or_excluded_tag": 10318,
  "poly:drop:not_binary_yes_no_or_unresolved": 91,
  "poly:events_listed": 5419,
  "poly:markets_seen": 6663,
  "poly:windows_truncated_by_page_cap": 0,
  "pool_events": 653,
  "pool_kalshi": 868,
  "pool_polymarket": 1098,
  "price_checked": 36,
  "closed_before_t0_plus_1d_yes_rate": 0.6833
}
all: {"n": 250, "by_venue": {"polymarket": 125, "kalshi": 125}, "by_category": {"Climate and Weather": 15, "Economics": 59, "Elections": 27, "Financials": 46, "Politics": 65, "Science and Technology": 16, "World": 22}, "by_split": {"dev": 50, "test": 200}, "base_rate_yes": 0.404, "mean_p_mkt": 0.3675, "p_mkt_source": {"last_trade": 126, "mid": 115, "previous": 9}, "n_events": 158, "t0_range": ["2026-02-08T18:00:00Z", "2026-09-24T21:00:00Z"]}
dev: {"n": 50, "by_venue": {"polymarket": 21, "kalshi": 29}, "by_category": {"Climate and Weather": 7, "Economics": 13, "Elections": 2, "Financials": 9, "Politics": 16, "World": 3}, "by_split": {"dev": 50}, "base_rate_yes": 0.4, "mean_p_mkt": 0.3724, "p_mkt_source": {"last_trade": 22, "mid": 25, "previous": 3}, "n_events": 32, "t0_range": ["2026-02-08T18:00:00Z", "2026-03-26T01:00:00Z"]}
test: {"n": 200, "by_venue": {"polymarket": 104, "kalshi": 96}, "by_category": {"Climate and Weather": 8, "Economics": 46, "Elections": 25, "Financials": 37, "Politics": 49, "Science and Technology": 16, "World": 19}, "by_split": {"test": 200}, "base_rate_yes": 0.405, "mean_p_mkt": 0.3663, "p_mkt_source": {"last_trade": 104, "mid": 90, "previous": 6}, "n_events": 126, "t0_range": ["2026-03-26T08:00:00Z", "2026-09-24T21:00:00Z"]}
canary: {"n": 30, "by_venue": {"kalshi": 15, "polymarket": 15}, "by_category": {"Climate and Weather": 2, "Companies": 1, "Economics": 3, "Elections": 5, "Politics": 8, "Science and Technology": 6, "World": 5}, "by_split": {"canary": 30}, "base_rate_yes": 0.4333, "mean_p_mkt": 0.3262, "p_mkt_source": {"mid": 13, "last_trade": 15, "previous": 2}, "n_events": 22, "t0_range": ["2025-01-12T14:00:00Z", "2025-05-28T14:00:00Z"]}
[exit 0]
$ uv run python -m mf.data.dataset --validate
OK 250 questions (dev=50 test=200) canary=30
[exit 0]
```

### M5 — Reasoning + Halawi aggregation + Batch path + pilot (PASS, 2026-10-07)

```
$ uv run pytest tests/test_reason.py tests/test_aggregate.py tests/test_batch.py -q
...........                                                                                  [100%]
11 passed in 0.76s
[exit 0]
$ uv run mf pilot --n 10 --allow-spend
[reason] 25/100 sync requests
[reason] 50/100 sync requests
[reason] 75/100 sync requests
[reason] 100/100 sync requests
{
  "created_utc": "2026-10-07T03:28:42.333031Z",
  "n_questions": 10,
  "usd_by_op_per_question_sync": {
    "query_gen": 0.000501,
    "reason": 0.034363,
    "reason_noret": 0.032131,
    "relevance_summary": 0.009601,
    "search_instant": 0.012,
    "supervisor_disagree": 0.0042,
    "supervisor_update": 0.001589
  },
  "usd_per_question_sync_total": 0.094386,
  "anthropic_usd_per_question_batch": 0.049139,
  "supervisor_trigger_rate": 0.5,
  "kept_evidence_per_question": [
    5,
    3,
    2,
    5,
    4,
    1,
    4,
    0,
    0,
    0
  ],
  "exa_results_per_question": [
    17,
    17,
    18,
    19,
    19,
    20,
    20,
    20,
    20,
    20
  ],
  "projected_backtest_anthropic_usd": 11.9634,
  "projected_backtest_exa_usd": 3.0,
  "remaining_anthropic_backtest_usd": 21.8338,
  "remaining_exa_2026-10_usd": 8.567,
  "forecast_stats": {
    "samples": 100,
    "samples_failed": 0,
    "supervisor_triggered": 5,
    "supervisor_replaced": 0,
    "supervisor_failed": 0,
    "questions": 10
  }
}
PROJECTED backtest: $11.96 anthropic, $3.00 exa (remaining: $21.83 anthropic backtest, $8.57 exa this month)
PILOT: projection within caps
[exit 0]
```

### M8 — Full backtest (FAIL, 2026-10-07)

```
$ uv run python scripts/check_metrics_arms.py
arms: 14 missing: [] without CI: [] n_test_scored: 200
CHECK1 OK
[exit 0]
$ MF_CACHE_MODE=readonly uv run mf evaluate --out reports/metrics_repro.json
'MF_CACHE_MODE' is not recognized as an internal or external command,
operable program or batch file.
[exit 1]
$ uv run python -c "import json;a=json.load(open('reports/metrics.json'));b=json.load(open('reports/metrics_repro.json'));assert a==b;print('REPRO OK')"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
FileNotFoundError: [Errno 2] No such file or directory: 'reports/metrics_repro.json'
[exit 1]
$ uv run mf budget
{
  "anthropic_backtest_cap_usd": 23.0,
  "anthropic_backtest_usd": 13.955241,
  "anthropic_cap_usd": 30.0,
  "anthropic_total_usd": 13.955241,
  "by_provider_op_month": [
    {
      "calls": 250,
      "month": "2026-10",
      "op": "query_gen",
      "provider": "anthropic",
      "usd": 0.139233
    },
    {
      "calls": 85,
      "month": "2026-10",
      "op": "reason",
      "provider": "anthropic",
      "usd": 0.58612
    },
    {
      "calls": 1200,
      "month": "2026-10",
      "op": "reason_batch",
      "provider": "anthropic",
      "usd": 4.56766
    },
    {
      "calls": 50,
      "month": "2026-10",
      "op": "reason_noret",
      "provider": "anthropic",
      "usd": 0.32131
    },
    {
      "calls": 1150,
      "month": "2026-10",
      "op": "reason_noret_batch",
      "provider": "anthropic",
      "usd": 4.05287
    },
    {
      "calls": 362,
      "month": "2026-10",
      "op": "relevance_summary",
      "provider": "anthropic",
      "usd": 2.610746
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_batch_batch",
      "provider": "anthropic",
      "usd": 4.6e-05
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_helper",
      "provider": "anthropic",
      "usd": 9.2e-05
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_reasoner",
      "provider": "anthropic",
      "usd": 0.000862
    },
    {
      "calls": 126,
      "month": "2026-10",
      "op": "supervisor_disagree",
      "provider": "anthropic",
      "usd": 1.201834
    },
    {
      "calls": 126,
      "month": "2026-10",
      "op": "supervisor_update",
      "provider": "anthropic",
      "usd": 0.474468
    },
    {
      "calls": 19,
      "month": "2026-10",
      "op": "search_fast",
      "provider": "exa",
      "usd": 0.133
    },
    {
      "calls": 758,
      "month": "2026-10",
      "op": "search_instant",
      "provider": "exa",
      "usd": 3.032
    }
  ],
  "exa_by_month_usd": {
    "2026-10": 3.165
  },
  "exa_monthly_cap_usd": 9.0,
  "n_paid_calls": 4129
}
Anthropic: $13.9552 of $30.00 total (backtest $13.9552 of $23.00)
Exa 2026-10: $3.1650 of $9.00
BUDGET OK: all caps respected
[exit 0]
```

_The FAIL above is a logging-harness bug (cmd.exe does not accept the POSIX `VAR=value cmd` prefix), not a project failure; `scripts/log_milestone.py` was fixed and M8 re-run below._

### M8 — Full backtest (re-run after logger fix) (PASS, 2026-10-07)

```
$ uv run python scripts/check_metrics_arms.py
arms: 14 missing: [] without CI: [] n_test_scored: 200
CHECK1 OK
[exit 0]
$ MF_CACHE_MODE=readonly uv run mf evaluate --out reports/metrics_repro.json
wrote reports/metrics_repro.json: n_test_scored=200 events=126 failed={'noret_single': 0, 'noret_ens': 0, 'halawi_single': 0, 'halawi': 0, 'halawi_sup': 0}
  const_0.5        Brier 0.2500  95% CI [0.2500, 0.2500]
  base_rate        Brier 0.2410  95% CI [0.2287, 0.2533]
  market           Brier 0.1676  95% CI [0.1382, 0.1978]
  noret_ens        Brier 0.2802  95% CI [0.2378, 0.3221]
  halawi           Brier 0.2794  95% CI [0.2364, 0.3227]
  halawi_sup       Brier 0.2695  95% CI [0.2280, 0.3122]
  aia              Brier 0.3029  95% CI [0.2515, 0.3554]
  market_ens_aia   Brier 0.1688  95% CI [0.1392, 0.1991]
  PRIMARY aia_minus_halawi: dBrier +0.0235 [+0.0058, +0.0394] P(d<0)=0.005
  PRIMARY market_ens_aia_minus_market: dBrier +0.0012 [+0.0004, +0.0021] P(d<0)=0.003
[exit 0]
$ uv run python -c "import json;a=json.load(open('reports/metrics.json'));b=json.load(open('reports/metrics_repro.json'));assert a==b;print('REPRO OK')"
REPRO OK
[exit 0]
$ uv run mf budget
{
  "anthropic_backtest_cap_usd": 23.0,
  "anthropic_backtest_usd": 13.955241,
  "anthropic_cap_usd": 30.0,
  "anthropic_total_usd": 13.955241,
  "by_provider_op_month": [
    {
      "calls": 250,
      "month": "2026-10",
      "op": "query_gen",
      "provider": "anthropic",
      "usd": 0.139233
    },
    {
      "calls": 85,
      "month": "2026-10",
      "op": "reason",
      "provider": "anthropic",
      "usd": 0.58612
    },
    {
      "calls": 1200,
      "month": "2026-10",
      "op": "reason_batch",
      "provider": "anthropic",
      "usd": 4.56766
    },
    {
      "calls": 50,
      "month": "2026-10",
      "op": "reason_noret",
      "provider": "anthropic",
      "usd": 0.32131
    },
    {
      "calls": 1150,
      "month": "2026-10",
      "op": "reason_noret_batch",
      "provider": "anthropic",
      "usd": 4.05287
    },
    {
      "calls": 362,
      "month": "2026-10",
      "op": "relevance_summary",
      "provider": "anthropic",
      "usd": 2.610746
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_batch_batch",
      "provider": "anthropic",
      "usd": 4.6e-05
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_helper",
      "provider": "anthropic",
      "usd": 9.2e-05
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_reasoner",
      "provider": "anthropic",
      "usd": 0.000862
    },
    {
      "calls": 126,
      "month": "2026-10",
      "op": "supervisor_disagree",
      "provider": "anthropic",
      "usd": 1.201834
    },
    {
      "calls": 126,
      "month": "2026-10",
      "op": "supervisor_update",
      "provider": "anthropic",
      "usd": 0.474468
    },
    {
      "calls": 19,
      "month": "2026-10",
      "op": "search_fast",
      "provider": "exa",
      "usd": 0.133
    },
    {
      "calls": 758,
      "month": "2026-10",
      "op": "search_instant",
      "provider": "exa",
      "usd": 3.032
    }
  ],
  "exa_by_month_usd": {
    "2026-10": 3.165
  },
  "exa_monthly_cap_usd": 9.0,
  "n_paid_calls": 4129
}
Anthropic: $13.9552 of $30.00 total (backtest $13.9552 of $23.00)
Exa 2026-10: $3.1650 of $9.00
BUDGET OK: all caps respected
[exit 0]
```

### M9 — Leakage audit (PASS, 2026-10-07)

```
$ uv run mf audit-leakage --summarize
audited=50 verdicts={'clean': 49, 'unsure': 1} LEAK RATE=0.00% (leak or unsure 2.00%)
[exit 0]
$ uv run python -c "import json;m=json.load(open('reports/metrics.json'));l=m['leakage'];print({k:l[k] for k in ('canary_n_scored','canary_noret_ens_brier','canary_market_brier','test_noret_ens_brier','test_market_brier')})"
{'canary_n_scored': 30, 'canary_noret_ens_brier': 0.162946, 'canary_market_brier': 0.190124, 'test_noret_ens_brier': 0.28017, 'test_market_brier': 0.16757}
[exit 0]
```

### M10 — Live mode (PASS, 2026-10-07)

```
$ uv run pytest tests/test_live_ledger.py -q
.........                                                                                    [100%]
9 passed in 0.33s
[exit 0]
$ uv run mf live --n 3 --dry-run
[live dry-run] seq=0 poly:2063128 p_mkt=0.97 halawi=0.45 aia=0.414 aia+mkt=0.7476 hash=11f4ea15
[live dry-run] seq=1 poly:2063129 p_mkt=0.03 halawi=0.3567 aia=0.2647 aia+mkt=0.1239 hash=977fcc32
[live dry-run] seq=2 poly:2063130 p_mkt=0.03 halawi=0.3167 aia=0.2088 aia+mkt=0.1015 hash=6338425f
[live dry-run] temp ledger OK n=3 head=6338425f2847f1d4c0e5a5cf1e6803095295d40373b636845b4e4ec66ec58e82; network calls: llm=24 (fake) exa=2 (mocked); real ledger untouched
[exit 0]
$ uv run mf verify-ledger
LEDGER OK n=10 head=dd4761a1291bec68a002420291764aa19fc1678430412ae9e5dc7920c2f5dbdc
[exit 0]
$ git log --oneline -- data/live/forecasts.jsonl
d740965 live: 2026-10-07 n=10 head=dd4761a1
[exit 0]
```

### M11 — Report, README, RESULTS (PASS, 2026-10-07)

```
$ uv run pytest tests/test_report.py -q
..                                                                                           [100%]
2 passed in 5.87s
[exit 0]
$ uv run python scripts/verify.py

$ uv run pytest -q -p no:cacheprovider
............................................................................................ [ 69%]
.........................................                                                    [100%]
133 passed in 8.94s
[exit 0]

$ uv run python -m mf.data.dataset --validate
OK 250 questions (dev=50 test=200) canary=30
[exit 0]

$ uv run mf evaluate --out reports/metrics_repro.json
wrote reports/metrics_repro.json: n_test_scored=200 events=126 failed={'noret_single': 0, 'noret_ens': 0, 'halawi_single': 0, 'halawi': 0, 'halawi_sup': 0}
  const_0.5        Brier 0.2500  95% CI [0.2500, 0.2500]
  base_rate        Brier 0.2410  95% CI [0.2287, 0.2533]
  market           Brier 0.1676  95% CI [0.1382, 0.1978]
  noret_ens        Brier 0.2802  95% CI [0.2378, 0.3221]
  halawi           Brier 0.2794  95% CI [0.2364, 0.3227]
  halawi_sup       Brier 0.2695  95% CI [0.2280, 0.3122]
  aia              Brier 0.3029  95% CI [0.2515, 0.3554]
  market_ens_aia   Brier 0.1688  95% CI [0.1392, 0.1991]
  PRIMARY aia_minus_halawi: dBrier +0.0235 [+0.0058, +0.0394] P(d<0)=0.005
  PRIMARY market_ens_aia_minus_market: dBrier +0.0012 [+0.0004, +0.0021] P(d<0)=0.003
[exit 0]

$ compare reports/metrics.json reports/metrics_repro.json (canonical JSON)
REPRO OK (identical after canonical JSON)

$ uv run mf verify-ledger
LEDGER OK n=10 head=dd4761a1291bec68a002420291764aa19fc1678430412ae9e5dc7920c2f5dbdc
[exit 0]

$ uv run mf budget
{
  "anthropic_backtest_cap_usd": 23.0,
  "anthropic_backtest_usd": 13.955241,
  "anthropic_cap_usd": 30.0,
  "anthropic_total_usd": 14.562981,
  "by_provider_op_month": [
    {
      "calls": 260,
      "month": "2026-10",
      "op": "query_gen",
      "provider": "anthropic",
      "usd": 0.144909
    },
    {
      "calls": 135,
      "month": "2026-10",
      "op": "reason",
      "provider": "anthropic",
      "usd": 0.9905
    },
    {
      "calls": 1200,
      "month": "2026-10",
      "op": "reason_batch",
      "provider": "anthropic",
      "usd": 4.56766
    },
    {
      "calls": 50,
      "month": "2026-10",
      "op": "reason_noret",
      "provider": "anthropic",
      "usd": 0.32131
    },
    {
      "calls": 1150,
      "month": "2026-10",
      "op": "reason_noret_batch",
      "provider": "anthropic",
      "usd": 4.05287
    },
    {
      "calls": 377,
      "month": "2026-10",
      "op": "relevance_summary",
      "provider": "anthropic",
      "usd": 2.737902
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_batch_batch",
      "provider": "anthropic",
      "usd": 4.6e-05
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_helper",
      "provider": "anthropic",
      "usd": 9.2e-05
    },
    {
      "calls": 1,
      "month": "2026-10",
      "op": "smoke_reasoner",
      "provider": "anthropic",
      "usd": 0.000862
    },
    {
      "calls": 131,
      "month": "2026-10",
      "op": "supervisor_disagree",
      "provider": "anthropic",
      "usd": 1.251616
    },
    {
      "calls": 131,
      "month": "2026-10",
      "op": "supervisor_update",
      "provider": "anthropic",
      "usd": 0.495214
    },
    {
      "calls": 19,
      "month": "2026-10",
      "op": "search_fast",
      "provider": "exa",
      "usd": 0.133
    },
    {
      "calls": 788,
      "month": "2026-10",
      "op": "search_instant",
      "provider": "exa",
      "usd": 3.152
    }
  ],
  "exa_by_month_usd": {
    "2026-10": 3.285
  },
  "exa_monthly_cap_usd": 9.0,
  "n_paid_calls": 4244
}
Anthropic: $14.5630 of $30.00 total (backtest $13.9552 of $23.00)
Exa 2026-10: $3.2850 of $9.00
BUDGET OK: all caps respected
[exit 0]

$ check RESULTS.md / README.md placeholders and METRICS blocks
RESULTS.md: METRICS block matches metrics.json
README.md: METRICS block matches metrics.json
RESULTS.md: no TODO/TBD/XX/_Pending placeholders

$ git status --porcelain --ignored
!! .env
!! .venv/
!! cache/
!! reports/metrics_repro.json
!! src/mf/__pycache__/
!! src/mf/core/__pycache__/
!! src/mf/data/__pycache__/
!! src/mf/eval/__pycache__/
!! src/mf/forecast/__pycache__/
!! src/mf/live/__pycache__/
!! src/mf/llm/__pycache__/
!! src/mf/retrieval/__pycache__/
!! state/
!! tests/__pycache__/
[exit 0]

$ git ls-files
.env.example
.gitattributes
.gitignore
.python-version
LEARNING.md
PLAN.md
PREREGISTRATION.md
README.md
RESOURCES.md
RESULTS.md
configs/default.toml
configs/pricing.toml
data/dataset/canary_precutoff.jsonl
data/dataset/dataset_card.json
data/dataset/questions.jsonl
data/live/forecasts.jsonl
data/runs/backtest_v1/evidence.jsonl
data/runs/backtest_v1/forecasts.jsonl
data/runs/backtest_v1/retrieval_meta.jsonl
data/runs/backtest_v1/samples.jsonl
prompts/CHANGELOG.md
prompts/lockfile.json
prompts/reasoning/r1_halawi_scratchpad_v1.md
prompts/reasoning/r2_base_rates_v1.md
prompts/reasoning/r3_inside_outside_view_v1.md
prompts/reasoning/r4_premortem_both_sides_v1.md
prompts/reasoning/r5_superforecaster_checklist_v1.md
prompts/retrieval/query_gen_v1.md
prompts/retrieval/relevance_summary_v1.md
prompts/smoke/smoke_helper_v1.md
prompts/smoke/smoke_reasoner_v1.md
prompts/supervisor/disagreement_v1.md
prompts/supervisor/update_v1.md
pyproject.toml
reports/figures/brier_bars.png
reports/figures/brier_by_horizon.png
reports/figures/delta_forest.png
reports/figures/reliability.png
reports/figures/scatter_vs_market.png
reports/index.html
reports/leakage_audit.csv
reports/leakage_audit_summary.json
reports/metrics.json
reports/spend.json
scripts/check_metrics_arms.py
scripts/live_weekly.ps1
scripts/log_milestone.py
scripts/verify.py
src/mf/__init__.py
src/mf/cli.py
src/mf/commands.py
src/mf/config.py
src/mf/core/__init__.py
src/mf/core/budget.py
src/mf/core/cache.py
src/mf/core/hashing.py
src/mf/core/http.py
src/mf/core/pricing.py
src/mf/core/timeutil.py
src/mf/data/__init__.py
src/mf/data/common.py
src/mf/data/dataset.py
src/mf/data/fixtures.py
src/mf/data/kalshi.py
src/mf/data/polymarket.py
src/mf/data/prices.py
src/mf/eval/__init__.py
src/mf/eval/arms.py
src/mf/eval/audit.py
src/mf/eval/bootstrap.py
src/mf/eval/calibration.py
src/mf/eval/metrics.py
src/mf/eval/report.py
src/mf/forecast/__init__.py
src/mf/forecast/aggregate.py
src/mf/forecast/calibrate.py
src/mf/forecast/market_ensemble.py
src/mf/forecast/pipeline.py
src/mf/forecast/reason.py
src/mf/forecast/supervisor.py
src/mf/live/__init__.py
src/mf/live/ledger.py
src/mf/live/run.py
src/mf/live/score.py
src/mf/live/select.py
src/mf/llm/__init__.py
src/mf/llm/batch.py
src/mf/llm/client.py
src/mf/llm/parse.py
src/mf/llm/prompts.py
src/mf/retrieval/__init__.py
src/mf/retrieval/exa_client.py
src/mf/retrieval/leakage.py
src/mf/retrieval/pipeline.py
src/mf/retrieval/queries.py
src/mf/retrieval/summarize.py
src/mf/runtime.py
src/mf/schemas.py
src/mf/smoke.py
tests/conftest.py
tests/fixtures/anthropic/smoke_haiku.json
tests/fixtures/anthropic/smoke_sonnet5.json
tests/fixtures/exa/search_synthetic.json
tests/fixtures/exa/smoke_fast_0.json
tests/fixtures/exa/smoke_fast_1.json
tests/fixtures/exa/smoke_instant_0.json
tests/fixtures/exa/smoke_instant_1.json
tests/fixtures/kalshi/can_close_early_market.json
tests/fixtures/kalshi/cutoff.json
tests/fixtures/kalshi/events_fed_settled.json
tests/fixtures/kalshi/historical_candles.json
tests/fixtures/kalshi/historical_markets_fed_jul26.json
tests/fixtures/kalshi/live_candles.json
tests/fixtures/kalshi/live_candles_404_for_historical.json
tests/fixtures/polymarket/event_negrisk.json
tests/fixtures/polymarket/event_non_yes_no.json
tests/fixtures/polymarket/prices_history.json
tests/test_aggregate.py
tests/test_batch.py
tests/test_bootstrap.py
tests/test_budget.py
tests/test_cache.py
tests/test_calibrate.py
tests/test_dataset.py
tests/test_exa_client.py
tests/test_kalshi.py
tests/test_leakage.py
tests/test_live_ledger.py
tests/test_llm_client.py
tests/test_market_ensemble.py
tests/test_metrics.py
tests/test_parse.py
tests/test_polymarket.py
tests/test_prices.py
tests/test_pricing.py
tests/test_prompts.py
tests/test_reason.py
tests/test_report.py
tests/test_retrieval.py
tests/test_supervisor.py
uv.lock
[exit 0]
git: .env, cache/, state/ are neither tracked nor staged

VERIFY: PASS metrics_sha=84cc418825e1f3bd4569f8015b52883c3ee39edaf0c22190d50fe40ddadca61f
[exit 0]
```
