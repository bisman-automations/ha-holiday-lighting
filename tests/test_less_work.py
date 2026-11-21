"""1.13.1: the minute check writes the file only when something changed, and
a light sensor re-checks only when its reading crosses the threshold.

1.13.3: a show's color step alone is written later, and the sun's height is
kept out of history."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.holiday_lighting.controller import lux_reading_dark
from custom_components.holiday_lighting.sensor import StatusSensor
from homeassistant.core import HomeAssistant, State

from .test_init import DARK, LIGHTS, _entry, _start, _tick, tz  # noqa: F401


async def test_minute_check_writes_only_changes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 7, 1, 13, 0, tzinfo=tz))  # no holiday today
    entry = _entry()
    with patch(DARK, return_value=False):
        await _start(hass, entry)
        controller = entry.runtime_data
        writes: list[dict] = []
        real = controller._store.async_save  # noqa: SLF001

        async def counted(data):
            writes.append(data)
            await real(data)

        controller._store.async_save = counted  # noqa: SLF001
        for minute in range(1, 6):
            await _tick(hass, freezer, datetime(2026, 7, 1, 13, minute, tzinfo=tz))
        assert writes == []  # five quiet minutes: nothing written
        controller.night.overridden.add("light.porch")
        await _tick(hass, freezer, datetime(2026, 7, 1, 13, 7, tzinfo=tz))
        assert len(writes) == 1 and writes[0]["overridden"] == ["light.porch"]


def test_lux_reading_dark() -> None:
    assert lux_reading_dark(State("sensor.lux", "5"), 20) is True
    assert lux_reading_dark(State("sensor.lux", "50"), 20) is False
    assert lux_reading_dark(State("sensor.lux", "unavailable"), 20) is None
    assert lux_reading_dark(State("sensor.lux", "bright"), 20) is None
    assert lux_reading_dark(None, 20) is None


async def test_lux_rechecks_only_on_a_crossing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 12, 24, 15, 0, tzinfo=tz))
    hass.states.async_set("sensor.lux", "500")
    entry = _entry(dark_source="lux", lux_sensor="sensor.lux")
    await _start(hass, entry)
    controller = entry.runtime_data
    checks: list[int] = []
    real = controller.async_evaluate

    async def counted():
        checks.append(1)
        await real()

    controller.async_evaluate = counted
    for lux in ("480", "450", "300", "120"):  # still bright
        hass.states.async_set("sensor.lux", lux)
        await hass.async_block_till_done()
    assert len(checks) == 1  # the first reading; the rest change nothing
    hass.states.async_set("sensor.lux", "10")  # crossed into dark
    await hass.async_block_till_done()
    assert len(checks) == 2


async def test_show_steps_are_written_later(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    """1.13.3: a show's color step alone is written at most every 15 minutes."""
    freezer.move_to(datetime(2026, 12, 24, 17, 0, tzinfo=tz))
    for light in LIGHTS:
        hass.states.async_set(light, "off")
    async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = _entry()
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        controller = entry.runtime_data
        assert controller.running is not None
        writes: list[dict] = []
        real = controller._store._async_write_data  # noqa: SLF001

        async def counted(data):
            await real(data)
            writes.append(data["data"])

        controller._store._async_write_data = counted  # noqa: SLF001
        for _ in range(60):  # 30 minutes of 30-second color steps
            freezer.tick(timedelta(seconds=30))
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)
        # Used to be one write a minute (30); now the moved step waits 15
        # minutes (written at minute 16; the next one is due at minute 32).
        assert len(writes) == 1
        assert 0 < writes[-1]["offset"] < controller.offset

        # Something real changes: written at once, with the current step.
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.holiday_lighting_turn_off_for_tonight"},
            blocking=True,
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(writes) == 2
        assert writes[-1]["offset"] == controller.offset
        assert writes[-1]["done_night"] == "2026-12-24"

        # Unloading writes a moved step straight away, leaving no timer.
        controller.offset += 1
        await _tick(hass, freezer, datetime(2026, 12, 24, 17, 32, tzinfo=tz))
        assert len(writes) == 2
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert len(writes) == 3
        assert writes[-1]["offset"] == controller.offset


def test_sun_elevation_is_not_recorded() -> None:
    """1.13.3: the sun's height (new every minute) stays out of history."""
    assert "sun_elevation" in StatusSensor._unrecorded_attributes  # noqa: SLF001
