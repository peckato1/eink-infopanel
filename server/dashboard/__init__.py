"""Dashboard server package.

Renders a weather + calendar dashboard to the exact byte format the ESP32
e-paper firmware expects, and serves it over HTTP.
"""

from __future__ import annotations

import logging

from flask import Flask

from . import api
from .config import Settings
from .data import DataSource, default_source
from .rendering import Renderer
from .service import DashboardService
from .telemetry import sink_for

__all__ = ["create_app"]


def create_app(
    settings: Settings | None = None,
    source: DataSource | None = None,
) -> Flask:
    """Application factory.

    Wires the data source, renderer and service together and registers the API blueprint.
    Pass ``settings``/``source`` to override the defaults (e.g. in tests or when a live data source is available).

    The log level defaults to ``INFO`` and can be raised (e.g. to ``DEBUG``, which traces which CalDAV calendars matched) via ``[logging] level`` in ``config.toml``.
    """
    settings = settings or Settings.load()

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    source = source or default_source(settings)

    app = Flask(__name__)
    app.config["SETTINGS"] = settings
    app.extensions["dashboard"] = DashboardService(
        settings=settings,
        source=source,
        renderer=Renderer(settings),
    )
    app.extensions["telemetry"] = sink_for(settings.telemetry)

    app.register_blueprint(api.bp)
    return app
