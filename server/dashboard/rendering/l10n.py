"""Czech date formatting.

Kept independent of any system ``cs_CZ`` locale so rendering is deterministic
wherever the server runs.
"""

from __future__ import annotations

from datetime import date, datetime

DAYS = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"]
DAYS_SHORT = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]
# Genitive form used in dates ("9. července 2026")
MONTHS_GENITIVE = [
    "ledna",
    "února",
    "března",
    "dubna",
    "května",
    "června",
    "července",
    "srpna",
    "září",
    "října",
    "listopadu",
    "prosince",
]


def format_date(dt: datetime, with_year: bool = True) -> str:
    """Format a date the Czech way, e.g. '9. července 2026'."""
    text = f"{dt.day}. {MONTHS_GENITIVE[dt.month - 1]}"
    return f"{text} {dt.year}" if with_year else text


def day_label(day: date, today: date) -> str:
    """Label for a calendar day header: 'Dnes', 'Zítra' or 'Pátek 11. 7.'."""
    delta = (day - today).days
    if delta == 0:
        return "Dnes"
    if delta == 1:
        return "Zítra"
    return f"{DAYS[day.weekday()]} {day.day}. {day.month}."
