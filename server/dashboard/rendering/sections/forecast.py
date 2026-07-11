"""Meteogram: temperature (red, left °C axis) and wind (black, right m/s axis)
over labelled precipitation bars."""

from __future__ import annotations

import math
from datetime import timedelta

from ...data.chmi import icon_to_lucide
from ...models import ForecastPoint
from .. import l10n
from ..canvas import Canvas
from ..primitives import dashed_h, text_size, wind_arrow
from ..theme import (
    BLACK,
    FORECAST_H,
    FORECAST_Y,
    PAD,
    RED,
    W_PORTRAIT,
)


def draw(canvas: Canvas, forecast: list[ForecastPoint]) -> None:
    d, fonts = canvas.draw, canvas.fonts
    d.text((PAD, FORECAST_Y + 12), "PŘEDPOVĚĎ", fill=BLACK, font=fonts.sm)

    if not forecast:
        _draw_empty(canvas)
        return

    # --- Plot geometry -----------------------------------------------------
    axis_w = 30  # left gutter (°C)
    right_axis_w = 30  # right gutter (m/s)
    plot_x0 = PAD + axis_w  # 50
    plot_x1 = W_PORTRAIT - PAD - right_axis_w  # 590
    graph_top = FORECAST_Y + 40  # 140
    axis_row_h = 48  # icons (20) + gap (2) + hour labels (~12) + margin
    graph_bot = FORECAST_Y + FORECAST_H - axis_row_h  # 372
    precip_h = 56
    precip_top = graph_bot - precip_h  # 316
    temp_top = graph_top  # 140
    temp_bot = precip_top - 8  # 308

    n = len(forecast)
    span = plot_x1 - plot_x0

    def x_at(i: int) -> float:
        return plot_x0 + (span * i / (n - 1) if n > 1 else span / 2)

    # --- Temperature scale (left axis) -------------------------------------
    temps = [p.temp_c for p in forecast]
    tmin, tmax = min(temps), max(temps)
    if tmax - tmin < 1.0:  # flat series — avoid zero span
        tmin, tmax = tmin - 1.0, tmax + 1.0
    headroom = (tmax - tmin) * 0.15
    lo, hi = tmin - headroom, tmax + headroom

    def y_temp(temp: float) -> float:
        return temp_bot - (temp - lo) / (hi - lo) * (temp_bot - temp_top)

    # Gridlines at 5 °C steps + °C labels (red, to match the curve)
    step = 5
    tick = math.ceil(lo / step) * step
    while tick <= hi:
        gy = int(y_temp(tick))
        dashed_h(d, plot_x0, plot_x1, gy)
        label = f"{tick:.0f}°"
        lw, lh = text_size(d, label, fonts.xs)
        d.text((plot_x0 - 6 - lw, gy - lh // 2), label, fill=RED, font=fonts.xs)
        tick += step

    # --- Wind scale (right axis) -------------------------------------------
    winds = [p.wind_ms for p in forecast]
    has_wind = all(w is not None for w in winds)
    if has_wind:
        wmax = max(winds)
        wind_hi = max(2.0, math.ceil(wmax / 2) * 2)  # even ceiling ≥ 2

        def y_wind(w: float) -> float:
            return temp_bot - (w / wind_hi) * (temp_bot - temp_top)

        for w in (0, wind_hi / 2, wind_hi):
            gy = int(y_wind(w))
            d.line([(plot_x1, gy), (plot_x1 + 4, gy)], fill=BLACK, width=1)
            label = f"{w:.0f}"
            _, lh = text_size(d, label, fonts.xs)
            d.text((plot_x1 + 7, gy - lh // 2), label, fill=BLACK, font=fonts.xs)
        unit = "m/s"
        uw, _ = text_size(d, unit, fonts.xs)
        d.text(
            (W_PORTRAIT - PAD - uw, FORECAST_Y + 14), unit, fill=BLACK, font=fonts.xs
        )

    # --- Day separators + baseline -----------------------------------------
    for i, p in enumerate(forecast):
        if p.time.hour == 0:
            d.line([(x_at(i), temp_top), (x_at(i), graph_bot)], fill=BLACK, width=1)
    d.line([(plot_x0, graph_bot), (plot_x1, graph_bot)], fill=BLACK, width=1)

    # --- Precipitation bars ------------------------------------------------
    # Only the peak bar of each contiguous rain spell is labelled with its mm,
    # which keeps dense clusters readable.
    pmax = max((p.precip_mm for p in forecast), default=0.0)
    scale_max = max(pmax, 2.0)  # floor so light rain isn't full height
    bar_w = max(2, int(span / max(n - 1, 1) * 0.7))

    spell_peak = -1  # index of the tallest bar in the current rain spell
    for i, p in enumerate(forecast):
        if p.precip_mm > 0:
            cx = x_at(i)
            bh = (p.precip_mm / scale_max) * precip_h
            d.rectangle(
                [cx - bar_w / 2, graph_bot - bh, cx + bar_w / 2, graph_bot], fill=BLACK
            )
            if spell_peak < 0 or p.precip_mm > forecast[spell_peak].precip_mm:
                spell_peak = i
        # end of a spell (dry hour or last point) → label its peak
        is_last = i == n - 1
        if spell_peak >= 0 and (p.precip_mm <= 0 or is_last):
            peak = forecast[spell_peak]
            label = f"{peak.precip_mm:.1f}"
            lw, lh = text_size(d, label, fonts.xs)
            bh = (peak.precip_mm / scale_max) * precip_h
            d.text(
                (x_at(spell_peak) - lw / 2, graph_bot - bh - lh - 6),
                label,
                fill=BLACK,
                font=fonts.xs,
            )
            spell_peak = -1

    # --- Wind curve + direction arrows (black) -----------------------------
    if has_wind:
        wpts = [(x_at(i), y_wind(w)) for i, w in enumerate(winds)]
        if len(wpts) > 1:
            d.line(wpts, fill=BLACK, width=2, joint="curve")
        else:
            cx, cy = wpts[0]
            d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=BLACK)
        # direction arrows every 6h, sitting just above the wind curve
        for i, p in enumerate(forecast):
            if p.time.hour % 6 == 0 and p.wind_dir_deg is not None:
                wind_arrow(d, x_at(i), y_wind(winds[i]) - 9, p.wind_dir_deg)

    # --- Temperature curve (red, on top) -----------------------------------
    pts = [(x_at(i), y_temp(p.temp_c)) for i, p in enumerate(forecast)]
    if len(pts) > 1:
        d.line(pts, fill=RED, width=2, joint="curve")
    else:
        cx, cy = pts[0]
        d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=RED)

    # --- Weather icons every 6h above the time axis ------------------------
    # Icon is drawn at the 6h tick but represents the midpoint (+3h) of each
    # 6h window, which better matches what weather services show for each period.
    icon_size = 20
    icon_y = graph_bot + 4
    by_time = {p.time: p for p in forecast}
    for i, p in enumerate(forecast):
        if p.time.hour % 6 != 0:
            continue
        mid = by_time.get(p.time + timedelta(hours=3), p)
        if mid.icon_code is None:
            continue
        lucide = icon_to_lucide(mid.icon_code)
        img = canvas.icons.get(lucide, icon_size, BLACK)
        canvas.image.paste(img, (int(x_at(i)) - icon_size // 2, icon_y), img)

    # --- Time axis: day names at midnight, hour ticks otherwise ------------
    ty = graph_bot + 4 + icon_size + 2
    for i, p in enumerate(forecast):
        if p.time.hour == 0:
            label = l10n.DAYS_SHORT[p.time.weekday()]
        elif p.time.hour % 6 == 0:
            label = str(p.time.hour)
        else:
            continue
        lw, _ = text_size(d, label, fonts.xs)
        d.text((x_at(i) - lw / 2, ty), label, fill=BLACK, font=fonts.xs)


def _draw_empty(canvas: Canvas) -> None:
    d, fonts = canvas.draw, canvas.fonts
    msg = "Žádná data předpovědi"
    mw, mh = text_size(d, msg, fonts.lg)
    d.text(
        ((W_PORTRAIT - mw) // 2, FORECAST_Y + (FORECAST_H - mh) // 2),
        msg,
        fill=BLACK,
        font=fonts.lg,
    )
