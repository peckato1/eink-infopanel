"""Telemetry sink: forward device health reports to VictoriaMetrics.

The firmware POSTs a small JSON report on every wake-up (RSSI, free heap, battery voltage, whether the frame rendered, and why it woke).
This module turns those into VictoriaMetrics gauges so the panel can be monitored and alerted on (low battery, weak signal, a device that stopped checking in).

Ingestion uses VictoriaMetrics' ``/api/v1/import/prometheus`` endpoint, which accepts plain Prometheus text-exposition lines — no extra dependency, and the same URL/basic-auth shape as the weather query source.
Everything here is best-effort: a push failure is logged, never raised, so telemetry can never take the request (or the device's sleep cycle) down.
"""

from __future__ import annotations

import logging
import time
from typing import Mapping, Protocol

import requests

from .config import TelemetryConfig

log = logging.getLogger(__name__)

_PUSH_TIMEOUT_S = 5
_USER_AGENT = "esp-epaper-dashboard/1.0 (+telemetry)"

#: Numeric report fields → exported gauge name. Missing fields are skipped.
_GAUGES = (
    ("rssi", "esp_rssi_dbm"),
    ("heap", "esp_free_heap_bytes"),
    ("vbat", "esp_battery_volts"),
    ("sleep", "esp_sleep_interval_seconds"),
    ("retries", "esp_fetch_retries"),
)


class TelemetrySink(Protocol):
    """Consumes one device telemetry report."""

    def record(self, report: Mapping[str, object]) -> None:
        """Handle a single telemetry report (best-effort; must not raise)."""
        ...


class LoggingTelemetrySink:
    """The default sink: just logs the report (no forwarding configured)."""

    def record(self, report: Mapping[str, object]) -> None:
        log.info("telemetry: %s", dict(report))


class VictoriaMetricsTelemetrySink:
    """Forwards telemetry to VictoriaMetrics, and logs it too."""

    def __init__(self, config: TelemetryConfig) -> None:
        self._config = config
        self._session = requests.Session()

    def record(self, report: Mapping[str, object]) -> None:
        log.info("telemetry: %s", dict(report))
        device = str(report.get("device") or self._config.device)
        body = render_prometheus(report, device, now=time.time())
        if not body:
            return
        try:
            resp = self._session.post(
                f"{self._config.url.rstrip('/')}/api/v1/import/prometheus",
                data=body.encode("utf-8"),
                headers={
                    "User-Agent": _USER_AGENT,
                    "Content-Type": "text/plain",
                },
                auth=self._auth(),
                timeout=_PUSH_TIMEOUT_S,
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — telemetry must never break the request
            log.warning("telemetry push to VictoriaMetrics failed: %s", exc)

    def _auth(self) -> tuple[str, str] | None:
        if self._config.username:
            return self._config.username, self._config.password
        return None


def sink_for(config: TelemetryConfig | None) -> TelemetrySink:
    """Return the telemetry sink for ``config`` (a logging no-op if unset)."""
    if config is None:
        return LoggingTelemetrySink()
    return VictoriaMetricsTelemetrySink(config)


def render_prometheus(report: Mapping[str, object], device: str, *, now: float) -> str:
    """Render a telemetry report as Prometheus text-exposition lines.

    ``device`` labels every series; ``now`` (epoch seconds) is exported as ``esp_last_seen_seconds`` so a stale device is easy to alert on.
    Returns an empty string if the report carries nothing numeric worth exporting.
    """
    device_label = f'device="{_escape(device)}"'
    lines: list[str] = []

    for field, metric in _GAUGES:
        value = _as_float(report.get(field))
        if value is not None:
            lines.append(f"{metric}{{{device_label}}} {value:g}")

    if "render_ok" in report:
        lines.append(
            f"esp_render_ok{{{device_label}}} {1 if report['render_ok'] else 0}"
        )

    wake = report.get("wake")
    if wake is not None:
        lines.append(f'esp_wake_info{{{device_label},reason="{_escape(str(wake))}"}} 1')

    if not lines:
        return ""

    lines.append(f"esp_last_seen_seconds{{{device_label}}} {now:.0f}")
    return "\n".join(lines) + "\n"


def _as_float(value: object) -> float | None:
    """Coerce a JSON scalar to float, or ``None`` if it isn't numeric."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _escape(value: str) -> str:
    """Escape a Prometheus label value (backslash, quote, newline)."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
