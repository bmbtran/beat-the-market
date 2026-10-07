"""`mf report`: figures, single-file reports/index.html, reports/spend.json, and the METRICS blocks in
README.md / RESULTS.md (every number comes from reports/metrics.json; nothing is typed by hand).

Chart palette: reference categorical slots 1-3 (blue, orange, aqua) on a #fcfcfb surface, validated
with the dataviz validator (all pairs pass; aqua < 3:1 contrast -> always direct-labeled + tabulated).
"""

from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
ARM_COLORS = {"aia": BLUE, "market": ORANGE, "halawi": AQUA}
START, END = "<!-- METRICS:START -->", "<!-- METRICS:END -->"
ARM_LABELS = {
    "const_0.5": "Constant 0.5", "base_rate": "Dev base rate", "market": "Market price at t0",
    "noret_single": "No retrieval, 1 sample", "noret_ens": "No retrieval, K=5", "halawi_single": "Retrieval, 1 sample",
    "halawi": "Halawi (retrieval, K=5)", "halawi_platt": "Halawi + Platt √3", "halawi_sup": "Halawi + supervisor",
    "aia": "AIA (supervisor + Platt √3)", "aia_platt_fit": "AIA, Platt fit on dev", "market_ens_halawi": "Halawi ⊕ market",
    "market_ens_aia": "AIA ⊕ market (CV)", "market_ens_aia_devw": "AIA ⊕ market (dev w)",
}
ORDER = list(ARM_LABELS)
SHORT = {"aia": "AIA", "halawi": "Halawi", "market": "Market"}


def _style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 1.0, "grid.linestyle": "-",
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10, "axes.titlesize": 11,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
        "lines.linewidth": 2, "lines.solid_capstyle": "round", "svg.hashsalt": "mf", "figure.dpi": 100,
        "axes.axisbelow": True,
    })


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)


def fig_reliability(m: dict, path: Path) -> None:
    arms = ["aia", "halawi", "market"]
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.2), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    for j, a in enumerate(arms):
        rows = m["reliability"][a]
        xs = [r["mean_p"] for r in rows if r["n"]]
        ys = [r["frac_yes"] for r in rows if r["n"]]
        ax = axes[0, j]
        ax.plot([0, 1], [0, 1], color=INK2, linewidth=1, alpha=0.5)
        ax.plot(xs, ys, color=ARM_COLORS[a], marker="o", markersize=7, markeredgecolor=SURFACE, markeredgewidth=2)
        ax.set_title(f"{SHORT[a]}  ·  ECE {m['arms'][a]['ece']:.3f}")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        if j == 0:
            ax.set_ylabel("Observed YES frequency")
        cx = [(r["bin_low"] + r["bin_high"]) / 2 for r in rows]
        axes[1, j].bar(cx, [r["n"] for r in rows], width=0.08, color=ARM_COLORS[a])
        axes[1, j].set_xlabel("Forecast probability (10 bins)")
        if j == 0:
            axes[1, j].set_ylabel("Questions")
    fig.suptitle(f"Reliability on the test set (n={m['n_test_scored']})", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    _save(fig, path)


def fig_brier_bars(m: dict, path: Path) -> None:
    arms = [a for a in ORDER if a in m["arms"]][::-1]
    b = [m["arms"][a]["brier"] for a in arms]
    lo = [m["arms"][a]["brier_ci"]["ci_low"] for a in arms]
    hi = [m["arms"][a]["brier_ci"]["ci_high"] for a in arms]
    fig, ax = plt.subplots(figsize=(8, 6))
    y = np.arange(len(arms))
    colors = [ORANGE if a == "market" else BLUE for a in arms]
    ax.barh(y, b, height=0.6, color=colors)
    ax.errorbar(b, y, xerr=[np.array(b) - lo, np.array(hi) - b], fmt="none", ecolor=INK, elinewidth=1.2, capsize=3)
    ax.axvline(m["arms"]["market"]["brier"], color=ORANGE, linewidth=1)
    for yi, bi, hii in zip(y, b, hi):
        ax.text(hii + 0.003, yi, f"{bi:.3f}", va="center", color=INK2, fontsize=9)
    ax.set_yticks(y, [ARM_LABELS[a] for a in arms])
    ax.set_xlabel("Brier score on test (lower is better), 95% cluster-bootstrap CI")
    ax.set_title("Every arm vs. the market price (orange line)")
    ax.grid(axis="y", visible=False)
    _save(fig, path)


def fig_delta_forest(m: dict, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5), sharey=True)
    arms = [a for a in ORDER if a not in ("market", "halawi")][::-1]
    for ax, key, ref in ((axes[0], "delta_brier_vs_market", "market"), (axes[1], "delta_brier_vs_halawi", "Halawi")):
        d = m[key]
        y = np.arange(len(arms))
        for yi, a in zip(y, arms):
            r = d[a]
            ax.plot([r["ci_low"], r["ci_high"]], [yi, yi], color=BLUE, linewidth=2)
            ax.plot(r["delta"], yi, "o", color=BLUE, markersize=7, markeredgecolor=SURFACE, markeredgewidth=2)
        ax.axvline(0, color=INK2, linewidth=1)
        ax.set_yticks(y, [ARM_LABELS[a] for a in arms])
        ax.set_title(f"ΔBrier vs {ref} (left of 0 = better)")
        ax.set_xlabel("Paired ΔBrier, 95% cluster-bootstrap CI")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5))
        ax.grid(axis="y", visible=False)
    fig.tight_layout()
    _save(fig, path)


