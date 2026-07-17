"""Tests for the CHMI daily-outlook parser (:mod:`dashboard.data.chmi_daily`).

Runnable either under pytest or directly (``python tests/test_chmi_daily.py``),
so no extra test dependency is required.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.data.chmi_daily import _daily_icon, _parse  # noqa: E402


def _day(num: int, dt: str, key: str, temp: float, weather: int, icon: int) -> dict:
    """One API row: a night row carries ``minimumTemperature``, a day row the max."""
    return {
        "number": num,
        "time": dt,
        key: temp,
        "weather": weather,
        "weatherIcon": icon,
    }


# Two rows per day: night (min) then day (max), like the live feed.
_SAMPLE = {
    "data": [
        _day(0, "2026-07-13T22:00:00Z", "minimumTemperature", 15, 95, 66),
        _day(0, "2026-07-14T10:00:00Z", "maximumTemperature", 29, 95, 66),
        _day(1, "2026-07-14T22:00:00Z", "minimumTemperature", 12, 0, 40),
        _day(1, "2026-07-15T10:00:00Z", "maximumTemperature", 25, 0, 40),
    ]
}


def test_parse_merges_night_and_day_rows():
    points = _parse(_SAMPLE)
    assert [p.day for p in points] == [date(2026, 7, 14), date(2026, 7, 15)]
    first = points[0]
    assert (first.temp_min_c, first.temp_max_c) == (15.0, 29.0)


def test_parse_sorts_by_day():
    shuffled = {"data": list(reversed(_SAMPLE["data"]))}
    assert [p.day for p in _parse(shuffled)] == [date(2026, 7, 14), date(2026, 7, 15)]


def test_parse_skips_incomplete_days():
    # A day with only a night row (no max) is dropped.
    partial = {"data": [_SAMPLE["data"][0]]}
    assert _parse(partial) == []


def test_icon_prefers_meteogram_icon():
    # The icon carries sky cover, so rain on a partly-cloudy day keeps its sun,
    # even when the WMO code (80 = rain showers) alone would say "cloud-rain".
    assert _daily_icon(80, 41) == "cloud-sun-rain"
    assert _daily_icon(80, 61) == "cloud-sun-rain"
    assert _daily_icon(0, 40) == "cloud-sun"


def test_icon_wmo_fallback_when_no_icon():
    assert _daily_icon(95, None) == "cloud-lightning"
    assert _daily_icon(80, None) == "cloud-rain"
    assert _daily_icon(None, None) == ""


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
