"""Holiday Lighting: holiday color themes rotated across your lights."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_HOLIDAY,
    DOMAIN,
    SERVICE_ADVANCE,
    SERVICE_START,
    SERVICE_STOP,
)
from .controller import HolidayLightingController

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type HolidayLightingConfigEntry = ConfigEntry[HolidayLightingController]

START_SCHEMA = vol.Schema({vol.Optional(ATTR_HOLIDAY): cv.string})


def _controller(hass: HomeAssistant) -> HolidayLightingController:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="not_loaded"
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services."""

    async def handle_start(call: ServiceCall) -> None:
        controller = _controller(hass)
        holiday_id = None
        if name := call.data.get(ATTR_HOLIDAY):
            matches = [
                h.id
                for h in controller.holidays.values()
                if h.name.casefold() == name.casefold()
            ]
            if not matches:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_holiday",
                    translation_placeholders={"holiday": name},
                )
            holiday_id = matches[0]
        await controller.async_force_on(holiday_id)

    async def handle_stop(call: ServiceCall) -> None:
        await _controller(hass).async_force_off()

    async def handle_advance(call: ServiceCall) -> None:
        await _controller(hass).async_advance()

    hass.services.async_register(DOMAIN, SERVICE_START, handle_start, START_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_STOP, handle_stop)
    hass.services.async_register(DOMAIN, SERVICE_ADVANCE, handle_advance)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: HolidayLightingConfigEntry
) -> bool:
    """Set up Holiday Lighting from a config entry."""
    controller = HolidayLightingController(hass, entry)
    await controller.async_setup()
    entry.runtime_data = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    async def _started(_hass: HomeAssistant) -> None:
        await controller.async_start()

    entry.async_on_unload(async_at_started(hass, _started))
    return True


async def _async_reload(hass: HomeAssistant, entry: HolidayLightingConfigEntry) -> None:
    """Reload when options or holidays change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: HolidayLightingConfigEntry
) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_unload()
    return unloaded
