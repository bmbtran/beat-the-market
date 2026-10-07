"""The anti-premature-done gate (PLAN.md §14). Prints every command and its full output.

Ends with `VERIFY: PASS metrics_sha=<sha256 of reports/metrics.json>` or `VERIFY: FAIL <reason>` (exit 1).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = dict(os.environ, MF_CACHE_MODE="readonly", PYTHONIOENCODING="utf-8", COLUMNS="100", NO_COLOR="1")
PLACEHOLDERS = re.compile(r"\bTODO\b|\bTBD\b|\bXX\b|_Pending")


def run(cmd: str) -> tuple[int, str]:
    print(f"\n$ {cmd}", flush=True)
    p = subprocess.run(cmd, shell=True, cwd=ROOT, env=ENV, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = (p.stdout + p.stderr).rstrip()
    print(out, flush=True)
    print(f"[exit {p.returncode}]", flush=True)
    return p.returncode, out


def fail(reason: str) -> int:
    print(f"\nVERIFY: FAIL {reason}")
    return 1


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from mf.core.hashing import canonical_json, file_sha256
    from mf.eval.report import extract_block, metrics_block

    code, out = run("uv run pytest -q -p no:cacheprovider")
    if code:
        return fail("pytest failed")
    n_passed = int(re.search(r"(\d+) passed", out).group(1)) if re.search(r"(\d+) passed", out) else 0
    if n_passed < 40:
        return fail(f"only {n_passed} tests (need >= 40)")

    code, _ = run("uv run python -m mf.data.dataset --validate")
    if code:
        return fail("dataset validation failed")

    metrics = ROOT / "reports" / "metrics.json"
    if not metrics.exists():
        return fail("reports/metrics.json missing")
    code, _ = run("uv run mf evaluate --out reports/metrics_repro.json")
    if code:
        return fail("readonly re-evaluation failed")
    a = json.loads(metrics.read_text(encoding="utf-8"))
    b = json.loads((ROOT / "reports" / "metrics_repro.json").read_text(encoding="utf-8"))
    print(f"\n$ compare reports/metrics.json reports/metrics_repro.json (canonical JSON)")
    if canonical_json(a) != canonical_json(b):
        print("DIFFERENT")
        return fail("metrics not reproducible")
    print("REPRO OK (identical after canonical JSON)")

    code, _ = run("uv run mf verify-ledger")
    if code:
        return fail("live ledger hash chain broken")

    code, _ = run("uv run mf budget")
    if code:
        return fail("budget cap exceeded")

    print("\n$ check RESULTS.md / README.md placeholders and METRICS blocks")
    block = metrics_block(a)
    for doc in ("RESULTS.md", "README.md"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        if doc == "RESULTS.md":
            # scan prose only: fenced blocks hold verbatim command output (which quotes these very words)
            prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
            hits = PLACEHOLDERS.findall(prose)
            if hits:
                return fail(f"RESULTS.md contains placeholders: {sorted(set(hits))}")
        if extract_block(text) != block:
            return fail(f"{doc} METRICS block does not match metrics.json (run `mf report`)")
        print(f"{doc}: METRICS block matches metrics.json")
    print("RESULTS.md: no TODO/TBD/XX/_Pending placeholders")

    code, out = run("git status --porcelain --ignored")
    bad = [l for l in out.splitlines() if not l.startswith("!!") and
           (l[3:].strip() == ".env" or l[3:].startswith("cache/") or l[3:].startswith("state/"))]
    code2, tracked = run("git ls-files")
    bad += [l for l in tracked.splitlines() if l == ".env" or l.startswith("cache/") or l.startswith("state/")]
    if bad:
        return fail(f"secret/cache/state files visible to git: {bad}")
    print("git: .env, cache/, state/ are neither tracked nor staged")

    print(f"\nVERIFY: PASS metrics_sha={file_sha256(metrics)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
