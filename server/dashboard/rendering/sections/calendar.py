"""Calendar section: 'KALENDÁŘ' label + upcoming events grouped by day.

Days are listed continuously from today up to the last event, so a day with
nothing on it shows as a slim "volno" row. That makes an empty today/tomorrow
obvious at a glance instead of silently jumping to the first busy day.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ...models import CalendarEvent
from .. import l10n
from ..canvas import Canvas
from ..primitives import text_size
from ..theme import (
    BLACK,
    CALENDAR_Y,
    DAY_HEADER_H,
    EVENT_H,
    EVENTS_Y,
    FOOTER_Y,
    PAD,
    RED,
    VOLNO_H,
    W_PORTRAIT,
    WHITE,
)

# Column geometry shared by every event row.
BADGE_SIZE = 20  # px — filled square with calendar letter
BADGE_X = PAD + 72  # right of time column (time ~70 px wide at 22 pt)
SEP_X = BADGE_X + BADGE_SIZE + 10  # 122
TITLE_X = SEP_X + 12  # 134


def draw(canvas: Canvas, events: list[CalendarEvent], now: datetime) -> None:
    d, fonts = canvas.draw, canvas.fonts
    today = now.date()

    # Section label (matches "PŘEDPOVĚĎ"; the date is already in the header)
    d.text((PAD, CALENDAR_Y + 8), "KALENDÁŘ", fill=BLACK, font=fonts.sm)

    if not events:
        _draw_empty(canvas)
        return

    # Upcoming first: by day, all-day before timed, then by time.
    events = sorted(events, key=lambda e: (e.date, 0 if e.all_day else 1, e.time))
    by_day: dict[date, list[CalendarEvent]] = {}
    for event in events:
        by_day.setdefault(event.date, []).append(event)

    # Walk every day from today to the last event so empty days are visible.
    y = EVENTS_Y
    day = min(today, min(by_day))
    last_day = max(by_day)
    while day <= last_day:
        day_events = by_day.get(day)
        if day_events:
            # Need room for the header plus at least its first event row.
            if y + DAY_HEADER_H + EVENT_H > FOOTER_Y:
                break
            y = _draw_day_header(canvas, day, today, y)
            for event in day_events:
                if y + EVENT_H > FOOTER_Y:
                    return
                _draw_event(canvas, event, y)
                y += EVENT_H
        else:
            # Empty day → slim "volno" row (header plus the muted marker).
            if y + DAY_HEADER_H + VOLNO_H > FOOTER_Y:
                break
            y = _draw_day_header(canvas, day, today, y)
            d.text(
                (TITLE_X, y + VOLNO_H // 2),
                "volno",
                fill=BLACK,
                font=fonts.sm,
                anchor="lm",
            )
            y += VOLNO_H
        day += timedelta(days=1)


def _draw_day_header(canvas: Canvas, day: date, today: date, y: int) -> int:
    """Draw a day's bold label with a trailing rule; return the next y."""
    d, fonts = canvas.draw, canvas.fonts
    hy = y + DAY_HEADER_H // 2
    label = l10n.day_label(day, today)
    d.text((PAD, hy), label, fill=BLACK, font=fonts.md, anchor="lm")
    lw, _ = text_size(d, label, fonts.md)
    d.line([(PAD + lw + 10, hy), (W_PORTRAIT - PAD, hy)], fill=BLACK, width=1)
    return y + DAY_HEADER_H


def _draw_event(canvas: Canvas, event: CalendarEvent, y: int) -> None:
    d, fonts = canvas.draw, canvas.fonts
    cy = y + EVENT_H // 2  # shared vertical center for the whole row

    # Time column: clock for timed events, a red accent bar for all-day.
    if event.all_day:
        d.rectangle(
            [PAD, cy - EVENT_H // 2 + 6, PAD + 5, cy + EVENT_H // 2 - 6],
            fill=RED,
        )
    else:
        d.text((PAD, cy), event.time, fill=RED, font=fonts.md, anchor="lm")

    if event.calendar:
        _draw_badge(canvas, event.calendar, BADGE_X, cy, BADGE_SIZE)
    d.line(
        [(SEP_X, cy - EVENT_H // 2 + 6), (SEP_X, cy + EVENT_H // 2 - 6)],
        fill=BLACK,
        width=1,
    )
    d.text((TITLE_X, cy), event.title, fill=BLACK, font=fonts.rg, anchor="lm")


def _draw_badge(canvas: Canvas, letter: str, x: int, cy: int, size: int) -> None:
    """Filled rounded square with a centered white calendar letter."""
    d, fonts = canvas.draw, canvas.fonts
    by0 = cy - size // 2
    d.rounded_rectangle([x, by0, x + size, by0 + size], radius=3, fill=BLACK)
    d.text((x + size / 2, cy), letter, fill=WHITE, font=fonts.xs, anchor="mm")


def _draw_empty(canvas: Canvas) -> None:
    d, fonts = canvas.draw, canvas.fonts
    msg = "Žádné nadcházející události"
    mw, mh = text_size(d, msg, fonts.lg)
    d.text(
        ((W_PORTRAIT - mw) // 2, EVENTS_Y + (FOOTER_Y - EVENTS_Y - mh) // 2),
        msg,
        fill=BLACK,
        font=fonts.lg,
    )
