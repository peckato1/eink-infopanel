"""Static placeholder data source.

Serves hand-made weather and calendar fixtures so the renderer can be developed end to end.
Replace with live providers (e.g. a CHMI ALADIN scraper and a calendar feed) by implementing :class:`~dashboard.data.DataSource` elsewhere.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..models import (
    CalendarEvent,
    DailyForecastPoint,
    DashboardData,
    ForecastPoint,
    WeatherNow,
    WeatherRecent,
)

_WEATHER = WeatherNow()
_RECENT = WeatherRecent(temp_min_c=12.6, temp_max_c=23.1, precip_mm=5.4)

# (day offset from today, time, title, calendar) — empty time == all-day
_EVENTS: list[tuple[int, str, str, str]] = [
    (0, "", "Name day: Bohuslava", "P"),
    (0, "09:00", "Team standup", "W"),
    (0, "12:30", "Lunch", "P"),
    (0, "15:00", "Doctor appointment", "P"),
    (1, "10:30", "1:1 with Jan", "W"),
    (1, "18:00", "Gym", "F"),
    (2, "08:00", "Kids pickup", "P"),
    (2, "14:00", "Design review", "W"),
    (3, "", "Public holiday", ""),
    (3, "11:00", "Lunch with client", "W"),
]

# Hand-made week outlook: (min °C, max °C, Lucide icon) per day from tomorrow.
_DAILY: list[tuple[float, float, str]] = [
    (14.0, 24.0, "cloud-sun"),
    (15.0, 26.0, "sun"),
    (16.0, 27.0, "sun"),
    (16.0, 23.0, "cloud-rain"),
    (13.0, 21.0, "cloud-rain"),
    (12.0, 22.0, "cloudy"),
    (13.0, 25.0, "cloud-sun"),
]

# Hand-made 48h dummy series, indexed by hour offset from the current full hour.
_TEMPS: list[float] = [
    16.2,
    15.4,
    14.7,
    14.1,
    13.6,
    13.2,
    13.5,
    15.0,  # h0–h7
    17.3,
    19.1,
    20.4,
    21.6,
    22.3,
    22.8,
    23.1,
    22.6,  # h8–h15
    21.4,
    19.8,
    18.3,
    17.1,
    16.3,
    15.7,
    15.1,
    14.6,  # h16–h23
    14.0,
    13.5,
    13.1,
    12.8,
    12.5,
    12.9,
    14.2,
    16.1,  # h24–h31
    18.0,
    19.6,
    20.7,
    21.3,
    21.0,
    20.2,
    18.9,
    17.4,  # h32–h39
    16.2,
    15.3,
    14.6,
    14.0,
    13.5,
    13.1,
    12.8,
    12.6,  # h40–h47
]
_PRECIP: list[float] = [
    0.0,
    0.0,
    0.0,
    0.2,
    0.5,
    0.0,
    0.0,
    0.0,  # h0–h7
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.3,
    1.1,
    2.4,  # h8–h15
    3.1,
    1.8,
    0.6,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,  # h16–h23
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,  # h24–h31
    0.0,
    0.0,
    0.4,
    0.9,
    0.2,
    0.0,
    0.0,
    0.0,  # h32–h39
    0.0,
    0.0,
    0.0,
    0.0,
    0.7,
    1.5,
    0.8,
    0.0,  # h40–h47
]
_WIND: list[float] = [
    4.1,
    3.8,
    3.5,
    3.2,
    2.9,
    2.7,
    3.0,
    3.6,  # h0–h7
    4.4,
    5.2,
    5.9,
    6.5,
    7.1,
    7.8,
    8.3,
    8.0,  # h8–h15
    7.2,
    6.4,
    5.7,
    5.1,
    4.6,
    4.2,
    3.9,
    3.6,  # h16–h23
    3.3,
    3.1,
    2.8,
    2.6,
    2.9,
    3.4,
    4.0,
    4.7,  # h24–h31
    5.5,
    6.2,
    6.8,
    7.0,
    6.6,
    5.9,
    5.1,
    4.5,  # h32–h39
    4.0,
    3.7,
    3.4,
    3.2,
    3.5,
    4.1,
    4.4,
    4.0,  # h40–h47
]
# Direction the wind blows FROM, degrees (0=N, 90=E, 180=S, 270=W)
_WIND_DIR: list[float] = [
    220,
    225,
    230,
    235,
    240,
    245,
    240,
    235,  # h0–h7
    230,
    225,
    220,
    215,
    210,
    205,
    200,
    205,  # h8–h15
    215,
    230,
    245,
    260,
    270,
    275,
    280,
    285,  # h16–h23
    290,
    295,
    300,
    305,
    300,
    290,
    280,
    270,  # h24–h31
    260,
    250,
    245,
    240,
    235,
    230,
    225,
    220,  # h32–h39
    215,
    210,
    205,
    210,
    220,
    235,
    250,
    260,  # h40–h47
]


class PlaceholderSource:
    """Static fixtures for every part of the dashboard.

    Implements the full :class:`~dashboard.data.DataSource` as well as the narrower :class:`~dashboard.data.WeatherSource` and :class:`~dashboard.data.CalendarSource`, so it can stand in for either half while the other is served by a live provider.
    """

    def fetch(self, now: datetime) -> DashboardData:
        return DashboardData(
            now=now,
            weather=_WEATHER,
            recent=_RECENT,
            events=self.events(now),
            forecast=self.forecast(now),
            daily=self.daily(now),
        )

    def weather(
        self, now: datetime
    ) -> tuple[WeatherNow, WeatherRecent, list[ForecastPoint]]:
        return _WEATHER, _RECENT, self.forecast(now)

    def events(self, now: datetime) -> list[CalendarEvent]:
        return self._events(now)

    def forecast(self, now: datetime) -> list[ForecastPoint]:
        return self._forecast(now)

    def daily(self, now: datetime) -> list[DailyForecastPoint]:
        today = now.date()
        return [
            DailyForecastPoint(
                day=today + timedelta(days=offset + 1),
                temp_min_c=tmin,
                temp_max_c=tmax,
                icon=icon,
            )
            for offset, (tmin, tmax, icon) in enumerate(_DAILY)
        ]

    @staticmethod
    def _events(now: datetime) -> list[CalendarEvent]:
        today = now.date()
        return [
            CalendarEvent(
                date=today + timedelta(days=offset),
                time=time,
                title=title,
                all_day=not time,
                calendar=cal,
            )
            for offset, time, title, cal in _EVENTS
        ]

    @staticmethod
    def _forecast(now: datetime) -> list[ForecastPoint]:
        start = now.replace(minute=0, second=0, microsecond=0)
        return [
            ForecastPoint(
                time=start + timedelta(hours=h),
                temp_c=_TEMPS[h],
                precip_mm=_PRECIP[h],
                wind_ms=_WIND[h],
                wind_dir_deg=_WIND_DIR[h],
            )
            for h in range(len(_TEMPS))
        ]
