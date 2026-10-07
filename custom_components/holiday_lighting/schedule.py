"""Date-window and color helpers for Holiday Lighting.

Everything here is plain logic with no Home Assistant runtime state, so it
can be unit tested directly.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.util.color import color_name_to_rgb

from .const import CONF_END, CONF_START

_MONTH_DAY_RE = re.compile(r"^(\d{1,2})-(\d{1,2})$")
_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
# A leap year, so Feb 29 is a valid start/end.
_REFERENCE_YEAR = 2024


def parse_month_day(value: str) -> tuple[int, int]:
    """Parse "MM-DD" (or a full ISO date, whose year is ignored)."""
    value = value.strip()
    if len(value) == 10 and value[4] == "-":
        value = value[5:]
    match = _MONTH_DAY_RE.match(value)
    if not match:
        raise ValueError(f"Invalid month-day: {value!r}")
    month, day = int(match.group(1)), int(match.group(2))
    # Raises ValueError for impossible dates such as 02-30.
    date(_REFERENCE_YEAR, month, day)
    return month, day


def format_month_day(month_day: tuple[int, int]) -> str:
    """Format a (month, day) tuple as "MM-DD"."""
    return f"{month_day[0]:02d}-{month_day[1]:02d}"


def in_window(today: date, start: str, end: str) -> bool:
    """Return True if today falls in the yearly start..end window (inclusive).

    Windows may wrap the new year, e.g. 12-31 to 01-01.
    """
    current = (today.month, today.day)
    first, last = parse_month_day(start), parse_month_day(end)
    if first <= last:
        return first <= current <= last
    return current >= first or current <= last


def window_length(start: str, end: str) -> int:
    """Number of days in the window, used to prefer more specific holidays."""
    first = date(_REFERENCE_YEAR, *parse_month_day(start))
    last = date(_REFERENCE_YEAR, *parse_month_day(end))
    days = (last - first).days
    if days < 0:
        days += 366
    return days + 1


def active_holiday(
    holidays: Iterable[Mapping[str, Any]], today: date
) -> Mapping[str, Any] | None:
    """Pick the holiday active today.

    When windows overlap, the shortest window wins so a specific holiday
    (New Year's Eve) beats a broad season (Winter).
    """
    matches = [
        holiday
        for holiday in holidays
        if in_window(today, holiday[CONF_START], holiday[CONF_END])
    ]
    if not matches:
        return None
    return min(
        matches,
        key=lambda holiday: window_length(holiday[CONF_START], holiday[CONF_END]),
    )


def next_start(start: str, today: date) -> date:
    """The next date (today or later) on which a window starts."""
    month, day = parse_month_day(start)
    for year in range(today.year, today.year + 9):
        try:
            candidate = date(year, month, day)
        except ValueError:  # Feb 29 in a non-leap year
            continue
        if candidate >= today:
            return candidate
    raise ValueError(f"No upcoming date for {start!r}")


def upcoming_holiday(
    holidays: Iterable[Mapping[str, Any]], today: date
) -> tuple[Mapping[str, Any], date] | None:
    """The holiday whose window starts next (after today)."""
    upcoming = [
        (holiday, next_start(holiday[CONF_START], today))
        for holiday in holidays
        if not in_window(today, holiday[CONF_START], holiday[CONF_END])
    ]
    if not upcoming:
        return None
    return min(upcoming, key=lambda item: item[1])


def parse_color(value: str) -> tuple[int, int, int]:
    """Parse a hex color (#FF8800) or CSS color name (orange) into RGB."""
    value = value.strip()
    if match := _HEX_RE.match(value):
        raw = match.group(1)
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    # color_name_to_rgb raises ValueError for unknown names.
    return color_name_to_rgb(value.lower().replace(" ", ""))


def parse_colors(value: str | Sequence[str]) -> list[str]:
    """Parse a comma-separated color list and normalise to "#RRGGBB"."""
    items = value.split(",") if isinstance(value, str) else list(value)
    colors = [item for item in (part.strip() for part in items) if item]
    if not colors:
        raise ValueError("At least one color is required")
    return ["#{:02X}{:02X}{:02X}".format(*parse_color(color)) for color in colors]


def rotation_assignments(
    lights: Sequence[str], colors: Sequence[str], offset: int
) -> dict[str, list[str]]:
    """Map each color to the lights that should show it for this step.

    Light i gets colors[(i - offset) % len(colors)], so advancing the offset
    makes each color march one light down the line.
    """
    assignments: dict[str, list[str]] = {}
    if not colors:
        return assignments
    for index, light in enumerate(lights):
        color = colors[(index - offset) % len(colors)]
        assignments.setdefault(color, []).append(light)
    return assignments


# --- Nightly on/off window -------------------------------------------------
#
# A "night" is identified by the date of its evening: anything from noon
# until noon the next day belongs to the same night. An off time before
# noon (e.g. 01:00) therefore means "after midnight" of that night.

_NOON = time(12, 0)


def night_of(now: datetime) -> date:
    """The evening date of the night that `now` belongs to."""
    if now.time() >= _NOON:
        return now.date()
    return now.date() - timedelta(days=1)


def hard_off_at(night: date, off_time: time, tzinfo: Any) -> datetime:
    """When the hard off time falls for the given night."""
    day = night if off_time >= _NOON else night + timedelta(days=1)
    return datetime.combine(day, off_time, tzinfo=tzinfo)


def lights_off_deadline(
    on_at: datetime, on_duration: timedelta | None, off_time: time | None
) -> datetime | None:
    """When lights turned on at `on_at` must turn off.

    The earlier of on_at + duration and the night's hard off time. None means
    neither limit is set, so the lights stay on until it is light again.
    """
    candidates: list[datetime] = []
    if on_duration:
        candidates.append(on_at + on_duration)
    if off_time is not None:
        candidates.append(hard_off_at(night_of(on_at), off_time, on_at.tzinfo))
    return min(candidates) if candidates else None


def can_start(now: datetime, off_time: time | None) -> bool:
    """Whether it is still early enough tonight to turn the lights on.

    Before the hard off time if one is set; otherwise only in the evening
    (noon to midnight), so a dark winter morning does not start a show.
    """
    if off_time is not None:
        return now < hard_off_at(night_of(now), off_time, now.tzinfo)
    return now.time() >= _NOON
