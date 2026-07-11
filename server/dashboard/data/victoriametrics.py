"""Live weather source backed by VictoriaMetrics (Prometheus HTTP API).

Derives the current temperature and the trailing min/max temperature and total precipitation from two MetricsQL selectors via ``/api/v1/query``.
The rain selector is a monotonic lifetime accumulation in metres, so the window's total is its value now minus its oldest value within the window.
VictoriaMetrics holds no forecast and none of the descriptive header fields (condition, sunrise/sunset), so those are taken from a fallback weather source (typically the placeholder fixture); only the temperature and the recent stats are live.

Results are cached with a short TTL and any query failure falls back to the last good copy — or, if there is none yet, to the fallback source — so a VictoriaMetrics outage never takes the dashboard down.
"""

from __future__ import annotations

import logging
import time as _time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime

import requests

from ..config import VictoriaMetricsConfig
from ..models import ForecastPoint, WeatherNow, WeatherRecent
from . import WeatherSource

log = logging.getLogger(__name__)

_QUERY_TIMEOUT_S = 10
_USER_AGENT = "esp-epaper-dashboard/1.0 (+victoriametrics)"
#: Lookback for the "current" temperature — one missed scrape must not blank it.
_CURRENT_LOOKBACK = "15m"
#: The rain series is a metre accumulation; render precipitation in millimetres.
_METRES_TO_MM = 1000.0

#: The live half we compute from VictoriaMetrics: the ``WeatherNow`` fields to overlay (always ``temp_c``, plus any configured header readings) and the recent stats.
_Live = tuple[dict[str, float], WeatherRecent]

#: Optional live "now" selectors → (WeatherNow field, scale applied to the raw value).
#: All are read in their target unit already (humidity in percent despite the ``_ratio`` metric name), so no scaling is needed.
_NOW_SELECTORS = (
    ("humidity_selector", "humidity_pct", 1.0),
    ("wind_selector", "wind_ms", 1.0),
    ("wind_gust_selector", "wind_gust_ms", 1.0),
    ("wind_dir_selector", "wind_dir_deg", 1.0),
    ("light_selector", "illuminance_lx", 1.0),
)


class VictoriaMetricsWeatherSource:
    """A :class:`~dashboard.data.WeatherSource` backed by VictoriaMetrics."""

    def __init__(
        self,
        config: VictoriaMetricsConfig,
        fallback: WeatherSource,
        *,
        cache_ttl_s: int = 900,
    ) -> None:
        self._config = config
        self._fallback = fallback
        self._cache_ttl_s = cache_ttl_s
        self._cache: tuple[float, _Live] | None = None
        # Reused across queries for connection keep-alive.
        self._session = requests.Session()

    def weather(
        self, now: datetime
    ) -> tuple[WeatherNow, WeatherRecent, list[ForecastPoint]]:
        # Forecast and the descriptive header fields aren't in VictoriaMetrics,
        # so take the whole shape from the fallback and overlay the live values.
        base_now, base_recent, forecast = self._fallback.weather(now)

        live = self._live()
        if live is None:
            return base_now, base_recent, forecast

        now_fields, recent = live
        return replace(base_now, **now_fields), recent, forecast

    def _live(self) -> _Live | None:
        """Return the live temperature/stats, cached, or ``None`` on failure."""
        cached = self._cache
        if cached is not None and _time.monotonic() - cached[0] < self._cache_ttl_s:
            return cached[1]

        try:
            live = self._fetch()
        except Exception as exc:  # noqa: BLE001 — never break the dashboard
            if cached is not None:
                log.warning("VictoriaMetrics query failed, using stale copy: %s", exc)
                return cached[1]
            log.warning("VictoriaMetrics query failed, using fallback weather: %s", exc)
            return None

        self._cache = (_time.monotonic(), live)
        return live

    def _fetch(self) -> _Live:
        temp = self._config.temp_selector
        rain = self._config.rain_selector
        window = self._config.window

        # The four selectors are independent, so run them concurrently: the
        # endpoint's latency is one round-trip instead of four in series.
        # Rain is a monotonic lifetime accumulator, so the window's total is its
        # value now minus its value at the window's start — regardless of how
        # large the absolute count is. The baseline is min_over_time (the oldest
        # sample in the window), not `offset {window}`: the station reports over
        # radio and drops the odd packet, so a point lookup at exactly one window
        # ago can hit a gap and vanish, whereas min_over_time just takes the
        # nearest surviving sample. increase()/rate() are wrong here — with less
        # than a full window of history they take ~0 as the start and report the
        # whole lifetime total. clamp_min guards a dip/gap from going negative.
        exprs = {
            "temp_now": f"last_over_time({temp}[{_CURRENT_LOOKBACK}])",
            "temp_min": f"min_over_time({temp}[{window}])",
            "temp_max": f"max_over_time({temp}[{window}])",
            "rain_m": (
                f"clamp_min("
                f"last_over_time({rain}[{_CURRENT_LOOKBACK}]) "
                f"- min_over_time({rain}[{window}]), 0)"
            ),
        }
        # Header readings are configured independently — query only the ones set.
        live_now = [
            (field, scale)
            for attr, field, scale in _NOW_SELECTORS
            if getattr(self._config, attr)
        ]
        for attr, field, _scale in _NOW_SELECTORS:
            selector = getattr(self._config, attr)
            if selector:
                exprs[field] = f"last_over_time({selector}[{_CURRENT_LOOKBACK}])"

        with ThreadPoolExecutor(max_workers=len(exprs)) as pool:
            values = dict(zip(exprs, pool.map(self._query_scalar, exprs.values())))

        now_fields = {"temp_c": values["temp_now"]}
        for field, scale in live_now:
            now_fields[field] = values[field] * scale

        recent = WeatherRecent(
            temp_min_c=values["temp_min"],
            temp_max_c=values["temp_max"],
            precip_mm=values["rain_m"] * _METRES_TO_MM,
        )
        log.debug(
            "VictoriaMetrics: now=%.1f°C min=%.1f max=%.1f precip=%.1fmm over %s; "
            "live now fields: %s",
            values["temp_now"],
            values["temp_min"],
            values["temp_max"],
            recent.precip_mm,
            window,
            now_fields,
        )
        return now_fields, recent

    def _query_scalar(self, expr: str) -> float:
        """Run an instant query and return the single scalar value it yields."""
        url = f"{self._config.url.rstrip('/')}/api/v1/query"
        resp = self._session.get(
            url,
            params={"query": expr},
            headers={"User-Agent": _USER_AGENT},
            auth=self._auth(),
            timeout=_QUERY_TIMEOUT_S,
        )
        resp.raise_for_status()
        payload = resp.json()

        if payload.get("status") != "success":
            raise RuntimeError(
                f"query {expr!r} returned status {payload.get('status')!r}"
            )
        result = payload.get("data", {}).get("result", [])
        if not result:
            raise RuntimeError(f"query {expr!r} returned no series")
        # Instant vector: each series' "value" is [timestamp, "<number>"].
        return float(result[0]["value"][1])

    def _auth(self) -> tuple[str, str] | None:
        if self._config.username:
            return self._config.username, self._config.password
        return None
