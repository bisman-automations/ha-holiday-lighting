"""Diagnostics for Holiday Lighting."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import HolidayLightingConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HolidayLightingConfigEntry
) -> dict[str, Any]:
    """Settings, holidays and live state, for bug reports."""
    controller = entry.runtime_data
    return {
        "options": dict(entry.options),
        "holidays": [
            {"id": subentry_id, "title": subentry.title, **dict(subentry.data)}
            for subentry_id, subentry in entry.subentries.items()
        ],
        "state": controller.diagnostics(),
    }
