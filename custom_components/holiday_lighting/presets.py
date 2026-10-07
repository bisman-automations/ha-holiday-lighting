"""Built-in holiday presets.

Holidays that move each year use rules (Nth weekday, or relative to Easter),
so their dates are right every year without editing.
"""

from __future__ import annotations

from typing import Any, Final

from .const import (
    CONF_COLOR_NAMES,
    CONF_COLORS,
    CONF_DAYS_AFTER,
    CONF_DAYS_BEFORE,
    CONF_END,
    CONF_KIND,
    CONF_MONTH,
    CONF_NAME,
    CONF_START,
    CONF_WEEK,
    CONF_WEEKDAY,
    KIND_EASTER,
    KIND_NTH_WEEKDAY,
    KIND_YEARLY,
)

MONDAY, THURSDAY, SUNDAY = 0, 3, 6
RED_WHITE_BLUE = {
    CONF_COLORS: ["#FF0000", "#FFFFFF", "#0000FF"],
    CONF_COLOR_NAMES: ["Red", "White", "Blue"],
}


def _yearly(
    name: str, start: str, end: str, colors: dict[str, list[str]]
) -> dict[str, Any]:
    return {
        CONF_NAME: name,
        CONF_KIND: KIND_YEARLY,
        CONF_START: start,
        CONF_END: end,
        **colors,
    }


def _nth(
    name: str,
    month: int,
    week: int,
    weekday: int,
    before: int,
    after: int,
    colors: dict[str, list[str]],
) -> dict[str, Any]:
    return {
        CONF_NAME: name,
        CONF_KIND: KIND_NTH_WEEKDAY,
        CONF_MONTH: month,
        CONF_WEEK: week,
        CONF_WEEKDAY: weekday,
        CONF_DAYS_BEFORE: before,
        CONF_DAYS_AFTER: after,
        **colors,
    }


PRESETS: Final[dict[str, dict[str, Any]]] = {
    "new_years": _yearly(
        "New Year's",
        "12-31",
        "01-01",
        {
            CONF_COLORS: ["#FFD700", "#FFFFFF", "#C0C0C0"],
            CONF_COLOR_NAMES: ["Gold", "White", "Silver"],
        },
    ),
    "valentines": _yearly(
        "Valentine's Day",
        "02-07",
        "02-14",
        {
            CONF_COLORS: ["#FF0000", "#FF69B4", "#FFFFFF"],
            CONF_COLOR_NAMES: ["Red", "Pink", "White"],
        },
    ),
    "st_patricks": _yearly(
        "St. Patrick's Day",
        "03-10",
        "03-17",
        {
            CONF_COLORS: ["#00A000", "#FFFFFF", "#FFD700"],
            CONF_COLOR_NAMES: ["Green", "White", "Gold"],
        },
    ),
    "easter": {
        CONF_NAME: "Easter",
        CONF_KIND: KIND_EASTER,
        CONF_DAYS_BEFORE: 7,
        CONF_DAYS_AFTER: 0,
        CONF_COLORS: ["#FFB6C1", "#E6E6FA", "#FFFACD", "#B0E0E6"],
        CONF_COLOR_NAMES: ["Pastel Pink", "Lavender", "Pale Yellow", "Light Blue"],
    },
    "mothers_day": _nth(
        "Mother's Day",
        5,
        2,
        SUNDAY,
        2,
        0,
        {
            CONF_COLORS: ["#FF69B4", "#FFFFFF", "#E6A8D7"],
            CONF_COLOR_NAMES: ["Pink", "White", "Orchid"],
        },
    ),
    "memorial_day": _nth("Memorial Day", 5, -1, MONDAY, 3, 0, RED_WHITE_BLUE),
    "independence_day": _yearly("Independence Day", "06-28", "07-05", RED_WHITE_BLUE),
    "labor_day": _nth("Labor Day", 9, 1, MONDAY, 3, 0, RED_WHITE_BLUE),
    "halloween": _yearly(
        "Halloween",
        "10-01",
        "10-31",
        {
            CONF_COLORS: ["#FF6600", "#8000FF", "#00FF00"],
            CONF_COLOR_NAMES: ["Orange", "Purple", "Green"],
        },
    ),
    "veterans_day": _yearly("Veterans Day", "11-08", "11-11", RED_WHITE_BLUE),
    "thanksgiving": _nth(
        "Thanksgiving",
        11,
        4,
        THURSDAY,
        7,
        1,
        {
            CONF_COLORS: ["#FF8C00", "#FFD700", "#B22222"],
            CONF_COLOR_NAMES: ["Dark Orange", "Gold", "Deep Red"],
        },
    ),
    "christmas": _yearly(
        "Christmas",
        "12-01",
        "12-26",
        {
            CONF_COLORS: ["#FF0000", "#00FF00", "#FFFFFF"],
            CONF_COLOR_NAMES: ["Red", "Green", "White"],
        },
    ),
}
