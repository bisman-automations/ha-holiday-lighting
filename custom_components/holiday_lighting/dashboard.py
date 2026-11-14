"""The Holiday Lights sidebar page's websocket API (1.13.0).

Everyone who can open Home Assistant can see the page and use the everyday
controls: the Enabled switch, the theme, the four buttons, tonight's off time,
the theme music, and tonight's lights (leave one out, give one back). Changing
how a holiday looks (tonight's brightness, speed and effect, keeping them,
and Try it now) is for admins; editing holidays goes through Home
Assistant's own config flow API, which is admin only too.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import datetime, time
import functools
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .const import DEFAULT_HOLIDAY_ID, DOMAIN, KIND_CALENDAR, MODES, THEME_AUTO
from .controller import Holiday, HolidayLightingController
from .schedule import current_window, hard_off_at, night_of, upcoming_holiday

WS = f"{DOMAIN}/"
COMING_NIGHTS = 21


def _controller(hass: HomeAssistant) -> HolidayLightingController | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    return None


def _iso(when: datetime | None) -> str | None:
    return when.isoformat() if when else None


def _holiday(
    controller: HolidayLightingController, holiday: Holiday | None
) -> dict | None:
    if holiday is None:
        return None
    return {
        "id": holiday.id,
        "name": holiday.name,
        "kind": holiday.kind,
        "colors": list(holiday.colors),
        "color_names": list(holiday.color_names),
        "mode": holiday.mode,
        "interval": holiday.interval,
        "brightness": holiday.brightness,
        "lights": len(holiday.lights),
        "default": holiday.id == DEFAULT_HOLIDAY_ID,
        "music": bool(controller.music_players and holiday.music_enabled)
        and holiday.id != DEFAULT_HOLIDAY_ID,
    }


def _lights(controller: HolidayLightingController) -> list[dict[str, Any]]:
    hass = controller.hass
    shown = controller.running or controller.shown_holiday()
    in_show = set(shown.lights) if shown else set()
    rows = []
    for entity_id in controller.all_lights:
        state = hass.states.get(entity_id)
        how, color = controller.light_color(entity_id)
        if entity_id in controller.night.left_out:
            how = "left_out"
        rows.append(
            {
                "entity_id": entity_id,
                "name": (state.name if state else entity_id.split(".", 1)[-1]),
                "kind": controller.light_kind(entity_id),
                "state": how,
                "color": color.get("hex") if color else None,
                "color_name": color.get("name") if color else None,
                "in_show": entity_id in in_show,
                "available": state is not None and state.state != STATE_UNAVAILABLE,
            }
        )
    return rows


def _music(controller: HolidayLightingController) -> dict[str, Any]:
    hass = controller.hass
    players = []
    for entity_id in controller.music_players:
        state = hass.states.get(entity_id)
        players.append(
            {
                "entity_id": entity_id,
                "name": state.name if state else entity_id,
                "state": state.state if state else STATE_UNAVAILABLE,
                "volume": round(float(state.attributes.get("volume_level") or 0) * 100)
                if state and state.attributes.get("volume_level") is not None
                else None,
            }
        )
    playing = controller.holidays.get(controller.music_holiday or "")
    return {
        "players": players,
        "playing": playing.name if playing else None,
        "error": controller.music_error,
        "off_tonight": controller.night.music_off,
    }


def _timeline(controller: HolidayLightingController) -> dict[str, Any]:
    hass = controller.hass
    lux = None
    if controller.lux_sensor and (state := hass.states.get(controller.lux_sensor)):
        if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                lux = float(state.state)
            except ValueError:
                lux = None
    return {
        "now": dt_util.now().isoformat(),
        "sunset": _iso(controller.sunset()),
        "on_at": _iso(controller.on_at),
        "next_on": _iso(controller.next_on()),
        "off_at": _iso(controller.next_off()),
        "hard_off": _iso(controller.hard_off_tonight()),
        "off_tonight": _iso(controller.night.off_at),
        "use_schedule": controller.use_schedule,
        "dark_source": controller.dark_source,
        "elevation": round(controller.current_sun_elevation(), 1),
        "threshold": controller.sun_elevation,
        "is_dark": controller.is_dark(),
        "lux": lux,
        "lux_threshold": controller.lux_threshold if controller.lux_sensor else None,
    }


def _when(holiday: Holiday) -> dict[str, str] | None:
    """The holiday's current window, else the next one."""
    if holiday.kind == KIND_CALENDAR:
        return None
    today = night_of(dt_util.now())
    mapping = holiday.as_mapping()
    if window := current_window(mapping, today):
        return {
            "start": window[0].isoformat(),
            "end": window[1].isoformat(),
            "now": "1",
        }
    found = upcoming_holiday([mapping], today)
    if not found:
        return None
    window = current_window(mapping, found[1])
    end = window[1] if window else found[1]
    return {"start": found[1].isoformat(), "end": end.isoformat()}


