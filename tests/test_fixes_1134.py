"""1.13.4: the late-command guard stops on Home Assistant's event loop, and a
calendar that can't be read on a new night doesn't keep last night's match."""

from __future__ import annotations

from datetime import datetime, timedelta
import threading
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component

from .test_init import DARK, _entry_with, _holiday, _start, _state, _tick, tz  # noqa: F401


async def test_guard_stops_on_the_event_loop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    """The guard's one-minute timer ran its stop in a worker thread."""
    freezer.move_to(datetime(2026, 10, 7, 22, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        controller = entry.runtime_data
        await controller.async_force_off()
        assert controller._guard_unsub is not None  # noqa: SLF001

        threads: list[int] = []
        real_stop = controller._stop_guard  # noqa: SLF001

        def recording_stop() -> None:
            threads.append(threading.get_ident())
            real_stop()

        controller._stop_guard = recording_stop  # noqa: SLF001
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert threads == [hass.loop_thread_id]
    assert controller._guard_unsub is None  # noqa: SLF001


async def test_unread_calendar_on_a_new_night_drops_last_nights_match(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 12, 5, 17, 0, tzinfo=tz))
    await async_setup_component(hass, "calendar", {})
    readable = True

    async def get_events(call: ServiceCall) -> dict:
        if not readable:
            raise HomeAssistantError("calendar offline")
        return {"calendar.games": {"events": [{"summary": "Bison game"}]}}

    hass.services.async_register(
        "calendar",
        "get_events",
        get_events,
        supports_response=SupportsResponse.ONLY,
    )
    async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26"),
        _holiday(
            "Game Day", kind="calendar", calendar="calendar.games", keyword="bison"
        ),
    )
    with patch(DARK, return_value=False):
        await _start(hass, entry)
        assert _state(hass, "active_holiday") == "Game Day"

        # Later the same evening a failed read keeps tonight's match.
        readable = False
        await _tick(hass, freezer, datetime(2026, 12, 5, 17, 30, tzinfo=tz))
        assert _state(hass, "active_holiday") == "Game Day"

        # The next night nothing says there's a game: back to the dates.
        await _tick(hass, freezer, datetime(2026, 12, 6, 13, 0, tzinfo=tz))
        assert _state(hass, "active_holiday") == "Christmas"


async def test_reload_writes_nothing_new(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    """The first check after a start or reload wrote the same file again."""
    freezer.move_to(datetime(2026, 7, 1, 13, 0, tzinfo=tz))  # no holiday today
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26"),
    )
    with patch(DARK, return_value=False):
        await _start(hass, entry)
        writes: list[dict] = []
        real = Store.async_save

        async def counted(store, data):
            writes.append(data)
            await real(store, data)

        with patch.object(Store, "async_save", counted):
            await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done(wait_background_tasks=True)
            await _tick(hass, freezer, datetime(2026, 7, 1, 13, 1, tzinfo=tz))
            await _tick(hass, freezer, datetime(2026, 7, 1, 13, 2, tzinfo=tz))
            assert writes == []
            # A real change is still written.
            await entry.runtime_data.async_set_theme(
                next(iter(entry.runtime_data.holidays))
            )
            assert len(writes) == 1
