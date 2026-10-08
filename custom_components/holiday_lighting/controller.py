"""The Holiday Lighting controller: decides when lights run and drives them."""

from __future__ import annotations

import asyncio
import logging
import random
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
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
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    ColorMode,
)
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
    EVENT_CALL_SERVICE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.service import async_extract_referenced_entity_ids
from homeassistant.helpers.storage import Store
from homeassistant.helpers.sun import get_astral_location
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALL_NIGHT,
    CONF_BRIGHTNESS,
    CONF_CALENDAR,
    CONF_COLOR_NAMES,
    CONF_COLORS,
    CONF_DARK_SOURCE,
    CONF_DEFAULT_COLOR_NAMES,
    CONF_DEFAULT_COLORS,
    CONF_DEFAULT_LIGHTS,
    CONF_INTERVAL,
    CONF_KEYWORD,
    CONF_KIND,
    CONF_LIGHTS,
    CONF_LUX_SENSOR,
    CONF_LUX_THRESHOLD,
    CONF_MODE,
    CONF_NAME,
    CONF_OFF_TIME,
    CONF_ON_DURATION,
    CONF_RESPECT_MANUAL,
    CONF_SUN_ELEVATION,
    CONF_SUN_SOURCE,
    CONF_TRANSITION,
    CONF_USE_SCHEDULE,
    CONF_WEEKEND_OFF_TIME,
    DARK_EITHER,
    DARK_LUX,
    DARK_SUN,
    DEFAULT_HOLIDAY_ID,
    DEFAULT_INTERVAL,
    DEFAULT_LUX_THRESHOLD,
    DEFAULT_SUN_ELEVATION,
    DEFAULT_TRANSITION,
    DOMAIN,
    KIND_CALENDAR,
    KIND_YEARLY,
    MODE_FADE,
    MODE_ROTATE,
    MODE_STATIC,
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
    LIGHT_COLOR,
    LIGHT_DIMMABLE,
    LIGHT_TEMP,
    active_holiday,
    can_start,
    color_to_brightness_pct,
    color_to_kelvin,
    effect_assignments,
    hard_off_at,
    light_kind,
    lights_off_deadline,
    night_of,
    upcoming_holiday,
)

_LOGGER = logging.getLogger(__name__)

EVALUATE_INTERVAL = timedelta(minutes=1)
CALENDAR_REFRESH = timedelta(minutes=15)
# After turning the lights off, undo our own late "on" commands this long.
OFF_GUARD_SECONDS = 60
LIGHT_COMMAND_TIMEOUT = 15  # seconds
DEFAULT_HOLIDAY_NAME = "Default colors"
# Evaluations a light must stay unavailable before a repair is raised.
UNAVAILABLE_STRIKES = 2

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
    kind: str
    data: Mapping[str, Any]
    colors: list[str]
    color_names: list[str]
    lights: list[str]
    mode: str
    interval: int
    brightness: int | None
    transition: float | None
    off_time: time | None = None
    on_duration: timedelta | None = None
    all_night: bool = False
    calendar: str | None = None
    keyword: str | None = None

    def as_mapping(self) -> dict[str, Any]:
        """Mapping form used by the schedule helpers."""
        return {**self.data, "id": self.id, CONF_KIND: self.kind}


@dataclass
class _NightState:
    """Things that reset every night."""

    overridden: set[str] = field(default_factory=set)


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    return dt_util.parse_time(value)


def _parse_duration(value: Mapping[str, Any] | None) -> timedelta | None:
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


def _shown_as(command: dict[str, Any]) -> str:
    """How a light shows its color: in color, as a white, or as a brightness."""
    if ATTR_RGB_COLOR in command:
        return "color"
    if ATTR_COLOR_TEMP_KELVIN in command:
        return f"{command[ATTR_COLOR_TEMP_KELVIN]}K white"
    if ATTR_BRIGHTNESS_PCT in command:
        return f"{command[ATTR_BRIGHTNESS_PCT]}% brightness"
    return "on"


