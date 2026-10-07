"""Extract probabilities and JSON from model text (prefill is not allowed on Sonnet 5)."""

from __future__ import annotations

import json
import re

PROB_RE = re.compile(r"FINAL PROBABILITY:\s*\**\s*([01](?:\.\d+)?|\.\d+)(?![\d.])\s*(%?)", re.IGNORECASE)
PCT_RE = re.compile(r"FINAL PROBABILITY:\s*\**\s*(\d{1,3}(?:\.\d+)?)\s*%", re.IGNORECASE)
P_MIN, P_MAX = 0.01, 0.99


def clamp(p: float) -> float:
    return min(P_MAX, max(P_MIN, p))


def parse_probability(text: str | None) -> float | None:
    """Last `FINAL PROBABILITY: x` wins. Percentages ("37%") are converted. Clamped to [0.01, 0.99]."""
    if not text:
        return None
    cands: list[tuple[int, float]] = []
    for m in PROB_RE.finditer(text):
        v = float(m.group(1))
        if m.group(2) == "%":
            v /= 100.0
        cands.append((m.start(), v))
    for m in PCT_RE.finditer(text):
        cands.append((m.start(), float(m.group(1)) / 100.0))
    if not cands:
        return None
    _, v = max(cands, key=lambda x: x[0])
    if not (0.0 <= v <= 1.0):
        return None
    return clamp(v)


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_json(text: str | None):
    """Tolerant JSON extraction: ```json fences, or the outermost {...} / [...] span. None on failure."""
    if not text:
        return None
    candidates = [m.group(1) for m in _FENCE_RE.finditer(text)] + [text]
    for c in candidates:
        c = c.strip()
        try:
            return json.loads(c)
        except ValueError:
            pass
        for open_c, close_c in (("{", "}"), ("[", "]")):
            i, j = c.find(open_c), c.rfind(close_c)
            if i != -1 and j > i:
                try:
                    return json.loads(c[i:j + 1])
                except ValueError:
                    continue
    return None
