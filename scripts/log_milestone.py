"""Run acceptance commands and append their verbatim output to RESULTS.md -> Milestone log.

Usage: uv run python scripts/log_milestone.py "M1 — Core" "cmd one" "cmd two" ...
Exits non-zero (and still logs, marked FAIL) if any command fails.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    title, cmds = sys.argv[1], sys.argv[2:]
    chunks, ok = [], True
    env = dict(os.environ, PYTHONIOENCODING="utf-8", COLUMNS="100", NO_COLOR="1")
    for cmd in cmds:
        # Support POSIX-style leading `VAR=value` assignments (cmd.exe on Windows does not).
        run_env, rest = dict(env), cmd
        while re.match(r"^[A-Z_][A-Z0-9_]*=\S+\s", rest):
            assign, rest = rest.split(None, 1)
            k, v = assign.split("=", 1)
            run_env[k] = v
        p = subprocess.run(rest, shell=True, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=run_env)
        out = (p.stdout + p.stderr).rstrip()
        chunks.append(f"$ {cmd}\n{out}\n[exit {p.returncode}]")
        ok &= p.returncode == 0
    status = "PASS" if ok else "FAIL"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = f"\n### {title} ({status}, {day})\n\n```\n" + "\n".join(chunks) + "\n```\n"
    results = ROOT / "RESULTS.md"
    text = results.read_text(encoding="utf-8")
    results.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8", newline="\n")
    print(block)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
