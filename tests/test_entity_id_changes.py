"""Entities keep running when their entity ID is changed (Home Assistant 2026.11+)."""

from __future__ import annotations

from datetime import datetime
import importlib
import inspect
import pkgutil
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

import custom_components.holiday_lighting as package
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity

from .test_init import DARK, _entry_with, _holiday, _start, _tick, tz  # noqa: F401

ADD_REMOVE_METHODS = (
    "async_prepare_to_add_to_hass",
    "async_added_to_hass",
    "async_will_remove_from_hass",
)


def _entity_classes() -> list[type[Entity]]:
    """Every Entity subclass defined in the integration."""
    classes: list[type[Entity]] = []
    for info in pkgutil.walk_packages(package.__path__, f"{package.__name__}."):
        module = importlib.import_module(info.name)
        classes.extend(
            cls
            for _, cls in inspect.getmembers(module, inspect.isclass)
            if issubclass(cls, Entity) and cls.__module__ == module.__name__
        )
    return classes


def test_every_add_remove_class_handles_entity_id_changes() -> None:
    """A class with its own add or remove code also has its own rename hook."""
    classes = _entity_classes()
    assert classes, "no entity classes found"
    missing = sorted(
        f"{cls.__module__}.{cls.__qualname__}"
        for cls in classes
        if any(method in cls.__dict__ for method in ADD_REMOVE_METHODS)
        and "async_entity_id_changed" not in cls.__dict__
    )
    assert not missing, f"missing async_entity_id_changed: {missing}"


@pytest.mark.skipif(
    not hasattr(Entity, "async_entity_id_changed"),
    reason="Entity ID changes are applied in place from Home Assistant 2026.11",
)
async def test_renamed_sensors_keep_updating(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    """A renamed light color sensor and status sensor still follow the lights."""
    freezer.move_to(datetime(2026, 10, 7, 20, 0, tzinfo=tz))
    for light in ("light.porch", "light.tree", "light.garage"):
        hass.states.async_set(light, "off", {"supported_color_modes": ["hs"]})
    async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday(
            "Halloween",
            kind="yearly",
            start="10-01",
            end="10-31",
            colors=["#FF6600", "#8000FF", "#00FF00"],
            color_names=["Orange", "Purple", "Green"],
        ),
    )
    with patch(DARK, return_value=False):
        await _start(hass, entry)

    registry = er.async_get(hass)
    renames = {
        "sensor.holiday_lighting_porch_color": "sensor.front_porch_color",
        "sensor.holiday_lighting_status": "sensor.holiday_lights_status",
    }
    before = {new: hass.states.get(old).state for old, new in renames.items()}
    for old, new in renames.items():
        registry.async_update_entity(old, new_entity_id=new)
    await hass.async_block_till_done()
    for old, new in renames.items():
        assert hass.states.get(old) is None
        assert hass.states.get(new).state == before[new]
    assert before["sensor.front_porch_color"] == "Off"

    with patch(DARK, return_value=True):
        await _tick(hass, freezer, datetime(2026, 10, 7, 20, 1, tzinfo=tz))
        assert hass.states.get("sensor.front_porch_color").state == "Orange"
        assert (
            hass.states.get("sensor.holiday_lights_status").state
            != before["sensor.holiday_lights_status"]
        )
        for old in renames:
            assert hass.states.get(old) is None
