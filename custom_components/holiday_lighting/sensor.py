"""Status sensors for Holiday Lighting."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HolidayLightingConfigEntry
from .const import (
    STATUS_DISABLED,
    STATUS_DONE,
    STATUS_NO_HOLIDAY,
    STATUS_ON,
    STATUS_WAITING,
)
from .controller import HolidayLightingController
from .entity import HolidayLightingEntity
from .schedule import LIGHT_COLOR

LIGHT_COLOR_PREFIX = "color_"
NO_HOLIDAY = "No holiday"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HolidayLightingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    controller = entry.runtime_data
    light_sensors = [
        LightColorSensor(hass, controller, entity_id)
        for entity_id in controller.all_lights
    ]
    # Drop color sensors for lights no holiday uses anymore.
    keep = {sensor.unique_id for sensor in light_sensors}
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_{LIGHT_COLOR_PREFIX}"
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = registry_entry.unique_id
        if unique_id.startswith(prefix) and unique_id not in keep:
            registry.async_remove(registry_entry.entity_id)
    async_add_entities(
        [
            StatusSensor(controller, "status"),
            ActiveHolidaySensor(controller, "active_holiday"),
            LightsOffSensor(controller, "lights_off_at"),
            *light_sensors,
        ]
    )


class StatusSensor(HolidayLightingEntity, SensorEntity):
    """What the lights are doing right now."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        STATUS_DISABLED,
        STATUS_WAITING,
        STATUS_ON,
        STATUS_DONE,
        STATUS_NO_HOLIDAY,
    ]

    @property
    def native_value(self) -> str:
        """Current status."""
        return self.controller.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Schedule details."""
        controller = self.controller
        return {
            "dark": controller.is_dark(),
            "sun_elevation": round(controller.current_sun_elevation(), 2),
            "lights_on_at": controller.on_at,
            "hard_off_tonight": controller.hard_off_tonight(),
            "manually_changed": sorted(controller.night.overridden),
        }


class ActiveHolidaySensor(HolidayLightingEntity, SensorEntity):
    """The holiday showing now, or the one picked for tonight."""

    @property
    def native_value(self) -> str:
        """Holiday name, "Default colors", or "No holiday"."""
        holiday = self.controller.shown_holiday()
        return holiday.name if holiday else NO_HOLIDAY

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Colors, lights, whether it's showing, and the next holiday."""
        controller = self.controller
        attrs: dict[str, Any] = {"showing": controller.running is not None}
        if holiday := controller.shown_holiday():
            attrs["colors"] = holiday.colors
            attrs["color_names"] = holiday.color_names
            attrs["lights"] = holiday.lights
            attrs["mode"] = holiday.mode
            attrs["white_lights"] = [
                entity_id
                for entity_id in holiday.lights
                if controller.light_kind(entity_id) != LIGHT_COLOR
            ]
        if upcoming := controller.upcoming():
            attrs["next_holiday"] = upcoming[0].name
            attrs["next_holiday_start"] = upcoming[1].isoformat()
        return attrs


class LightsOffSensor(HolidayLightingEntity, SensorEntity):
    """When tonight's lights will turn off."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Tonight's off time, or the next night's once tonight is done."""
        return self.controller.next_off()


class LightColorSensor(HolidayLightingEntity, SensorEntity):
    """The color one light is showing right now."""

    # These change on every color step; keep the details out of history.
    _unrecorded_attributes = frozenset(
        {"light", "hex", "rgb_color", "shown_as", "holiday"}
    )

    def __init__(
        self,
        hass: HomeAssistant,
        controller: HolidayLightingController,
        light_entity_id: str,
    ) -> None:
        """Initialise for one light."""
        super().__init__(controller, "light_color")
        self.light_entity_id = light_entity_id
        self._attr_unique_id = (
            f"{controller.entry.entry_id}_{LIGHT_COLOR_PREFIX}{light_entity_id}"
        )
        state = hass.states.get(light_entity_id)
        light_name = (
            state.name
            if state is not None
            else light_entity_id.split(".", 1)[-1].replace("_", " ").title()
        )
        self._attr_translation_placeholders = {"light": light_name}

    async def async_added_to_hass(self) -> None:
        """Update on every color step, not just status changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.controller.async_add_light_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> str:
        """The color name, or Off / Manual."""
        what, details = self.controller.light_color(self.light_entity_id)
        if details is not None:
            return details["name"]
        return "Manual" if what == "manual" else "Off"

    @property
    def icon(self) -> str:
        """Lit bulb while showing a color."""
        what, _details = self.controller.light_color(self.light_entity_id)
        if what == "color":
            return "mdi:lightbulb-on"
        return (
            "mdi:lightbulb-alert-outline"
            if what == "manual"
            else "mdi:lightbulb-outline"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Hex, RGB, how it's shown, and the holiday."""
        attrs: dict[str, Any] = {"light": self.light_entity_id}
        what, details = self.controller.light_color(self.light_entity_id)
        if details is not None:
            attrs.update(details)
            attrs.pop("name", None)
        return attrs
