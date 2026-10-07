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