@callback
def dashboard_state(
    controller: HolidayLightingController, is_admin: bool
) -> dict[str, Any]:
    """Everything the page shows."""
    tonight = night_of(dt_util.now())
    upcoming = controller.upcoming()
    shown = controller.running or controller.shown_holiday()
    coming = []
    for day, holiday in controller.nights_ahead(COMING_NIGHTS):
        coming.append(
            {
                "date": day.isoformat(),
                "holiday": _holiday(controller, holiday),
            }
        )
    trial = controller.trial
    return {
        "is_admin": is_admin,
        "enabled": controller.enabled,
        "status": controller.status,
        "theme": controller.theme,
        "themes": [
            {"id": h.id, "name": h.name}
            for h in sorted(controller.holidays.values(), key=lambda h: h.name)
        ],
        "default_colors": controller.default_holiday is not None,
        "default_tonight": controller.default_night == tonight,
        "shown": _holiday(controller, shown),
        "running": controller.running is not None,
        "tweaks": dict(controller.night.tweaks),
        "modes": list(MODES),
        "timeline": _timeline(controller),
        "lights": _lights(controller),
        "music": _music(controller),
        "holidays": sorted(
            (
                {**_holiday(controller, h), "when": _when(h)}  # type: ignore[dict-item]
                for h in controller.holidays.values()
            ),
            key=lambda h: ((h["when"] or {}).get("start", "9999"), h["name"]),
        ),
        "coming": coming,
        "next": (
            {
                "name": upcoming[0].name,
                "date": upcoming[1].isoformat(),
                "days": (upcoming[1] - dt_util.now().date()).days,
            }
            if upcoming
            else None
        ),
        "history": list(reversed(controller.history)),
        "trial": (
            {
                "holiday": trial["holiday"],
                "name": trial["name"],
                "until": _iso(trial["until"]),
            }
            if trial
            else None
        ),
        "entry_id": controller.entry.entry_id,
    }


type Handler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict, HolidayLightingController],
    Coroutine[Any, Any, None],
]


