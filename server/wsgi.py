"""WSGI entrypoint.

Run in development with ``uv run flask --app wsgi:app --debug run``.
For production, point any WSGI server (gunicorn, uwsgi) at the ``app`` object below.
"""

from __future__ import annotations

from dashboard import create_app
from dashboard.config import Settings

settings = Settings.load()
app = create_app(settings)


if __name__ == "__main__":
    app.run(host=settings.host, port=settings.port)
