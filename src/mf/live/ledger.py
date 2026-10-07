"""Append-only, SHA-256 hash-chained forecast ledger (data/live/forecasts.jsonl).

hash_i = sha256(canonical_json(record_i without "hash") + prev_hash), prev_hash_0 = 64 zeros.
Records are only ever appended (file opened with "a"); `verify` recomputes the chain, so editing any
field of record i breaks verification at i. Committing the file to git after each run timestamps it
publicly, so forecasts cannot be backfilled.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from mf.core.hashing import canonical_json, sha256_hex
from mf.schemas import LiveRecord

GENESIS = "0" * 64


def record_hash(record: dict, prev_hash: str) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return sha256_hex(canonical_json(body) + prev_hash)


def read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def head(path: Path) -> tuple[int, str]:
    """(next seq, prev hash) from the last line."""
    recs = read_records(path)
    if not recs:
        return 0, GENESIS
    return recs[-1]["seq"] + 1, recs[-1]["hash"]


def append(path: Path, fields: dict) -> LiveRecord:
    """fields: every LiveRecord field except seq, prev_hash, hash."""
    seq, prev = head(path)
    rec = LiveRecord(**fields, seq=seq, prev_hash=prev, hash="")
    d = json.loads(rec.model_dump_json())
    d["hash"] = record_hash(d, prev)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(canonical_json(d) + "\n")
    return LiveRecord.model_validate(d)


@dataclass
class VerifyResult:
    ok: bool
    n: int
    head: str
    bad_index: int | None = None
    reason: str = ""


def verify(path: Path) -> VerifyResult:
    prev = GENESIS
    recs = read_records(path)
    for i, r in enumerate(recs):
        if r.get("seq") != i:
            return VerifyResult(False, len(recs), prev, i, f"seq {r.get('seq')} != {i}")
        if r.get("prev_hash") != prev:
            return VerifyResult(False, len(recs), prev, i, "prev_hash mismatch")
        if record_hash(r, prev) != r.get("hash"):
            return VerifyResult(False, len(recs), prev, i, "hash mismatch (record modified)")
        try:
            LiveRecord.model_validate(r)
        except Exception as e:  # noqa: BLE001
            return VerifyResult(False, len(recs), prev, i, f"schema: {e}")
        prev = r["hash"]
    return VerifyResult(True, len(recs), prev)