def fig_scatter(m: dict, path: Path) -> None:
    pts = m["scatter"]
    fig, ax = plt.subplots(figsize=(6, 6))
    for yv, color, marker, label in ((1, BLUE, "o", "Resolved YES"), (0, ORANGE, "^", "Resolved NO")):
        xs = [p["p_mkt"] for p in pts if p["y"] == yv]
        ys = [p["p_aia"] for p in pts if p["y"] == yv]
        ax.scatter(xs, ys, s=40, color=color, marker=marker, edgecolors=SURFACE, linewidths=1.5,
                   label=f"{label} (n={len(xs)})", alpha=0.9)
    ax.plot([0, 1], [0, 1], color=INK2, linewidth=1, alpha=0.6)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Market price at t0")
    ax.set_ylabel("AIA forecast")
    ax.set_title("AIA forecast vs. market, by outcome")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    _save(fig, path)


def fig_horizon(m: dict, path: Path) -> None:
    bd = m["breakdowns"]["horizon"]
    buckets = [b for b in ("<7d", "7-30d", ">30d") if b in bd]
    arms = ["market", "halawi", "aia"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    w = 0.24
    x = np.arange(len(buckets))
    for k, a in enumerate(arms):
        vals = [bd[b][a] for b in buckets]
        bars = ax.bar(x + (k - 1) * (w + 0.02), vals, width=w, color=ARM_COLORS[a], label=ARM_LABELS[a])
        for rect, v in zip(bars, vals):
            ax.text(rect.get_x() + rect.get_width() / 2, v + 0.003, f"{v:.3f}", ha="center", fontsize=8, color=INK2)
    ax.set_xticks(x, [f"{b}\n(n={bd[b]['n']})" for b in buckets])
    ax.set_ylabel("Brier (lower is better)")
    ax.set_title("Brier by forecast horizon (time from t0 to scheduled close)")
    ax.set_ylim(0, max(bd[b][a] for b in buckets for a in arms) * 1.15)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3)
    ax.grid(axis="x", visible=False)
    _save(fig, path)


