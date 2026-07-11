"""Individual dashboard sections, each drawing onto a shared :class:`Canvas`."""

from __future__ import annotations

from . import calendar, footer, forecast, header, summary

__all__ = ["header", "forecast", "summary", "calendar", "footer"]
