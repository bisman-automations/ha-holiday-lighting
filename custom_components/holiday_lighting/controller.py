"""The Holiday Lighting controller: decides when lights run and drives them."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    ColorMode,
)
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.sun import get_astral_location
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BRIGHTNESS,
    CONF_COLORS,
    CONF_DARK_SOURCE,
    CONF_DEFAULT_LIGHTS,
    CONF_END,
    CONF_INTERVAL,
    CONF_LIGHTS,
    CONF_LUX_SENSOR,
    CONF_LUX_THRESHOLD,
    CONF_MODE,
    CONF_NAME,
    CONF_OFF_TIME,
    CONF_ON_DURATION,
    CONF_START,
    CONF_SUN_ELEVATION,
    CONF_TRANSITION,
    CONF_USE_SCHEDULE,
    DARK_EITHER,
    DARK_LUX,
    DARK_SUN,
    DEFAULT_INTERVAL,
    DEFAULT_LUX_THRESHOLD,
    DEFAULT_SUN_ELEVATION,
    DOMAIN,
    MODE_ROTATE,
    STATUS_DISABLED,
    STATUS_DONE,
    STATUS_NO_HOLIDAY,
    STATUS_ON,
    STATUS_WAITING,
    STORAGE_VERSION,
    SUBENTRY_HOLIDAY,
    THEME_AUTO,
)
from .schedule import (
    active_holiday,
    can_start,
    hard_off_at,
    lights_off_deadline,
    night_of,
    rotation_assignments,
    upcoming_holiday,
)

_LOGGER = logging.getLogger(__name__)

EVALUATE_INTERVAL = timedelta(minutes=1)

_COLOR_ATTRS_BY_MODE: dict[str, str] = {
    ColorMode.COLOR_TEMP: ATTR_COLOR_TEMP_KELVIN,
    ColorMode.HS: ATTR_HS_COLOR,
    ColorMode.RGB: ATTR_RGB_COLOR,
    ColorMode.RGBW: ATTR_RGBW_COLOR,
    ColorMode.RGBWW: ATTR_RGBWW_COLOR,
    ColorMode.XY: ATTR_XY_COLOR,
}


@dataclass(frozen=True)
class Holiday:
    """A configured holiday."""

    id: str
    name: str
    start: str
    end: str
    colors: list[str]
    lights: list[str]
    mode: str
    interval: int
    brightness: int | None
    transition: float | None

    def as_mapping(self) -> dict[str, Any]:
        """Mapping form used by the schedule helpers."""
        return {"id": self.id, CONF_START: self.start, CONF_END: self.end}


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    return dt_util.parse_time(value)


def _parse_duration(value: dict[str, Any] | None) -> timedelta | None:
    if not value:
        return None
    duration = timedelta(
        days=value.get("days", 0),
        hours=value.get("hours", 0),
        minutes=value.get("minutes", 0),
        seconds=value.get("seconds", 0),
    )
    return duration or None


def _hex_to_rgb(color: str) -> list[int]:
    color = color.lstrip("#")
    return [int(color[i : i + 2], 16) for i in (0, 2, 4)]


class HolidayLightingController:
    """Owns the lighting state machine for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise from the config entry."""
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._rotation_unsub: CALLBACK_TYPE | None = None
        self._lock = asyncio.Lock()

        default_lights = list(entry.options.get(CONF_DEFAULT_LIGHTS, []))
        self.holidays: dict[str, Holiday] = {}
        for subentry_id, subentry in entry.subentries.items():
            if subentry.subentry_type != SUBENTRY_HOLIDAY:
                continue
            data = subentry.data
            self.holidays[subentry_id] = Holiday(
                id=subentry_id,
                name=data[CONF_NAME],
                start=data[CONF_START],
                end=data[CONF_END],
                colors=list(data[CONF_COLORS]),
                lights=list(data.get(CONF_LIGHTS) or default_lights),
                mode=data.get(CONF_MODE, MODE_ROTATE),
                interval=int(data.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
                brightness=data.get(CONF_BRIGHTNESS),
                transition=data.get(CONF_TRANSITION),
            )

        options = entry.options
        self.use_schedule: bool = options.get(CONF_USE_SCHEDULE, True)
        self.dark_source: str = options.get(CONF_DARK_SOURCE, DARK_SUN)
        self.sun_elevation: float = float(
            options.get(CONF_SUN_ELEVATION, DEFAULT_SUN_ELEVATION)
        )
        self.lux_sensor: str | None = options.get(CONF_LUX_SENSOR)
        self.lux_threshold: float = float(
            options.get(CONF_LUX_THRESHOLD, DEFAULT_LUX_THRESHOLD)
        )
        self.on_duration = _parse_duration(options.get(CONF_ON_DURATION))
        self.off_time = _parse_time(options.get(CONF_OFF_TIME))

        # Persisted state
        self.enabled = False
        self.theme = THEME_AUTO
        self.on_at: datetime | None = None
        self.done_night: date | None = None
        self.offset = 0
        self._snapshot: dict[str, dict[str, Any]] = {}

        # Runtime state
        self.running: Holiday | None = None
        self.status = STATUS_DISABLED

    # --- lifecycle ---------------------------------------------------------

    async def async_setup(self) -> None:
        """Load saved state and start watching the clock and sensors."""
        if stored := await self._store.async_load():
            self.enabled = stored.get("enabled", False)
            theme = stored.get("theme", THEME_AUTO)
            self.theme = theme if theme in self.holidays else THEME_AUTO
            if on_at := stored.get("on_at"):
                self.on_at = dt_util.parse_datetime(on_at)
            if done := stored.get("done_night"):
                self.done_night = date.fromisoformat(done)
            self.offset = stored.get("offset", 0)
            self._snapshot = stored.get("snapshot", {})

        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_tick, EVALUATE_INTERVAL)
        )
        if self.lux_sensor and self.dark_source in (DARK_LUX, DARK_EITHER):
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, [self.lux_sensor], self._async_lux_changed
                )
            )

    async def async_start(self) -> None:
        """First evaluation, once Home Assistant (and the lights) are up."""
        await self.async_evaluate()

    async def async_unload(self) -> None:
        """Stop timers. Lights are left as they are; state is saved."""
        self._stop_rotation()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._async_save()

    # --- listeners ---------------------------------------------------------

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Register an entity update callback."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # --- public controls ---------------------------------------------------

    async def async_set_enabled(self, enabled: bool) -> None:
        """Arm or disarm. Disarming restores the lights' previous state."""
        async with self._lock:
            self.enabled = enabled
            if not enabled:
                await self._async_release(restore=True)
                self.done_night = None
                self.status = STATUS_DISABLED
        await self.async_evaluate()

    async def async_set_theme(self, theme: str) -> None:
        """Choose a holiday by subentry id, or THEME_AUTO."""
        self.theme = theme if theme in self.holidays else THEME_AUTO
        await self.async_evaluate()

    async def async_force_on(self, holiday_id: str | None = None) -> None:
        """Turn lights on now, ignoring darkness. Off rules still apply."""
        async with self._lock:
            self.enabled = True
            if holiday_id:
                self.theme = holiday_id
            now = dt_util.now()
            holiday = self._selected_holiday(now)
            if holiday is None:
                self.status = STATUS_NO_HOLIDAY
            else:
                self.done_night = None
                self.on_at = now
                await self._async_run(holiday)
                self.status = STATUS_ON
            await self._async_save()
        self._notify()

    async def async_force_off(self) -> None:
        """Turn lights off and treat tonight as done."""
        async with self._lock:
            await self._async_end_night(dt_util.now())
            self.status = STATUS_DONE if self.enabled else STATUS_DISABLED
            await self._async_save()
        self._notify()

    async def async_advance(self) -> None:
        """Shift the rotation one step."""
        async with self._lock:
            if self.running:
                self.offset += 1
                await self._async_apply(self.running)
        self._notify()

    # --- derived info for entities ----------------------------------------

    @property
    def deadline(self) -> datetime | None:
        """When the lights will turn off, if they are on and a limit is set."""
        if self.on_at is None or not self.use_schedule:
            return None
        return lights_off_deadline(self.on_at, self.on_duration, self.off_time)

    def upcoming(self) -> tuple[Holiday, date] | None:
        """The next holiday to start, and when."""
        result = upcoming_holiday(
            [h.as_mapping() for h in self.holidays.values()], dt_util.now().date()
        )
        if result is None:
            return None
        return self.holidays[result[0]["id"]], result[1]

    def is_dark(self) -> bool:
        """Whether it is dark enough to start the lights."""
        sun_dark = lux_dark = False
        if self.dark_source in (DARK_SUN, DARK_EITHER):
            location, elevation = get_astral_location(self.hass)
            sun_dark = (
                location.solar_elevation(dt_util.now(), elevation) < self.sun_elevation
            )
        if self.dark_source in (DARK_LUX, DARK_EITHER) and self.lux_sensor:
            state = self.hass.states.get(self.lux_sensor)
            if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    lux_dark = float(state.state) < self.lux_threshold
                except ValueError:
                    lux_dark = False
        return sun_dark or lux_dark

    # --- evaluation --------------------------------------------------------

    async def _async_tick(self, _now: datetime) -> None:
        await self.async_evaluate()

    async def _async_lux_changed(self, _event: Event) -> None:
        if self.on_at is None:
            await self.async_evaluate()

    async def async_evaluate(self) -> None:
        """Decide what the lights should be doing right now."""
        async with self._lock:
            await self._async_evaluate_locked(dt_util.now())
            await self._async_save()
        self._notify()

    def _selected_holiday(self, now: datetime) -> Holiday | None:
        if self.theme != THEME_AUTO:
            return self.holidays.get(self.theme)
        # Use the night's date so New Year's Eve still counts at 00:30.
        found = active_holiday(
            [h.as_mapping() for h in self.holidays.values()], night_of(now)
        )
        return self.holidays[found["id"]] if found else None

    async def _async_evaluate_locked(self, now: datetime) -> None:
        if not self.enabled:
            self.status = STATUS_DISABLED
            return

        holiday = self._selected_holiday(now)
        if holiday is None:
            if self.on_at is not None:
                await self._async_end_night(now)
            self.status = STATUS_NO_HOLIDAY
            return

        if not self.use_schedule:
            # Always on while enabled.
            if self.on_at is None:
                self.on_at = now
            if self.running is None or self.running.id != holiday.id:
                await self._async_run(holiday)
            self.status = STATUS_ON
            return

        if self.on_at is not None:
            deadline = self.deadline
            if (deadline is not None and now >= deadline) or (
                deadline is None and not self.is_dark()
            ):
                await self._async_end_night(now)
                self.status = STATUS_DONE
                return
            if self.running is None or self.running.id != holiday.id:
                await self._async_run(holiday)
            self.status = STATUS_ON
            return

        night = night_of(now)
        if self.done_night == night or not can_start(now, self.off_time):
            self.status = STATUS_DONE
            return
        if not self.is_dark():
            self.status = STATUS_WAITING
            return

        self.on_at = now
        await self._async_run(holiday)
        self.status = STATUS_ON

    # --- driving lights ----------------------------------------------------

    async def _async_run(self, holiday: Holiday) -> None:
        """Start showing a holiday (switching from another if needed)."""
        self._stop_rotation()
        if self.running is not None and self.running.id != holiday.id:
            self.offset = 0
        # Lights the previous holiday used but this one doesn't go back.
        released = [e for e in self._snapshot if e not in holiday.lights]
        await self._async_restore(released)
        self._take_snapshot(holiday.lights)
        self.running = holiday
        await self._async_apply(holiday)
        if holiday.mode == MODE_ROTATE and len(holiday.colors) > 1:
            self._rotation_unsub = async_track_time_interval(
                self.hass,
                self._async_rotate,
                timedelta(seconds=max(1, holiday.interval)),
            )

    async def _async_rotate(self, _now: datetime) -> None:
        async with self._lock:
            if self.running is None:
                return
            self.offset += 1
            await self._async_apply(self.running)

    def _stop_rotation(self) -> None:
        if self._rotation_unsub:
            self._rotation_unsub()
            self._rotation_unsub = None

    async def _async_apply(self, holiday: Holiday) -> None:
        assignments = rotation_assignments(holiday.lights, holiday.colors, self.offset)
        calls = []
        for color, entity_ids in assignments.items():
            data: dict[str, Any] = {
                ATTR_ENTITY_ID: entity_ids,
                ATTR_RGB_COLOR: _hex_to_rgb(color),
            }
            if holiday.brightness:
                data[ATTR_BRIGHTNESS_PCT] = holiday.brightness
            if holiday.transition:
                data[ATTR_TRANSITION] = holiday.transition
            calls.append(
                self.hass.services.async_call(
                    LIGHT_DOMAIN, SERVICE_TURN_ON, data, blocking=True
                )
            )
        for result in await asyncio.gather(*calls, return_exceptions=True):
            if isinstance(result, Exception):
                _LOGGER.warning("Failed to set holiday color: %s", result)

    async def _async_end_night(self, now: datetime) -> None:
        """Schedule finished: turn lights off and wait for tomorrow."""
        self._stop_rotation()
        lights = list(self._snapshot)
        if self.running:
            lights.extend(e for e in self.running.lights if e not in lights)
        if lights:
            data: dict[str, Any] = {ATTR_ENTITY_ID: lights}
            if self.running and self.running.transition:
                data[ATTR_TRANSITION] = self.running.transition
            try:
                await self.hass.services.async_call(
                    LIGHT_DOMAIN, SERVICE_TURN_OFF, data, blocking=True
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Failed to turn off holiday lights: %s", err)
        self._snapshot.clear()
        self.running = None
        self.on_at = None
        self.offset = 0
        self.done_night = night_of(now)

    async def _async_release(self, restore: bool) -> None:
        """Stop and put lights back the way they were."""
        self._stop_rotation()
        if restore:
            await self._async_restore(list(self._snapshot))
        self._snapshot.clear()
        self.running = None
        self.on_at = None
        self.offset = 0

    def _take_snapshot(self, entity_ids: list[str]) -> None:
        for entity_id in entity_ids:
            if entity_id in self._snapshot:
                continue
            state = self.hass.states.get(entity_id)
            if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            saved: dict[str, Any] = {"on": state.state == STATE_ON}
            if saved["on"]:
                if (brightness := state.attributes.get(ATTR_BRIGHTNESS)) is not None:
                    saved[ATTR_BRIGHTNESS] = brightness
                mode = state.attributes.get(ATTR_COLOR_MODE)
                attr = _COLOR_ATTRS_BY_MODE.get(mode) if mode else None
                if attr and (value := state.attributes.get(attr)) is not None:
                    saved[attr] = list(value) if isinstance(value, tuple) else value
            self._snapshot[entity_id] = saved

    async def _async_restore(self, entity_ids: list[str]) -> None:
        calls = []
        for entity_id in entity_ids:
            saved = self._snapshot.pop(entity_id, None)
            if saved is None:
                continue
            if not saved.get("on"):
                calls.append(
                    self.hass.services.async_call(
                        LIGHT_DOMAIN,
                        SERVICE_TURN_OFF,
                        {ATTR_ENTITY_ID: entity_id},
                        blocking=True,
                    )
                )
                continue
            data = {k: v for k, v in saved.items() if k != "on"}
            data[ATTR_ENTITY_ID] = entity_id
            calls.append(
                self.hass.services.async_call(
                    LIGHT_DOMAIN, SERVICE_TURN_ON, data, blocking=True
                )
            )
        for result in await asyncio.gather(*calls, return_exceptions=True):
            if isinstance(result, Exception):
                _LOGGER.warning("Failed to restore a light: %s", result)

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "enabled": self.enabled,
                "theme": self.theme,
                "on_at": self.on_at.isoformat() if self.on_at else None,
                "done_night": self.done_night.isoformat() if self.done_night else None,
                "offset": self.offset,
                "snapshot": self._snapshot,
            }
        )

    def hard_off_tonight(self) -> datetime | None:
        """Tonight's hard off time, for display."""
        if self.off_time is None:
            return None
        now = dt_util.now()
        return hard_off_at(night_of(now), self.off_time, now.tzinfo)
