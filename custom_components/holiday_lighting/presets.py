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
    color_names: list[str]


PRESETS: Final[dict[str, Preset]] = {
    "new_years": {
        "name": "New Year's",
        "start": "12-31",
        "end": "01-01",
        "colors": ["#FFD700", "#FFFFFF", "#C0C0C0"],
        "color_names": ["Gold", "White", "Silver"],
    },
    "valentines": {
        "name": "Valentine's Day",
        "start": "02-07",
        "end": "02-14",
        "colors": ["#FF0000", "#FF69B4", "#FFFFFF"],
        "color_names": ["Red", "Pink", "White"],
    },
    "st_patricks": {
        "name": "St. Patrick's Day",
        "start": "03-10",
        "end": "03-17",
        "colors": ["#00A000", "#FFFFFF", "#FFD700"],
        "color_names": ["Green", "White", "Gold"],
    },
    "easter": {
        "name": "Easter",
        "start": "03-25",
        "end": "04-25",
        "colors": ["#FFB6C1", "#E6E6FA", "#FFFACD", "#B0E0E6"],
        "color_names": ["Pastel Pink", "Lavender", "Pale Yellow", "Light Blue"],
    },
    "independence_day": {
        "name": "Independence Day",
        "start": "06-28",
        "end": "07-05",
        "colors": ["#FF0000", "#FFFFFF", "#0000FF"],
        "color_names": ["Red", "White", "Blue"],
    },
    "halloween": {
        "name": "Halloween",
        "start": "10-01",
        "end": "10-31",
        "colors": ["#FF6600", "#8000FF", "#00FF00"],
        "color_names": ["Orange", "Purple", "Green"],
    },
    "thanksgiving": {
        "name": "Thanksgiving",
        "start": "11-20",
        "end": "11-30",
        "colors": ["#FF8C00", "#FFD700", "#B22222"],
        "color_names": ["Dark Orange", "Gold", "Deep Red"],
    },
    "christmas": {
        "name": "Christmas",
        "start": "12-01",
        "end": "12-26",
        "colors": ["#FF0000", "#00FF00", "#FFFFFF"],
        "color_names": ["Red", "Green", "White"],
    },
}
