"""Start, stop and next buttons for Holiday Lighting."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HolidayLightingConfigEntry
from .controller import HolidayLightingController
from .entity import HolidayLightingEntity


@dataclass(frozen=True, kw_only=True)
class HolidayButtonDescription(ButtonEntityDescription):
    """A button and what it does."""

    press: Callable[[HolidayLightingController], Awaitable[None]]


BUTTONS: tuple[HolidayButtonDescription, ...] = (
    HolidayButtonDescription(
        key="start", press=lambda controller: controller.async_force_on()
    ),
    HolidayButtonDescription(
        key="stop", press=lambda controller: controller.async_force_off()
    ),
    HolidayButtonDescription(
        key="next", press=lambda controller: controller.async_advance()
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HolidayLightingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    async_add_entities(
        HolidayLightingButton(entry.runtime_data, description)
        for description in BUTTONS
    )


class HolidayLightingButton(HolidayLightingEntity, ButtonEntity):
    """Run a Holiday Lighting action."""

    entity_description: HolidayButtonDescription

    def __init__(
        self,
        controller: HolidayLightingController,
        description: HolidayButtonDescription,
    ) -> None:
        """Initialise the button."""
        super().__init__(controller, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle the press."""
        await self.entity_description.press(self.controller)