def fig_live(scores: list[dict], path: Path) -> bool:
    rows = [r for r in sorted(scores, key=lambda r: r["seq"]) if r.get("brier_aia") is not None]
    if not rows:
        return False
    n = np.arange(1, len(rows) + 1)
    fig, ax = plt.subplots(figsize=(8, 4))
    for key, color, label in (("brier_aia", BLUE, "AIA"), ("brier_mkt_at_forecast", ORANGE, "Market")):
        cum = np.cumsum([r[key] for r in rows]) / n
        ax.plot(n, cum, color=color, label=label)
        ax.text(n[-1] + 0.2, cum[-1], f"{label} {cum[-1]:.3f}", va="center", color=INK2, fontsize=9)
    ax.set_xlabel("Resolved live forecasts (in ledger order)")
    ax.set_ylabel("Cumulative mean Brier")
    ax.set_title("Live track record")
    ax.legend(loc="upper right")
    _save(fig, path)
    return True


# ---------------------------------------------------------------------------------------------
# METRICS block (markdown) - the only way numbers get into README/RESULTS
# ---------------------------------------------------------------------------------------------
def metrics_block(m: dict) -> str:
    a = m["arms"]
    lines = [
        f"_Auto-generated from `reports/metrics.json` by `mf report`. Test set: {m['n_test_scored']} questions "
        f"({m['n_events_scored']} events) scored of {m['n_test_total']}; test YES rate {m['test_base_rate']:.3f}; "
        f"paired cluster bootstrap B={m['bootstrap']['B']} by event._",
        "",
        "| Arm | Brier | 95% CI | Log loss | ECE | BSS vs market |",
        "|---|---|---|---|---|---|",
    ]
    for arm in ORDER:
        if arm not in a:
            continue
        r = a[arm]
        ci = r["brier_ci"]
        lines.append(f"| {ARM_LABELS[arm]} (`{arm}`) | {r['brier']:.4f} | [{ci['ci_low']:.4f}, {ci['ci_high']:.4f}] | "
                     f"{r['log_loss']:.4f} | {r['ece']:.4f} | {r['bss_vs_market']:+.4f} |")
    lines += ["", "**Pre-registered primary comparisons** (paired ΔBrier, negative = first arm better):", ""]
    for k, v in m["primary_comparisons"].items():
        lines.append(f"- `{k}`: {v['delta']:+.4f} (95% CI [{v['ci_low']:+.4f}, {v['ci_high']:+.4f}]; "
                     f"P(Δ<0) = {v['frac_draws_below_0']:.3f})")
    lk = m["leakage"]
    if "canary_noret_ens_brier" in lk:
        lines += ["", f"**Leak canary** (no retrieval, K=5): canary Brier {lk['canary_noret_ens_brier']:.4f} "
                      f"(n={lk['canary_n_scored']}, market {lk['canary_market_brier']:.4f}) vs test Brier "
                      f"{lk['test_noret_ens_brier']:.4f} (market {lk['test_market_brier']:.4f})."]
    return "\n".join(lines)


def replace_block(text: str, block: str) -> str:
    if START not in text or END not in text:
        raise ValueError("METRICS markers missing")
    pre, rest = text.split(START, 1)
    _, post = rest.split(END, 1)
    return f"{pre}{START}\n{block}\n{END}{post}"


def extract_block(text: str) -> str:
    return text.split(START, 1)[1].split(END, 1)[0].strip("\n")


