"""Enable switch for Holiday Lighting."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HolidayLightingConfigEntry
from .entity import HolidayLightingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HolidayLightingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch."""
    async_add_entities([HolidayLightingSwitch(entry.runtime_data, "enabled")])


class HolidayLightingSwitch(HolidayLightingEntity, SwitchEntity):
    """Arms the nightly schedule (or, without a schedule, runs the lights)."""

    @property
    def is_on(self) -> bool:
        """Whether holiday lighting is enabled."""
        return self.controller.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable holiday lighting."""
        await self.controller.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable and restore the lights."""
        await self.controller.async_set_enabled(False)
