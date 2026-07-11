"""The drawing context passed to each section."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from .fonts import FontSet
from .icons import IconSet


@dataclass(frozen=True)
class Canvas:
    """Everything a section needs to draw onto the shared portrait image."""

    image: Image.Image  # the RGB frame being composed
    draw: ImageDraw.ImageDraw  # bound to ``image``
    fonts: FontSet
    icons: IconSet
