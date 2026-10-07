"""Status sensors for Holiday Lighting."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HolidayLightingConfigEntry
from .const import (
    STATUS_DISABLED,
    STATUS_DONE,
    STATUS_NO_HOLIDAY,
    STATUS_ON,
    STATUS_WAITING,
)
from .entity import HolidayLightingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HolidayLightingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    controller = entry.runtime_data
    async_add_entities(
        [
            StatusSensor(controller, "status"),
            ActiveHolidaySensor(controller, "active_holiday"),
            LightsOffSensor(controller, "lights_off_at"),
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
            "lights_on_at": controller.on_at,
            "hard_off_tonight": controller.hard_off_tonight(),
        }


class ActiveHolidaySensor(HolidayLightingEntity, SensorEntity):
    """The holiday currently showing (or selected for tonight)."""

    @property
    def native_value(self) -> str | None:
        """Holiday name."""
        running = self.controller.running
        return running.name if running else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Colors, lights and the next holiday."""
        attrs: dict[str, Any] = {}
        if running := self.controller.running:
            attrs["colors"] = running.colors
            attrs["lights"] = running.lights
            attrs["mode"] = running.mode
        if upcoming := self.controller.upcoming():
            attrs["next_holiday"] = upcoming[0].name
            attrs["next_holiday_start"] = upcoming[1].isoformat()
        return attrs


class LightsOffSensor(HolidayLightingEntity, SensorEntity):
    """When tonight's lights will turn off."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Scheduled off time."""
        return self.controller.deadline
