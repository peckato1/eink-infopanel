"""Tests for the wake-up policy (:mod:`dashboard.wakeup`).

Runnable either under pytest or directly (``python tests/test_wakeup.py``), so
no extra test dependency is required.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.config import Settings  # noqa: E402
from dashboard.wakeup import next_wakeup  # noqa: E402

# Fixed local zone so epoch results are deterministic (CET-ish, no DST).
TZ = timezone(timedelta(hours=1))
BASE = Settings()  # align=True, interval 1800, quiet hours off


def _at(y, mo, d, h, mi, s=0) -> datetime:
    return datetime(y, mo, d, h, mi, s, tzinfo=TZ)


def _wake(now: datetime, settings: Settings) -> datetime:
    return datetime.fromtimestamp(next_wakeup(now, settings), TZ)


def test_daytime_aligns_to_half_hour():
    assert _wake(_at(2026, 7, 10, 14, 7), BASE) == _at(2026, 7, 10, 14, 30)


def test_on_boundary_moves_strictly_forward():
    assert _wake(_at(2026, 7, 10, 14, 30), BASE) == _at(2026, 7, 10, 15, 0)


def test_day_rollover_wakes_at_midnight():
    assert _wake(_at(2026, 7, 10, 23, 47), BASE) == _at(2026, 7, 11, 0, 0)


def test_no_align_uses_plain_interval():
    settings = replace(BASE, wake_align=False)
    assert _wake(_at(2026, 7, 10, 14, 7), settings) == _at(2026, 7, 10, 14, 37)


def test_quiet_night_sleeps_until_morning():
    settings = replace(BASE, quiet_start="23:00", quiet_end="06:00")
    assert _wake(_at(2026, 7, 10, 1, 0), settings) == _at(2026, 7, 10, 6, 0)


def test_quiet_evening_jumps_to_next_morning():
    settings = replace(BASE, quiet_start="23:00", quiet_end="06:00")
    # 22:50 aligns to 23:00, which is inside the window → next 06:00 (tomorrow).
    assert _wake(_at(2026, 7, 10, 22, 50), settings) == _at(2026, 7, 11, 6, 0)


def test_quiet_disabled_behaves_like_alignment():
    settings = replace(BASE, quiet_start="", quiet_end="06:00")
    assert _wake(_at(2026, 7, 10, 14, 7), settings) == _at(2026, 7, 10, 14, 30)


def test_result_is_always_in_the_future():
    for hh in range(24):
        for mm in (0, 7, 30, 47, 59):
            now = _at(2026, 7, 10, hh, mm)
            assert next_wakeup(now, BASE) > now.timestamp()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
