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


# --- 1.2: holiday kinds and effects -----------------------------------------

import random  # noqa: E402

from custom_components.holiday_lighting.schedule import (  # noqa: E402
    current_window,
    easter_sunday,
    effect_assignments,
    holiday_windows,
    next_start,
    nth_weekday,
)


def test_easter_and_nth_weekday() -> None:
    assert easter_sunday(2026) == date(2026, 4, 5)
    assert easter_sunday(2027) == date(2027, 3, 28)
    assert easter_sunday(2038) == date(2038, 4, 25)
    assert nth_weekday(2026, 11, 4, 3) == date(2026, 11, 26)  # Thanksgiving
    assert nth_weekday(2027, 11, 4, 3) == date(2027, 11, 25)
    assert nth_weekday(2026, 5, -1, 0) == date(2026, 5, 25)  # Memorial Day
    assert nth_weekday(2026, 12, -1, 4) == date(2026, 12, 25)  # last Fri of Dec
    assert nth_weekday(2026, 9, 1, 0) == date(2026, 9, 7)  # Labor Day


THANKSGIVING = {
    "kind": "nth_weekday",
    "month": 11,
    "week": 4,
    "weekday": 3,
    "days_before": 7,
    "days_after": 1,
}


def test_rule_windows_move_each_year() -> None:
    assert holiday_windows(THANKSGIVING, 2026) == [
        (date(2026, 11, 19), date(2026, 11, 27))
    ]
    assert holiday_windows(THANKSGIVING, 2027) == [
        (date(2027, 11, 18), date(2027, 11, 26))
    ]
    easter = {"kind": "easter", "days_before": 7, "days_after": 0}
    assert current_window(easter, date(2026, 3, 30)) is not None
    assert current_window(easter, date(2026, 4, 6)) is None
    assert next_start(easter, date(2026, 4, 6)) == date(2027, 3, 21)


def test_one_time_event() -> None:
    party = {"kind": "once", "start_date": "2026-11-14", "end_date": "2026-11-15"}
    assert current_window(party, date(2026, 11, 14))
    assert current_window(party, date(2027, 11, 14)) is None
    assert next_start(party, date(2026, 10, 1)) == date(2026, 11, 14)
    assert next_start(party, date(2026, 12, 1)) is None


def test_calendar_holiday_wins_tonight() -> None:
    holidays = [
        {"id": "xmas", "kind": "yearly", "start": "12-01", "end": "12-26"},
        {"id": "game", "kind": "calendar"},
    ]
    assert active_holiday(holidays, date(2026, 12, 5))["id"] == "xmas"
    assert active_holiday(holidays, date(2026, 12, 5), {"game"})["id"] == "game"
    assert upcoming_holiday(holidays, date(2026, 12, 30))[0]["id"] == "xmas"


def test_effects() -> None:
    lights = ["a", "b", "c"]
    colors = ["R", "G"]
    assert effect_assignments("static", lights, colors, 5) == {
        "R": ["a", "c"],
        "G": ["b"],
    }
    assert effect_assignments("cycle", lights, colors, 0) == {"R": lights}
    assert effect_assignments("fade", lights, colors, 1) == {"G": lights}
    twinkle = effect_assignments("twinkle", lights, colors, 0, random.Random(1))
    assert sorted(sum(twinkle.values(), [])) == lights
    assert set(twinkle) <= set(colors)
    assert effect_assignments("rotate", lights, colors, 1) == {
        "G": ["a", "c"],
        "R": ["b"],
    }


@pytest.mark.parametrize(
    ("preset", "year", "window"),
    [
        ("fathers_day", 2027, ("2027-06-18", "2027-06-20")),  # 3rd Sunday of June
        ("fathers_day", 2028, ("2028-06-16", "2028-06-18")),
        ("presidents_day", 2027, ("2027-02-15", "2027-02-15")),  # 3rd Monday of Feb
        ("kwanzaa", 2026, ("2026-12-26", "2027-01-01")),
    ],
)
def test_new_preset_dates(preset: str, year: int, window: tuple[str, str]) -> None:
    from custom_components.holiday_lighting.presets import PRESETS

    start, end = holiday_windows(PRESETS[preset], year)[0]
    assert (start.isoformat(), end.isoformat()) == window


def test_new_presets_do_not_steal_neighbors() -> None:
    from custom_components.holiday_lighting.presets import PRESETS

    holidays = [{**preset, "id": key} for key, preset in PRESETS.items()]
    expected = {
        "2027-02-14": "valentines",
        "2027-02-15": "presidents_day",
        "2027-06-12": "sacred_heart_month",
        "2027-06-20": "fathers_day",
        "2027-12-25": "christmas",
        "2027-12-31": "new_years",
    }
    for day, key in expected.items():
        assert active_holiday(holidays, date.fromisoformat(day))["id"] == key


@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        # Easter 2027 is March 28; 2028 is April 16.
        ("divine_mercy", {2027: "2027-04-04", 2028: "2028-04-23"}),
        ("pentecost", {2027: "2027-05-16", 2028: "2028-06-04"}),
        ("corpus_christi", {2027: "2027-05-30", 2028: "2028-06-18"}),
        ("sacred_heart_feast", {2027: "2027-06-04", 2028: "2028-06-23"}),
        ("immaculate_heart", {2027: "2027-06-05", 2028: "2028-06-24"}),
    ],
)
def test_easter_relative_feasts(preset: str, expected: dict[int, str]) -> None:
    from custom_components.holiday_lighting.presets import PRESETS

    for year, day in expected.items():
        assert holiday_windows(PRESETS[preset], year) == [
            (date.fromisoformat(day), date.fromisoformat(day))
        ]


def test_easter_offset_defaults_to_easter_sunday() -> None:
    """Easter holidays saved before the offset existed are unchanged."""
    saved = {"kind": "easter", "days_before": 7, "days_after": 0}
    assert holiday_windows(saved, 2027) == [(date(2027, 3, 21), date(2027, 3, 28))]


def test_feast_days_win_over_seasons() -> None:
    from custom_components.holiday_lighting.presets import PRESETS

    holidays = [{**preset, "id": key} for key, preset in PRESETS.items()]
    expected = {
        "2027-06-04": "sacred_heart_feast",
        "2027-06-10": "sacred_heart_month",
        "2027-12-08": "immaculate_conception",
        "2027-12-12": "guadalupe",
        "2027-12-25": "christmas",
    }
    for day, key in expected.items():
        assert active_holiday(holidays, date.fromisoformat(day))["id"] == key
