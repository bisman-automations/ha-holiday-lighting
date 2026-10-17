"""The Holiday Lights sidebar panel."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

PANEL_PATH = "holiday-lighting"
PANEL_COMPONENT = "holiday-lighting-panel"
PANEL_TITLE = "Holiday Lights"
PANEL_ICON = "mdi:string-lights"
STATIC_URL = f"/{DOMAIN}_static"
_DIR = Path(__file__).parent
_STATIC_KEY = f"{DOMAIN}_static_registered"


async def async_setup_panel(hass: HomeAssistant) -> None:
    """Serve the panel script and add the sidebar entry."""
    if not hass.data.get(_STATIC_KEY):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(_DIR / "frontend"), True)]
        )
        hass.data[_STATIC_KEY] = True
    # The version in the URL makes browsers fetch the new script after an upgrade.
    version = (await async_get_integration(hass, DOMAIN)).version
    await async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/holiday-lighting-panel.js?v={version}",
        require_admin=False,
    )


def async_teardown_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar entry."""
    async_remove_panel(hass, PANEL_PATH, warn_if_unknown=False)
