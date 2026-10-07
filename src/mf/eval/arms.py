"""Assemble every pre-registered arm (PLAN.md §12) and compute metrics + paired cluster-bootstrap CIs.

Inputs are committed files only (questions.jsonl, canary_precutoff.jsonl, data/runs/<run>/forecasts.jsonl,
retrieval_meta.jsonl), so `mf evaluate` costs $0 and does not need the cache.

Scoring set (pre-registered): test questions where every LLM base arm (noret_single, noret_ens,
halawi_single, halawi, halawi_sup) produced a probability ("complete cases"). Failures are counted per arm.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from mf.eval import metrics as M
from mf.eval.bootstrap import ClusterBootstrap
from mf.eval.calibration import reliability_table
from mf.forecast.calibrate import fit_platt, platt
from mf.forecast.market_ensemble import blend, cross_fit, fit_weight
from mf.retrieval.pipeline import _read_jsonl
from mf.schemas import Question

BASE_ARMS = ["noret_single", "noret_ens", "halawi_single", "halawi", "halawi_sup"]
ALL_ARMS = ["const_0.5", "base_rate", "market", "noret_single", "noret_ens", "halawi_single", "halawi",
            "halawi_platt", "halawi_sup", "aia", "aia_platt_fit", "market_ens_halawi", "market_ens_aia",
            "market_ens_aia_devw"]
HEADLINE = ["const_0.5", "base_rate", "market", "halawi", "aia", "market_ens_aia"]
PRIMARY_COMPARISONS = [("aia", "halawi"), ("market_ens_aia", "market")]
DECIMALS = 6


def _r(x):
    if isinstance(x, float):
        return round(x, DECIMALS)
    if isinstance(x, dict):
        return {k: _r(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_r(v) for v in x]
    return x


def horizon_bucket(days: float) -> str:
    return "<7d" if days < 7 else ("7-30d" if days <= 30 else ">30d")


def load_base(run_dir: Path) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = defaultdict(dict)
    for r in _read_jsonl(run_dir / "forecasts.jsonl"):
        out[r["qid"]][r["arm"]] = r["p"]
    return out


def load_sup_triggered(run_dir: Path) -> dict[str, bool]:
    return {r["qid"]: bool(r["components"].get("triggered")) for r in _read_jsonl(run_dir / "forecasts.jsonl")
            if r["arm"] == "halawi_sup"}


def build_arms(test: list[Question], dev: list[Question], base: dict, platt_coef: float) -> tuple[dict, dict]:
    """Returns ({arm: np.array over `test`}, info)."""
    y_dev = np.array([q.outcome for q in dev], float)
    base_rate = float(y_dev.mean())
    g = lambda qs, arm: np.array([base[q.qid][arm] for q in qs], float)
    arms = {
        "const_0.5": np.full(len(test), 0.5),
        "base_rate": np.full(len(test), base_rate),
        "market": np.array([q.p_mkt_t0 for q in test], float),
    }
    for a in BASE_ARMS:
        arms[a] = g(test, a)
    arms["halawi_platt"] = platt(arms["halawi"], platt_coef)
    arms["aia"] = platt(arms["halawi_sup"], platt_coef)
    dev_ok = [q for q in dev if base.get(q.qid, {}).get("halawi_sup") is not None]
    a_fit, _ = fit_platt(g(dev_ok, "halawi_sup"), [q.outcome for q in dev_ok])
    arms["aia_platt_fit"] = platt(arms["halawi_sup"], a_fit)
    y = np.array([q.outcome for q in test], float)
    groups = [q.event_id for q in test]
    arms["market_ens_halawi"], w_h = cross_fit(arms["halawi"], arms["market"], y, groups)
    arms["market_ens_aia"], w_a = cross_fit(arms["aia"], arms["market"], y, groups)
    dev_aia = platt(g(dev_ok, "halawi_sup"), platt_coef)
    w_dev = fit_weight(dev_aia, [q.p_mkt_t0 for q in dev_ok], [q.outcome for q in dev_ok])
    arms["market_ens_aia_devw"] = blend(arms["aia"], arms["market"], w_dev)
    info = {"dev_base_rate": base_rate, "platt_coef_fixed": platt_coef, "platt_coef_fit_on_dev": a_fit,
            "n_dev_used_for_fits": len(dev_ok), "market_ens_halawi_fold_weights": w_h,
            "market_ens_aia_fold_weights": w_a, "market_ens_aia_dev_weight": w_dev}
    return arms, info


def arm_block(p, y, mkt, bs: ClusterBootstrap) -> dict:
    out = M.summary(p, y, mkt)
    out["brier_ci"] = bs.ci((p - y) ** 2)
    pc = np.clip(p, *M.LL_CLIP)
    out["log_loss_ci"] = bs.ci(-(y * np.log(pc) + (1 - y) * np.log(1 - pc)))
    return out


def evaluate(s, B: int = 10_000) -> dict:
    from mf.data.dataset import read_questions

    ddir = s.data_dir / "dataset"
    allq = read_questions(ddir / "questions.jsonl")
    canary = read_questions(ddir / "canary_precutoff.jsonl")
    dev = [q for q in allq if q.split == "dev"]
    test_all = [q for q in allq if q.split == "test"]
    base = load_base(s.run_dir)
    failed = {a: sum(1 for q in test_all if base.get(q.qid, {}).get(a) is None) for a in BASE_ARMS}
    test = [q for q in test_all if all(base.get(q.qid, {}).get(a) is not None for a in BASE_ARMS)]
    arms, info = build_arms(test, dev, base, s.pipeline.platt_coef)
    y = np.array([q.outcome for q in test], float)
    mkt = arms["market"]
    bs = ClusterBootstrap([q.event_id for q in test], B=B)
    sq = {a: (p - y) ** 2 for a, p in arms.items()}
    res: dict = {
        "n_test_total": len(test_all), "n_test_scored": len(test), "n_events_scored": len(set(q.event_id for q in test)),
        "failed_questions_by_arm": failed, "fits": info, "bootstrap": {"B": B, "seed": 0, "cluster": "event_id"},
        "test_base_rate": float(y.mean()),
        "arms": {a: arm_block(arms[a], y, mkt, bs) for a in ALL_ARMS},
        "delta_brier_vs_halawi": {a: bs.delta(sq[a], sq["halawi"]) for a in ALL_ARMS if a != "halawi"},
        "delta_brier_vs_market": {a: bs.delta(sq[a], sq["market"]) for a in ALL_ARMS if a != "market"},
        "primary_comparisons": {f"{a}_minus_{b}": bs.delta(sq[a], sq[b]) for a, b in PRIMARY_COMPARISONS},
    }
    # Breakdowns (pre-registered): venue, category, horizon bucket, supervisor-triggered.
    trig = load_sup_triggered(s.run_dir)
    keys = {
        "venue": lambda q: q.venue, "category": lambda q: q.category,
        "horizon": lambda q: horizon_bucket(q.horizon_days),
        "supervisor_triggered": lambda q: "triggered" if trig.get(q.qid) else "not_triggered",
    }
    res["breakdowns"] = {}
    for name, fn in keys.items():
        groups = defaultdict(list)
        for i, q in enumerate(test):
            groups[fn(q)].append(i)
        res["breakdowns"][name] = {
            k: {"n": len(ix), **{a: M.brier(arms[a][ix], y[ix]) for a in HEADLINE}}
            for k, ix in sorted(groups.items())}
    res["reliability"] = {a: reliability_table(arms[a], y) for a in ("aia", "halawi", "market")}
    # Leakage checks
    res["leakage"] = leakage_block(s, canary, test, base, arms, y)
    res["scatter"] = [{"qid": q.qid, "p_aia": float(arms["aia"][i]), "p_mkt": float(mkt[i]), "y": int(y[i])}
                      for i, q in enumerate(test)]
    res["horizon_days"] = [float(q.horizon_days) for q in test]
    return _r(res)


def leakage_block(s, canary, test, base, arms, y) -> dict:
    can = [q for q in canary if base.get(q.qid, {}).get("noret_ens") is not None]
    out: dict = {"canary_n_scored": len(can), "canary_n_total": len(canary)}
    if can:
        yc = np.array([q.outcome for q in can], float)
        pc = np.array([base[q.qid]["noret_ens"] for q in can], float)
        mc = np.array([q.p_mkt_t0 for q in can], float)
        out["canary_noret_ens_brier"] = M.brier(pc, yc)
        out["canary_market_brier"] = M.brier(mc, yc)
        out["canary_noret_ens_bss_vs_market"] = M.brier_skill(pc, yc, mc)
    out["test_noret_ens_brier"] = M.brier(arms["noret_ens"], y)
    out["test_market_brier"] = M.brier(arms["market"], y)
    out["test_noret_ens_bss_vs_market"] = M.brier_skill(arms["noret_ens"], y, arms["market"])
    meta = {m["qid"]: m for m in _read_jsonl(s.run_dir / "retrieval_meta.jsonl")}
    drops = defaultdict(int)
    for q in test:
        for k, v in (meta.get(q.qid, {}).get("drop_counts") or {}).items():
            drops[k] += v
    out["evidence_drop_counts_test"] = dict(sorted(drops.items()))
    out["kept_evidence_per_question_test"] = float(np.mean([meta.get(q.qid, {}).get("n_kept", 0) for q in test]))
    keep = np.array([not meta.get(q.qid, {}).get("haiku_flagged_any", False) for q in test])
    out["robustness_aia_excluding_haiku_flagged"] = {
        "n": int(keep.sum()), "aia_brier": M.brier(arms["aia"][keep], y[keep]) if keep.any() else None,
        "market_brier": M.brier(arms["market"][keep], y[keep]) if keep.any() else None,
        "aia_brier_all": M.brier(arms["aia"], y)}
    return out


def write_metrics(res: dict, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return text
