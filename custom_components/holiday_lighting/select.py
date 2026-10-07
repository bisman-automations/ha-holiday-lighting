"""Theme select for Holiday Lighting."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HolidayLightingConfigEntry
from .const import THEME_AUTO
from .entity import HolidayLightingEntity

AUTO_LABEL = "Auto"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HolidayLightingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select."""
    async_add_entities([HolidayThemeSelect(entry.runtime_data, "theme")])


class HolidayThemeSelect(HolidayLightingEntity, SelectEntity):
    """Pick a holiday, or Auto to follow the calendar."""

    @property
    def options(self) -> list[str]:
        """Auto plus every holiday name."""
        names = sorted(h.name for h in self.controller.holidays.values())
        return [AUTO_LABEL, *names]

    @property
    def current_option(self) -> str:
        """The selected theme."""
        holiday = self.controller.holidays.get(self.controller.theme)
        return holiday.name if holiday else AUTO_LABEL

    async def async_select_option(self, option: str) -> None:
        """Change the theme."""
        theme = THEME_AUTO
        for holiday in self.controller.holidays.values():
            if holiday.name == option:
                theme = holiday.id
                break
        await self.controller.async_set_theme(theme)
