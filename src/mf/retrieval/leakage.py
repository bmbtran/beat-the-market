"""Deterministic retrieval-leakage filters (PLAN.md §12 check 3).

Order (first failing rule is recorded as the drop reason):
  blocklisted_domain -> null_date -> date_after_cutoff -> text_post_t0_date
The text scan only fires on dates attached to an update/publication marker ("Updated Sept. 3, 2026",
"Published: 2026-09-03", "Last modified ..."). Questions are about scheduled future events, so plain
forward-looking date mentions ("the Fed meets on September 16, 2026") are NOT leaks; the Haiku judge
(mentions_events_after_t0 / reveals_outcome) handles "already happened after t0" semantically.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from mf.core import timeutil

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_MARKER = r"(?:updated|last\s+updated|published|posted|modified|last\s+modified|revised|as\s+of)\s*(?:on|:)?\s*"
# "Updated September 3, 2026" / "Updated Sep 3 2026" / "Updated 3 September 2026" / "Updated: 2026-09-03"
_PATTERNS = [
    re.compile(_MARKER + _MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.IGNORECASE),
    re.compile(_MARKER + r"(\d{1,2})\s+" + _MON + r",?\s+(\d{4})", re.IGNORECASE),
    re.compile(_MARKER + r"(\d{4})-(\d{2})-(\d{2})", re.IGNORECASE),
    re.compile(_MARKER + r"(\d{1,2})/(\d{1,2})/(\d{4})", re.IGNORECASE),
    re.compile(_MARKER + _MON + r",?\s+(\d{4})", re.IGNORECASE),
]


def domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_blocklisted(url: str, blocklist: list[str]) -> bool:
    host = domain(url)
    return any(host == d or host.endswith("." + d) for d in blocklist)


def _mk(y: int, m: int, d: int) -> datetime | None:
    try:
        return datetime(y, m, d, tzinfo=timeutil.UTC)
    except ValueError:
        return None


def marked_dates(text: str) -> list[datetime]:
    """Dates that follow an update/publication marker in `text`."""
    out: list[datetime] = []
    for i, pat in enumerate(_PATTERNS):
        for m in pat.finditer(text or ""):
            g = m.groups()
            if i == 0:
                dt = _mk(int(g[2]), MONTHS[g[0].lower().rstrip(".")], int(g[1]))
            elif i == 1:
                dt = _mk(int(g[2]), MONTHS[g[1].lower().rstrip(".")], int(g[0]))
            elif i == 2:
                dt = _mk(int(g[0]), int(g[1]), int(g[2]))
            elif i == 3:  # US style M/D/YYYY
                dt = _mk(int(g[2]), int(g[0]), int(g[1]))
            else:  # month-year only -> first day of that month
                dt = _mk(int(g[1]), MONTHS[g[0].lower().rstrip(".")], 1)
            if dt:
                out.append(dt)
    return out


def text_has_post_t0_date(text: str, t0: datetime) -> datetime | None:
    """Return the first marked date strictly after t0's day (month-only dates: after t0's month)."""
    t0_day = timeutil.parse(t0).replace(hour=0, minute=0, second=0, microsecond=0)
    for dt in marked_dates(text):
        if dt > t0_day:
            return dt
    return None


def deterministic_drop_reason(url: str, title: str, published: datetime | None, text: str,
                              t0: datetime, cutoff: datetime, blocklist: list[str]) -> str | None:
    if is_blocklisted(url, blocklist):
        return "blocklisted_domain"
    if published is None:
        return "null_date"
    if published > cutoff:
        return "date_after_cutoff"
    if text_has_post_t0_date(f"{title}\n{text}", t0):
        return "text_post_t0_date"
    return None
