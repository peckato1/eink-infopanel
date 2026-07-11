"""Hourly forecast from the CHMI (Czech Hydrometeorological Institute) meteogram API.

Fetches the ALADIN NWP model output for a configured station and caches it.
Wraps another WeatherSource and replaces only the forecast half.
"""

from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timedelta

import requests

from dataclasses import replace

from ..config import ChmiConfig
from ..models import ForecastPoint, WeatherNow, WeatherRecent
from . import WeatherSource

# CHMI meteogram icon code → Lucide icon name.
# Tens = sky condition; units = precipitation type (0=dry, 1=drizzle, 2=rain,
# 3=freezing rain, 4=sleet, 5=snow, 6=hail, 9=thunderstorm).
# Day bases: 10 clear, 20 mostly clear, 40 partly cloudy, 60 mostly cloudy,
#            70 very cloudy, 80 overcast, 90 fog
# Night bases (moon): 110, 120, 140, 160, 170
_DAY_BASE = {10: "sun", 20: "cloud-sun", 40: "cloud-sun", 60: "cloudy", 70: "cloud", 80: "cloud", 90: "cloud-fog"}
_NIGHT_BASE = {110: "moon", 120: "cloud-moon", 140: "cloud-moon", 160: "cloudy", 170: "cloud"}
_PRECIP_DAY = {1: "cloud-drizzle", 2: "cloud-rain", 3: "cloud-rain", 4: "cloud-hail", 5: "cloud-snow", 6: "cloud-hail", 9: "cloud-lightning"}
_PRECIP_NIGHT = {1: "cloud-moon-rain", 2: "cloud-moon-rain", 3: "cloud-moon-rain", 4: "cloud-snow", 5: "cloud-snow", 6: "cloud-hail", 9: "cloud-lightning"}


def icon_to_lucide(code: int) -> str:
    """Map a CHMI icon code to a Lucide icon name."""
    base, precip = (code // 10) * 10, code % 10
    if base in _NIGHT_BASE:
        return _NIGHT_BASE[base] if precip == 0 else _PRECIP_NIGHT.get(precip, _NIGHT_BASE[base])
    if base in _DAY_BASE:
        return _DAY_BASE[base] if precip == 0 else _PRECIP_DAY.get(precip, _DAY_BASE[base])
    return "cloud-sun"

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
        forecast = self._get_forecast(now)
        now_icon = _current_icon(forecast, now)
        weather_now = replace(base_now, icon=now_icon) if now_icon else base_now
        return weather_now, recent, forecast

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
        raw_icon = entry.get("icon")
        points.append(
            ForecastPoint(
                time=dt,
                temp_c=float(t),
                precip_mm=float(entry.get("prec") or 0.0),
                wind_ms=float(wind) if wind is not None else None,
                wind_dir_deg=float(wdir) if wdir is not None else None,
                icon_code=int(raw_icon) if raw_icon is not None else None,
            )
        )
    return points


def _current_icon(forecast: list[ForecastPoint], now: datetime) -> str:
    """Return the Lucide icon name for the hour closest to now, or empty string."""
    now_utc = now.astimezone()
    current = next(
        (p for p in reversed(forecast) if p.time.astimezone() <= now_utc),
        forecast[0] if forecast else None,
    )
    if current is None or current.icon_code is None:
        return ""
    return icon_to_lucide(current.icon_code)
