"""Visual constants for the portrait design canvas.

The panel renders three hard colors, so everything here is one of :data:`RED`,
:data:`BLACK` or :data:`WHITE`. Layout is expressed as absolute coordinates on
the 640×960 portrait canvas; the sections read these rather than recomputing
offsets, so vertical rhythm stays consistent.
"""

from __future__ import annotations

# --- Canvas -----------------------------------------------------------------
# Portrait design canvas. Must equal the panel's native size transposed; the
# encoder asserts this when it rotates the design into native orientation.
W_PORTRAIT = 640
H_PORTRAIT = 960

# --- Colors -----------------------------------------------------------------
RED = (255, 0, 0)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# --- Vertical layout (y coordinates, top to bottom) -------------------------
HEADER_H = 100

FORECAST_Y = HEADER_H  # 100
FORECAST_H = 300

SUMMARY_Y = FORECAST_Y + FORECAST_H  # 400 — last-24h stats strip
SUMMARY_H = 36

DIVIDER_Y = SUMMARY_Y + SUMMARY_H  # 436
DIVIDER_H = 2

CALENDAR_Y = DIVIDER_Y + DIVIDER_H  # 438
CALENDAR_LABEL_H = 30  # "KALENDÁŘ" section label
EVENTS_Y = CALENDAR_Y + CALENDAR_LABEL_H  # 468

DAY_HEADER_H = 28  # per-day label + rule
EVENT_H = 34  # single event row
VOLNO_H = 24  # slim "volno" row shown for a day with no events

FOOTER_H = 34
FOOTER_Y = H_PORTRAIT - FOOTER_H  # 926

# Uniform horizontal margin used by every section.
PAD = 20
