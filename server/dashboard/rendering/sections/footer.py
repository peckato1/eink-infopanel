"""Footer with the last-updated timestamp."""

from __future__ import annotations

from datetime import datetime

from ..canvas import Canvas
from ..primitives import text_size
from ..theme import BLACK, FOOTER_H, FOOTER_Y, W_PORTRAIT


def draw(canvas: Canvas, updated_at: datetime) -> None:
    d, fonts = canvas.draw, canvas.fonts
    d.line([(0, FOOTER_Y), (W_PORTRAIT, FOOTER_Y)], fill=BLACK, width=1)

    text = f"Aktualizováno: {updated_at.strftime('%d. %m. %Y %H:%M')}"
    tw, th = text_size(d, text, fonts.xs)
    d.text(
        ((W_PORTRAIT - tw) // 2, FOOTER_Y + (FOOTER_H - th) // 2),
        text,
        fill=BLACK,
        font=fonts.xs,
    )
