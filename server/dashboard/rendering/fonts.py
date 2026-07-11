"""Font set used by the renderer."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import ImageFont

from ..config import Settings


@dataclass(frozen=True)
class FontSet:
    """The fonts every section draws with, loaded once per renderer."""

    xxl: ImageFont.FreeTypeFont  # 56 px bold — header temperature
    xl: ImageFont.FreeTypeFont  # 44 px bold — header day name
    lg: ImageFont.FreeTypeFont  # 28 px       — dates, section bars
    md: ImageFont.FreeTypeFont  # 20 px bold  — event times, day headers
    rg: ImageFont.FreeTypeFont  # 20 px       — event titles
    sm: ImageFont.FreeTypeFont  # 18 px       — section labels
    xs: ImageFont.FreeTypeFont  # 15 px       — footer

    @classmethod
    def load(cls, settings: Settings) -> "FontSet":
        """Load the DejaVu faces, falling back to Pillow's bitmap font."""
        bold = settings.font_bold_path
        regular = settings.font_regular_path
        try:
            return cls(
                xxl=ImageFont.truetype(bold, 56),
                xl=ImageFont.truetype(bold, 44),
                lg=ImageFont.truetype(regular, 28),
                md=ImageFont.truetype(bold, 20),
                rg=ImageFont.truetype(regular, 20),
                sm=ImageFont.truetype(regular, 18),
                xs=ImageFont.truetype(regular, 15),
            )
        except OSError:
            fallback = ImageFont.load_default()
            return cls(
                xxl=fallback,
                xl=fallback,
                lg=fallback,
                md=fallback,
                rg=fallback,
                sm=fallback,
                xs=fallback,
            )
