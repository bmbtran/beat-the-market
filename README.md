# market-forecaster

Work in progress.

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