@callback
def _is_light_command(event_data: Mapping[str, Any]) -> bool:
    """A light on/off/toggle service call (light.* or homeassistant.*)."""
    return event_data.get(ATTR_DOMAIN) in (LIGHT_DOMAIN, "homeassistant") and (
        event_data.get(ATTR_SERVICE) in (SERVICE_TURN_ON, SERVICE_TURN_OFF, "toggle")
    )


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
        self._light_watch_unsub: CALLBACK_TYPE | None = None
        self._guard_unsub: Callable[[], None] | None = None
        self._step_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._rng = random.Random()

        default_lights = list(entry.options.get(CONF_DEFAULT_LIGHTS, []))
        self.holidays: dict[str, Holiday] = {}
        for subentry_id, subentry in entry.subentries.items():
            if subentry.subentry_type != SUBENTRY_HOLIDAY:
                continue
            data = subentry.data
            colors = list(data[CONF_COLORS])
            names = list(data.get(CONF_COLOR_NAMES) or colors)
            self.holidays[subentry_id] = Holiday(
                id=subentry_id,
                name=data[CONF_NAME],
                kind=data.get(CONF_KIND, KIND_YEARLY),
                data=dict(data),
                colors=colors,
                color_names=names,
                lights=list(data.get(CONF_LIGHTS) or default_lights),
                mode=data.get(CONF_MODE, MODE_ROTATE),
                interval=int(data.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
                brightness=data.get(CONF_BRIGHTNESS),
                transition=data.get(CONF_TRANSITION),
                off_time=_parse_time(data.get(CONF_OFF_TIME)),
                on_duration=_parse_duration(data.get(CONF_ON_DURATION)),
                all_night=bool(data.get(CONF_ALL_NIGHT, False)),
                calendar=data.get(CONF_CALENDAR),
                keyword=(data.get(CONF_KEYWORD) or "").strip() or None,
            )

        options = entry.options
        # Colors for nights with no holiday (empty: lights stay off).
        self.default_holiday: Holiday | None = None
        if default_colors := list(options.get(CONF_DEFAULT_COLORS) or []):
            self.default_holiday = Holiday(
                id=DEFAULT_HOLIDAY_ID,
                name=DEFAULT_HOLIDAY_NAME,
                kind=DEFAULT_HOLIDAY_ID,
                data={},
                colors=default_colors,
                color_names=list(
                    options.get(CONF_DEFAULT_COLOR_NAMES) or default_colors
                ),
                lights=default_lights,
                mode=MODE_STATIC,
                interval=DEFAULT_INTERVAL,
                brightness=None,
                transition=DEFAULT_TRANSITION,
            )
        # Every light any holiday (or the default colors) can use, in order.
        self.all_lights: list[str] = list(
            dict.fromkeys(
                [
                    *default_lights,
                    *(e for h in self.holidays.values() for e in h.lights),
                ]
            )
        )
        # What each light is showing right now.
        self.light_colors: dict[str, dict[str, Any]] = {}
        self._light_listeners: list[Callable[[], None]] = []

        self.use_schedule: bool = options.get(CONF_USE_SCHEDULE, True)
        self.dark_source: str = options.get(CONF_DARK_SOURCE, DARK_SUN)
        self.sun_elevation: float = float(
            options.get(CONF_SUN_ELEVATION, DEFAULT_SUN_ELEVATION)
        )
        self.sun_source: str | None = options.get(CONF_SUN_SOURCE) or None
        self.lux_sensor: str | None = options.get(CONF_LUX_SENSOR)
        self.lux_threshold: float = float(
            options.get(CONF_LUX_THRESHOLD, DEFAULT_LUX_THRESHOLD)
        )
        self.on_duration = _parse_duration(options.get(CONF_ON_DURATION))
        self.off_time = _parse_time(options.get(CONF_OFF_TIME))
        self.weekend_off_time = _parse_time(options.get(CONF_WEEKEND_OFF_TIME))
        self.respect_manual: bool = options.get(CONF_RESPECT_MANUAL, True)

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
        self.night = _NightState()
        self._night_key: date | None = None
        self._calendar_active: set[str] = set()
        self._calendar_checked: tuple[date, datetime] | None = None
        self._our_contexts: deque[str] = deque(maxlen=64)
        self._commanded: dict[str, tuple[tuple[str, Any] | None, datetime]] = {}
        self.slow_light_commands = 0
        self.skipped_steps = 0
        self._unavailable_strikes: dict[str, int] = {}

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
            if (key := stored.get("night_key")) and stored.get("overridden"):
                self._night_key = date.fromisoformat(key)
                self.night.overridden = set(stored["overridden"])

        self._remove_stale_issues()
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
        self._stop_watching_lights()
        self._stop_guard()
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
    def async_add_light_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Register a per-light color sensor update callback."""
        self._light_listeners.append(listener)

        @callback
        def remove() -> None:
            self._light_listeners.remove(listener)

        return remove

    @callback
    def _notify_lights(self) -> None:
        for listener in list(self._light_listeners):
            listener()

    def light_color(self, entity_id: str) -> tuple[str, dict[str, Any] | None]:
        """("color", details), ("manual", None) or ("off", None) for a light."""
        if entity_id in self.night.overridden:
            return "manual", None
        if self.running is not None and entity_id in self.light_colors:
            return "color", self.light_colors[entity_id]
        return "off", None

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
            await self._async_refresh_calendars(now)
            holiday = self._selected_holiday(now)
            if holiday is None:
                self.status = STATUS_NO_HOLIDAY
            else:
                self.done_night = None
                self.on_at = now
                self.status = STATUS_ON
                await self._async_run(holiday)
            await self._async_save()
        self._notify()

    async def async_force_off(self) -> None:
        """Turn every holiday light off and treat tonight as done."""
        # Don't wait for a color step stuck on slow lights.
        if self._step_task is not None and not self._step_task.done():
            self._step_task.cancel()
        async with self._lock:
            await self._async_end_night(dt_util.now(), include_manual=True)
            self.status = STATUS_DONE if self.enabled else STATUS_DISABLED
            await self._async_save()
        self._notify()

    async def async_advance(self) -> None:
        """Shift the effect one step."""
        async with self._lock:
            if self.running:
                self.offset += 1
                await self._async_apply(self.running)
        self._notify()

    # --- derived info for entities ----------------------------------------

    def off_time_for(self, holiday: Holiday | None, night: date) -> time | None:
        """The hard off time that applies to a holiday on a given night."""
        if holiday is not None:
            if holiday.all_night:
                return None
            if holiday.off_time is not None:
                return holiday.off_time
        # Friday and Saturday nights
        if self.weekend_off_time is not None and night.weekday() in (4, 5):
            return self.weekend_off_time
        return self.off_time

    def planned_for(self, day: date) -> Holiday | None:
        """What the lights will show on the night of `day`.

        Calendar holidays depend on calendar events, which are only checked
        for tonight, so other nights show what the dates alone pick.
        """
        tonight = night_of(dt_util.now())
        holidays = [
            h.as_mapping()
            for h in self.holidays.values()
            if h.kind != KIND_CALENDAR or day == tonight
        ]
        found = active_holiday(
            holidays, day, self._calendar_active if day == tonight else ()
        )
        if found:
            return self.holidays[found["id"]]
        return self.default_holiday

    def duration_for(self, holiday: Holiday | None) -> timedelta | None:
        """How long lights stay on for a holiday."""
        if holiday is not None:
            if holiday.all_night:
                return None
            if holiday.on_duration is not None:
                return holiday.on_duration
        return self.on_duration

    def deadline_for(self, holiday: Holiday | None) -> datetime | None:
        """When lights turned on for `holiday` must turn off."""
        if self.on_at is None or not self.use_schedule:
            return None
        return lights_off_deadline(
            self.on_at,
            self.duration_for(holiday),
            self.off_time_for(holiday, night_of(self.on_at)),
        )

    @property
    def deadline(self) -> datetime | None:
        """When the lights will turn off, if they are on and a limit is set."""
        return self.deadline_for(self.running)

    def upcoming(self) -> tuple[Holiday, date] | None:
        """The next dated holiday to start, and when."""
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
            sun_dark = self.current_sun_elevation() < self.sun_elevation
        if self.dark_source in (DARK_LUX, DARK_EITHER) and self.lux_sensor:
            state = self.hass.states.get(self.lux_sensor)
            if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    lux_dark = float(state.state) < self.lux_threshold
                except ValueError:
                    lux_dark = False
        return sun_dark or lux_dark

    def sun_elevation_from_source(self) -> float | None:
        """Elevation from the chosen entity, or None if unset or unavailable.

        A `sun` entity (the Sun integration's sun.sun) is read from its
        elevation attribute; any other entity from its numeric state.
        """
        if not self.sun_source:
            return None
        state = self.hass.states.get(self.sun_source)
        if state is None:
            return None
        raw = (
            state.attributes.get("elevation") if state.domain == "sun" else state.state
        )
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def current_sun_elevation(self) -> float:
        """Sun elevation now: the chosen entity, else calculated locally."""
        if (from_source := self.sun_elevation_from_source()) is not None:
            return from_source
        location, elevation = get_astral_location(self.hass)
        return location.solar_elevation(dt_util.now(), elevation)

    def hard_off_tonight(self) -> datetime | None:
        """Tonight's hard off time, for display."""
        now = dt_util.now()
        night = night_of(now)
        holiday = self.running or self._selected_holiday(now)
        off_time = self.off_time_for(holiday, night)
        if off_time is None:
            return None
        return hard_off_at(night, off_time, now.tzinfo)

    def diagnostics(self) -> dict[str, Any]:
        """Runtime state for the diagnostics download."""
        return {
            "enabled": self.enabled,
            "status": self.status,
            "theme": self.theme,
            "running": self.running.name if self.running else None,
            "on_at": self.on_at.isoformat() if self.on_at else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "done_night": self.done_night.isoformat() if self.done_night else None,
            "offset": self.offset,
            "dark": self.is_dark(),
            "busy": self._lock.locked(),
            "slow_light_commands": self.slow_light_commands,
            "skipped_rotation_steps": self.skipped_steps,
            "sun_elevation": round(self.current_sun_elevation(), 2),
            "sun_source": self.sun_source,
            "sun_source_ok": self.sun_elevation_from_source() is not None,
            "calendar_active": sorted(
                self.holidays[i].name
                for i in self._calendar_active
                if i in self.holidays
            ),
            "overridden_tonight": sorted(self.night.overridden),
            "snapshot_lights": sorted(self._snapshot),
        }

    # --- evaluation --------------------------------------------------------

    async def _async_tick(self, _now: datetime) -> None:
        await self.async_evaluate()

    async def _async_lux_changed(self, _event: Event) -> None:
        if self.on_at is None:
            await self.async_evaluate()

    async def async_evaluate(self) -> None:
        """Decide what the lights should be doing right now."""
        async with self._lock:
            now = dt_util.now()
            await self._async_refresh_calendars(now)
            await self._async_evaluate_locked(now)
            self._check_repairs()
            await self._async_save()
        self._notify()

    def _selected_holiday(self, now: datetime) -> Holiday | None:
        if self.theme != THEME_AUTO:
            return self.holidays.get(self.theme)
        # Use the night's date so New Year's Eve still counts at 00:30.
        found = active_holiday(
            [h.as_mapping() for h in self.holidays.values()],
            night_of(now),
            self._calendar_active,
        )
        if found:
            return self.holidays[found["id"]]
        return self.default_holiday

    async def _async_refresh_calendars(self, now: datetime) -> None:
        """Find calendar holidays with a matching event tonight."""
        calendar_holidays = [
            h for h in self.holidays.values() if h.kind == KIND_CALENDAR and h.calendar
        ]
        if not calendar_holidays:
            self._calendar_active = set()
            return
        night = night_of(now)
        if (
            self._calendar_checked is not None
            and self._calendar_checked[0] == night
            and now - self._calendar_checked[1] < CALENDAR_REFRESH
        ):
            return
        # Events overlapping this evening (noon to midnight).
        start = datetime.combine(night, time(12), tzinfo=now.tzinfo)
        end = datetime.combine(night + timedelta(days=1), time(0), tzinfo=now.tzinfo)
        entity_ids = sorted({h.calendar for h in calendar_holidays if h.calendar})
        try:
            async with asyncio.timeout(LIGHT_COMMAND_TIMEOUT):
                response = await self.hass.services.async_call(
                    "calendar",
                    "get_events",
                    {
                        ATTR_ENTITY_ID: entity_ids,
                        "start_date_time": start.isoformat(),
                        "end_date_time": end.isoformat(),
                    },
                    blocking=True,
                    return_response=True,
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not read calendars %s: %s", entity_ids, err)
            return
        active: set[str] = set()
        for holiday in calendar_holidays:
            events = (response or {}).get(holiday.calendar, {}).get("events", [])
            for event in events:
                summary = str(event.get("summary", ""))
                if holiday.keyword is None or holiday.keyword.casefold() in (
                    summary.casefold()
                ):
                    active.add(holiday.id)
                    break
        self._calendar_active = active
        self._calendar_checked = (night, now)

    async def _async_evaluate_locked(self, now: datetime) -> None:
        if self._night_key != night_of(now):
            self._night_key = night_of(now)
            self.night = _NightState()

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
            self.status = STATUS_ON
            if self.running is None or self.running.id != holiday.id:
                await self._async_run(holiday)
            return

        if self.on_at is not None:
            deadline = self.deadline_for(holiday)
            if (deadline is not None and now >= deadline) or (
                deadline is None and not self.is_dark()
            ):
                lit_night = night_of(self.on_at)
                await self._async_end_night(now)
                self.status = STATUS_DONE
                if lit_night == night_of(now):
                    return
                # A missed off time from an earlier night; tonight is fresh.
            else:
                if self.running is None or self.running.id != holiday.id:
                    await self._async_run(holiday)
                self.status = STATUS_ON
                return

        night = night_of(now)
        if self.done_night == night or not can_start(
            now, self.off_time_for(holiday, night)
        ):
            self.status = STATUS_DONE
            return
        if not self.is_dark():
            self.status = STATUS_WAITING
            return

        self.on_at = now
        self.status = STATUS_ON
        await self._async_run(holiday)

    # --- driving lights ----------------------------------------------------

    def _controlled(self, holiday: Holiday) -> list[str]:
        """The holiday's lights, minus any changed by hand tonight."""
        return [e for e in holiday.lights if e not in self.night.overridden]

    async def _async_run(self, holiday: Holiday) -> None:
        """Start showing a holiday (switching from another if needed)."""
        self._stop_rotation()
        if self.running is not None and self.running.id != holiday.id:
            self.offset = 0
        # Lights the previous holiday used but this one doesn't go back.
        released = [e for e in self._snapshot if e not in holiday.lights]
        await self._async_restore(released)
        self._take_snapshot(self._controlled(holiday))
        self.running = holiday
        await self._async_apply(holiday)
        if holiday.mode != MODE_STATIC and len(holiday.colors) > 1:
            self._rotation_unsub = async_track_time_interval(
                self.hass,
                self._async_rotate,
                timedelta(seconds=max(1, holiday.interval)),
            )
        self._watch_lights(holiday)

    async def _async_rotate(self, _now: datetime) -> None:
        if self._lock.locked():
            # The last step (or an evaluation) is still waiting on the lights.
            # Skip this step rather than letting steps pile up.
            self.skipped_steps += 1
            return
        self._step_task = asyncio.current_task()
        try:
            async with self._lock:
                if self.running is None:
                    return
                self.offset += 1
                await self._async_apply(self.running)
        finally:
            self._step_task = None

    def _guard_off(self, lights: list[str], off_context: Context) -> None:
        """For a minute, undo our own late "on" commands after turning off.

        A color step that timed out can still reach a slow light after the
        lights were turned off. That state change carries one of our
        contexts, so turn the light back off. Anything else turning a light
        on (a person, an automation) is left alone.
        """
        self._stop_guard()

        async def _late_on(event: Event) -> None:
            new_state = event.data.get("new_state")
            if (
                new_state is None
                or new_state.state != STATE_ON
                or new_state.context.id not in self._our_contexts
                or new_state.context.id == off_context.id
            ):
                return
            _LOGGER.debug(
                "A late command turned %s back on; turning it off",
                event.data["entity_id"],
            )
            await self.hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: event.data["entity_id"]},
                blocking=False,
                context=off_context,
            )

        unsub_state = async_track_state_change_event(self.hass, lights, _late_on)
        unsub_timer = async_call_later(
            self.hass, OFF_GUARD_SECONDS, lambda _now: self._stop_guard()
        )

        def stop() -> None:
            unsub_state()
            unsub_timer()

        self._guard_unsub = stop

    def _stop_guard(self) -> None:
        if self._guard_unsub is not None:
            self._guard_unsub()
            self._guard_unsub = None

    def _stop_rotation(self) -> None:
        if self._rotation_unsub:
            self._rotation_unsub()
            self._rotation_unsub = None

    def _context(self) -> Context:
        context = Context()
        self._our_contexts.append(context.id)
        return context

    async def _async_apply(self, holiday: Holiday) -> None:
        lights = self._controlled(holiday)
        assignments = effect_assignments(
            holiday.mode, lights, holiday.colors, self.offset, self._rng
        )
        transition = holiday.transition
        if holiday.mode == MODE_FADE:
            # Blend across the whole step.
            transition = float(max(1, holiday.interval))
        context = self._context()
        now = dt_util.utcnow()
        # Group lights that get the exact same command into one call.
        commands: dict[tuple, list[str]] = {}
        names = dict(zip(holiday.colors, holiday.color_names, strict=False))
        for color, entity_ids in assignments.items():
            rgb = _hex_to_rgb(color)
            for entity_id in entity_ids:
                key, expected = self._command_for(entity_id, rgb, holiday)
                commands.setdefault(key, []).append(entity_id)
                self._commanded[entity_id] = (expected, now)
                self.light_colors[entity_id] = {
                    "name": names.get(color, color),
                    "hex": color,
                    "rgb_color": rgb,
                    "shown_as": _shown_as(dict(key)),
                    "holiday": holiday.name,
                }
        self._notify_lights()
        calls = []
        for key, entity_ids in commands.items():
            data: dict[str, Any] = {
                ATTR_ENTITY_ID: entity_ids,
                **{k: list(v) if isinstance(v, tuple) else v for k, v in key},
            }
            if transition:
                data[ATTR_TRANSITION] = transition
            calls.append(
                self.hass.services.async_call(
                    LIGHT_DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=context
                )
            )
        await self._async_light_calls(calls, "set holiday colors")

    async def _async_light_calls(self, calls: list, what: str) -> None:
        """Run light service calls together, without waiting forever.

        A slow or unresponsive light must not hold the controller (and the
        off-time check behind it) hostage.
        """
        if not calls:
            return
        try:
            async with asyncio.timeout(LIGHT_COMMAND_TIMEOUT):
                results = await asyncio.gather(*calls, return_exceptions=True)
        except TimeoutError:
            self.slow_light_commands += 1
            _LOGGER.warning(
                "Lights took longer than %ss to %s; carrying on",
                LIGHT_COMMAND_TIMEOUT,
                what,
            )
            return
        for result in results:
            if isinstance(result, Exception):
                _LOGGER.warning("Failed to %s: %s", what, result)

    def light_kind(self, entity_id: str) -> str:
        """Whether a light shows color, color temperature, brightness or on/off."""
        state = self.hass.states.get(entity_id)
        modes = state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) if state else None
        return light_kind(modes)

    def _command_for(
        self, entity_id: str, rgb: list[int], holiday: Holiday
    ) -> tuple[tuple, tuple[str, Any] | None]:
        """The turn_on data for one light, and what it should report back."""
        kind = self.light_kind(entity_id)
        data: dict[str, Any] = {}
        expected: tuple[str, Any] | None
        if kind == LIGHT_COLOR:
            data[ATTR_RGB_COLOR] = rgb
            expected = ("rgb", rgb)
        elif kind == LIGHT_TEMP:
            kelvin = color_to_kelvin(rgb)
            state = self.hass.states.get(entity_id)
            if state is not None:
                low = state.attributes.get("min_color_temp_kelvin")
                high = state.attributes.get("max_color_temp_kelvin")
                if low:
                    kelvin = max(kelvin, int(low))
                if high:
                    kelvin = min(kelvin, int(high))
            data[ATTR_COLOR_TEMP_KELVIN] = kelvin
            expected = ("kelvin", kelvin)
        elif kind == LIGHT_DIMMABLE:
            data[ATTR_BRIGHTNESS_PCT] = color_to_brightness_pct(
                rgb, holiday.brightness or 100
            )
            expected = None
        else:
            expected = None
        if holiday.brightness and kind in (LIGHT_COLOR, LIGHT_TEMP):
            data[ATTR_BRIGHTNESS_PCT] = holiday.brightness
        key = tuple(
            sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in data.items())
        )
        return key, expected

    async def _async_end_night(
        self, now: datetime, *, include_manual: bool = False
    ) -> None:
        """Schedule finished: turn lights off and wait for tomorrow.

        The schedule leaves lights someone changed by hand alone; the
        "Turn off for tonight" button turns off every holiday light.
        """
        self._stop_rotation()
        self._stop_watching_lights()
        lights = list(self._snapshot)
        if self.running:
            pool = (
                self.running.lights
                if include_manual
                else self._controlled(self.running)
            )
            lights.extend(e for e in pool if e not in lights)
        if not include_manual:
            lights = [e for e in lights if e not in self.night.overridden]
        if lights:
            off_context = self._context()
            self._guard_off(lights, off_context)
            data: dict[str, Any] = {ATTR_ENTITY_ID: lights}
            if self.running and self.running.transition:
                data[ATTR_TRANSITION] = self.running.transition
            await self._async_light_calls(
                [
                    self.hass.services.async_call(
                        LIGHT_DOMAIN,
                        SERVICE_TURN_OFF,
                        data,
                        blocking=True,
                        context=off_context,
                    )
                ],
                "turn off holiday lights",
            )
        # The night the lights were on is done, which may be an earlier
        # night than now if Home Assistant missed the off time.
        lit_night = night_of(self.on_at) if self.on_at else night_of(now)
        self._snapshot.clear()
        self._commanded.clear()
        self.light_colors.clear()
        self.running = None
        self.on_at = None
        self.offset = 0
        self.done_night = lit_night
        self._notify_lights()

    async def _async_release(self, restore: bool) -> None:
        """Stop and put lights back the way they were."""
        self._stop_rotation()
        self._stop_watching_lights()
        if restore:
            await self._async_restore(list(self._snapshot))
        self._snapshot.clear()
        self._commanded.clear()
        self.light_colors.clear()
        self.night.overridden.clear()
        self.running = None
        self.on_at = None
        self.offset = 0
        self._notify_lights()

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
        context = self._context()
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
                        context=context,
                    )
                )
                continue
            data = {k: v for k, v in saved.items() if k != "on"}
            data[ATTR_ENTITY_ID] = entity_id
            calls.append(
                self.hass.services.async_call(
                    LIGHT_DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=context
                )
            )
        await self._async_light_calls(calls, "restore lights")

    # --- manual changes ----------------------------------------------------

    def _watch_lights(self, holiday: Holiday) -> None:
        self._stop_watching_lights()
        if not self.respect_manual or not holiday.lights:
            return
        self._light_watch_unsub = self.hass.bus.async_listen(
            EVENT_CALL_SERVICE,
            self._async_light_command,
            event_filter=_is_light_command,
        )

    def _stop_watching_lights(self) -> None:
        if self._light_watch_unsub:
            self._light_watch_unsub()
            self._light_watch_unsub = None

    @callback
    def _async_light_command(self, event: Event) -> None:
        """Leave a light alone for the night if someone else commands it.

        Only light service calls made by something other than this
        integration count: the app, an automation, a remote, a voice
        assistant. Reported colors are not compared, since slow lights
        often report an older color long after a command.
        """
        holiday = self.running
        if holiday is None or event.context.id in self._our_contexts:
            return
        call = ServiceCall(
            self.hass,
            event.data[ATTR_DOMAIN],
            event.data[ATTR_SERVICE],
            dict(event.data.get(ATTR_SERVICE_DATA) or {}),
            event.context,
        )
        selected = async_extract_referenced_entity_ids(self.hass, call)
        targets = selected.referenced | selected.indirectly_referenced
        changed = [
            entity_id
            for entity_id in holiday.lights
            if entity_id in targets and entity_id not in self.night.overridden
        ]
        if not changed:
            return
        _LOGGER.info(
            "%s changed by %s.%s; leaving it alone until tomorrow",
            ", ".join(changed),
            event.data[ATTR_DOMAIN],
            event.data[ATTR_SERVICE],
        )
        for entity_id in changed:
            self.night.overridden.add(entity_id)
            # They own it now: don't restore or turn it off later.
            self._snapshot.pop(entity_id, None)
            self._commanded.pop(entity_id, None)
        self._notify_lights()
        self._notify()
        self.hass.async_create_task(self._async_save())

    # --- repairs -----------------------------------------------------------

    def _check_repairs(self) -> None:
        """Raise or clear issues for the holiday that is running."""
        holiday = self.running
        if holiday is None:
            return
        unavailable: list[str] = []
        for entity_id in holiday.lights:
            state = self.hass.states.get(entity_id)
            if state is None or state.state == STATE_UNAVAILABLE:
                strikes = self._unavailable_strikes.get(entity_id, 0) + 1
                self._unavailable_strikes[entity_id] = strikes
                if strikes >= UNAVAILABLE_STRIKES:
                    unavailable.append(entity_id)
                continue
            self._unavailable_strikes.pop(entity_id, None)
        self._set_issue("lights_unavailable", holiday, unavailable)

    def _set_issue(self, key: str, holiday: Holiday, lights: list[str]) -> None:
        issue_id = f"{key}_{holiday.id}"
        if not lights:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=key,
            translation_placeholders={
                "holiday": holiday.name,
                "lights": ", ".join(lights),
            },
        )

    def _remove_stale_issues(self) -> None:
        """Drop issues for holidays that no longer exist."""
        registry = ir.async_get(self.hass)
        for domain, issue_id in list(registry.issues):
            if domain != DOMAIN:
                continue
            holiday_id = issue_id.rsplit("_", 1)[-1]
            # "no_color" issues came from 1.4 and earlier: those lights are
            # handled now, so the issue no longer applies.
            if holiday_id not in self.holidays or issue_id.startswith("no_color_"):
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    # --- storage -----------------------------------------------------------

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "enabled": self.enabled,
                "theme": self.theme,
                "on_at": self.on_at.isoformat() if self.on_at else None,
                "done_night": self.done_night.isoformat() if self.done_night else None,
                "offset": self.offset,
                "snapshot": self._snapshot,
                "night_key": self._night_key.isoformat() if self._night_key else None,
                "overridden": sorted(self.night.overridden),
            }
        )
