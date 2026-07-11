"""Application service: ties the data, rendering and encoding layers together.

This is the single place that knows the full pipeline (fetch → render → pack) and the wake-up policy, keeping the HTTP layer thin.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PIL import Image

from .config import Settings
from .data import DataSource
from .encoding import pack_frame
from .rendering import Renderer
from .wakeup import next_wakeup


@dataclass(frozen=True)
class Frame:
    """A packed frame plus the epoch second the firmware should next wake."""

    payload: bytes
    next_wakeup: int


class DashboardService:
    """Produces rendered images and packed frames on demand."""

    def __init__(
        self,
        settings: Settings,
        source: DataSource,
        renderer: Renderer,
    ) -> None:
        self._settings = settings
        self._source = source
        self._renderer = renderer

    def render_image(self, now: datetime | None = None) -> Image.Image:
        """Render the current dashboard as a portrait design image."""
        data = self._source.fetch(now or datetime.now())
        return self._renderer.render(data)

    def build_frame(self, now: datetime | None = None) -> Frame:
        """Render and pack a frame, and compute the next wake-up time."""
        now = (now or datetime.now()).astimezone()
        image = self.render_image(now)
        payload = pack_frame(image, self._settings.panel)
        return Frame(
            payload=payload,
            next_wakeup=next_wakeup(now, self._settings),
        )
