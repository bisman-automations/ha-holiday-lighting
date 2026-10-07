"""Date-window and color helpers for Holiday Lighting.

Everything here is plain logic with no Home Assistant runtime state, so it
can be unit tested directly.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.util.color import color_name_to_rgb

from .const import (
    CONF_DAYS_AFTER,
    CONF_DAYS_BEFORE,
    CONF_END,
    CONF_END_DATE,
    CONF_KIND,
    CONF_MONTH,
    CONF_START,
    CONF_START_DATE,
    CONF_WEEK,
    CONF_WEEKDAY,
    KIND_EASTER,
    KIND_NTH_WEEKDAY,
    KIND_ONCE,
    KIND_YEARLY,
    MODE_CYCLE,
    MODE_FADE,
    MODE_STATIC,
    MODE_TWINKLE,
)

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


# --- Holiday windows ---------------------------------------------------------
#
# Every kind of holiday reduces to "the date windows it covers in a given
# year". Calendar holidays have no fixed dates; the controller decides those.


def easter_sunday(year: int) -> date:
    """Western (Gregorian) Easter Sunday, anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    month, day = divmod(h + el - 7 * m + 114, 31)
    return date(year, month, day + 1)


def nth_weekday(year: int, month: int, week: int, weekday: int) -> date:
    """The Nth weekday of a month (week -1 = last), e.g. 4th Thursday."""
    if week == -1:
        last_day = (date(year + (month == 12), month % 12 + 1, 1)) - timedelta(days=1)
        return last_day - timedelta(days=(last_day.weekday() - weekday) % 7)
    first = date(year, month, 1)
    first_match = first + timedelta(days=(weekday - first.weekday()) % 7)
    return first_match + timedelta(weeks=week - 1)


def _yearly_date(year: int, month_day: tuple[int, int]) -> date:
    try:
        return date(year, *month_day)
    except ValueError:  # Feb 29 in a non-leap year
        return date(year, 2, 28)


def holiday_windows(holiday: Mapping[str, Any], year: int) -> list[tuple[date, date]]:
    """Windows (inclusive start, end) for a holiday, anchored in `year`."""
    kind = holiday.get(CONF_KIND, KIND_YEARLY)
    if kind == KIND_YEARLY:
        first = parse_month_day(holiday[CONF_START])
        last = parse_month_day(holiday[CONF_END])
        start = _yearly_date(year, first)
        end = _yearly_date(year + (last < first), last)
        return [(start, end)]
    if kind in (KIND_NTH_WEEKDAY, KIND_EASTER):
        if kind == KIND_EASTER:
            anchor = easter_sunday(year)
        else:
            anchor = nth_weekday(
                year,
                int(holiday[CONF_MONTH]),
                int(holiday[CONF_WEEK]),
                int(holiday[CONF_WEEKDAY]),
            )
        before = timedelta(days=int(holiday.get(CONF_DAYS_BEFORE, 0)))
        after = timedelta(days=int(holiday.get(CONF_DAYS_AFTER, 0)))
        return [(anchor - before, anchor + after)]
    if kind == KIND_ONCE:
        start = date.fromisoformat(holiday[CONF_START_DATE])
        end = date.fromisoformat(holiday[CONF_END_DATE])
        return [(start, end)] if start.year == year else []
    return []


def _windows_near(holiday: Mapping[str, Any], day: date) -> list[tuple[date, date]]:
    windows: list[tuple[date, date]] = []
    for year in (day.year - 1, day.year, day.year + 1):
        windows.extend(holiday_windows(holiday, year))
    return windows


def current_window(holiday: Mapping[str, Any], day: date) -> tuple[date, date] | None:
    """The window containing `day`, if any."""
    for start, end in _windows_near(holiday, day):
        if start <= day <= end:
            return start, end
    return None


def window_length(start: str, end: str) -> int:
    """Number of days in a yearly MM-DD window."""
    window = holiday_windows({CONF_START: start, CONF_END: end}, _REFERENCE_YEAR)[0]
    return (window[1] - window[0]).days + 1


def active_holiday(
    holidays: Iterable[Mapping[str, Any]],
    today: date,
    calendar_active: Iterable[str] = (),
) -> Mapping[str, Any] | None:
    """Pick the holiday active today.

    Calendar holidays with an event tonight win. Otherwise, when windows
    overlap, the shortest window wins, so a specific holiday (New Year's Eve)
    beats a broad season (Winter).
    """
    holidays = list(holidays)
    calendar_ids = set(calendar_active)
    for holiday in holidays:
        if holiday.get("id") in calendar_ids:
            return holiday
    best: tuple[int, Mapping[str, Any]] | None = None
    for holiday in holidays:
        if (window := current_window(holiday, today)) is None:
            continue
        length = (window[1] - window[0]).days + 1
        if best is None or length < best[0]:
            best = (length, holiday)
    return best[1] if best else None


def next_start(holiday: Mapping[str, Any], today: date) -> date | None:
    """The next window start after today, if the holiday has dates."""
    starts = [
        start
        for year in range(today.year, today.year + 3)
        for start, _end in holiday_windows(holiday, year)
        if start > today
    ]
    return min(starts) if starts else None


def upcoming_holiday(
    holidays: Iterable[Mapping[str, Any]], today: date
) -> tuple[Mapping[str, Any], date] | None:
    """The holiday whose window starts next (after today)."""
    upcoming = [
        (holiday, start)
        for holiday in holidays
        if current_window(holiday, today) is None
        and (start := next_start(holiday, today)) is not None
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


def rgb_to_hex(rgb: Sequence[int]) -> str:
    """[255, 136, 0] -> "#FF8800"."""
    red, green, blue = (max(0, min(255, int(c))) for c in rgb)
    return f"#{red:02X}{green:02X}{blue:02X}"


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


def effect_assignments(
    mode: str,
    lights: Sequence[str],
    colors: Sequence[str],
    offset: int,
    rng: random.Random | None = None,
) -> dict[str, list[str]]:
    """Which lights get which color for this step of an effect.

    - rotate (chase): colors march one light down the list each step
    - static: the step-0 chase pattern, never moving
    - cycle / fade: every light shows the same color, stepping through the
      list together (fade blends between them)
    - twinkle: each light picks a random color each step
    """
    if not colors or not lights:
        return {}
    if mode == MODE_STATIC:
        return rotation_assignments(lights, colors, 0)
    if mode in (MODE_CYCLE, MODE_FADE):
        return {colors[offset % len(colors)]: list(lights)}
    if mode == MODE_TWINKLE:
        rng = rng or random.Random()
        assignments: dict[str, list[str]] = {}
        for light in lights:
            assignments.setdefault(rng.choice(list(colors)), []).append(light)
        return assignments
    return rotation_assignments(lights, colors, offset)


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
