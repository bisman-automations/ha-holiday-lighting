"""Config, options and holiday (subentry) flows for Holiday Lighting."""

from __future__ import annotations

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
from homeassistant.helpers.selector import (
    BooleanSelector,
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
    CONF_BRIGHTNESS,
    CONF_COLOR_NAMES,
    CONF_COLORS,
    CONF_DARK_SOURCE,
    CONF_DEFAULT_LIGHTS,
    CONF_END,
    CONF_INTERVAL,
    CONF_LIGHTS,
    CONF_LUX_SENSOR,
    CONF_LUX_THRESHOLD,
    CONF_MODE,
    CONF_NAME,
    CONF_OFF_TIME,
    CONF_ON_DURATION,
    CONF_PRESETS,
    CONF_START,
    CONF_SUN_ELEVATION,
    CONF_TRANSITION,
    CONF_USE_SCHEDULE,
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
    MODE_ROTATE,
    MODES,
    SUBENTRY_HOLIDAY,
)
from .presets import PRESETS
from .schedule import format_month_day, parse_colors, parse_month_day, rgb_to_hex

CONF_PRESET = "preset"
PRESET_CUSTOM = "custom"

LIGHTS_SELECTOR = EntitySelector(
    EntitySelectorConfig(domain=LIGHT_DOMAIN, multiple=True, reorder=True)
)

# Each color is an item with a picker and an optional name; the list can be
# dragged into the order the colors rotate in.
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

DEFAULT_SCHEDULE: dict[str, Any] = {
    CONF_USE_SCHEDULE: True,
    CONF_DARK_SOURCE: DARK_SUN,
    CONF_SUN_ELEVATION: DEFAULT_SUN_ELEVATION,
    CONF_LUX_THRESHOLD: DEFAULT_LUX_THRESHOLD,
    CONF_ON_DURATION: DEFAULT_ON_DURATION,
    CONF_OFF_TIME: DEFAULT_OFF_TIME,
}


def _suggested(values: dict[str, Any], key: str) -> dict[str, Any]:
    if key in values and values[key] is not None:
        return {"suggested_value": values[key]}
    return {}


def _schedule_schema(values: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_USE_SCHEDULE, default=values.get(CONF_USE_SCHEDULE, True)
            ): BooleanSelector(),
            vol.Required(
                CONF_DARK_SOURCE, default=values.get(CONF_DARK_SOURCE, DARK_SUN)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=DARK_SOURCES,
                    translation_key=CONF_DARK_SOURCE,
                    mode=SelectSelectorMode.LIST,
                )
            ),
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
        }
    )


def _validate_schedule(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if user_input[CONF_DARK_SOURCE] in (DARK_LUX, DARK_EITHER) and not user_input.get(
        CONF_LUX_SENSOR
    ):
        errors[CONF_LUX_SENSOR] = "lux_sensor_required"
    return errors


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


def parse_color_rgb(hex_color: str) -> tuple[int, int, int]:
    """Hex string -> RGB tuple."""
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _holiday_schema(values: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=values.get(CONF_NAME, "")): TextSelector(),
            vol.Required(
                CONF_START, default=values.get(CONF_START, "")
            ): TextSelector(),
            vol.Required(CONF_END, default=values.get(CONF_END, "")): TextSelector(),
            vol.Required(CONF_COLORS, default=_color_items(values)): COLORS_SELECTOR,
            vol.Optional(
                CONF_LIGHTS, description=_suggested(values, CONF_LIGHTS)
            ): LIGHTS_SELECTOR,
            vol.Required(
                CONF_MODE, default=values.get(CONF_MODE, MODE_ROTATE)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=MODES,
                    translation_key=CONF_MODE,
                    mode=SelectSelectorMode.LIST,
                )
            ),
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
        }
    )


def _normalise_holiday(
    user_input: dict[str, Any], taken_names: set[str]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate and normalise holiday form input."""
    errors: dict[str, str] = {}
    data = dict(user_input)
    data[CONF_NAME] = data[CONF_NAME].strip()
    if not data[CONF_NAME]:
        errors[CONF_NAME] = "name_required"
    elif data[CONF_NAME].casefold() in taken_names:
        errors[CONF_NAME] = "name_exists"
    for key in (CONF_START, CONF_END):
        try:
            data[key] = format_month_day(parse_month_day(data[key]))
        except ValueError:
            errors[key] = "invalid_date"
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
    return data, errors


def _preset_data(key: str, lights: list[str]) -> dict[str, Any]:
    preset = PRESETS[key]
    return {
        CONF_NAME: preset["name"],
        CONF_START: preset["start"],
        CONF_END: preset["end"],
        CONF_COLORS: list(preset["colors"]),
        CONF_COLOR_NAMES: list(preset["color_names"]),
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
                        title=PRESETS[key]["name"],
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

    def _taken_names(self, exclude: str | None = None) -> set[str]:
        entry = self._get_entry()
        return {
            subentry.title.casefold()
            for subentry_id, subentry in entry.subentries.items()
            if subentry.subentry_type == SUBENTRY_HOLIDAY and subentry_id != exclude
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start from a preset or from scratch."""
        if user_input is not None:
            preset = user_input[CONF_PRESET]
            lights = self._get_entry().options.get(CONF_DEFAULT_LIGHTS, [])
            if preset == PRESET_CUSTOM:
                self._prefill = {CONF_LIGHTS: lights}
            else:
                self._prefill = _preset_data(preset, lights)
            return await self.async_step_holiday()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRESET, default=PRESET_CUSTOM): SelectSelector(
                        SelectSelectorConfig(
                            options=[PRESET_CUSTOM, *PRESETS],
                            translation_key=CONF_PRESET,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_holiday(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Holiday details."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _normalise_holiday(user_input, self._taken_names())
            if not errors:
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="holiday",
            data_schema=_holiday_schema(user_input or self._prefill),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing holiday."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _normalise_holiday(
                user_input, self._taken_names(exclude=subentry.subentry_id)
            )
            if not errors:
                return self.async_update_and_abort(
                    self._get_entry(), subentry, title=data[CONF_NAME], data=data
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_holiday_schema(user_input or dict(subentry.data)),
            errors=errors,
        )
