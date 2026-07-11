"""HTTP API — the endpoints the firmware and developers talk to.

Kept deliberately thin: each route delegates to the :class:`DashboardService` registered on the app.
"""

from __future__ import annotations

import io

from flask import Blueprint, Response, current_app, jsonify, request

from .service import DashboardService
from .telemetry import TelemetrySink

bp = Blueprint("api", __name__, url_prefix="/api/v1")


def _service() -> DashboardService:
    return current_app.extensions["dashboard"]


def _telemetry() -> TelemetrySink:
    return current_app.extensions["telemetry"]


@bp.get("/image.bin")
def image_bin() -> Response:
    """Packed frame for the firmware, with the next wake-up hint."""
    frame = _service().build_frame()
    return Response(
        frame.payload,
        status=200,
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(frame.payload)),
            "X-Next-Wakeup": str(frame.next_wakeup),
        },
    )


@bp.get("/preview")
def preview() -> Response:
    """Human-friendly PNG of the current design, for development."""
    image = _service().render_image()
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf, status=200, headers={"Content-Type": "image/png"})


@bp.post("/telemetry")
def telemetry() -> Response:
    """Best-effort device telemetry sink (RSSI, heap, battery, …).

    Forwarded to VictoriaMetrics when configured; always logged.
    """
    body = request.get_json(silent=True) or {}
    _telemetry().record(body)
    return jsonify(ok=True)
