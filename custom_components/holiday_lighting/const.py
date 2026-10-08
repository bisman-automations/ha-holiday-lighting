"""Constants for the Holiday Lighting integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "holiday_lighting"

# Options keys
CONF_DEFAULT_LIGHTS: Final = "default_lights"
CONF_PRESETS: Final = "presets"
CONF_DEFAULT_COLORS: Final = "default_colors"
CONF_DEFAULT_COLOR_NAMES: Final = "default_color_names"
DEFAULT_HOLIDAY_ID: Final = "default"

# Per-holiday keys
CONF_NAME: Final = "name"
CONF_COLORS: Final = "colors"
CONF_COLOR_NAMES: Final = "color_names"
CONF_START: Final = "start"
CONF_END: Final = "end"
CONF_LIGHTS: Final = "lights"
CONF_MODE: Final = "mode"
CONF_INTERVAL: Final = "interval"
CONF_BRIGHTNESS: Final = "brightness"
CONF_TRANSITION: Final = "transition"

# Holiday kinds (how the dates are decided)
CONF_KIND: Final = "kind"
KIND_YEARLY: Final = "yearly"
KIND_NTH_WEEKDAY: Final = "nth_weekday"
KIND_EASTER: Final = "easter"
KIND_ADVENT: Final = "advent"
KIND_ONCE: Final = "once"
KIND_CALENDAR: Final = "calendar"
KINDS: Final = [
    KIND_YEARLY,
    KIND_NTH_WEEKDAY,
    KIND_EASTER,
    KIND_ADVENT,
    KIND_ONCE,
    KIND_CALENDAR,
]

CONF_MONTH: Final = "month"
CONF_WEEK: Final = "week"  # 1-4, or -1 for the last
CONF_WEEKDAY: Final = "weekday"  # 0 = Monday
CONF_DAYS_BEFORE: Final = "days_before"
CONF_DAYS_AFTER: Final = "days_after"
CONF_EASTER_OFFSET: Final = "easter_offset"  # days from Easter Sunday
CONF_ADVENT_OFFSET: Final = "advent_offset"  # days from the First Sunday of Advent
CONF_THROUGH_CHRISTMAS_EVE: Final = "through_christmas_eve"
CONF_START_DATE: Final = "start_date"
CONF_END_DATE: Final = "end_date"
CONF_CALENDAR: Final = "calendar"
CONF_KEYWORD: Final = "keyword"

# Per-holiday schedule overrides (off_time / on_duration reuse the option keys)
CONF_ALL_NIGHT: Final = "all_night"

MODE_ROTATE: Final = "rotate"  # Chase
MODE_STATIC: Final = "static"
MODE_CYCLE: Final = "cycle"
MODE_FADE: Final = "fade"
MODE_TWINKLE: Final = "twinkle"
MODES: Final = [MODE_ROTATE, MODE_STATIC, MODE_CYCLE, MODE_FADE, MODE_TWINKLE]

DEFAULT_INTERVAL: Final = 30
DEFAULT_TRANSITION: Final = 2

# Schedule (options) keys
CONF_USE_SCHEDULE: Final = "use_schedule"
CONF_DARK_SOURCE: Final = "dark_source"
CONF_SUN_ELEVATION: Final = "sun_elevation"
CONF_SUN_SOURCE: Final = "sun_source"
CONF_LUX_SENSOR: Final = "lux_sensor"
CONF_LUX_THRESHOLD: Final = "lux_threshold"
CONF_ON_DURATION: Final = "on_duration"
CONF_OFF_TIME: Final = "off_time"
CONF_WEEKEND_OFF_TIME: Final = "weekend_off_time"
CONF_RESPECT_MANUAL: Final = "respect_manual"

DARK_SUN: Final = "sun"
DARK_LUX: Final = "lux"
DARK_EITHER: Final = "either"
DARK_SOURCES: Final = [DARK_SUN, DARK_LUX, DARK_EITHER]

DEFAULT_SUN_ELEVATION: Final = -2.0
DEFAULT_LUX_THRESHOLD: Final = 20.0
DEFAULT_ON_DURATION: Final = {"hours": 5, "minutes": 0, "seconds": 0}
DEFAULT_OFF_TIME: Final = "23:00:00"

SUBENTRY_HOLIDAY: Final = "holiday"

# Controller states (reported by the status sensor)
STATUS_DISABLED: Final = "disabled"
STATUS_WAITING: Final = "waiting_for_dark"
STATUS_ON: Final = "on"
STATUS_DONE: Final = "done_for_tonight"
STATUS_NO_HOLIDAY: Final = "no_holiday"

# Theme select values
THEME_AUTO: Final = "auto"

# Service names
SERVICE_START: Final = "start"
SERVICE_STOP: Final = "stop"
SERVICE_ADVANCE: Final = "advance"
ATTR_HOLIDAY: Final = "holiday"

STORAGE_VERSION: Final = 1
