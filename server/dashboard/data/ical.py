"""Live calendar source backed by iCalendar (ICS) feeds.

Fetches one or more ICS URLs, expands recurring events over a forward window, and maps them to :class:`~dashboard.models.CalendarEvent`.
Raw feeds are cached with a short TTL so repeated renders don't hammer the network.
A fetch failure falls back to the last good copy (or is skipped) rather than taking the whole dashboard down.
"""

from __future__ import annotations

import logging
import time as _time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta

import icalendar
import recurring_ical_events
import requests

from ..config import CalendarConfig
from ..models import CalendarEvent

log = logging.getLogger(__name__)

_FETCH_TIMEOUT_S = 10
_USER_AGENT = "esp-epaper-dashboard/1.0 (+ical)"


def expand_ics(
    raw: bytes | str,
    label: str,
    start: datetime,
    end: datetime,
    tz,
) -> list[CalendarEvent]:
    """Parse ICS data and map events in ``[start, end)`` to calendar events.

    Recurrences are expanded over the window.
    ``start``/``end`` must be timezone-aware; ``tz`` is the local zone timed events are rendered in.
    Shared by the ICS-feed and CalDAV sources.
    """
    cal = icalendar.Calendar.from_ical(raw)
    out: list[CalendarEvent] = []
    for comp in recurring_ical_events.of(cal).between(start, end):
        dt = comp["DTSTART"].dt
        title = str(comp.get("SUMMARY", "")).strip()
        if not title:
            continue

        if isinstance(dt, datetime):
            if dt.tzinfo is not None:
                dt = dt.astimezone(tz)
            out.append(
                CalendarEvent(
                    date=dt.date(),
                    time=dt.strftime("%H:%M"),
                    title=title,
                    all_day=False,
                    calendar=label,
                )
            )
        else:  # a plain date → all-day event
            out.append(
                CalendarEvent(
                    date=dt,
                    time="",
                    title=title,
                    all_day=True,
                    calendar=label,
                )
            )
    return out


class IcalCalendarSource:
    """A :class:`~dashboard.data.CalendarSource` over a set of ICS feeds."""

    def __init__(
        self,
        calendars: tuple[CalendarConfig, ...],
        *,
        window_days: int = 7,
        cache_ttl_s: int = 900,
    ) -> None:
        self._calendars = calendars
        self._window_days = window_days
        self._cache_ttl_s = cache_ttl_s
        # url -> (monotonic fetch time, raw ICS bytes)
        self._cache: dict[str, tuple[float, bytes]] = {}
        # Reused across feeds for connection keep-alive.
        self._session = requests.Session()

    def events(self, now: datetime) -> list[CalendarEvent]:
        tz = now.astimezone().tzinfo  # system local timezone
        start = datetime.combine(now.date(), time.min, tzinfo=tz)
        end = start + timedelta(days=self._window_days)

        def fetch(cal: CalendarConfig) -> list[CalendarEvent]:
            raw = self._raw(cal.url)
            if raw is None:
                return []
            try:
                return expand_ics(raw, cal.label, start, end, tz)
            except Exception:  # noqa: BLE001 — a bad feed must not break others
                log.exception("failed to parse calendar %s", cal.url)
                return []

        # Feeds are independent, so fetch them concurrently; order is preserved
        # so the merged list stays deterministic.
        events: list[CalendarEvent] = []
        if self._calendars:
            with ThreadPoolExecutor(max_workers=len(self._calendars)) as pool:
                for cal_events in pool.map(fetch, self._calendars):
                    events.extend(cal_events)
        return events

    def _raw(self, url: str) -> bytes | None:
        """Return the ICS bytes for ``url``, cached, or ``None`` on failure."""
        cached = self._cache.get(url)
        if cached is not None and _time.monotonic() - cached[0] < self._cache_ttl_s:
            return cached[1]

        try:
            resp = self._session.get(
                url,
                headers={"User-Agent": _USER_AGENT},
                timeout=_FETCH_TIMEOUT_S,
            )
            resp.raise_for_status()
            raw = resp.content
        except requests.RequestException as exc:
            if cached is not None:
                log.warning(
                    "calendar fetch failed for %s, using stale copy: %s", url, exc
                )
                return cached[1]
            log.warning("calendar fetch failed for %s: %s", url, exc)
            return None

        self._cache[url] = (_time.monotonic(), raw)
        return raw
