from datetime import datetime, timezone

from mf.retrieval.leakage import (deterministic_drop_reason, is_blocklisted, marked_dates,
                                  text_has_post_t0_date)

UTC = timezone.utc
T0 = datetime(2026, 6, 1, tzinfo=UTC)
CUT = datetime(2026, 5, 31, tzinfo=UTC)
BL = ["polymarket.com", "wikipedia.org", "x.com"]
PUB = datetime(2026, 5, 1, tzinfo=UTC)


def test_updated_post_t0_text_is_dropped():
    txt = "Senate passes bill. Updated September 3, 2026 with the final tally."
    assert deterministic_drop_reason("https://news.com/a", "t", PUB, txt, T0, CUT, BL) == "text_post_t0_date"


def test_marker_formats():
    assert marked_dates("Last updated: 2026-09-03") == [datetime(2026, 9, 3, tzinfo=UTC)]
    assert marked_dates("Published 3 Sept. 2026") == [datetime(2026, 9, 3, tzinfo=UTC)]
    assert marked_dates("Posted on 9/3/2026") == [datetime(2026, 9, 3, tzinfo=UTC)]
    assert marked_dates("Updated Sep 2026") == [datetime(2026, 9, 1, tzinfo=UTC)]


def test_forward_looking_dates_are_not_leaks():
    txt = "The Fed meets on September 16, 2026; analysts expect a hold. Published May 1, 2026."
    assert text_has_post_t0_date(txt, T0) is None
    assert deterministic_drop_reason("https://news.com/a", "t", PUB, txt, T0, CUT, BL) is None


def test_same_day_or_earlier_marker_ok():
    assert text_has_post_t0_date("Updated June 1, 2026", T0) is None
    assert text_has_post_t0_date("Updated June 2, 2026", T0) == datetime(2026, 6, 2, tzinfo=UTC)
    assert text_has_post_t0_date("Updated June 2026", T0) is None  # month-only == t0's month


def test_blocklist_including_subdomains():
    assert is_blocklisted("https://en.wikipedia.org/wiki/X", BL)
    assert is_blocklisted("https://www.polymarket.com/event/y", BL)
    assert not is_blocklisted("https://box.com/x", BL)  # suffix match must respect dot boundary
    assert deterministic_drop_reason("https://x.com/p/1", "t", PUB, "", T0, CUT, BL) == "blocklisted_domain"


def test_null_and_late_dates():
    assert deterministic_drop_reason("https://n.com/a", "t", None, "", T0, CUT, BL) == "null_date"
    late = datetime(2026, 5, 31, 12, tzinfo=UTC)
    assert deterministic_drop_reason("https://n.com/a", "t", late, "", T0, CUT, BL) == "date_after_cutoff"