# ---------------------------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------------------------
HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>market-forecaster report</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#fcfcfb;color:#0b0b0b;font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;max-width:1040px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.6rem}h2{margin-top:2.2rem;border-bottom:1px solid #e4e3df;padding-bottom:.3rem}
table{border-collapse:collapse;margin:.8rem 0;font-size:.9rem}td,th{border-bottom:1px solid #e4e3df;padding:.3rem .6rem;text-align:right}
td:first-child,th:first-child{text-align:left}th{color:#52514e;font-weight:600}
img{max-width:100%;height:auto;margin:.6rem 0}.muted{color:#52514e}code{font-size:.85rem}
</style></head><body>
<h1>market-forecaster — results report</h1>
<p class="muted">Generated by <code>mf report</code> from <code>reports/metrics.json</code> (sha256 {{ metrics_sha[:16] }}…).
Test set: {{ m.n_test_scored }} questions, {{ m.n_events_scored }} events. All numbers are machine-inserted.</p>

<h2>Headline</h2>
<table><tr><th>Arm</th><th>Brier</th><th>95% CI</th><th>Log loss</th><th>ECE</th><th>BSS vs market</th><th>|p − p_mkt|</th></tr>
{% for arm in order if arm in m.arms %}{% set r = m.arms[arm] %}
<tr><td>{{ labels[arm] }} <code>{{ arm }}</code></td><td>{{ "%.4f"|format(r.brier) }}</td>
<td>[{{ "%.4f"|format(r.brier_ci.ci_low) }}, {{ "%.4f"|format(r.brier_ci.ci_high) }}]</td>
<td>{{ "%.4f"|format(r.log_loss) }}</td><td>{{ "%.4f"|format(r.ece) }}</td><td>{{ "%+.4f"|format(r.bss_vs_market) }}</td>
<td>{{ "%.3f"|format(r.mean_abs_diff_vs_market) }}</td></tr>{% endfor %}
</table>
<h3>Pre-registered primary comparisons</h3>
<table><tr><th>Comparison</th><th>ΔBrier</th><th>95% CI</th><th>P(Δ&lt;0)</th></tr>
{% for k, v in m.primary_comparisons.items() %}<tr><td>{{ k }}</td><td>{{ "%+.4f"|format(v.delta) }}</td>
<td>[{{ "%+.4f"|format(v.ci_low) }}, {{ "%+.4f"|format(v.ci_high) }}]</td><td>{{ "%.3f"|format(v.frac_draws_below_0) }}</td></tr>{% endfor %}
</table>
{% for name, b64 in figs %}<img alt="{{ name }}" src="data:image/png;base64,{{ b64 }}">{% endfor %}

<h2>Breakdowns (Brier)</h2>
{% for name, bd in m.breakdowns.items() %}<h3>By {{ name }}</h3>
<table><tr><th>{{ name }}</th><th>n</th>{% for a in headline %}<th>{{ a }}</th>{% endfor %}</tr>
{% for k, row in bd.items() %}<tr><td>{{ k }}</td><td>{{ row.n }}</td>{% for a in headline %}<td>{{ "%.4f"|format(row[a]) }}</td>{% endfor %}</tr>{% endfor %}
</table>{% endfor %}

<h2>Leakage checks</h2>
<table>{% for k, v in leak_rows %}<tr><td>{{ k }}</td><td>{{ v }}</td></tr>{% endfor %}</table>

<h2>Reliability tables</h2>
{% for a, rows in m.reliability.items() %}<h3>{{ labels[a] }}</h3>
<table><tr><th>bin</th><th>n</th><th>mean p</th><th>YES freq</th></tr>
{% for r in rows %}<tr><td>{{ "%.1f–%.1f"|format(r.bin_low, r.bin_high) }}</td><td>{{ r.n }}</td>
<td>{{ "%.3f"|format(r.mean_p) if r.mean_p is not none else "–" }}</td><td>{{ "%.3f"|format(r.frac_yes) if r.frac_yes is not none else "–" }}</td></tr>{% endfor %}
</table>{% endfor %}

<h2>Fitted parameters</h2>
<table>{% for k, v in m.fits.items() %}<tr><td>{{ k }}</td><td>{{ v }}</td></tr>{% endfor %}</table>

<h2>Live track record</h2>
<p>{{ live_summary }}</p>
{% if live_rows %}<table><tr><th>seq</th><th>created</th><th>question</th><th>p_mkt</th><th>p_aia</th><th>outcome</th></tr>
{% for r in live_rows %}<tr><td>{{ r.seq }}</td><td>{{ r.created_utc[:10] }}</td><td>{{ r.title[:70] }}</td><td>{{ r.p_mkt_at_forecast }}</td>
<td>{{ r.p_aia }}</td><td>{{ r.outcome }}</td></tr>{% endfor %}</table>{% endif %}

<h2>Spend</h2>
<table><tr><td>Anthropic total</td><td>${{ "%.2f"|format(spend.anthropic_total_usd) }} of ${{ "%.2f"|format(spend.anthropic_cap_usd) }}</td></tr>
{% for mth, v in spend.exa_by_month_usd.items() %}<tr><td>Exa {{ mth }}</td><td>${{ "%.2f"|format(v) }} of ${{ "%.2f"|format(spend.exa_monthly_cap_usd) }}</td></tr>{% endfor %}
<tr><td>Paid API calls</td><td>{{ spend.n_paid_calls }}</td></tr></table>

<h2>Links</h2>
<ul class="muted"><li>Halawi et al. 2024: https://arxiv.org/abs/2402.18563</li>
<li>AIA Forecaster: https://arxiv.org/abs/2511.07678</li>
<li>Paleka et al., Pitfalls in Evaluating LM Forecasters: https://arxiv.org/abs/2506.00723</li></ul>
</body></html>
"""


def build_report(s, log=print) -> dict:
    import jinja2

    from mf.core.budget import BudgetGuard
    from mf.core.hashing import file_sha256
    from mf.live import ledger as L

    _style()
    rep = s.reports_dir
    mpath = rep / "metrics.json"
    m = json.loads(mpath.read_text(encoding="utf-8"))
    figdir = rep / "figures"
    figs = {
        "brier_bars": fig_brier_bars, "delta_forest": fig_delta_forest, "reliability": fig_reliability,
        "scatter_vs_market": fig_scatter, "brier_by_horizon": fig_horizon,
    }
    for name, fn in figs.items():
        fn(m, figdir / f"{name}.png")
    live_path = s.data_dir / "live" / "forecasts.jsonl"
    scores_path = s.data_dir / "live" / "scores.jsonl"
    live = L.read_records(live_path)
    scores = [json.loads(l) for l in scores_path.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if scores_path.exists() else []
    has_live_fig = fig_live(scores, figdir / "live_cumulative.png")
    spend = BudgetGuard(s.state_dir / "ledger.jsonl", s.budget, run_id="report").summary()
    (rep / "spend.json").write_text(json.dumps(spend, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    names = list(figs) + (["live_cumulative"] if has_live_fig else [])
    b64 = [(n, base64.b64encode((figdir / f"{n}.png").read_bytes()).decode()) for n in names]
    lk = m["leakage"]
    leak_rows = [(k, json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in sorted(lk.items())]
    audit = rep / "leakage_audit_summary.json"
    if audit.exists():
        leak_rows.append(("human audit (50 kept items)", audit.read_text(encoding="utf-8").strip()))
    by_seq = {r["seq"]: r for r in scores}
    live_rows = [dict(r, outcome=by_seq.get(r["seq"], {}).get("outcome", "open")) for r in live]
    v = L.verify(live_path)
    live_summary = (f"{len(live)} forecasts logged (hash chain {'OK' if v.ok else 'BROKEN'}, head {v.head[:16]}…); "
                    f"{len(scores)} resolved so far.")
    html = jinja2.Environment(undefined=jinja2.StrictUndefined, autoescape=True).from_string(HTML).render(
        m=m, labels=ARM_LABELS, order=ORDER, figs=b64, headline=["market", "halawi", "aia", "market_ens_aia"],
        leak_rows=leak_rows, live_summary=live_summary, live_rows=live_rows, spend=spend,
        metrics_sha=file_sha256(mpath))
    (rep / "index.html").write_text(html, encoding="utf-8", newline="\n")
    block = metrics_block(m)
    for doc in ("README.md", "RESULTS.md"):
        p = s.root / doc
        p.write_text(replace_block(p.read_text(encoding="utf-8"), block), encoding="utf-8", newline="\n")
    log(f"report: {len(names)} figures, reports/index.html, reports/spend.json, METRICS blocks updated")
    return {"figures": names, "metrics_sha": file_sha256(mpath)}
