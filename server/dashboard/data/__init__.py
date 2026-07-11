"""Data sources for the dashboard.

The dashboard is assembled from two independent halves:

* a :class:`WeatherSource` — current conditions, recent measurements and the hourly forecast, and
* a :class:`CalendarSource` — the upcoming events.

A :class:`DataSource` is the top-level seam the service layer consumes; it produces a whole :class:`~dashboard.models.DashboardData`.
:class:`CompositeSource` glues a weather half and a calendar half into one, so each can be a live provider or the :class:`~dashboard.data.placeholder.PlaceholderSource` fixture independently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..config import Settings
from ..models import (
    CalendarEvent,
    DashboardData,
    ForecastPoint,
    WeatherNow,
    WeatherRecent,
)
from .placeholder import PlaceholderSource


class WeatherSource(Protocol):
    """Produces the weather half of the dashboard for a given moment."""

    def weather(
        self, now: datetime
    ) -> tuple[WeatherNow, WeatherRecent, list[ForecastPoint]]:
        """Return current conditions, recent measurements and the forecast."""
        ...


class CalendarSource(Protocol):
    """Produces the upcoming events for a given moment."""

    def events(self, now: datetime) -> list[CalendarEvent]:
        """Return the events to show, as of ``now``."""
        ...


class DataSource(Protocol):
    """Produces the current dashboard state for a given moment."""

    def fetch(self, now: datetime) -> DashboardData:
        """Return the dashboard data as of ``now``."""
        ...


class CompositeSource:
    """A :class:`DataSource` assembled from a weather and a calendar source."""

    def __init__(self, weather: WeatherSource, calendar: CalendarSource) -> None:
        self._weather = weather
        self._calendar = calendar

    def fetch(self, now: datetime) -> DashboardData:
        weather, recent, forecast = self._weather.weather(now)
        return DashboardData(
            now=now,
            weather=weather,
            recent=recent,
            events=self._calendar.events(now),
            forecast=forecast,
        )


class MergedCalendarSource:
    """A :class:`CalendarSource` that concatenates several calendar sources."""

    def __init__(self, sources: list[CalendarSource]) -> None:
        self._sources = sources

    def events(self, now: datetime) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        for source in self._sources:
            events.extend(source.events(now))
        return events


def default_source(settings: Settings) -> DataSource:
    """The data source used when the app is created without an explicit one.

    Live providers are wired in only when configured; the weather half (unless VictoriaMetrics is set up) and any unconfigured calendar fall back to the :class:`PlaceholderSource` fixture.
    """
    placeholder = PlaceholderSource()

    weather: WeatherSource = placeholder
    if settings.victoriametrics is not None:
        from .victoriametrics import VictoriaMetricsWeatherSource

        weather = VictoriaMetricsWeatherSource(
            settings.victoriametrics,
            fallback=placeholder,
            cache_ttl_s=settings.victoriametrics.cache_ttl_s,
        )

    if settings.forecast is not None:
        from .chmi import ChmiWeatherSource

        weather = ChmiWeatherSource(settings.forecast, inner=weather)

    if settings.location is not None:
        from .suntimes import SunTimesWeatherSource

        weather = SunTimesWeatherSource(settings.location, inner=weather)

    calendars: list[CalendarSource] = []
    if settings.calendars:
        from .ical import IcalCalendarSource

        calendars.append(
            IcalCalendarSource(
                settings.calendars,
                window_days=settings.calendar_window_days,
                cache_ttl_s=settings.calendar_cache_ttl_s,
            )
        )
    if settings.caldavs:
        from .caldav import CaldavCalendarSource

        for caldav in settings.caldavs:
            calendars.append(
                CaldavCalendarSource(
                    caldav,
                    window_days=settings.calendar_window_days,
                    cache_ttl_s=settings.calendar_cache_ttl_s,
                )
            )

    if not calendars:
        # No live calendars: only build a composite if the weather half is live.
        if weather is placeholder:
            return placeholder
        return CompositeSource(weather=weather, calendar=placeholder)

    calendar = calendars[0] if len(calendars) == 1 else MergedCalendarSource(calendars)
    return CompositeSource(weather=weather, calendar=calendar)


__all__ = [
    "CalendarSource",
    "CompositeSource",
    "DataSource",
    "MergedCalendarSource",
    "PlaceholderSource",
    "WeatherSource",
    "default_source",
]
