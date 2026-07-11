"""Live calendar source backed by a read-only CalDAV account.

Connects to a CalDAV server (e.g. Fastmail), runs a time-range query per selected calendar, and expands the returned objects into :class:`~dashboard.models.CalendarEvent`.
Recurrence expansion and the date/time mapping are shared with the ICS source via :func:`expand_ics`.

The whole event list is cached with a short TTL so repeated renders don't hit the network.
Any failure falls back to the last good copy (or an empty list) so a CalDAV outage never takes the dashboard down.
"""

from __future__ import annotations

import logging
import time as _time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta

import caldav

from ..config import CaldavConfig
from ..models import CalendarEvent
from .ical import expand_ics

log = logging.getLogger(__name__)

_CONNECT_TIMEOUT_S = 10


class CaldavCalendarSource:
    """A :class:`~dashboard.data.CalendarSource` over a read-only CalDAV account."""

    def __init__(
        self,
        config: CaldavConfig,
        *,
        window_days: int = 7,
        cache_ttl_s: int = 900,
    ) -> None:
        self._config = config
        self._window_days = window_days
        self._cache_ttl_s = cache_ttl_s
        self._labels = {c.name: c.label for c in config.calendars}
        self._cache: tuple[float, list[CalendarEvent]] | None = None

    def events(self, now: datetime) -> list[CalendarEvent]:
        cached = self._cache
        if cached is not None and _time.monotonic() - cached[0] < self._cache_ttl_s:
            log.debug(
                "CalDAV %s: serving %d cached events",
                self._config.username,
                len(cached[1]),
            )
            return cached[1]

        tz = now.astimezone().tzinfo  # system local timezone
        start = datetime.combine(now.date(), time.min, tzinfo=tz)
        end = start + timedelta(days=self._window_days)

        try:
            events = self._fetch(start, end, tz)
        except Exception as exc:  # noqa: BLE001 — never break the dashboard
            if cached is not None:
                log.warning("CalDAV fetch failed, using stale copy: %s", exc)
                return cached[1]
            log.warning("CalDAV fetch failed: %s", exc)
            return []

        self._cache = (_time.monotonic(), events)
        log.debug(
            "CalDAV %s: fetched %d events in window [%s, %s)",
            self._config.username,
            len(events),
            start,
            end,
        )
        return events

    def _fetch(self, start: datetime, end: datetime, tz) -> list[CalendarEvent]:
        client = caldav.DAVClient(
            url=self._config.url,
            username=self._config.username,
            password=self._config.password,
            timeout=_CONNECT_TIMEOUT_S,
        )
        with client:
            calendars = client.principal().calendars()
            log.debug(
                "CalDAV %s: server offers calendars %s; configured filter %s",
                self._config.username,
                [cal.name for cal in calendars],
                sorted(self._labels) if self._labels else "(all)",
            )
            # When specific calendars are configured, skip the rest.
            selected = [
                cal for cal in calendars if not self._labels or cal.name in self._labels
            ]
            for cal in calendars:
                if cal not in selected:
                    log.debug(
                        "CalDAV %s: skipping calendar %r (not in filter)",
                        self._config.username,
                        cal.name,
                    )

            # One time-range query per calendar; they're independent, so run
            # them concurrently (niquests' session is thread-safe). Order is
            # preserved so the merged list stays deterministic.
            def fetch(cal):
                return self._fetch_calendar(cal, start, end, tz)

            events: list[CalendarEvent] = []
            if selected:
                with ThreadPoolExecutor(max_workers=len(selected)) as pool:
                    for cal_events in pool.map(fetch, selected):
                        events.extend(cal_events)
        return events

    def _fetch_calendar(
        self, cal, start: datetime, end: datetime, tz
    ) -> list[CalendarEvent]:
        """Search one calendar and expand its objects into events."""
        label = self._labels.get(cal.name, "")
        objs = cal.search(start=start, end=end, event=True)
        events: list[CalendarEvent] = []
        for obj in objs:
            try:
                events.extend(expand_ics(obj.data, label, start, end, tz))
            except Exception:  # noqa: BLE001 — one bad object mustn't break the rest
                log.exception("failed to parse a CalDAV event in %s", cal.name)
        log.debug(
            "CalDAV %s: calendar %r (label %r) → %d objects, %d events",
            self._config.username,
            cal.name,
            label,
            len(objs),
            len(events),
        )
        return events
