"""Individual dashboard sections, each drawing onto a shared :class:`Canvas`."""

from __future__ import annotations

from . import calendar, daily, footer, forecast, header, summary

__all__ = ["header", "forecast", "daily", "summary", "calendar", "footer"]
