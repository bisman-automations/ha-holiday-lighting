"""Config, options and holiday (subentry) flows for Holiday Lighting."""

from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateSelector,
    DurationSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    ObjectSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)

from .const import (
    CONF_ADVENT_OFFSET,
    CONF_ALL_NIGHT,
    CONF_BRIGHTNESS,
    CONF_CALENDAR,
    CONF_COLOR_NAMES,
    CONF_COLORS,
    CONF_DARK_SOURCE,
    CONF_DAYS_AFTER,
    CONF_DAYS_BEFORE,
    CONF_DEFAULT_LIGHTS,
    CONF_EASTER_OFFSET,
    CONF_END,
    CONF_END_DATE,
    CONF_INTERVAL,
    CONF_KEYWORD,
    CONF_KIND,
    CONF_LIGHTS,
    CONF_LUX_SENSOR,
    CONF_LUX_THRESHOLD,
    CONF_MODE,
    CONF_MONTH,
    CONF_NAME,
    CONF_OFF_TIME,
    CONF_ON_DURATION,
    CONF_PRESETS,
    CONF_RESPECT_MANUAL,
    CONF_START,
    CONF_START_DATE,
    CONF_SUN_ELEVATION,
    CONF_SUN_SOURCE,
    CONF_THROUGH_CHRISTMAS_EVE,
    CONF_TRANSITION,
    CONF_USE_SCHEDULE,
    CONF_WEEK,
    CONF_WEEKDAY,
    CONF_WEEKEND_OFF_TIME,
    DARK_EITHER,
    DARK_LUX,
    DARK_SOURCES,
    DARK_SUN,
    DEFAULT_INTERVAL,
    DEFAULT_LUX_THRESHOLD,
    DEFAULT_OFF_TIME,
    DEFAULT_ON_DURATION,
    DEFAULT_SUN_ELEVATION,
    DEFAULT_TRANSITION,
    DOMAIN,
    KIND_ADVENT,
    KIND_CALENDAR,
    KIND_EASTER,
    KIND_NTH_WEEKDAY,
    KIND_ONCE,
    KIND_YEARLY,
    KINDS,
    MODE_ROTATE,
    MODES,
    SUBENTRY_HOLIDAY,
)
from .presets import PRESETS
from .schedule import format_month_day, parse_colors, parse_month_day, rgb_to_hex

CONF_PRESET = "preset"
PRESET_CUSTOM = "custom"
SECTION_SCHEDULE = "schedule_override"
WEEK_LAST = "last"

LIGHTS_SELECTOR = EntitySelector(
    EntitySelectorConfig(domain=LIGHT_DOMAIN, multiple=True, reorder=True)
)

# Each color is an item with a picker and an optional name; the list can be
# dragged into the order the colors rotate in. Field selectors must be plain
# dicts: the object selector's validator does not accept Selector instances.
FIELD_COLOR = "color"
FIELD_COLOR_NAME = "name"
COLORS_SELECTOR = ObjectSelector(
    ObjectSelectorConfig(
        multiple=True,
        label_field=FIELD_COLOR_NAME,
        translation_key="color_list",
        fields={
            FIELD_COLOR_NAME: {"selector": {"text": {}}, "required": False},
            FIELD_COLOR: {"selector": {"color_rgb": {}}, "required": True},
        },
    )
)

DAYS_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=0, max=60, step=1, unit_of_measurement="days", mode=NumberSelectorMode.BOX
    )
)

EASTER_OFFSET_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=-60, max=90, step=1, unit_of_measurement="days", mode=NumberSelectorMode.BOX
    )
)

DEFAULT_SCHEDULE: dict[str, Any] = {
    CONF_USE_SCHEDULE: True,
    CONF_DARK_SOURCE: DARK_SUN,
    CONF_SUN_ELEVATION: DEFAULT_SUN_ELEVATION,
    CONF_LUX_THRESHOLD: DEFAULT_LUX_THRESHOLD,
    CONF_ON_DURATION: DEFAULT_ON_DURATION,
    CONF_OFF_TIME: DEFAULT_OFF_TIME,
    CONF_RESPECT_MANUAL: True,
}


def _suggested(values: dict[str, Any], key: str) -> dict[str, Any]:
    if key in values and values[key] is not None:
        return {"suggested_value": values[key]}
    return {}


def _select(options: list[str], key: str, *, dropdown: bool = False) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            translation_key=key,
            mode=SelectSelectorMode.DROPDOWN if dropdown else SelectSelectorMode.LIST,
        )
    )


