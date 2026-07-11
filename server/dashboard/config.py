"""Application configuration.

All tunables live here as typed settings loaded from ``config.toml`` so the
rest of the package never reaches for ``os.environ`` or hardcodes magic numbers.
The only environment variable is ``DASHBOARD_CONFIG``, which locates the config
file itself (a path that, by nature, cannot live inside the file).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

#: Directory containing the ``server`` package — the base for relative paths.
_SERVER_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class PanelSpec:
    """Geometry of the GDEY116Z91 e-paper panel.

    The controller is native landscape (``native_w`` × ``native_h``) but the panel is mounted portrait, so the dashboard is drawn on a portrait canvas (``design_w`` × ``design_h``) and rotated into the native orientation before it is packed.
    See ``docs/frame-format.md`` for the full wire format.
    """

    native_w: int = 960
    native_h: int = 640
    strip_h: int = 80

    @property
    def design_w(self) -> int:
        """Width of the portrait design canvas (native height)."""
        return self.native_h

    @property
    def design_h(self) -> int:
        """Height of the portrait design canvas (native width)."""
        return self.native_w

    @property
    def stride(self) -> int:
        """Bytes per 1bpp plane row (8 pixels per byte)."""
        return self.native_w // 8

    @property
    def frame_bytes(self) -> int:
        """Total size of a packed frame: black + red plane over all strips."""
        return 2 * self.stride * self.native_h


@dataclass(frozen=True)
class CalendarConfig:
    """One iCalendar (ICS) feed and the badge it maps to.

    ``label`` is the single character drawn in the calendar badge (e.g. ``"W"`` for work, ``"P"`` for personal); empty means no badge.
    """

    url: str
    label: str = ""


@dataclass(frozen=True)
class CaldavCalendar:
    """A named calendar within a CalDAV account and the badge it maps to.

    ``name`` matches the calendar's display name on the server; ``label`` is the single-character badge (empty means no badge).
    """

    name: str
    label: str = ""


@dataclass(frozen=True)
class CaldavConfig:
    """A read-only CalDAV account (e.g. Fastmail) to pull events from.

    Credentials are secret, so this comes from ``config.toml``.
    When ``calendars`` is empty every calendar on the account is included with no badge; otherwise only the listed names are, each with its label.
    """

    url: str
    username: str
    password: str
    calendars: tuple[CaldavCalendar, ...] = ()


@dataclass(frozen=True)
class TelemetryConfig:
    """Where to forward device telemetry (``/api/v1/telemetry`` POSTs).

    The firmware reports RSSI, free heap, battery voltage, render outcome and wake reason on every wake-up; when this section is present they are pushed to a VictoriaMetrics instance as gauges so the device can be monitored/alerted on.
    Typically the same instance as ``[victoriametrics]``, but kept separate so the write target and credentials are explicit.
    Omit to only log them.

    ``device`` is the value of the ``device`` label on every exported series (a ``"device"`` field in the POST body overrides it, for multiple panels).
    """

    url: str
    username: str = ""
    password: str = ""
    device: str = "dashboard"


@dataclass(frozen=True)
class LocationConfig:
    """Geographic location of the panel, for computing sunrise/sunset locally.

    Sunrise and sunset depend only on the date and a fixed latitude/longitude, so they're computed on-device rather than fetched.
    Not secret, but lives in ``config.toml`` as it's deployment-specific.
    """

    latitude: float
    longitude: float


@dataclass(frozen=True)
class VictoriaMetricsConfig:
    """Connection to a VictoriaMetrics (Prometheus HTTP API) for live weather.

    ``temp_selector`` and ``rain_selector`` are MetricsQL series selectors (e.g. ``meteo_temperature_celsius`` and ``meteo_rain_m``); the source derives the current temperature and the trailing min/max temperature and total precipitation from them over ``window``.
    Full MetricsQL expressions are accepted, so ``avg(meteo_temperature_celsius)`` works for aggregating multiple stations.
    ``rain_selector`` is expected to be a rain accumulation in metres — it is converted to millimetres.

    Credentials are optional (HTTP basic auth); omit them for an unauthenticated instance.
    The URL is not necessarily secret, but it lives in ``config.toml`` alongside the rest of the deployment-specific config.
    """

    url: str
    temp_selector: str
    rain_selector: str
    window: str = "24h"
    cache_ttl_s: int = 900
    username: str = ""
    password: str = ""
    #: Optional live "now" selectors for the header readings; empty = keep the fallback source's value.
    #: Each is read in its display unit (humidity in percent, wind in m/s, direction in degrees, light in lux).
    humidity_selector: str = ""
    wind_selector: str = ""
    wind_dir_selector: str = ""
    light_selector: str = ""


@dataclass(frozen=True)
class Settings:
    """Runtime settings, with defaults suitable for local development."""

    panel: PanelSpec = field(default_factory=PanelSpec)

    #: Seconds between wake-ups during the day (the base refresh interval).
    refresh_interval_s: int = 1800

    #: Align wake-ups to the ``refresh_interval_s`` grid from local midnight (e.g. :00/:30 for 1800 s) instead of drifting by ``now + interval``.
    wake_align: bool = True

    #: Quiet-hours window as ``"HH:MM"`` local time; empty disables it.
    #: Inside the window the device sleeps until ``quiet_end`` instead of refreshing.
    quiet_start: str = ""
    quiet_end: str = ""

    #: Host/port for the built-in development server.
    host: str = "0.0.0.0"
    port: int = 8080

    #: TrueType fonts used by the renderer.
    font_bold_path: str = "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
    font_regular_path: str = "/usr/share/fonts/TTF/DejaVuSans.ttf"

    #: ICS calendar feeds to merge into the events list.
    #: Secret URLs, so these come from ``config.toml`` rather than defaults.
    calendars: tuple[CalendarConfig, ...] = ()

    #: Read-only CalDAV accounts to merge events from, if configured.
    caldavs: tuple[CaldavConfig, ...] = ()

    #: VictoriaMetrics source for live weather, if configured.
    victoriametrics: VictoriaMetricsConfig | None = None

    #: Where to forward device telemetry, if configured (else it's only logged).
    telemetry: TelemetryConfig | None = None

    #: Panel location for computing sunrise/sunset, if configured.
    location: LocationConfig | None = None

    #: How far ahead to expand calendar events (including recurrences).
    calendar_window_days: int = 7

    #: How long a fetched calendar feed is reused before re-fetching.
    calendar_cache_ttl_s: int = 900

    #: Root logging level. ``DEBUG`` traces which CalDAV calendars matched.
    log_level: str = "INFO"

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> "Settings":
        """Build settings from ``config.toml``.

        The config file path defaults to ``config.toml`` next to the ``server`` package; pass ``path`` or set ``DASHBOARD_CONFIG`` to override it.
        A missing file is fine — the app just runs with development defaults and no live calendars.
        """
        defaults = cls()

        if path is None:
            path = os.environ.get("DASHBOARD_CONFIG", _SERVER_DIR / "config.toml")
        path = Path(path)
        if not path.is_absolute():
            path = _SERVER_DIR / path
        if not path.exists():
            return defaults

        with path.open("rb") as fh:
            data = tomllib.load(fh)

        calendars = tuple(
            CalendarConfig(url=entry["url"], label=entry.get("label", ""))
            for entry in data.get("calendars", [])
        )
        caldavs = _parse_caldavs(data.get("caldav"))
        victoriametrics = _parse_victoriametrics(data.get("victoriametrics"))
        telemetry = _parse_telemetry(data.get("telemetry"))
        location = _parse_location(data.get("location"))
        cal = data.get("calendar", {})
        wake = data.get("wake", {})
        server = data.get("server", {})
        logging_cfg = data.get("logging", {})
        return replace(
            defaults,
            calendars=calendars,
            caldavs=caldavs,
            victoriametrics=victoriametrics,
            telemetry=telemetry,
            location=location,
            calendar_window_days=cal.get("window_days", defaults.calendar_window_days),
            calendar_cache_ttl_s=cal.get("cache_ttl_s", defaults.calendar_cache_ttl_s),
            refresh_interval_s=wake.get("interval_s", defaults.refresh_interval_s),
            wake_align=wake.get("align", defaults.wake_align),
            quiet_start=wake.get("quiet_start", defaults.quiet_start),
            quiet_end=wake.get("quiet_end", defaults.quiet_end),
            host=server.get("host", defaults.host),
            port=int(server.get("port", defaults.port)),
            font_bold_path=server.get("font_bold", defaults.font_bold_path),
            font_regular_path=server.get("font_regular", defaults.font_regular_path),
            log_level=logging_cfg.get("level", defaults.log_level),
        )


def _parse_caldavs(
    raw: Mapping[str, object] | list[Mapping[str, object]] | None,
) -> tuple[CaldavConfig, ...]:
    """Build CalDAV accounts from the ``caldav`` config entry.

    Accepts either a single ``[caldav]`` table or a ``[[caldav]]`` array of tables, so several accounts can be merged (and old single-table configs keep working).
    """
    if not raw:
        return ()
    tables = raw if isinstance(raw, list) else [raw]
    return tuple(_parse_caldav(table) for table in tables)


def _parse_caldav(table: Mapping[str, object]) -> CaldavConfig:
    """Build one :class:`CaldavConfig` from a single ``caldav`` table."""
    calendars = tuple(
        CaldavCalendar(name=entry["name"], label=entry.get("label", ""))
        for entry in table.get("calendars", [])
    )
    return CaldavConfig(
        url=table["url"],
        username=table["username"],
        password=table["password"],
        calendars=calendars,
    )


def _parse_telemetry(
    raw: Mapping[str, object] | None,
) -> TelemetryConfig | None:
    """Build the telemetry forwarding config from the ``telemetry`` table.

    Returns ``None`` when the section is absent, so telemetry is only logged.
    """
    if not raw:
        return None
    defaults = TelemetryConfig(url="")
    return TelemetryConfig(
        url=raw["url"],
        username=raw.get("username", defaults.username),
        password=raw.get("password", defaults.password),
        device=raw.get("device", defaults.device),
    )


def _parse_location(
    raw: Mapping[str, object] | None,
) -> LocationConfig | None:
    """Build the location config from the ``location`` table.

    Returns ``None`` when the section is absent, so sunrise/sunset stay at the placeholder values.
    """
    if not raw:
        return None
    return LocationConfig(
        latitude=float(raw["latitude"]),
        longitude=float(raw["longitude"]),
    )


def _parse_victoriametrics(
    raw: Mapping[str, object] | None,
) -> VictoriaMetricsConfig | None:
    """Build the VictoriaMetrics config from the ``victoriametrics`` table.

    Returns ``None`` when the section is absent, so live weather stays off and the placeholder fixture is used.
    """
    if not raw:
        return None
    defaults = VictoriaMetricsConfig(url="", temp_selector="", rain_selector="")
    return VictoriaMetricsConfig(
        url=raw["url"],
        temp_selector=raw["temp_selector"],
        rain_selector=raw["rain_selector"],
        window=raw.get("window", defaults.window),
        cache_ttl_s=raw.get("cache_ttl_s", defaults.cache_ttl_s),
        username=raw.get("username", defaults.username),
        password=raw.get("password", defaults.password),
        humidity_selector=raw.get("humidity_selector", defaults.humidity_selector),
        wind_selector=raw.get("wind_selector", defaults.wind_selector),
        wind_dir_selector=raw.get("wind_dir_selector", defaults.wind_dir_selector),
        light_selector=raw.get("light_selector", defaults.light_selector),
    )
