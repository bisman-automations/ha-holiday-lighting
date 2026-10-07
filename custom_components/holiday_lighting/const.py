"""Constants for the Holiday Lighting integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "holiday_lighting"

# Options keys
CONF_DEFAULT_LIGHTS: Final = "default_lights"
CONF_PRESETS: Final = "presets"

# Per-holiday keys
CONF_NAME: Final = "name"
CONF_COLORS: Final = "colors"
CONF_START: Final = "start"
CONF_END: Final = "end"
CONF_LIGHTS: Final = "lights"
CONF_MODE: Final = "mode"
CONF_INTERVAL: Final = "interval"
CONF_BRIGHTNESS: Final = "brightness"
CONF_TRANSITION: Final = "transition"

MODE_ROTATE: Final = "rotate"
MODE_STATIC: Final = "static"
MODES: Final = [MODE_ROTATE, MODE_STATIC]

DEFAULT_INTERVAL: Final = 30
DEFAULT_TRANSITION: Final = 2

# Schedule (options) keys
CONF_USE_SCHEDULE: Final = "use_schedule"
CONF_DARK_SOURCE: Final = "dark_source"
CONF_SUN_ELEVATION: Final = "sun_elevation"
CONF_LUX_SENSOR: Final = "lux_sensor"
CONF_LUX_THRESHOLD: Final = "lux_threshold"
CONF_ON_DURATION: Final = "on_duration"
CONF_OFF_TIME: Final = "off_time"

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