# --- Schedule (setup + options) ----------------------------------------------


def _schedule_schema(values: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_USE_SCHEDULE, default=values.get(CONF_USE_SCHEDULE, True)
            ): BooleanSelector(),
            vol.Required(
                CONF_DARK_SOURCE, default=values.get(CONF_DARK_SOURCE, DARK_SUN)
            ): _select(DARK_SOURCES, CONF_DARK_SOURCE),
            vol.Required(
                CONF_SUN_ELEVATION,
                default=values.get(CONF_SUN_ELEVATION, DEFAULT_SUN_ELEVATION),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=-18,
                    max=10,
                    step=0.5,
                    unit_of_measurement="°",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_SUN_SOURCE, description=_suggested(values, CONF_SUN_SOURCE)
            ): EntitySelector(EntitySelectorConfig(domain=["sun", "sensor"])),
            vol.Optional(
                CONF_LUX_SENSOR, description=_suggested(values, CONF_LUX_SENSOR)
            ): EntitySelector(
                EntitySelectorConfig(
                    domain="sensor", device_class=SensorDeviceClass.ILLUMINANCE
                )
            ),
            vol.Required(
                CONF_LUX_THRESHOLD,
                default=values.get(CONF_LUX_THRESHOLD, DEFAULT_LUX_THRESHOLD),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=2000,
                    step=1,
                    unit_of_measurement="lx",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_ON_DURATION, description=_suggested(values, CONF_ON_DURATION)
            ): DurationSelector(),
            vol.Optional(
                CONF_OFF_TIME, description=_suggested(values, CONF_OFF_TIME)
            ): TimeSelector(),
            vol.Optional(
                CONF_WEEKEND_OFF_TIME,
                description=_suggested(values, CONF_WEEKEND_OFF_TIME),
            ): TimeSelector(),
            vol.Required(
                CONF_RESPECT_MANUAL, default=values.get(CONF_RESPECT_MANUAL, True)
            ): BooleanSelector(),
        }
    )


