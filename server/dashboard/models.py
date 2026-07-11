"""View model — the data structures the renderer consumes.

These are produced by a :class:`dashboard.data.DataSource` and are deliberately free of any rendering or transport concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image


@dataclass
class WeatherNow:
    """Current conditions shown in the header."""

    temp_c: float = 24.0
    condition: str = "Partly cloudy"
    sunrise: str = "05:12"  # "HH:MM"
    sunset: str = "21:34"  # "HH:MM"
    humidity_pct: float = 58.0  # relative humidity, %
    wind_ms: float = 3.4  # wind speed, m/s
    wind_gust_ms: float | None = None  # wind gust speed, m/s; None if not available
    wind_dir_deg: float = 225.0  # meteo. direction wind blows FROM (0=N, 90=E)
    illuminance_lx: float = 8200.0  # ambient light, lux


@dataclass
class WeatherRecent:
    """Measured weather over the last 24 hours."""

    temp_min_c: float
    temp_max_c: float
    precip_mm: float


@dataclass
class ForecastPoint:
    """A single hour bucket of the meteogram."""

    time: datetime  # timestamp of the hour bucket
    temp_c: float  # temperature °C
    precip_mm: float  # precipitation for this hour (mm)
    icon: "Image | None" = None  # ready-made weather icon; not drawn yet
    wind_ms: float | None = None  # wind speed (m/s)
    wind_dir_deg: float | None = None  # meteo. direction wind blows FROM (0=N, 90=E)


@dataclass
class CalendarEvent:
    """One upcoming calendar entry."""

    date: date  # day the event falls on
    time: str  # "09:00" or "All day"
    title: str
    all_day: bool = False
    calendar: str = ""  # single-char calendar label, e.g. "W"=Work, "P"=Personal


@dataclass
class DashboardData:
    """Everything the renderer needs to draw one frame."""

    now: datetime
    weather: WeatherNow
    recent: WeatherRecent
    events: list[CalendarEvent]
    forecast: list[ForecastPoint]
