"""1.13.1: the minute check writes the file only when something changed, and
a light sensor re-checks only when its reading crosses the threshold."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from custom_components.holiday_lighting.controller import lux_reading_dark
from homeassistant.core import HomeAssistant, State

from .test_init import DARK, _entry, _start, _tick, tz  # noqa: F401


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
        controller.offset = 15
        await _tick(hass, freezer, datetime(2026, 7, 1, 13, 7, tzinfo=tz))
        assert len(writes) == 1 and writes[0]["offset"] == 15


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
