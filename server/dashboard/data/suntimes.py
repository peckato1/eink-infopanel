"""Weather decorator that fills in sunrise/sunset from the panel's location.

Sunrise and sunset depend only on the date and a fixed latitude/longitude, so they're computed locally with :mod:`astral` rather than fetched — no network round-trip, and correct even when the underlying weather source (VictoriaMetrics or the placeholder) carries no such data.
Wraps another :class:`WeatherSource` and overlays the computed times onto its :class:`~dashboard.models.WeatherNow`.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime

from astral import Observer
from astral.sun import sunrise, sunset

from ..config import LocationConfig
from ..models import ForecastPoint, WeatherNow, WeatherRecent
from . import WeatherSource

log = logging.getLogger(__name__)


class SunTimesWeatherSource:
    """A :class:`WeatherSource` that overlays locally computed sun times."""

    def __init__(self, config: LocationConfig, inner: WeatherSource) -> None:
        self._observer = Observer(latitude=config.latitude, longitude=config.longitude)
        self._inner = inner

    def weather(
        self, now: datetime
    ) -> tuple[WeatherNow, WeatherRecent, list[ForecastPoint]]:
        base_now, recent, forecast = self._inner.weather(now)
        return replace(base_now, **self._sun_times(now)), recent, forecast

    def _sun_times(self, now: datetime) -> dict[str, str]:
        """Sunrise/sunset for today as ``{"sunrise": ..., "sunset": ...}``.

        Empty when the sun neither rises nor sets (polar day/night), leaving the underlying source's values in place.
        """
        tz = now.astimezone().tzinfo  # now is naive local; attach the system zone
        try:
            rise = sunrise(self._observer, date=now.date(), tzinfo=tz)
            set_ = sunset(self._observer, date=now.date(), tzinfo=tz)
        except ValueError as exc:  # no sunrise/sunset at this latitude today
            log.warning("no sun times for %s: %s", now.date(), exc)
            return {}
        return {
            "sunrise": rise.strftime("%H:%M"),
            "sunset": set_.strftime("%H:%M"),
        }
