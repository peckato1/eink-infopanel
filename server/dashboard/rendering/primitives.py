"""Low-level drawing helpers shared across sections."""

from __future__ import annotations

import math

from PIL import ImageDraw, ImageFont

from .theme import BLACK


def text_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
) -> tuple[int, int]:
    """Return the (width, height) of ``text`` rendered in ``font``."""
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def dashed_h(
    draw: ImageDraw.ImageDraw,
    x0: int,
    x1: int,
    y: int,
    dash: int = 8,
    gap: int = 6,
    fill=BLACK,
    width: int = 1,
) -> None:
    """Draw a dashed horizontal line from ``x0`` to ``x1``."""
    x = x0
    while x < x1:
        draw.line([(x, y), (min(x + dash, x1), y)], fill=fill, width=width)
        x += dash + gap


def dashed_v(
    draw: ImageDraw.ImageDraw,
    x: int,
    y0: int,
    y1: int,
    dash: int = 8,
    gap: int = 6,
    fill=BLACK,
    width: int = 1,
) -> None:
    """Draw a dashed vertical line from ``y0`` to ``y1``."""
    y = y0
    while y < y1:
        draw.line([(x, y), (x, min(y + dash, y1))], fill=fill, width=width)
        y += dash + gap


def wind_arrow(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    dir_from_deg: float,
    size: int = 12,
    fill=BLACK,
) -> None:
    """Draw a small arrow flying downwind (points where the wind blows TO)."""
    brg = math.radians((dir_from_deg + 180) % 360)  # downwind bearing
    dx, dy = math.sin(brg), -math.cos(brg)  # screen unit vector
    half = size / 2
    hx, hy = cx + dx * half, cy + dy * half  # head
    tx, ty = cx - dx * half, cy - dy * half  # tail
    draw.line([(tx, ty), (hx, hy)], fill=fill, width=1)
    ah = size * 0.42
    for phi in (math.radians(150), math.radians(-150)):
        c, s = math.cos(phi), math.sin(phi)
        bx, by = dx * c - dy * s, dx * s + dy * c  # travel vector rotated back
        draw.line([(hx, hy), (hx + bx * ah, hy + by * ah)], fill=fill, width=1)
