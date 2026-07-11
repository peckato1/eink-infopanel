"""Weather and UI icons (Lucide, ISC — pre-rasterized black-on-transparent)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ICON_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "icons"

# Weather condition (lowercased) → Lucide icon name.
_CONDITION_ICONS = {
    "clear": "sun",
    "sunny": "sun",
    "partly cloudy": "cloud-sun",
    "cloudy": "cloudy",
    "overcast": "cloud",
    "fog": "cloud-fog",
    "mist": "cloud-fog",
    "drizzle": "cloud-drizzle",
    "rain": "cloud-rain",
    "showers": "cloud-rain-wind",
    "snow": "cloud-snow",
    "sleet": "cloud-hail",
    "thunderstorm": "cloud-lightning",
    "windy": "wind",
}
_FALLBACK_ICON = "cloud-sun"


class IconSet:
    """Loads, caches and tints Lucide icon masters on demand."""

    def __init__(self, icon_dir: Path = ICON_DIR) -> None:
        self._dir = icon_dir
        self._masters: dict[str, Image.Image] = {}

    def get(
        self,
        name: str,
        size: int,
        color: tuple[int, int, int],
        rotate: float = 0.0,
    ) -> Image.Image:
        """Return the named icon scaled to ``size`` px and tinted to ``color``.

        ``rotate`` turns the icon counter-clockwise by that many degrees (used to
        point a direction arrow); the master stays within its box, so no clip.
        """
        master = self._masters.get(name)
        if master is None:
            master = Image.open(self._dir / f"{name}.png").convert("RGBA")
            self._masters[name] = master
        if rotate:
            master = master.rotate(rotate, resample=Image.BICUBIC, expand=False)
        scaled = master.resize((size, size), Image.LANCZOS)
        solid = Image.new("RGBA", scaled.size, (*color, 0))
        solid.putalpha(scaled.getchannel("A"))
        return solid

    @staticmethod
    def for_condition(condition: str) -> str:
        """Map a weather condition string to a Lucide icon name."""
        return _CONDITION_ICONS.get(condition.strip().lower(), _FALLBACK_ICON)
