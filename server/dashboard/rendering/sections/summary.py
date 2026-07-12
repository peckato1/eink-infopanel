"""Stats strip below the meteogram: last-24h min/max temperature and rainfall."""

from __future__ import annotations

from ...models import WeatherRecent
from ..canvas import Canvas
from ..primitives import text_size
from ..theme import BLACK, PAD, RED, SUMMARY_H, SUMMARY_Y, W_PORTRAIT


def draw(canvas: Canvas, recent: WeatherRecent) -> None:
    d, fonts = canvas.draw, canvas.fonts
    d.text((PAD, SUMMARY_Y + 8), "HISTORIE 24H", fill=BLACK, font=fonts.sm)
    cy = SUMMARY_Y + SUMMARY_H - 14  # stats baseline in lower half

    groups = [
        ("min", f"{recent.temp_min_c:.1f} °C", RED),
        ("max", f"{recent.temp_max_c:.1f} °C", RED),
        ("srážky", f"{recent.precip_mm:.1f} mm", BLACK),
    ]
    label_font, value_font = fonts.xs, fonts.sm
    inner_gap, group_gap = 6, 20

    segments = []
    for i, (label, value, color) in enumerate(groups):
        segments.append((label, label_font, BLACK, inner_gap))
        trailing = group_gap if i < len(groups) - 1 else 0
        segments.append((value, value_font, color, trailing))

    widths = [text_size(d, text, font)[0] for text, font, _, _ in segments]
    content_w = sum(widths) + sum(gap for *_, gap in segments)

    x = (W_PORTRAIT - content_w) // 2
    for (text, font, color, gap), w in zip(segments, widths):
        d.text((x, cy), text, fill=color, font=font, anchor="lm")
        x += w + gap