def _validate_schedule(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if user_input[CONF_DARK_SOURCE] in (DARK_LUX, DARK_EITHER) and not user_input.get(
        CONF_LUX_SENSOR
    ):
        errors[CONF_LUX_SENSOR] = "lux_sensor_required"
    return errors


# --- Holidays ----------------------------------------------------------------


def parse_color_rgb(hex_color: str) -> tuple[int, int, int]:
    """Hex string -> RGB tuple."""
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _color_items(values: dict[str, Any]) -> list[dict[str, Any]]:
    """Stored hex colors (plus names) -> items for the color list selector."""
    colors = values.get(CONF_COLORS) or []
    if colors and isinstance(colors[0], dict):
        return list(colors)  # Already form items (re-showing after an error)
    names = values.get(CONF_COLOR_NAMES) or []
    items = []
    for index, hex_color in enumerate(colors):
        name = names[index] if index < len(names) and names[index] else hex_color
        items.append(
            {FIELD_COLOR_NAME: name, FIELD_COLOR: list(parse_color_rgb(hex_color))}
        )
    return items


def _dates_schema(kind: str, values: dict[str, Any]) -> dict[Any, Any]:
    """Fields that decide when a holiday of this kind is active."""
    if kind == KIND_YEARLY:
        return {
            vol.Required(
                CONF_START, default=values.get(CONF_START, "")
            ): TextSelector(),
            vol.Required(CONF_END, default=values.get(CONF_END, "")): TextSelector(),
        }
    days = {
        vol.Required(
            CONF_DAYS_BEFORE, default=values.get(CONF_DAYS_BEFORE, 0)
        ): DAYS_SELECTOR,
        vol.Required(
            CONF_DAYS_AFTER, default=values.get(CONF_DAYS_AFTER, 0)
        ): DAYS_SELECTOR,
    }
    if kind == KIND_NTH_WEEKDAY:
        week = values.get(CONF_WEEK, 1)
        return {
            vol.Required(
                CONF_WEEK, default=WEEK_LAST if str(week) == "-1" else str(week)
            ): _select(["1", "2", "3", "4", WEEK_LAST], CONF_WEEK, dropdown=True),
            vol.Required(
                CONF_WEEKDAY, default=str(values.get(CONF_WEEKDAY, 0))
            ): _select([str(d) for d in range(7)], CONF_WEEKDAY, dropdown=True),
            vol.Required(CONF_MONTH, default=str(values.get(CONF_MONTH, 1))): _select(
                [str(m) for m in range(1, 13)], CONF_MONTH, dropdown=True
            ),
            **days,
        }
    if kind == KIND_EASTER:
        return {
            vol.Required(
                CONF_EASTER_OFFSET, default=values.get(CONF_EASTER_OFFSET, 0)
            ): EASTER_OFFSET_SELECTOR,
            **days,
        }
    if kind == KIND_ADVENT:
        return {
            vol.Required(
                CONF_ADVENT_OFFSET, default=values.get(CONF_ADVENT_OFFSET, 0)
            ): EASTER_OFFSET_SELECTOR,
            **days,
            vol.Optional(
                CONF_THROUGH_CHRISTMAS_EVE,
                default=bool(values.get(CONF_THROUGH_CHRISTMAS_EVE, False)),
            ): BooleanSelector(),
        }
    if kind == KIND_ONCE:
        return {
            vol.Required(
                CONF_START_DATE, default=values.get(CONF_START_DATE, vol.UNDEFINED)
            ): DateSelector(),
            vol.Required(
                CONF_END_DATE, default=values.get(CONF_END_DATE, vol.UNDEFINED)
            ): DateSelector(),
        }
    return {
        vol.Required(
            CONF_CALENDAR, default=values.get(CONF_CALENDAR, vol.UNDEFINED)
        ): EntitySelector(EntitySelectorConfig(domain="calendar")),
        vol.Optional(CONF_KEYWORD, description=_suggested(values, CONF_KEYWORD)): (
            TextSelector()
        ),
    }


def _section_default(override: dict[str, Any]) -> dict[str, Any]:
    """Current override values for the collapsed schedule section.

    The frontend fills a section from its default rather than from the
    fields inside it, so the default has to carry every current value.
    """
    default: dict[str, Any] = {CONF_ALL_NIGHT: bool(override.get(CONF_ALL_NIGHT))}
    for key in (CONF_ON_DURATION, CONF_OFF_TIME):
        if override.get(key):
            default[key] = override[key]
    return default


def _holiday_schema(kind: str, values: dict[str, Any]) -> vol.Schema:
    override = values.get(SECTION_SCHEDULE) or values
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=values.get(CONF_NAME, "")): TextSelector(),
            **_dates_schema(kind, values),
            vol.Required(CONF_COLORS, default=_color_items(values)): COLORS_SELECTOR,
            vol.Optional(
                CONF_LIGHTS, description=_suggested(values, CONF_LIGHTS)
            ): LIGHTS_SELECTOR,
            vol.Required(
                CONF_MODE, default=values.get(CONF_MODE, MODE_ROTATE)
            ): _select(MODES, CONF_MODE),
            vol.Required(
                CONF_INTERVAL, default=values.get(CONF_INTERVAL, DEFAULT_INTERVAL)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=3600,
                    step=1,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_BRIGHTNESS, description=_suggested(values, CONF_BRIGHTNESS)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=100,
                    step=1,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                CONF_TRANSITION,
                default=values.get(CONF_TRANSITION, DEFAULT_TRANSITION),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=60,
                    step=0.5,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(SECTION_SCHEDULE, default=_section_default(override)): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_ALL_NIGHT,
                            default=bool(override.get(CONF_ALL_NIGHT, False)),
                        ): BooleanSelector(),
                        vol.Optional(
                            CONF_ON_DURATION,
                            description=_suggested(override, CONF_ON_DURATION),
                        ): DurationSelector(),
                        vol.Optional(
                            CONF_OFF_TIME,
                            description=_suggested(override, CONF_OFF_TIME),
                        ): TimeSelector(),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def _normalise_holiday(
    kind: str, user_input: dict[str, Any], taken_names: set[str]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate form input and turn it into stored holiday data."""
    errors: dict[str, str] = {}
    data = {k: v for k, v in user_input.items() if k != SECTION_SCHEDULE}
    data[CONF_KIND] = kind
    data[CONF_NAME] = data[CONF_NAME].strip()
    if not data[CONF_NAME]:
        errors[CONF_NAME] = "name_required"
    elif data[CONF_NAME].casefold() in taken_names:
        errors[CONF_NAME] = "name_exists"

    if kind == KIND_YEARLY:
        for key in (CONF_START, CONF_END):
            try:
                data[key] = format_month_day(parse_month_day(data[key]))
            except ValueError:
                errors[key] = "invalid_date"
    elif kind == KIND_NTH_WEEKDAY:
        data[CONF_WEEK] = -1 if data[CONF_WEEK] == WEEK_LAST else int(data[CONF_WEEK])
        data[CONF_WEEKDAY] = int(data[CONF_WEEKDAY])
        data[CONF_MONTH] = int(data[CONF_MONTH])
    elif kind == KIND_ONCE:
        if date.fromisoformat(data[CONF_END_DATE]) < date.fromisoformat(
            data[CONF_START_DATE]
        ):
            errors[CONF_END_DATE] = "end_before_start"
    elif kind == KIND_CALENDAR:
        data[CONF_KEYWORD] = (data.get(CONF_KEYWORD) or "").strip()
    for key in (
        CONF_DAYS_BEFORE,
        CONF_DAYS_AFTER,
        CONF_EASTER_OFFSET,
        CONF_ADVENT_OFFSET,
    ):
        if key in data:
            data[key] = int(data[key])

    colors = data.get(CONF_COLORS) or []
    if isinstance(colors, str):
        # Text input (older forms, tests): "red, #00FF00"
        try:
            data[CONF_COLORS] = parse_colors(colors)
            data[CONF_COLOR_NAMES] = list(data[CONF_COLORS])
        except ValueError:
            errors[CONF_COLORS] = "invalid_colors"
    elif not colors:
        errors[CONF_COLORS] = "colors_required"
    else:
        hexes = [rgb_to_hex(item[FIELD_COLOR]) for item in colors]
        data[CONF_COLORS] = hexes
        data[CONF_COLOR_NAMES] = [
            (item.get(FIELD_COLOR_NAME) or "").strip() or hexes[index]
            for index, item in enumerate(colors)
        ]
    data[CONF_INTERVAL] = int(data[CONF_INTERVAL])
    if CONF_BRIGHTNESS in data:
        data[CONF_BRIGHTNESS] = int(data[CONF_BRIGHTNESS])

    override = user_input.get(SECTION_SCHEDULE) or {}
    if override.get(CONF_ALL_NIGHT):
        data[CONF_ALL_NIGHT] = True
    for key in (CONF_ON_DURATION, CONF_OFF_TIME):
        if override.get(key):
            data[key] = override[key]
    return data, errors


def _preset_data(key: str, lights: list[str]) -> dict[str, Any]:
    return {
        **PRESETS[key],
        CONF_PRESET: key,
        CONF_LIGHTS: list(lights),
        CONF_MODE: MODE_ROTATE,
        CONF_INTERVAL: DEFAULT_INTERVAL,
        CONF_TRANSITION: DEFAULT_TRANSITION,
    }


class HolidayLightingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup: default lights, starter holidays, nightly schedule."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._setup: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options flow for the schedule and default lights."""
        return HolidayLightingOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Holidays are subentries."""
        return {SUBENTRY_HOLIDAY: HolidaySubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick default lights and starter holidays."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            self._setup = user_input
            return await self.async_step_schedule()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DEFAULT_LIGHTS): LIGHTS_SELECTOR,
                    vol.Optional(CONF_PRESETS, default=[]): SelectSelector(
                        SelectSelectorConfig(
                            options=list(PRESETS),
                            translation_key=CONF_PRESET,
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """When the lights come on and go off."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_schedule(user_input)
            if not errors:
                lights = self._setup.get(CONF_DEFAULT_LIGHTS, [])
                subentries: list[ConfigSubentryData] = [
                    ConfigSubentryData(
                        data=_preset_data(key, lights),
                        subentry_type=SUBENTRY_HOLIDAY,
                        title=PRESETS[key][CONF_NAME],
                        unique_id=None,
                    )
                    for key in self._setup.get(CONF_PRESETS, [])
                ]
                return self.async_create_entry(
                    title="Holiday Lighting",
                    data={},
                    options={CONF_DEFAULT_LIGHTS: lights, **user_input},
                    subentries=subentries,
                )

        return self.async_show_form(
            step_id="schedule",
            data_schema=_schedule_schema(user_input or DEFAULT_SCHEDULE),
            errors=errors,
        )


class HolidayLightingOptionsFlow(OptionsFlow):
    """Change the schedule and default lights."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_schedule(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)

        values = user_input or dict(self.config_entry.options)
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DEFAULT_LIGHTS,
                    description=_suggested(values, CONF_DEFAULT_LIGHTS),
                ): LIGHTS_SELECTOR,
            }
        ).extend(_schedule_schema(values).schema)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


class HolidaySubentryFlow(ConfigSubentryFlow):
    """Add or edit a holiday."""

    def __init__(self) -> None:
        """Initialise the flow."""
        self._prefill: dict[str, Any] = {}
        self._kind = KIND_YEARLY
        self._preset: str | None = None

    def _taken_names(self, exclude: str | None = None) -> set[str]:
        entry = self._get_entry()
        return {
            subentry.title.casefold()
            for subentry_id, subentry in entry.subentries.items()
            if subentry.subentry_type == SUBENTRY_HOLIDAY and subentry_id != exclude
        }

    def _used_presets(self) -> set[str]:
        """Presets that already have a holiday.

        Holidays remember the preset they came from; ones added before that
        was stored are matched by name.
        """
        by_name = {preset[CONF_NAME].casefold(): key for key, preset in PRESETS.items()}
        used: set[str] = set()
        for subentry in self._get_entry().subentries.values():
            if subentry.subentry_type != SUBENTRY_HOLIDAY:
                continue
            if key := subentry.data.get(CONF_PRESET):
                used.add(key)
            elif key := by_name.get(subentry.title.casefold()):
                used.add(key)
        return used

    def _default_lights(self) -> list[str]:
        return list(self._get_entry().options.get(CONF_DEFAULT_LIGHTS, []))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start from a preset or from scratch."""
        if user_input is not None:
            preset = user_input[CONF_PRESET]
            if preset == PRESET_CUSTOM or preset not in PRESETS:
                return await self.async_step_kind()
            self._preset = preset
            self._prefill = _preset_data(preset, self._default_lights())
            self._kind = self._prefill[CONF_KIND]
            return await self.async_step_holiday()

        used = self._used_presets()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRESET, default=PRESET_CUSTOM): _select(
                        [PRESET_CUSTOM, *(k for k in PRESETS if k not in used)],
                        CONF_PRESET,
                        dropdown=True,
                    )
                }
            ),
        )

    async def async_step_kind(self, _: Any = None) -> SubentryFlowResult:
        """Choose how a custom holiday's dates work."""
        return self.async_show_menu(step_id="kind", menu_options=KINDS)

    async def _async_custom(self, kind: str) -> SubentryFlowResult:
        self._kind = kind
        self._prefill = {CONF_LIGHTS: self._default_lights()}
        return await self.async_step_holiday()

    async def async_step_yearly(self, _: Any = None) -> SubentryFlowResult:
        """Same dates every year."""
        return await self._async_custom(KIND_YEARLY)

    async def async_step_nth_weekday(self, _: Any = None) -> SubentryFlowResult:
        """Nth weekday of a month."""
        return await self._async_custom(KIND_NTH_WEEKDAY)

    async def async_step_easter(self, _: Any = None) -> SubentryFlowResult:
        """Around Easter."""
        return await self._async_custom(KIND_EASTER)

    async def async_step_advent(self, _: Any = None) -> SubentryFlowResult:
        """Relative to the First Sunday of Advent."""
        return await self._async_custom(KIND_ADVENT)

    async def async_step_once(self, _: Any = None) -> SubentryFlowResult:
        """A one-time event."""
        return await self._async_custom(KIND_ONCE)

    async def async_step_calendar(self, _: Any = None) -> SubentryFlowResult:
        """Whenever a calendar has an event."""
        return await self._async_custom(KIND_CALENDAR)

    async def async_step_holiday(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Holiday details."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _normalise_holiday(
                self._kind, user_input, self._taken_names()
            )
            if not errors:
                if self._preset:
                    data[CONF_PRESET] = self._preset
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="holiday",
            data_schema=_holiday_schema(self._kind, user_input or self._prefill),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing holiday."""
        subentry = self._get_reconfigure_subentry()
        kind = subentry.data.get(CONF_KIND, KIND_YEARLY)
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _normalise_holiday(
                kind, user_input, self._taken_names(exclude=subentry.subentry_id)
            )
            if not errors:
                if preset := subentry.data.get(CONF_PRESET):
                    data[CONF_PRESET] = preset
                return self.async_update_and_abort(
                    self._get_entry(), subentry, title=data[CONF_NAME], data=data
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_holiday_schema(kind, user_input or dict(subentry.data)),
            errors=errors,
        )
