"""Rendering layer: turns :class:`~dashboard.models.DashboardData` into a portrait design image.

The :class:`Renderer` loads fonts and the icon cache once and is reused across requests.
Sections are composed onto a single shared :class:`Canvas`.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from ..config import Settings
from ..models import DashboardData
from . import sections
from .canvas import Canvas
from .fonts import FontSet
from .icons import IconSet
from .theme import BLACK, DIVIDER_H, DIVIDER_Y, H_PORTRAIT, W_PORTRAIT, WHITE

__all__ = ["Renderer"]


class Renderer:
    """Draws the dashboard onto a 640×960 portrait canvas."""

    def __init__(self, settings: Settings) -> None:
        self._fonts = FontSet.load(settings)
        self._icons = IconSet()

    def render(self, data: DashboardData) -> Image.Image:
        image = Image.new("RGB", (W_PORTRAIT, H_PORTRAIT), WHITE)
        draw = ImageDraw.Draw(image)
        # Draw text without anti-aliasing: the 3-color panel is bilevel per
        # channel, so grid-aligned glyphs stay crisp instead of getting frayed
        # when the anti-aliased grays are thresholded during packing.
        draw.fontmode = "1"

        canvas = Canvas(image=image, draw=draw, fonts=self._fonts, icons=self._icons)

        # Divider between forecast and calendar
        draw.rectangle(
            [0, DIVIDER_Y, W_PORTRAIT - 1, DIVIDER_Y + DIVIDER_H - 1], fill=BLACK
        )

        sections.header.draw(canvas, data.weather, data.now)
        sections.forecast.draw(canvas, data.forecast)
        sections.summary.draw(canvas, data.recent)
        sections.calendar.draw(canvas, data.events, data.now)
        sections.footer.draw(canvas, data.now)

        return image
