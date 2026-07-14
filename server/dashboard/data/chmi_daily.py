"""Multi-day outlook from the CHMI daily forecast API.

Unlike the meteogram (:mod:`.chmi`), this endpoint returns a single national
outlook (no station id) as ~9 days, each split into a night row carrying the
daily minimum and a day row carrying the daily maximum. We merge the pair into
one :class:`DailyForecastPoint` per day.
"""

from __future__ import annotations

import logging
import time as _time
from datetime import datetime

import requests

from ..models import DailyForecastPoint
from .chmi import icon_to_lucide

log = logging.getLogger(__name__)

_URL = "https://data-provider.chmi.cz/api/graphs/graf.forecast"
_TIMEOUT_S = 10
_USER_AGENT = "esp-epaper-dashboard/1.0 (+chmi)"


def _daily_icon(weather: int | None, weather_icon: int | None) -> str:
    """Pick a Lucide icon for a day.

    Significant weather is taken from the WMO ``weather`` (ww) code, which is
    well-defined; for a dry day the sky/cloud baseline is reused from the
    meteogram icon mapping.
    """
    if weather is not None:
        if weather >= 95:  # thunderstorm
            return "cloud-lightning"
        if weather in (85, 86):  # snow showers
            return "cloud-snow"
        if 80 <= weather <= 82:  # rain showers
            return "cloud-rain"
        if 71 <= weather <= 77:  # snow
            return "cloud-snow"
        if 61 <= weather <= 67:  # rain / freezing rain
            return "cloud-rain"
        if 51 <= weather <= 57:  # drizzle
            return "cloud-drizzle"
        if 45 <= weather <= 48:  # fog
            return "cloud-fog"
    if weather_icon is not None:
        return icon_to_lucide(weather_icon)
    return ""


class ChmiDailyForecastSource:
    """A daily-outlook source backed by the CHMI forecast endpoint."""

    def __init__(self, days: int = 7, cache_ttl_s: int = 3600) -> None:
        self._days = days
        self._cache_ttl_s = cache_ttl_s
        self._cache: tuple[float, list[DailyForecastPoint]] | None = None
        self._session = requests.Session()

    def daily(self, now: datetime) -> list[DailyForecastPoint]:
        points = self._get(now)
        # Start tomorrow — today is already covered by the header and meteogram.
        today = now.astimezone().date()
        upcoming = [p for p in points if p.day > today]
        return upcoming[: self._days]

    def _get(self, now: datetime) -> list[DailyForecastPoint]:
        cached = self._cache
        if cached is not None and _time.monotonic() - cached[0] < self._cache_ttl_s:
            return cached[1]

        try:
            points = _fetch(self._session)
        except Exception as exc:  # noqa: BLE001 — never break the dashboard
            if cached is not None:
                log.warning("CHMI daily fetch failed, using stale copy: %s", exc)
                return cached[1]
            log.warning("CHMI daily fetch failed, returning empty outlook: %s", exc)
            return []

        self._cache = (_time.monotonic(), points)
        log.debug("CHMI daily: fetched %d days", len(points))
        return points


def _fetch(session: requests.Session) -> list[DailyForecastPoint]:
    resp = session.get(_URL, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_S)
    resp.raise_for_status()
    return _parse(resp.json())


def _parse(data: dict) -> list[DailyForecastPoint]:
    """Merge the night (min) and day (max) rows of each day into one point."""
    by_day: dict[int, dict] = {}
    for entry in data.get("data", []):
        num = entry.get("number")
        if num is None:
            continue
        by_day.setdefault(num, {})
        row = by_day[num]
        if "minimumTemperature" in entry:
            row["min"] = float(entry["minimumTemperature"])
        if "maximumTemperature" in entry:
            row["max"] = float(entry["maximumTemperature"])
            # The day row (10:00Z) names the calendar day and its icon.
            row["day"] = datetime.fromisoformat(entry["time"]).astimezone().date()
            row["weather"] = entry.get("weather")
            row["icon"] = entry.get("weatherIcon")

    points: list[DailyForecastPoint] = []
    for row in by_day.values():
        if "day" not in row or "min" not in row or "max" not in row:
            continue
        points.append(
            DailyForecastPoint(
                day=row["day"],
                temp_min_c=row["min"],
                temp_max_c=row["max"],
                icon=_daily_icon(row.get("weather"), row.get("icon")),
            )
        )
    points.sort(key=lambda p: p.day)
    return points
