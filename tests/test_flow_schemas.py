"""Every config, options and holiday form reaches the frontend intact.

Regression for Home Assistant 2026.10, which serializes forms with probatio
instead of voluptuous-serialize. Each form is fetched through the same HTTP
API the frontend uses, so the JSON checked here is exactly what a browser
gets on the Home Assistant release under test (the minimum, 2026.2, and the
newest). Every field must be a UI selector (or a section of selectors) so it
renders as a proper control rather than a bare text box.
"""

from __future__ import annotations

from http import HTTPStatus
import json
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.holiday_lighting.config_flow import (
    DEFAULT_SCHEDULE,
    _holiday_schema,
    _preset_data,
    _schedule_schema,
)
from custom_components.holiday_lighting.const import DOMAIN, KINDS
from custom_components.holiday_lighting.presets import PRESETS
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .flow_schema import serialize_schema

LIGHTS = ["light.porch", "light.tree"]
FLOW_API = "/api/config/config_entries"


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Holiday Lighting",
        data={},
        options={**DEFAULT_SCHEDULE, "default_lights": LIGHTS},
        subentries_data=[
            ConfigSubentryData(
                data=_preset_data("christmas", LIGHTS),
                subentry_type="holiday",
                title="Christmas",
                unique_id=None,
            )
        ],
    )


def assert_frontend_fields(fields: Any) -> None:
    """Fields are JSON, and each one is a selector or a section of selectors."""
    assert isinstance(fields, list) and fields
    json.dumps(fields)  # what the HTTP view sends; raises on anything odd
    for field in fields:
        assert isinstance(field, dict), field
        if field.get("type") == "expandable":
            assert_frontend_fields(field["schema"])
        else:
            assert "selector" in field, f"{field.get('name')} has no UI selector"


async def _client(hass: HomeAssistant, hass_client, entry=None):
    """An HTTP client for the flow API, the way the frontend talks to it.

    Everything that registers HTTP routes (the integration's frontend and
    panel dependencies, and the entry itself, which adds its panel) is set up
    first: the test client freezes the router when it starts.
    """
    for component in ("frontend", "panel_custom", "config"):
        assert await async_setup_component(hass, component, {})
    if entry is not None:
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return await hass_client()


async def _post(client, path: str, body: dict) -> dict:
    response = await client.post(path, json=body)
    assert response.status == HTTPStatus.OK, await response.text()
    return await response.json()


async def test_config_flow_steps(hass: HomeAssistant, hass_client) -> None:
    client = await _client(hass, hass_client)
    result = await _post(client, f"{FLOW_API}/flow", {"handler": DOMAIN})
    assert result["step_id"] == "user"
    assert_frontend_fields(result["data_schema"])

    flow = f"{FLOW_API}/flow/{result['flow_id']}"
    result = await _post(client, flow, {"default_lights": LIGHTS, "presets": []})
    assert result["step_id"] == "schedule"
    assert_frontend_fields(result["data_schema"])


async def test_options_flow_step(hass: HomeAssistant, hass_client) -> None:
    entry = _entry()
    client = await _client(hass, hass_client, entry)

    result = await _post(
        client, f"{FLOW_API}/options/flow", {"handler": entry.entry_id}
    )
    assert result["step_id"] == "init"
    fields = result["data_schema"]
    assert_frontend_fields(fields)
    names = {field["name"] for field in fields}
    assert {"default_lights", "default_colors", "sun_source"} <= names


async def test_holiday_subentry_steps(hass: HomeAssistant, hass_client) -> None:
    entry = _entry()
    client = await _client(hass, hass_client, entry)
    handler = [entry.entry_id, "holiday"]

    # Add from a preset.
    result = await _post(client, f"{FLOW_API}/subentries/flow", {"handler": handler})
    assert result["step_id"] == "user"
    assert_frontend_fields(result["data_schema"])
    result = await _post(
        client,
        f"{FLOW_API}/subentries/flow/{result['flow_id']}",
        {"preset": "halloween"},
    )
    assert result["step_id"] == "holiday"
    assert_frontend_fields(result["data_schema"])

    # Add a custom holiday of every kind.
    for kind in KINDS:
        result = await _post(
            client, f"{FLOW_API}/subentries/flow", {"handler": handler}
        )
        flow = f"{FLOW_API}/subentries/flow/{result['flow_id']}"
        result = await _post(client, flow, {"preset": "custom"})
        assert result["type"] == "menu"
        result = await _post(client, flow, {"next_step_id": kind})
        assert result["step_id"] == "holiday", kind
        assert_frontend_fields(result["data_schema"])

    # Edit the saved holiday.
    subentry_id = next(iter(entry.subentries))
    result = await _post(
        client,
        f"{FLOW_API}/subentries/flow",
        {"handler": handler, "subentry_id": subentry_id, "source": "reconfigure"},
    )
    assert result["step_id"] == "reconfigure"
    assert_frontend_fields(result["data_schema"])


@pytest.mark.parametrize("preset", list(PRESETS))
def test_every_preset_form(preset: str) -> None:
    data = _preset_data(preset, LIGHTS)
    assert_frontend_fields(serialize_schema(_holiday_schema(data["kind"], data)))


@pytest.mark.parametrize("kind", KINDS)
def test_every_custom_kind_form(kind: str) -> None:
    assert_frontend_fields(serialize_schema(_holiday_schema(kind, {"lights": LIGHTS})))


def test_schedule_form() -> None:
    assert_frontend_fields(serialize_schema(_schedule_schema(DEFAULT_SCHEDULE)))
