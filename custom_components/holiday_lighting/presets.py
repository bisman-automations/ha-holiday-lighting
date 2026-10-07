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
    CONF_EASTER_OFFSET,
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


def _easter(name: str, offset: int, colors: dict[str, list[str]]) -> dict[str, Any]:
    """A one-day feast a fixed number of days from Easter Sunday."""
    return {
        CONF_NAME: name,
        CONF_KIND: KIND_EASTER,
        CONF_EASTER_OFFSET: offset,
        CONF_DAYS_BEFORE: 0,
        CONF_DAYS_AFTER: 0,
        **colors,
    }


def _c(hexes: list[str], names: list[str]) -> dict[str, list[str]]:
    return {CONF_COLORS: hexes, CONF_COLOR_NAMES: names}


BLUE, WHITE, GOLD, RED = "#1E64FF", "#FFFFFF", "#FFC72C", "#FF0000"
PURPLE = "#7B2CBF"

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
    "epiphany": _yearly(
        "Epiphany",
        "01-06",
        "01-06",
        _c([GOLD, WHITE, PURPLE], ["Gold", "White", "Purple"]),
    ),
    "presidents_day": _nth("Presidents' Day", 2, 3, MONDAY, 0, 0, RED_WHITE_BLUE),
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
    "st_joseph": _yearly(
        "St. Joseph", "03-19", "03-19", _c([WHITE, GOLD], ["White", "Gold"])
    ),
    "annunciation": _yearly(
        "Annunciation", "03-25", "03-25", _c([BLUE, WHITE], ["Blue", "White"])
    ),
    "easter": {
        CONF_NAME: "Easter",
        CONF_KIND: KIND_EASTER,
        CONF_DAYS_BEFORE: 7,
        CONF_DAYS_AFTER: 0,
        CONF_COLORS: ["#FFB6C1", "#E6E6FA", "#FFFACD", "#B0E0E6"],
        CONF_COLOR_NAMES: ["Pastel Pink", "Lavender", "Pale Yellow", "Light Blue"],
    },
    "divine_mercy": _easter(
        "Divine Mercy Sunday",
        7,
        _c([RED, "#A0D8FF", WHITE], ["Red", "Pale Blue", "White"]),
    ),
    "earth_day": _yearly(
        "Earth Day",
        "04-22",
        "04-22",
        {
            CONF_COLORS: ["#00FF40", "#0060FF", "#00C8A0"],
            CONF_COLOR_NAMES: ["Green", "Blue", "Teal"],
        },
    ),
    "cinco_de_mayo": _yearly(
        "Cinco de Mayo",
        "05-05",
        "05-05",
        {
            CONF_COLORS: ["#00A651", "#FFFFFF", "#CE1126"],
            CONF_COLOR_NAMES: ["Green", "White", "Red"],
        },
    ),
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
    "pentecost": _easter(
        "Pentecost", 49, _c([RED, "#FF6600", GOLD], ["Red", "Orange", "Gold"])
    ),
    "corpus_christi": _easter(
        "Corpus Christi", 63, _c([GOLD, WHITE], ["Gold", "White"])
    ),
    "sacred_heart_feast": _easter(
        "Feast of the Sacred Heart",
        68,
        _c([RED, GOLD, WHITE], ["Red", "Gold", "White"]),
    ),
    "immaculate_heart": _easter(
        "Immaculate Heart of Mary",
        69,
        _c([BLUE, WHITE, "#FF5A8C"], ["Blue", "White", "Rose"]),
    ),
    "sacred_heart_month": _yearly(
        "Month of the Sacred Heart of Jesus",
        "06-01",
        "06-30",
        {
            CONF_COLORS: ["#FF0000", "#FFC72C", "#FFFFFF"],
            CONF_COLOR_NAMES: ["Red", "Gold", "White"],
        },
    ),
    "fathers_day": _nth(
        "Father's Day",
        6,
        3,
        SUNDAY,
        2,
        0,
        {
            CONF_COLORS: ["#1E64FF", "#FFFFFF", "#6EC6FF"],
            CONF_COLOR_NAMES: ["Blue", "White", "Light Blue"],
        },
    ),
    "juneteenth": _yearly("Juneteenth", "06-19", "06-19", RED_WHITE_BLUE),
    "independence_day": _yearly("Independence Day", "06-28", "07-05", RED_WHITE_BLUE),
    "assumption": _yearly(
        "Assumption of Mary",
        "08-15",
        "08-15",
        _c([BLUE, WHITE, GOLD], ["Blue", "White", "Gold"]),
    ),
    "labor_day": _nth("Labor Day", 9, 1, MONDAY, 3, 0, RED_WHITE_BLUE),
    "patriot_day": _yearly("Patriot Day", "09-11", "09-11", RED_WHITE_BLUE),
    "halloween": _yearly(
        "Halloween",
        "10-01",
        "10-31",
        {
            CONF_COLORS: ["#FF6600", "#8000FF", "#00FF00"],
            CONF_COLOR_NAMES: ["Orange", "Purple", "Green"],
        },
    ),
    "all_saints": _yearly(
        "All Saints' Day", "11-01", "11-01", _c([WHITE, GOLD], ["White", "Gold"])
    ),
    "all_souls": _yearly(
        "All Souls' Day", "11-02", "11-02", _c([PURPLE, WHITE], ["Purple", "White"])
    ),
    "dia_de_los_muertos": _yearly(
        "Día de los Muertos",
        "11-01",
        "11-02",
        {
            CONF_COLORS: ["#FF8C00", "#FF00A0", "#7B2CBF"],
            CONF_COLOR_NAMES: ["Marigold", "Magenta", "Purple"],
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
    "immaculate_conception": _yearly(
        "Immaculate Conception", "12-08", "12-08", _c([BLUE, WHITE], ["Blue", "White"])
    ),
    "guadalupe": _yearly(
        "Our Lady of Guadalupe",
        "12-12",
        "12-12",
        _c(["#00B5AD", "#E0115F", GOLD], ["Turquoise", "Rose", "Gold"]),
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
    "kwanzaa": _yearly(
        "Kwanzaa",
        "12-26",
        "01-01",
        {
            CONF_COLORS: ["#E31B23", "#FFC72C", "#00A651"],
            CONF_COLOR_NAMES: ["Red", "Gold", "Green"],
        },
    ),
}
