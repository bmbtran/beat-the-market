# RESULTS — market-forecaster

> Every number in this file comes from `reports/metrics.json` (inserted by `mf report`) or is verbatim
> command output. Nothing here is typed by hand.

## Verify

_Pending: `uv run python scripts/verify.py` output goes here once the project is complete._

## Headline

<!-- METRICS:START -->
_Pending: populated by `mf report` after the M8 backtest._
<!-- METRICS:END -->

## What didn't work

_Pending: filled after the backtest._

## Leakage

_Pending: canary vs test, human audit rate, filter counts._

## Cost

_Pending: from `reports/spend.json`._

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
