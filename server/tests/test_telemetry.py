"""Tests for telemetry forwarding (:mod:`dashboard.telemetry`).

Runnable under pytest or directly (``python tests/test_telemetry.py``).
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.serving import make_server  # noqa: E402
from werkzeug.wrappers import Request, Response  # noqa: E402

from dashboard.config import TelemetryConfig  # noqa: E402
from dashboard.telemetry import (  # noqa: E402
    LoggingTelemetrySink,
    VictoriaMetricsTelemetrySink,
    render_prometheus,
    sink_for,
)

SAMPLE = {
    "rssi": -71,
    "heap": 110328,
    "render_ok": True,
    "wake": "timer",
    "vbat": 3.94,
    "sleep": 1800,
    "retries": 2,
}


def test_render_covers_all_fields():
    text = render_prometheus(SAMPLE, "panel", now=1783692000.0)
    lines = set(text.strip().splitlines())
    assert 'esp_rssi_dbm{device="panel"} -71' in lines
    assert 'esp_free_heap_bytes{device="panel"} 110328' in lines
    assert 'esp_battery_volts{device="panel"} 3.94' in lines
    assert 'esp_sleep_interval_seconds{device="panel"} 1800' in lines
    assert 'esp_fetch_retries{device="panel"} 2' in lines
    assert 'esp_render_ok{device="panel"} 1' in lines
    assert 'esp_wake_info{device="panel",reason="timer"} 1' in lines
    assert 'esp_last_seen_seconds{device="panel"} 1783692000' in lines


def test_render_ok_false_and_missing_battery():
    text = render_prometheus(
        {"rssi": -80, "heap": 90000, "render_ok": False, "wake": "poweron"},
        "panel",
        now=1.0,
    )
    assert 'esp_render_ok{device="panel"} 0' in text
    assert "esp_battery_volts" not in text  # absent field is skipped


def test_render_escapes_labels():
    text = render_prometheus({"wake": 'a"b\\c'}, 'de"vice', now=1.0)
    assert 'device="de\\"vice"' in text
    assert 'reason="a\\"b\\\\c"' in text


def test_empty_report_renders_nothing():
    assert render_prometheus({}, "panel", now=1.0) == ""


def test_sink_for_selects_by_config():
    assert isinstance(sink_for(None), LoggingTelemetrySink)
    assert isinstance(
        sink_for(TelemetryConfig(url="http://x")), VictoriaMetricsTelemetrySink
    )


def test_forwards_to_victoriametrics():
    """The sink POSTs exposition text to /api/v1/import/prometheus."""
    received: dict[str, object] = {}

    @Request.application
    def app(request):
        received["path"] = request.path
        received["body"] = request.get_data(as_text=True)
        received["ctype"] = request.headers.get("Content-Type")
        return Response("", status=204)

    srv = make_server("127.0.0.1", 8097, app)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        sink = VictoriaMetricsTelemetrySink(
            TelemetryConfig(url="http://127.0.0.1:8097", device="panel")
        )
        sink.record(SAMPLE)
    finally:
        srv.shutdown()

    assert received["path"] == "/api/v1/import/prometheus"
    assert received["ctype"] == "text/plain"
    assert 'esp_rssi_dbm{device="panel"} -71' in received["body"]


def test_push_failure_is_swallowed():
    """A dead endpoint must not raise — telemetry is best-effort."""
    sink = VictoriaMetricsTelemetrySink(
        TelemetryConfig(url="http://127.0.0.1:1")  # nothing listening
    )
    sink.record(SAMPLE)  # must return normally


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
