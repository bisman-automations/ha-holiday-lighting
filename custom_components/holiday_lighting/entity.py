"""Base entity for Holiday Lighting."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .controller import HolidayLightingController


class HolidayLightingEntity(Entity):
    """Shared device info and controller wiring."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: HolidayLightingController, key: str) -> None:
        """Initialise the entity."""
        self.controller = controller
        entry_id = controller.entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=controller.entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Update whenever the controller changes."""
        self.async_on_remove(
            self.controller.async_add_listener(self.async_write_ha_state)
        )
