"""Wake-up policy: when should the firmware next fetch a frame.

The firmware is a thin client — it sleeps until the absolute epoch second we hand it in the ``X-Next-Wakeup`` header.
All the scheduling smarts live here:

* **Alignment** — snap wake-ups to the ``refresh_interval_s`` grid measured from local midnight (e.g. :00/:30 for a 1800 s interval) so they don't drift.
* **Day rollover** — never sleep blindly past local midnight, so the day-based layout flips to the new day shortly after 00:00.
* **Quiet hours** — inside the configured night window, sleep through until the morning instead of refreshing a display nobody is looking at.

The single entry point, :func:`next_wakeup`, is pure (no clock reads, no I/O): the caller passes ``now`` so it stays trivially testable.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from .config import Settings

#: Small offset so a post-midnight wake-up lands *after* the boundary, ensuring
#: the new day has begun when the frame is rendered.
_ROLLOVER_OFFSET = timedelta(seconds=60)


def next_wakeup(now: datetime, settings: Settings) -> int:
    """Return the absolute epoch second the firmware should next wake at.

    ``now`` must be a timezone-aware local datetime.
    The result is always strictly in the future relative to ``now``.
    """
    interval = timedelta(seconds=settings.refresh_interval_s)

    if settings.wake_align:
        base = _align_up(now, settings.refresh_interval_s)
    else:
        base = now + interval

    quiet = _parse_hhmm(settings.quiet_start), _parse_hhmm(settings.quiet_end)
    if quiet[0] is not None and quiet[1] is not None:
        if _in_quiet(base, quiet[0], quiet[1]):
            # Sleep through the night: wake at the next occurrence of quiet_end.
            base = _next_time_at(now, quiet[1])
    else:
        # Outside quiet hours, don't sleep blindly across midnight — wake just
        # after it so the day-based layout rolls over promptly.
        midnight = _next_midnight(now)
        if base > midnight:
            base = midnight + _ROLLOVER_OFFSET

    if base <= now:  # defensive: never hand back a past/now timestamp
        base = now + interval
    return int(base.timestamp())


def _align_up(now: datetime, interval_s: int) -> datetime:
    """Next multiple of ``interval_s`` (from local midnight) strictly after ``now``."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = (now - midnight).total_seconds()
    steps = int(elapsed // interval_s) + 1  # strictly forward, even on a boundary
    return midnight + timedelta(seconds=steps * interval_s)


def _next_midnight(now: datetime) -> datetime:
    """Local midnight at the start of the day after ``now``."""
    return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def _next_time_at(now: datetime, at: time) -> datetime:
    """Next datetime with local time ``at`` that is strictly after ``now``."""
    candidate = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _in_quiet(moment: datetime, start: time, end: time) -> bool:
    """Whether ``moment`` falls in the ``[start, end)`` quiet window.

    The window may wrap past midnight (``start`` later than ``end``).
    """
    t = moment.timetz().replace(tzinfo=None)
    if start <= end:
        return start <= t < end
    return t >= start or t < end


def _parse_hhmm(value: str) -> time | None:
    """Parse ``"HH:MM"`` into a :class:`~datetime.time`, or ``None`` if empty/bad."""
    if not value:
        return None
    try:
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    except (ValueError, TypeError):
        return None
