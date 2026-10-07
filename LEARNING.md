# LEARNING — the ideas behind market-forecaster

Short notes on every concept this project leans on, followed by interview-style questions with
compact model answers. Where a number from this project is relevant, see `RESULTS.md` (all numbers
there are machine-generated; none are repeated here so they can't go stale).

---

## 1. Scoring forecasts

**Proper scoring rules.** A scoring rule is *proper* if a forecaster minimizes expected loss by
reporting their true belief. Brier score `(p − y)²` and log loss `−[y log p + (1−y) log(1−p)]` are
both strictly proper. Accuracy@0.5 is not: it rewards 0.51 and 0.99 equally, so it cannot tell a
calibrated forecaster from a reckless one.

**Brier vs log loss.** Brier is bounded (0–1) and forgiving of confident misses; log loss is
unbounded and punishes a confident miss severely (p=0.01 on a YES costs 4.6). We clip log loss to
[0.01, 0.99] so one extreme forecast cannot dominate the mean. Brier is the primary metric because
prediction-market literature (AIA, Halawi, ForecastBench) reports it, which makes comparisons possible.

**Murphy decomposition.** `Brier = Reliability − Resolution + Uncertainty`.
- *Uncertainty* `ō(1−ō)` depends only on the outcomes (the base rate), not the forecaster.
- *Reliability* (lower is better) is calibration error: within each forecast bin, how far is the
  forecast from the observed frequency.
- *Resolution* (higher is better) is how far bin frequencies move away from the base rate, i.e. how
  much the forecasts *discriminate*.
The identity is exact only when bins are the unique forecast values; with 10 equal-width bins a
small within-bin variance term appears (the test suite checks the exact case).

**Calibration vs sharpness.** A forecaster who always says the base rate is perfectly calibrated
and useless. Sharpness is willingness to move away from the base rate; resolution is sharpness that
turns out to be right. Good forecasting is *maximize sharpness subject to calibration*.

**Reliability diagrams and ECE pitfalls.** ECE (expected calibration error) averages |mean p −
frequency| over bins, weighted by count. With 200 questions and 10 bins, many bins hold < 10 items,
so ECE is noisy and biased upward even for a perfect forecaster. Always show bin counts (our
reliability figure has a count panel) and don't over-read small ECE differences.

## 2. Aggregation and extremization

**Why averaging pulls toward 0.5.** Each sample's probability mixes signal with noise. Averaging
removes noise but also averages away *private information*: if five forecasters each have partial
evidence pointing the same way, the right pooled belief is more extreme than any of them, yet the
mean sits in the middle. Averages of probabilities are systematically under-confident.

**Extremization / Platt scaling.** `p' = sigmoid(a · logit(p))` with `a > 1` pushes forecasts
away from 0.5. AIA uses a *fixed* `a = √3` from Neyman & Roughgarden (2022), who show it is a
robust choice for aggregating substitutable signals. Fixing `a` costs no data and cannot overfit;
fitting `a` on our 50 dev questions is reported only as a secondary arm because the estimate is noisy.

**Trimmed mean vs median vs log-odds pooling.** The trimmed mean (drop min and max of 5) is robust
to one wild sample and keeps more information than the median. Log-odds (geometric) pooling
averages in logit space; it extremizes slightly by construction and is the natural pairing with
Platt scaling. We use the trimmed mean to stay faithful to Halawi.

**Wisdom of crowds needs independent errors.** Five prompts on one model are *not* five independent
forecasters: they share training data and blind spots (the "monoculture" paper, arXiv 2606.26583,
measures ρ≈0.70 between LLM errors). Expect ensembling gains to be smaller than with human crowds.
The AIA supervisor is one response: instead of averaging disagreements away, it investigates them.

## 3. Markets as a baseline

**Efficient-market hypothesis for prediction markets.** A liquid market price aggregates many
traders' information and money; beating it consistently is hard. The honest prior is that an LLM
will *not* beat a liquid market, which is why the main comparison is "LLM ⊕ market vs market".

**Favorite–longshot bias.** Longshots tend to be over-priced and favourites under-priced (fees,
risk-loving bettors, the asymmetric payoff of shorting a 3¢ contract). We drop questions with
p_mkt outside [0.03, 0.97] partly because near-certain questions add noise and no signal.

**Bid/ask mid vs last trade.** The last trade can be stale by hours; the mid of the current bid and
ask is a better real-time estimate when the spread is tight. We use the mid when the spread is
≤ 10¢ and fall back to the last trade otherwise (the source is recorded per question).

**Why a blend can beat both.** If the LLM's errors are only partly correlated with the market's,
`w·p_llm + (1−w)·p_mkt` reduces variance even when the LLM alone is worse. The weight must be fit
out-of-sample (we use 5-fold cross-fitting grouped by event, and separately a dev-fit weight).

## 4. Leakage — why most forecasting backtests lie

Taxonomy (after Paleka et al., *Pitfalls in Evaluating LM Forecasters*):
1. **Model knowledge leakage.** The model was trained on text written after the question resolved.
   Fix: only questions created *after* the reasoner's training cutoff (Sonnet 5: Jan 2026).
   Detector: a *canary* set resolved before the cutoff — if the model "knows" those outcomes, its
   no-retrieval Brier there will be suspiciously good.
2. **Retrieval leakage.** Search results published (or silently updated) after t0. Fixes: Exa
   `endPublishedDate = t0 − 24h`, drop undated results (in our smoke test, *undated* results were
   overwhelmingly post-cutoff odds pages), regex for "Updated <date>" markers, a domain blocklist
   (prediction markets, Wikipedia, social media), and an LLM judge for "describes events after t0".
3. **Question-text leakage.** Market metadata that encodes the answer: Kalshi's `expiration_value`
   holds the realized outcome text (e.g. "Hike 25bps"), `rules_secondary` can be amended, and
   Polymarket descriptions accumulate "Update:" paragraphs. Fix: whitelist the fields that may reach
   a prompt (`schemas.prompt_fields`) and test that rendered prompts never contain outcome text.
4. **Selection leakage ("resolved early" bias).** If you only keep markets that closed in your
   window, "will X happen by Dec 31" questions that resolved YES early are over-represented. Fix:
   filter on the *scheduled* close, not the actual close (Kalshi: `expected_expiration_time`, which
   an early close doesn't move), and report the YES rate of questions dropped for closing before t0.

## 5. Statistics for small N

**Bootstrap.** Resample the test set with replacement many times and recompute the metric; the
spread of the resampled metrics approximates its sampling distribution (95% percentile CI).

**Cluster bootstrap.** Two Kalshi markets on the same Fed meeting are not independent; resampling
questions individually understates uncertainty. We resample whole *events* (clusters).

**Paired tests.** "Is AIA better than Halawi?" should compare the two on the *same* questions:
bootstrap the per-question difference in loss. Pairing removes the large between-question
variance (some questions are just hard) and shrinks the CI dramatically.

**Power and the minimum detectable effect.** With 200 questions and a paired ΔBrier SD around 0.06,
the standard error is ≈0.004, so the smallest effect detectable with 80% power at α=0.05 is about
2.8·SE ≈ 0.012 — larger than the 0.005–0.008 gains AIA reports per component. Inconclusive is the
expected outcome for some ablations, and saying so is the correct report.

**Pre-registration.** Writing down the arms, the primary metric and the primary comparisons
*before* touching the test set (PREREGISTRATION.md, committed first) prevents the garden of
forking paths: trying many subsets and reporting the one that looks good.

## 6. Building the LLM pipeline

**RAG for forecasting.** Query generation (the model writes search queries, not the user's raw
question), retrieval, relevance filtering, then summarization so the reasoner sees short, dated,
relevant facts instead of raw pages. Retrieval helps most when there was prior public discussion
(Hindcast, arXiv 2607.14051).

**LLM-as-judge.** A cheap helper model rates relevance 1–6 and flags leakage. Judges make mistakes,
so the deterministic filters run first, and a human audits a random sample (the leak rate is reported).

**Prompt versioning + content-addressed caching.** Every call's cache key is the sha256 of the
canonical request (model, rendered prompt, prompt file hash, sample index). Editing a prompt
changes its hash, which invalidates exactly the affected calls and nothing else. Released prompts
are frozen via a lockfile test; changes go to a new `_v2` file.

**Batch API economics.** Message Batches cost 50% of synchronous calls, at the price of latency
(minutes to hours). Every reasoning sample is batchable because nothing waits on it; the supervisor
is sequential (it depends on the samples), so it runs synchronously.

**Hash chains for tamper-evident logs.** Each live record stores `hash = sha256(record + prev_hash)`.
Changing any old record changes its hash, which breaks every later link. Committing the file to a
public git remote after each run adds an external timestamp, so forecasts cannot be backfilled.

---

## Likely interview questions (with short answers)

**Why Brier and not accuracy?** Accuracy is not a proper scoring rule: it ignores confidence, so it
rewards 0.51 and 0.99 equally and can't measure calibration. Brier is proper, decomposes into
calibration and discrimination, and is the standard in the forecasting literature.

**Your model beats the market by 0.003 — is it real?** Probably not on its own. Check the paired
cluster-bootstrap CI on the difference; with ~200 questions the MDE is ~0.012, so 0.003 is well
inside noise. I'd also check it isn't driven by one category or by leakage (canary, audit), and
I'd want it to replicate forward on the live ledger before believing it.

**How do you know there's no leakage?** I can't prove absence, so I layer defences and measure:
post-cutoff questions only; a canary set to detect model-memory leakage; dated-before-t0 retrieval
with undated results dropped; marker-date regex; blocklist; an LLM leak judge; a 50-item human audit
with a reported leak rate; and a robustness re-score excluding questions whose retrieval surfaced
any flagged item. The residual risk is stated, not hidden.

**Why does averaging LLM samples under-confide, and how does extremizing fix it?** Averaging
probabilities discards the fact that independent pieces of evidence pointing the same way should
compound. Extremizing (`sigmoid(a·logit p)`, a≈√3) restores that compounding; a fixed coefficient
avoids overfitting a small calibration set.

**How would you turn forecasts into trades?** Only trade when |p − p_mkt| exceeds fees plus half
the spread plus a margin for model error; size with fractional Kelly (full Kelly assumes your p is
exact). Account for Kalshi's fee formula, slippage, capital lock-up until resolution, and adverse
selection (if your limit order fills, someone may know more than you). Accuracy gains of 0.01 Brier
rarely survive all of that; Prediction Arena (arXiv 2604.07355) found frontier models lost money live.

**How would you scale to 10k questions within budget?** Batch everything batchable; cache by
content; shrink K where ensembling gains flatten; use the cheap model for retrieval helpers; share
retrieval across markets in the same event; prompt-cache the long static system prompt; measure
$/question on a pilot and enforce caps in code before each call.

**What's the difference between calibration and sharpness?** Calibration: when you say 70%, it
happens 70% of the time. Sharpness: how far your forecasts move from the base rate. Constant
base-rate forecasts are calibrated but not sharp; the goal is maximal sharpness subject to calibration.

**Why cluster the bootstrap by event?** Markets on the same event (e.g. several Fed-decision
strikes) have correlated outcomes and correlated forecast errors. Treating them as independent
overstates the effective sample size and produces CIs that are too narrow.

**How would you detect that a provider silently changed a model?** Keep a fixed canary prompt set
with cached responses; periodically re-run it uncached and compare outputs, token counts and
probability distributions (e.g. KS test on canary forecasts). Log the response `model` field and
request IDs, and pin dated model IDs where offered.

**Design a live eval that can't be backfilled.** Append-only, hash-chained forecast log; each run
commits the log to a public remote (a timestamp you don't control); record the market price fetched
at forecast time; score only after resolution with a separate append-only scores file; publish the
verification command (`mf verify-ledger`) so anyone can check the chain.
