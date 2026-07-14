"""Multi-day outlook: a row of daily cells below the meteogram.

Each cell shows a weekday, a weather icon, and the day's high (red) / low
(black) temperature, giving a "rest of the week" glance the hourly graph above
cannot fit.
"""

from __future__ import annotations

from ...models import DailyForecastPoint
from .. import l10n
from ..canvas import Canvas
from ..primitives import text_size
from ..theme import (
    BLACK,
    DAILY_H,
    DAILY_Y,
    PAD,
    RED,
    W_PORTRAIT,
)

_ICON_SIZE = 22


def draw(canvas: Canvas, daily: list[DailyForecastPoint]) -> None:
    if not daily:
        return

    d, fonts = canvas.draw, canvas.fonts
    n = len(daily)
    span = W_PORTRAIT - 2 * PAD
    cell_w = span / n

    # Section label, matching PŘEDPOVĚĎ / HISTORIE 24H / KALENDÁŘ; the label and
    # whitespace are the delimiter from the meteogram above.
    d.text((PAD, DAILY_Y + 2), "VÝHLED", fill=BLACK, font=fonts.sm)

    label_y = DAILY_Y + 24
    icon_y = DAILY_Y + 38
    temp_y = DAILY_Y + DAILY_H - 14

    for i, day in enumerate(daily):
        cx = PAD + cell_w * (i + 0.5)

        # Weekday label
        label = l10n.DAYS_SHORT[day.day.weekday()]
        lw, _ = text_size(d, label, fonts.xs)
        d.text((cx - lw / 2, label_y), label, fill=BLACK, font=fonts.xs)

        # Weather icon
        if day.icon:
            img = canvas.icons.get(day.icon, _ICON_SIZE, BLACK)
            canvas.image.paste(img, (int(cx - _ICON_SIZE / 2), icon_y), img)

        # High (red) / low (black), centred as one group
        hi = f"{round(day.temp_max_c)}°"
        lo = f"{round(day.temp_min_c)}°"
        sep = "/"
        parts = [(hi, RED), (sep, BLACK), (lo, BLACK)]
        widths = [text_size(d, text, fonts.xs)[0] for text, _ in parts]
        x = cx - sum(widths) / 2
        for (text, color), w in zip(parts, widths):
            d.text((x, temp_y), text, fill=color, font=fonts.xs)
            x += w
