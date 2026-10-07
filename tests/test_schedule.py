"""Tests for the pure schedule helpers."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.holiday_lighting.schedule import (
    active_holiday,
    can_start,
    in_window,
    lights_off_deadline,
    night_of,
    parse_colors,
    parse_month_day,
    rgb_to_hex,
    rotation_assignments,
    upcoming_holiday,
)

TZ = ZoneInfo("America/Chicago")


def at(day: int, hour: int, minute: int = 0, month: int = 12) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=TZ)


def test_parse_month_day() -> None:
    assert parse_month_day("12-25") == (12, 25)
    assert parse_month_day("2026-07-04") == (7, 4)
    assert parse_month_day("02-29") == (2, 29)
    for bad in ("13-01", "02-30", "christmas", ""):
        with pytest.raises(ValueError):
            parse_month_day(bad)


def test_in_window_wraps_new_year() -> None:
    assert in_window(date(2026, 12, 31), "12-31", "01-01")
    assert in_window(date(2027, 1, 1), "12-31", "01-01")
    assert not in_window(date(2027, 1, 2), "12-31", "01-01")
    assert in_window(date(2026, 12, 1), "12-01", "12-26")
    assert not in_window(date(2026, 11, 30), "12-01", "12-26")


def test_shortest_window_wins() -> None:
    holidays = [
        {"id": "winter", "start": "12-01", "end": "02-28"},
        {"id": "xmas", "start": "12-20", "end": "12-26"},
    ]
    assert active_holiday(holidays, date(2026, 12, 24))["id"] == "xmas"
    assert active_holiday(holidays, date(2026, 12, 10))["id"] == "winter"
    assert active_holiday(holidays, date(2026, 6, 1)) is None


def test_upcoming_holiday() -> None:
    holidays = [
        {"id": "halloween", "start": "10-01", "end": "10-31"},
        {"id": "xmas", "start": "12-01", "end": "12-26"},
    ]
    found, when = upcoming_holiday(holidays, date(2026, 10, 15))
    assert found["id"] == "xmas" and when == date(2026, 12, 1)
    found, when = upcoming_holiday(holidays, date(2026, 12, 30))
    assert found["id"] == "halloween" and when == date(2027, 10, 1)


def test_parse_colors() -> None:
    assert parse_colors("red, #00ff00 , 0000FF") == ["#FF0000", "#00FF00", "#0000FF"]
    assert parse_colors(["white"]) == ["#FFFFFF"]
    with pytest.raises(ValueError):
        parse_colors("not-a-color")
    with pytest.raises(ValueError):
        parse_colors(" , ")


def test_rotation_moves_colors_down_the_line() -> None:
    lights = ["light.a", "light.b", "light.c", "light.d"]
    colors = ["R", "G", "W"]
    assert rotation_assignments(lights, colors, 0) == {
        "R": ["light.a", "light.d"],
        "G": ["light.b"],
        "W": ["light.c"],
    }
    # Each color moves one light down: R was on a, now on b.
    assert rotation_assignments(lights, colors, 1) == {
        "W": ["light.a", "light.d"],
        "R": ["light.b"],
        "G": ["light.c"],
    }


def test_night_of() -> None:
    assert night_of(at(24, 18)) == date(2026, 12, 24)
    assert night_of(at(25, 0, 30)) == date(2026, 12, 24)
    assert night_of(at(25, 12)) == date(2026, 12, 25)


def test_deadline_is_earlier_of_duration_and_hard_off() -> None:
    on_at = at(24, 17, 30)
    # 5h -> 22:30, before 23:00
    assert lights_off_deadline(on_at, timedelta(hours=5), time(23)) == at(24, 22, 30)
    # 7h -> 00:30, after 23:00
    assert lights_off_deadline(on_at, timedelta(hours=7), time(23)) == at(24, 23)
    # Hard off after midnight
    assert lights_off_deadline(on_at, None, time(1)) == at(25, 1)
    assert lights_off_deadline(on_at, timedelta(hours=2), None) == at(24, 19, 30)
    assert lights_off_deadline(on_at, None, None) is None


def test_can_start() -> None:
    assert can_start(at(24, 17), time(23))
    assert not can_start(at(24, 23, 5), time(23))
    assert can_start(at(25, 0, 30), time(1))
    assert not can_start(at(25, 6), time(1))
    # No hard off: evenings only
    assert can_start(at(24, 17), None)
    assert not can_start(at(25, 6), None)


def test_rgb_to_hex() -> None:
    assert rgb_to_hex([255, 136, 0]) == "#FF8800"
    assert rgb_to_hex((0, 0, 0)) == "#000000"
