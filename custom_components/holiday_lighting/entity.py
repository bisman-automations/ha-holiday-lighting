"""Base entity for Holiday Lighting."""

from __future__ import annotations

from homeassistant.core import callback
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
            manufacturer="Holiday Lighting",
            model="Holiday light schedule",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Update whenever the controller changes."""
        self.async_on_remove(
            self.controller.async_add_listener(self.async_write_ha_state)
        )

    @callback
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Keep running when the entity ID is changed (Home Assistant 2026.11+).

        Nothing here is keyed on the entity ID, so the entity carries on as is.
        """
        parent = getattr(super(), "async_entity_id_changed", None)
        if parent is not None:
            parent(old_entity_id)
