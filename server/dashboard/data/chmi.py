"""Hourly forecast from the CHMI (Czech Hydrometeorological Institute) meteogram API.

Fetches the ALADIN NWP model output for a configured station and caches it.
Wraps another WeatherSource and replaces only the forecast half.
"""

from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timedelta

import requests

from ..config import ChmiConfig
from ..models import ForecastPoint, WeatherNow, WeatherRecent
from . import WeatherSource

log = logging.getLogger(__name__)

_BASE_URL = "https://data-provider.chmi.cz/api/graphs/graf.meteogram"
_TIMEOUT_S = 10
_USER_AGENT = "esp-epaper-dashboard/1.0 (+chmi)"


class ChmiWeatherSource:
    """A WeatherSource decorator that overlays CHMI hourly forecast."""

    def __init__(
        self,
        config: ChmiConfig,
        inner: WeatherSource,
    ) -> None:
        self._config = config
        self._inner = inner
        self._cache: tuple[float, list[ForecastPoint]] | None = None
        self._session = requests.Session()

    def weather(
        self, now: datetime
    ) -> tuple[WeatherNow, WeatherRecent, list[ForecastPoint]]:
        base_now, recent, _ = self._inner.weather(now)
        return base_now, recent, self._get_forecast(now)

    def _get_forecast(self, now: datetime) -> list[ForecastPoint]:
        cached = self._cache
        if (
            cached is not None
            and _time.monotonic() - cached[0] < self._config.cache_ttl_s
        ):
            return _slice(cached[1], now, self._config.hours)

        try:
            points = self._fetch()
        except Exception as exc:  # noqa: BLE001 — never break the dashboard
            if cached is not None:
                log.warning("CHMI fetch failed, using stale copy: %s", exc)
                return _slice(cached[1], now, self._config.hours)
            log.warning("CHMI fetch failed, returning empty forecast: %s", exc)
            return []

        self._cache = (_time.monotonic(), points)
        log.debug(
            "CHMI: fetched %d hourly points for station %d",
            len(points),
            self._config.station_id,
        )
        return _slice(points, now, self._config.hours)

    def _fetch(self) -> list[ForecastPoint]:
        url = f"{_BASE_URL}/{self._config.station_id}"
        resp = self._session.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT_S,
        )
        resp.raise_for_status()
        return _parse(resp.json())


def _slice(
    points: list[ForecastPoint], now: datetime, hours: int
) -> list[ForecastPoint]:
    start = now.replace(minute=0, second=0, microsecond=0).astimezone()
    end = start + timedelta(hours=hours)
    return [p for p in points if start <= p.time.astimezone() < end]


def _parse(data: dict) -> list[ForecastPoint]:
    points: list[ForecastPoint] = []
    for entry in data.get("data", []):
        t = entry.get("t2m")
        if t is None:
            continue
        dt = datetime.fromisoformat(entry["validityTime"]).astimezone()
        wind = entry.get("windSpeed")
        wdir = entry.get("windDirection")
        points.append(
            ForecastPoint(
                time=dt,
                temp_c=float(t),
                precip_mm=float(entry.get("prec") or 0.0),
                wind_ms=float(wind) if wind is not None else None,
                wind_dir_deg=float(wdir) if wdir is not None else None,
            )
        )
    return points
