"""End-to-end evaluate -> report on a synthetic project; README/RESULTS numbers must equal metrics.json."""

import json
import re
import shutil
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from mf.config import load_settings, settings
from mf.eval.arms import ALL_ARMS, evaluate, write_metrics
from mf.eval.report import ARM_LABELS, build_report, extract_block, metrics_block
from mf.schemas import ArmForecast, Question

UTC = timezone.utc


@pytest.fixture
def project(tmp_path):
    real = settings()
    root = tmp_path / "proj"
    shutil.copytree(real.root / "configs", root / "configs")
    for doc in ("README.md", "RESULTS.md"):
        (root / doc).write_text(f"# {doc}\n\n<!-- METRICS:START -->\nold\n<!-- METRICS:END -->\n\ntail\n",
                                encoding="utf-8")
    rng = np.random.default_rng(7)
    qs, rows = [], []
    t = datetime(2026, 3, 1, tzinfo=UTC)

    def add(i, split, ev):
        truth = rng.uniform(0.1, 0.9)
        y = int(rng.random() < truth)
        mkt = float(np.clip(truth + rng.normal(0, 0.08), 0.03, 0.97))
        q = Question(qid=f"kalshi:Q{i}", venue="kalshi" if i % 2 else "polymarket", event_id=f"E{ev}",
                     title=f"Synthetic question {i}?", description="d", category=["Politics", "Economics"][i % 2],
                     created_at=t, t0=t + timedelta(days=2 + i % 40), scheduled_close=t + timedelta(days=50),
                     resolved_at=t + timedelta(days=51), horizon_days=float([3, 15, 45][i % 3]), p_mkt_t0=round(mkt, 4),
                     p_mkt_source="mid", volume=1e4, outcome=y, split=split, source_url="u")
        qs.append(q)
        llm = float(np.clip(truth + rng.normal(0, 0.15), 0.02, 0.98))
        for arm, p in (("noret_single", 0.5), ("noret_ens", 0.45), ("halawi_single", llm), ("halawi", llm),
                       ("halawi_sup", float(np.clip(llm + rng.normal(0, 0.03), 0.02, 0.98)))):
            comp = {"triggered": bool(i % 3 == 0)} if arm == "halawi_sup" else {}
            rows.append(json.loads(ArmForecast(qid=q.qid, arm=arm, p=p, components=comp).model_dump_json()))

    for i in range(30):
        add(i, "dev", i)
    for i in range(30, 150):
        add(i, "test", i // 2)
    rows[-1]["p"] = None  # one failed question -> excluded from scoring, counted as failed
    dd = root / "data" / "dataset"
    dd.mkdir(parents=True)
    (dd / "questions.jsonl").write_text("".join(q.model_dump_json() + "\n" for q in qs), encoding="utf-8")
    (dd / "canary_precutoff.jsonl").write_text("", encoding="utf-8")
    rd = root / "data" / "runs" / "backtest_v1"
    rd.mkdir(parents=True)
    (rd / "forecasts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (rd / "retrieval_meta.jsonl").write_text("", encoding="utf-8")
    return load_settings(root)


def test_evaluate_report_roundtrip(project):
    s = project
    m = evaluate(s, B=500)
    assert set(m["arms"]) == set(ALL_ARMS)
    assert m["n_test_total"] == 120 and m["n_test_scored"] == 119 and m["failed_questions_by_arm"]["halawi_sup"] == 1
    assert m["arms"]["const_0.5"]["brier"] == 0.25
    for a in ALL_ARMS:
        ci = m["arms"][a]["brier_ci"]
        assert ci["ci_low"] <= m["arms"][a]["brier"] <= ci["ci_high"]
    write_metrics(m, s.reports_dir / "metrics.json")
    # reproducible byte-for-byte
    assert json.dumps(evaluate(s, B=500), sort_keys=True) == json.dumps(m, sort_keys=True)
    build_report(s, log=lambda x: None)
    block = metrics_block(json.loads((s.reports_dir / "metrics.json").read_text(encoding="utf-8")))
    for doc in ("README.md", "RESULTS.md"):
        text = (s.root / doc).read_text(encoding="utf-8")
        assert extract_block(text) == block and text.endswith("tail\n")
    # every Brier number in the README table equals metrics.json
    readme = (s.root / "README.md").read_text(encoding="utf-8")
    for arm in ALL_ARMS:
        row = next(l for l in readme.splitlines() if f"(`{arm}`)" in l)
        assert float(row.split("|")[2]) == pytest.approx(m["arms"][arm]["brier"], abs=5e-5)
    html = (s.reports_dir / "index.html").read_text(encoding="utf-8")
    assert "<script" not in html and 'src="http' not in html and "href=" not in html
    for name in ("brier_bars", "delta_forest", "reliability", "scatter_vs_market", "brier_by_horizon"):
        assert (s.reports_dir / "figures" / f"{name}.png").exists()
    assert (s.reports_dir / "spend.json").exists()


def test_arm_labels_cover_all_arms():
    assert set(ALL_ARMS) <= set(ARM_LABELS)
