"""The Holiday Lights sidebar panel."""

import json
from pathlib import Path

from custom_components.holiday_lighting.const import DOMAIN
from custom_components.holiday_lighting.panel import PANEL_PATH
from homeassistant.components.frontend import DATA_PANELS
from homeassistant.core import HomeAssistant

from .test_init import _entry, _start

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "holiday_lighting"


def _version() -> str:
    return json.loads((COMPONENT_DIR / "manifest.json").read_text())["version"]


async def test_sidebar_panel_added_and_removed(hass: HomeAssistant) -> None:
    """Setting up adds the panel to the sidebar; unloading removes it."""
    entry = _entry()
    await _start(hass, entry)

    panels = hass.data[DATA_PANELS]
    assert PANEL_PATH in panels
    panel = panels[PANEL_PATH]
    assert panel.sidebar_title == "Holiday Lights"
    assert panel.sidebar_icon == "mdi:string-lights"
    assert panel.require_admin is False
    assert f"holiday-lighting-panel.js?v={_version()}" in json.dumps(
        panel.config, default=str
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert PANEL_PATH not in hass.data[DATA_PANELS]


async def test_panel_script_is_served(hass: HomeAssistant, hass_client) -> None:
    """The panel's web component is available from the integration's static path."""
    entry = _entry()
    await _start(hass, entry)
    client = await hass_client()

    response = await client.get(
        f"/{DOMAIN}_static/holiday-lighting-panel.js?v={_version()}"
    )
    assert response.status == 200
    body = await response.text()
    assert 'customElements.define("holiday-lighting-panel"' in body
    assert "Loading holiday lights" in body
