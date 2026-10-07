"""Human leakage audit (PLAN.md §12 check 2): sample kept evidence -> CSV -> human_verdict -> leak rate."""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path

from mf.retrieval.pipeline import _read_jsonl

FIELDS = ["n", "qid", "t0", "question", "url", "published_date", "evidence_title", "summary", "relevance",
          "haiku_leak_flag", "human_verdict", "notes"]
VERDICTS = {"clean", "leak", "unsure"}


def sample_audit(s, n: int = 50, seed: int = 20261006) -> Path:
    from mf.data.dataset import read_questions

    out = s.reports_dir / "leakage_audit.csv"
    if out.exists() and any(r["human_verdict"] for r in read_audit(out)):
        raise FileExistsError(f"{out} already has human verdicts; refusing to overwrite")
    qs = {q.qid: q for q in read_questions(s.data_dir / "dataset" / "questions.jsonl")}
    kept = [e for e in _read_jsonl(s.run_dir / "evidence.jsonl") if e["kept"] and e["qid"] in qs]
    kept.sort(key=lambda e: (e["qid"], e["url"]))
    rows = random.Random(seed).sample(kept, min(n, len(kept)))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for i, e in enumerate(rows, 1):
            q = qs[e["qid"]]
            w.writerow({"n": i, "qid": e["qid"], "t0": q.t0.strftime("%Y-%m-%d"), "question": q.title,
                        "url": e["url"], "published_date": (e["published_date"] or "")[:10],
                        "evidence_title": e["title"], "summary": e["summary"], "relevance": e["relevance"],
                        "haiku_leak_flag": e["leak_flag"], "human_verdict": "", "notes": ""})
    return out


def read_audit(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def summarize_audit(s) -> dict:
    path = s.reports_dir / "leakage_audit.csv"
    rows = read_audit(path)
    verdicts = Counter(r["human_verdict"].strip().lower() for r in rows)
    missing = [r["n"] for r in rows if r["human_verdict"].strip().lower() not in VERDICTS]
    res = {"n": len(rows), "verdicts": dict(sorted(verdicts.items())), "missing_verdicts": missing,
           "leak_rate": verdicts.get("leak", 0) / len(rows) if rows else None,
           "leak_or_unsure_rate": (verdicts.get("leak", 0) + verdicts.get("unsure", 0)) / len(rows) if rows else None}
    (s.reports_dir / "leakage_audit_summary.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n",
                                                              encoding="utf-8", newline="\n")
    return res
