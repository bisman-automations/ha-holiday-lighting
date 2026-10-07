"""Built-in holiday presets.

Dates are fixed yearly windows. Holidays that move (Easter, Thanksgiving,
Hanukkah) use a window wide enough to cover typical years; adjust them in
the holiday's settings if needed.
"""

from __future__ import annotations

from typing import Final, TypedDict


class Preset(TypedDict):
    """A holiday preset."""

    name: str
    start: str
    end: str
    colors: list[str]


PRESETS: Final[dict[str, Preset]] = {
    "new_years": {
        "name": "New Year's",
        "start": "12-31",
        "end": "01-01",
        "colors": ["#FFD700", "#FFFFFF", "#C0C0C0"],
    },
    "valentines": {
        "name": "Valentine's Day",
        "start": "02-07",
        "end": "02-14",
        "colors": ["#FF0000", "#FF69B4", "#FFFFFF"],
    },
    "st_patricks": {
        "name": "St. Patrick's Day",
        "start": "03-10",
        "end": "03-17",
        "colors": ["#00A000", "#FFFFFF", "#FFD700"],
    },
    "easter": {
        "name": "Easter",
        "start": "03-25",
        "end": "04-25",
        "colors": ["#FFB6C1", "#E6E6FA", "#FFFACD", "#B0E0E6"],
    },
    "independence_day": {
        "name": "Independence Day",
        "start": "06-28",
        "end": "07-05",
        "colors": ["#FF0000", "#FFFFFF", "#0000FF"],
    },
    "halloween": {
        "name": "Halloween",
        "start": "10-01",
        "end": "10-31",
        "colors": ["#FF6600", "#8000FF", "#00FF00"],
    },
    "thanksgiving": {
        "name": "Thanksgiving",
        "start": "11-20",
        "end": "11-30",
        "colors": ["#FF8C00", "#FFD700", "#B22222"],
    },
    "christmas": {
        "name": "Christmas",
        "start": "12-01",
        "end": "12-26",
        "colors": ["#FF0000", "#00FF00", "#FFFFFF"],
    },
}
