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

# CHMI meteogram icon code → Lucide icon name, mapped explicitly per code.
#
# The code is not cleanly decomposable: the tens digit is the sky state (10
# clear … 80 overcast, 90 fog; +100 for the night/moon variants) but the units
# digit's meaning shifts between bases — e.g. on base 40 a "3" is snow, while on
# base 60 it is sleet. Rather than special-case that, every real code is listed.
# Codes were read off the CHMI icon set at
# https://www.chmi.cz/o/chmu-theme/images/icon/<code>.svg
#
# Lucide keeps the sun/moon only for its rain variants — it has none for snow or
# thunder, so those drop the sun/moon; sleet folds into snow (no mixed icon), and
# thunder-with-hail (…9) folds into plain thunder.
_ICON_MAP = {
    # --- day: dry ---
    10: "sun", 20: "cloud-sun", 40: "cloud-sun", 60: "cloud-sun", 70: "cloud-sun",
    80: "cloud", 90: "cloud-fog",
    # --- day: rain (sun kept where the sky shows it) ---
    41: "cloud-sun-rain", 61: "cloud-sun-rain", 62: "cloud-sun-rain",
    71: "cloud-sun-rain", 72: "cloud-sun-rain",
    81: "cloud-rain", 82: "cloud-rain", 91: "cloud-rain", 92: "cloud-rain",
    # --- day: snow / sleet ---
    43: "cloud-snow", 45: "cloud-snow", 63: "cloud-snow", 64: "cloud-snow",
    65: "cloud-snow", 73: "cloud-snow", 74: "cloud-snow", 75: "cloud-snow",
    83: "cloud-snow", 84: "cloud-snow", 85: "cloud-snow", 93: "cloud-snow",
    94: "cloud-snow",
    # --- day: thunderstorm (incl. with hail) ---
    46: "cloud-lightning", 66: "cloud-lightning", 69: "cloud-lightning",
    76: "cloud-lightning", 79: "cloud-lightning", 86: "cloud-lightning",
    89: "cloud-lightning",
    # --- night: dry ---
    110: "moon", 120: "cloud-moon", 140: "cloud-moon", 160: "cloud-moon",
    170: "cloud-moon",
    # --- night: rain ---
    141: "cloud-moon-rain", 161: "cloud-moon-rain", 162: "cloud-moon-rain",
    171: "cloud-moon-rain", 172: "cloud-moon-rain",
    # --- night: snow / sleet ---
    143: "cloud-snow", 145: "cloud-snow", 163: "cloud-snow", 164: "cloud-snow",
    165: "cloud-snow", 173: "cloud-snow", 174: "cloud-snow", 175: "cloud-snow",
    # --- night: thunderstorm (incl. with hail) ---
    146: "cloud-lightning", 166: "cloud-lightning", 169: "cloud-lightning",
    176: "cloud-lightning", 179: "cloud-lightning",
}


def icon_to_lucide(code: int) -> str:
    """Map a CHMI meteogram icon code to a Lucide icon name."""
    return _ICON_MAP.get(code, "cloud-sun")

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
