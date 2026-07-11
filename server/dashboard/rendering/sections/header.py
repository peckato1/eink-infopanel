"""Header strip: day + date on the left, conditions + temperature on the right."""

from __future__ import annotations

from datetime import datetime

from ...models import WeatherNow
from .. import l10n
from ..canvas import Canvas
from ..primitives import text_size
from ..theme import BLACK, HEADER_H, PAD, W_PORTRAIT, WHITE


def _format_lux(lx: float) -> str:
    """Ambient light as a compact string: lux below 1000, klux above."""
    if lx >= 1000:
        return f"{lx / 1000:.1f} klx"
    return f"{lx:.0f} lx"


def draw(canvas: Canvas, weather: WeatherNow, now: datetime) -> None:
    image, d, fonts, icons = canvas.image, canvas.draw, canvas.fonts, canvas.icons
    d.rectangle([0, 0, W_PORTRAIT - 1, HEADER_H - 1], fill=BLACK)

    # Left: day name stacked above date, vertically centred.
    day_name = l10n.DAYS[now.weekday()].upper()
    date_str = l10n.format_date(now)
    day_w, day_h = text_size(d, day_name, fonts.xl)
    _, date_h = text_size(d, date_str, fonts.lg)
    block_h = day_h + 4 + date_h
    y0 = (HEADER_H - block_h) // 2

    d.text((PAD, y0), day_name, fill=WHITE, font=fonts.xl)
    d.text((PAD, y0 + day_h + 4), date_str, fill=WHITE, font=fonts.lg)

    x_right = W_PORTRAIT - PAD
    # Right cluster: big temperature over the small readings, flush right.
    temp_cy, readings_cy = 42, 84

    # Condition icon + temperature.
    temp_str = f"{weather.temp_c:.0f}°C"
    temp_w, _ = text_size(d, temp_str, fonts.xxl)
    cond_size = 48
    gap = 14
    widget_x = x_right - (cond_size + gap + temp_w)
    cond = icons.get(icons.for_condition(weather.condition), cond_size, WHITE)
    image.paste(cond, (widget_x, temp_cy - cond_size // 2), cond)
    d.text(
        (widget_x + cond_size + gap, temp_cy),
        temp_str,
        fill=WHITE,
        font=fonts.xxl,
        anchor="lm",
    )

    # Humidity / wind / light, icon + value each, right-aligned under the temp.
    ic, ig, sep = 18, 4, 14
    # The wind icon is an up-arrow rotated to point where the wind blows *to*
    # (meteo. direction is where it blows *from*, hence +180). PIL rotates
    # counter-clockwise but compass bearings run clockwise, hence the negation.
    wind_rot = -((weather.wind_dir_deg + 180) % 360)
    wind_val = (
        f"{weather.wind_ms * 3.6:.0f} / {weather.wind_gust_ms * 3.6:.0f} km/h"
        if weather.wind_gust_ms is not None
        else f"{weather.wind_ms * 3.6:.0f} km/h"
    )
    segments = (
        ("droplet", f"{weather.humidity_pct:.0f}%", 0.0),
        ("arrow-up", wind_val, wind_rot),
        ("sun-medium", _format_lux(weather.illuminance_lx), 0.0),
    )
    seg_w = [ic + ig + text_size(d, val, fonts.sm)[0] for _, val, _ in segments]
    x = x_right - (sum(seg_w) + sep * (len(segments) - 1))
    for (name, val, rot), w in zip(segments, seg_w):
        icon = icons.get(name, ic, WHITE, rotate=rot)
        image.paste(icon, (x, readings_cy - ic // 2), icon)
        d.text((x + ic + ig, readings_cy), val, fill=WHITE, font=fonts.sm, anchor="lm")
        x += w + sep

    # Sunrise + sunset on one line at the very top, centred in the gap between
    # the day name and the temperature. Kept compact (small icons, xs text) so it
    # still clears the widest day name, "PONDĚLÍ".
    sun_size, sun_gap, pair_gap = 16, 5, 14
    sun_cy = 15
    sun_pairs = (("sunrise", weather.sunrise), ("sunset", weather.sunset))
    pair_w = [sun_size + sun_gap + text_size(d, t, fonts.xs)[0] for _, t in sun_pairs]
    sun_w = sum(pair_w) + pair_gap * (len(sun_pairs) - 1)
    corridor_l, corridor_r = PAD + day_w, widget_x
    x = corridor_l + (corridor_r - corridor_l - sun_w) // 2
    for (icon_name, time_str), w in zip(sun_pairs, pair_w):
        icon = icons.get(icon_name, sun_size, WHITE)
        image.paste(icon, (x, sun_cy - sun_size // 2), icon)
        d.text(
            (x + sun_size + sun_gap, sun_cy),
            time_str,
            fill=WHITE,
            font=fonts.xs,
            anchor="lm",
        )
        x += w + pair_gap