def _with_controller(func: Handler) -> Callable:
    """Find the controller, run the command, and answer with the new state."""

    @functools.wraps(func)
    async def wrapper(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        controller = _controller(hass)
        if controller is None:
            connection.send_error(
                msg["id"], "not_loaded", "Holiday Lighting isn't set up"
            )
            return
        try:
            await func(hass, connection, msg, controller)
        except (HomeAssistantError, ValueError) as err:
            connection.send_error(msg["id"], "failed", str(err))
            return
        # The controller may have been replaced (keeping a holiday reloads).
        controller = _controller(hass) or controller
        connection.send_result(
            msg["id"], dashboard_state(controller, connection.user.is_admin)
        )

    return wrapper


@websocket_api.websocket_command({vol.Required("type"): WS + "state"})
@websocket_api.async_response
@_with_controller
async def ws_state(hass, connection, msg, controller) -> None:
    """The page's state."""


@websocket_api.websocket_command(
    {vol.Required("type"): WS + "enabled", vol.Required("enabled"): bool}
)
@websocket_api.async_response
@_with_controller
async def ws_enabled(hass, connection, msg, controller) -> None:
    await controller.async_set_enabled(msg["enabled"])


@websocket_api.websocket_command(
    {vol.Required("type"): WS + "theme", vol.Required("theme"): str}
)
@websocket_api.async_response
@_with_controller
async def ws_theme(hass, connection, msg, controller) -> None:
    if msg["theme"] != THEME_AUTO and msg["theme"] not in controller.holidays:
        raise ValueError("Pick one of the holidays")
    await controller.async_set_theme(msg["theme"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS + "press",
        vol.Required("action"): vol.In(("start", "next", "stop", "default")),
    }
)
@websocket_api.async_response
@_with_controller
async def ws_press(hass, connection, msg, controller) -> None:
    """The four everyday buttons."""
    action = msg["action"]
    if action == "start":
        await controller.async_force_on()
    elif action == "next":
        await controller.async_advance()
    elif action == "stop":
        await controller.async_force_off()
    else:
        await controller.async_use_default_tonight()


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS + "off_tonight",
        vol.Optional("extend_minutes"): vol.All(vol.Coerce(int), vol.Range(1, 720)),
        vol.Optional("off_at"): str,
        vol.Optional("reset"): bool,
    }
)
@websocket_api.async_response
@_with_controller
async def ws_off_tonight(hass, connection, msg, controller) -> None:
    """Keep the lights on longer tonight, turn them off at a time, or go back
    to the usual off time."""
    if msg.get("reset"):
        await controller.async_set_off_tonight(None)
        return
    if minutes := msg.get("extend_minutes"):
        await controller.async_set_off_tonight(extend_minutes=minutes)
        return
    parsed = dt_util.parse_time(msg.get("off_at") or "")
    if parsed is None:
        raise ValueError("Pick a time")
    now = dt_util.now()
    off_at = hard_off_at(night_of(now), time(parsed.hour, parsed.minute), now.tzinfo)
    await controller.async_set_off_tonight(off_at)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS + "tweaks",
        vol.Optional("brightness"): vol.Any(
            None, vol.All(vol.Coerce(int), vol.Range(0, 100))
        ),
        vol.Optional("interval"): vol.Any(
            None, vol.All(vol.Coerce(int), vol.Range(1, 3600))
        ),
        vol.Optional("mode"): vol.Any(None, vol.In(MODES)),
        vol.Optional("reset"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@_with_controller
async def ws_tweaks(hass, connection, msg, controller) -> None:
    """Tonight's brightness, speed and effect (admins)."""
    if msg.get("reset"):
        await controller.async_set_tweaks(None)
        return
    tweaks = {**controller.night.tweaks}
    for key in ("brightness", "interval", "mode"):
        if key in msg:
            tweaks[key] = msg[key]
    await controller.async_set_tweaks(tweaks)


@websocket_api.websocket_command({vol.Required("type"): WS + "keep_tweaks"})
@websocket_api.require_admin
@websocket_api.async_response
@_with_controller
async def ws_keep_tweaks(hass, connection, msg, controller) -> None:
    """Save tonight's brightness, speed and effect to the holiday (admins)."""
    await controller.async_keep_tweaks()
    await hass.async_block_till_done()


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS + "light",
        vol.Required("entity_id"): str,
        vol.Required("action"): vol.In(("leave_out", "include", "give_back")),
    }
)
@websocket_api.async_response
@_with_controller
async def ws_light(hass, connection, msg, controller) -> None:
    """One light, tonight: leave it out, put it back, or give it back to the show."""
    await controller.async_set_light(msg["entity_id"], msg["action"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS + "music",
        vol.Required("action"): vol.In(("play", "stop", "volume")),
        vol.Optional("volume"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
    }
)
@websocket_api.async_response
@_with_controller
async def ws_music(hass, connection, msg, controller) -> None:
    await controller.async_music(msg["action"], msg.get("volume"))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS + "try",
        vol.Required("holiday_id"): str,
        vol.Optional("minutes", default=2): vol.All(vol.Coerce(int), vol.Range(1, 10)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@_with_controller
async def ws_try(hass, connection, msg, controller) -> None:
    """Show a holiday on the lights for a few minutes (admins)."""
    await controller.async_try(msg["holiday_id"], msg["minutes"])


@websocket_api.websocket_command({vol.Required("type"): WS + "try/stop"})
@websocket_api.require_admin
@websocket_api.async_response
@_with_controller
async def ws_try_stop(hass, connection, msg, controller) -> None:
    await controller.async_end_trial()


@callback
def async_register_dashboard(hass: HomeAssistant) -> None:
    for command in (
        ws_state,
        ws_enabled,
        ws_theme,
        ws_press,
        ws_off_tonight,
        ws_tweaks,
        ws_keep_tweaks,
        ws_light,
        ws_music,
        ws_try,
        ws_try_stop,
    ):
        websocket_api.async_register_command(hass, command)
