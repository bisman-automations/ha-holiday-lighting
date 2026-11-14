"""The sidebar page's websocket API and the controls behind it (1.13.0)."""

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    CLIENT_ID,
    MockUser,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.holiday_lighting.const import DOMAIN
from homeassistant.core import HomeAssistant
from tests.test_init import DARK, LIGHTS, _entry_with, _holiday, _start, _tick, tz  # noqa: F401

SPEAKERS = ["media_player.porch_speaker"]


def _entry(**options):
    return _entry_with(
        _holiday(
            "Halloween",
            kind="yearly",
            start="10-01",
            end="10-31",
            colors=["#FF6600", "#8000FF"],
        ),
        _holiday(
            "Christmas",
            kind="yearly",
            start="12-01",
            end="12-26",
            colors=["#FF0000", "#00FF00"],
        ),
        **options,
    )


def _lights(hass: HomeAssistant) -> dict:
    for light in LIGHTS:
        hass.states.async_set(light, "off", {"supported_color_modes": ["rgb"]})
    return {
        "on": async_mock_service(hass, "light", "turn_on"),
        "off": async_mock_service(hass, "light", "turn_off"),
    }


async def _client(hass, hass_ws_client, user):
    """Log in with a token made at the frozen time."""
    refresh = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    return await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))


async def _ws(client, **msg):
    await client.send_json_auto_id(msg)
    return await client.receive_json()


async def test_state_and_everyday_controls(
    hass: HomeAssistant,
    hass_ws_client,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 15, 0, tzinfo=tz))
    calls = _lights(hass)
    entry = _entry()
    dark = False
    with patch(DARK, side_effect=lambda: dark):
        await _start(hass, entry)
        client = await _client(hass, hass_ws_client, hass_admin_user)

        reply = await _ws(client, type=f"{DOMAIN}/state")
        assert reply["success"]
        state = reply["result"]
        assert state["is_admin"] is True
        assert state["enabled"] is True
        assert state["status"] == "waiting_for_dark"
        assert state["shown"]["name"] == "Halloween"
        assert [h["name"] for h in state["themes"]] == ["Christmas", "Halloween"]
        # Holidays in date order: Halloween is on now, Christmas comes later.
        assert [h["name"] for h in state["holidays"]] == ["Halloween", "Christmas"]
        assert state["holidays"][0]["when"]["now"]
        assert state["holidays"][1]["when"]["start"] == "2026-12-01"
        assert state["next"] == {
            "name": "Christmas",
            "date": "2026-12-01",
            "days": 42,
        }
        assert len(state["coming"]) == 21
        assert state["coming"][0]["holiday"]["name"] == "Halloween"
        assert state["coming"][12]["holiday"] is None  # November 1st
        assert [row["entity_id"] for row in state["lights"]] == LIGHTS
        assert state["timeline"]["threshold"] == -2
        assert state["timeline"]["hard_off"].startswith("2026-10-20T23:00")

        # Start now, then stop.
        reply = await _ws(client, type=f"{DOMAIN}/press", action="start")
        assert reply["result"]["status"] == "on"
        assert calls["on"]
        reply = await _ws(client, type=f"{DOMAIN}/press", action="stop")
        assert reply["result"]["status"] == "done_for_tonight"

        # The theme, and a theme that doesn't exist.
        christmas = next(h["id"] for h in state["themes"] if h["name"] == "Christmas")
        reply = await _ws(client, type=f"{DOMAIN}/theme", theme=christmas)
        assert reply["result"]["theme"] == christmas
        reply = await _ws(client, type=f"{DOMAIN}/theme", theme="nope")
        assert not reply["success"]
        await _ws(client, type=f"{DOMAIN}/theme", theme="auto")

        reply = await _ws(client, type=f"{DOMAIN}/enabled", enabled=False)
        assert reply["result"]["enabled"] is False
        assert hass.states.get("switch.holiday_lighting_enabled").state == "off"


async def test_keep_on_longer_tonight(
    hass: HomeAssistant,
    hass_ws_client,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 18, 0, tzinfo=tz))
    calls = _lights(hass)
    with patch(DARK, return_value=True):
        await _start(hass, _entry())
        client = await _client(hass, hass_ws_client, hass_admin_user)
        state = (await _ws(client, type=f"{DOMAIN}/state"))["result"]
        # 5 hours from 18:00, but 23:00 is the hard off time.
        assert state["timeline"]["off_at"].startswith("2026-10-20T23:00")

        reply = await _ws(client, type=f"{DOMAIN}/off_tonight", extend_minutes=60)
        timeline = reply["result"]["timeline"]
        assert timeline["off_at"].startswith("2026-10-21T00:00")
        assert timeline["off_tonight"].startswith("2026-10-21T00:00")

        # Past 23:00 the lights stay on, and turn off at midnight.
        calls["off"].clear()
        await _tick(hass, freezer, datetime(2026, 10, 20, 23, 30, tzinfo=tz))
        assert not calls["off"]
        await _tick(hass, freezer, datetime(2026, 10, 21, 0, 1, tzinfo=tz))
        assert calls["off"]
        assert hass.states.get("sensor.holiday_lighting_status").state == (
            "done_for_tonight"
        )
        # The night is in the history.
        client = await _client(hass, hass_ws_client, hass_admin_user)
        state = (await _ws(client, type=f"{DOMAIN}/state"))["result"]
        (night,) = state["history"]
        assert night["night"] == "2026-10-20"
        assert night["holiday"] == "Halloween"
        assert night["on"].startswith("2026-10-20T18:00")
        assert night["off"].startswith("2026-10-21T00:01")


async def test_off_time_tonight(
    hass: HomeAssistant,
    hass_ws_client,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 18, 0, tzinfo=tz))
    calls = _lights(hass)
    with patch(DARK, return_value=True):
        await _start(hass, _entry())
        client = await _client(hass, hass_ws_client, hass_admin_user)

        reply = await _ws(client, type=f"{DOMAIN}/off_tonight", off_at="21:15")
        assert reply["result"]["timeline"]["off_at"].startswith("2026-10-20T21:15")
        # A time before now is refused; so is a time that isn't one.
        reply = await _ws(client, type=f"{DOMAIN}/off_tonight", off_at="17:00")
        assert not reply["success"]
        reply = await _ws(client, type=f"{DOMAIN}/off_tonight", off_at="soon")
        assert not reply["success"]
        await _ws(client, type=f"{DOMAIN}/off_tonight", off_at="21:15")

        calls["off"].clear()
        await _tick(hass, freezer, datetime(2026, 10, 20, 21, 16, tzinfo=tz))
        assert calls["off"]

        # Back to the usual rules: tonight comes back on until 23:00.
        reply = await _ws(client, type=f"{DOMAIN}/off_tonight", reset=True)
        assert reply["result"]["timeline"]["off_tonight"] is None


async def test_off_time_in_the_past_is_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 22, 0, tzinfo=tz))
    _lights(hass)
    with patch(DARK, return_value=True):
        entry = _entry()
        await _start(hass, entry)
        controller = entry.runtime_data
        try:
            await controller.async_set_off_tonight(
                datetime(2026, 10, 20, 21, 0, tzinfo=tz)
            )
        except Exception as err:  # noqa: BLE001
            assert err.translation_key == "off_time_passed"
        else:
            raise AssertionError("expected a refusal")
        try:
            await controller.async_set_off_tonight(
                datetime(2026, 10, 22, 21, 0, tzinfo=tz)
            )
        except Exception as err:  # noqa: BLE001
            assert err.translation_key == "off_time_too_late"
        else:
            raise AssertionError("expected a refusal")


async def test_tonights_tweaks_and_keeping_them(
    hass: HomeAssistant,
    hass_ws_client,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 18, 0, tzinfo=tz))
    calls = _lights(hass)
    entry = _entry()
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        client = await _client(hass, hass_ws_client, hass_admin_user)

        calls["on"].clear()
        reply = await _ws(client, type=f"{DOMAIN}/tweaks", brightness=40, interval=5)
        result = reply["result"]
        assert result["tweaks"] == {"brightness": 40, "interval": 5}
        assert result["shown"]["interval"] == 5
        assert calls["on"]
        assert all(call.data.get("brightness_pct") == 40 for call in calls["on"])

        # Brightness 0 means the holiday's own.
        reply = await _ws(client, type=f"{DOMAIN}/tweaks", brightness=0)
        assert reply["result"]["shown"]["brightness"] in (None, 100)

        await _ws(client, type=f"{DOMAIN}/tweaks", mode="cycle")
        reply = await _ws(client, type=f"{DOMAIN}/keep_tweaks")
        assert reply["success"], reply
        await hass.async_block_till_done(wait_background_tasks=True)
        (halloween,) = [s for s in entry.subentries.values() if s.title == "Halloween"]
        assert halloween.data["interval"] == 5
        assert halloween.data["mode"] == "cycle"
        assert entry.runtime_data.night.tweaks == {}

        # Nothing left to keep.
        reply = await _ws(client, type=f"{DOMAIN}/keep_tweaks")
        assert not reply["success"]

        await _ws(client, type=f"{DOMAIN}/tweaks", interval=9)
        reply = await _ws(client, type=f"{DOMAIN}/tweaks", reset=True)
        assert reply["result"]["tweaks"] == {}
        assert reply["result"]["shown"]["interval"] == 5


async def test_tweaks_are_for_tonight_only(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 18, 0, tzinfo=tz))
    _lights(hass)
    entry = _entry()
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        controller = entry.runtime_data
        await controller.async_set_tweaks({"interval": 7})
        assert controller.running.interval == 7
        await _tick(hass, freezer, datetime(2026, 10, 21, 18, 0, tzinfo=tz))
        assert entry.runtime_data.night.tweaks == {}
        assert entry.runtime_data.running.interval == 30


async def test_leave_a_light_out_and_give_one_back(
    hass: HomeAssistant,
    hass_ws_client,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 18, 0, tzinfo=tz))
    calls = _lights(hass)
    entry = _entry()
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        client = await _client(hass, hass_ws_client, hass_admin_user)

        reply = await _ws(
            client, type=f"{DOMAIN}/light", entity_id="light.tree", action="leave_out"
        )
        rows = {row["entity_id"]: row for row in reply["result"]["lights"]}
        assert rows["light.tree"]["state"] == "left_out"
        # Put back as it was before the show (off).
        assert any("light.tree" in call.data["entity_id"] for call in calls["off"])
        calls["on"].clear()
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert calls["on"]
        assert all("light.tree" not in call.data["entity_id"] for call in calls["on"])

        calls["on"].clear()
        reply = await _ws(
            client, type=f"{DOMAIN}/light", entity_id="light.tree", action="include"
        )
        rows = {row["entity_id"]: row for row in reply["result"]["lights"]}
        assert rows["light.tree"]["state"] == "color"
        assert any("light.tree" in call.data["entity_id"] for call in calls["on"])

        # A light changed by hand, given back.
        controller = entry.runtime_data
        controller.night.overridden.add("light.porch")
        reply = await _ws(
            client, type=f"{DOMAIN}/light", entity_id="light.porch", action="give_back"
        )
        assert "light.porch" not in controller.night.overridden

        reply = await _ws(
            client, type=f"{DOMAIN}/light", entity_id="light.nope", action="include"
        )
        assert not reply["success"]

        # Still left out after a restart the same night.
        await controller.async_set_light("light.garage", "leave_out")
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert "light.garage" in entry.runtime_data.night.left_out


async def test_music_controls(
    hass: HomeAssistant,
    hass_ws_client,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 18, 0, tzinfo=tz))
    _lights(hass)
    play = async_mock_service(hass, "music_assistant", "play_media")
    volume = async_mock_service(hass, "media_player", "volume_set")
    async_mock_service(hass, "media_player", "repeat_set")
    stop = async_mock_service(hass, "media_player", "media_stop")
    hass.states.async_set(SPEAKERS[0], "idle", {"volume_level": 0.3})
    with patch(DARK, return_value=True):
        entry = _entry(music_players=SPEAKERS, music_volume=30)
        await _start(hass, entry)
        client = await _client(hass, hass_ws_client, hass_admin_user)
        assert len(play) == 1

        reply = await _ws(client, type=f"{DOMAIN}/state")
        music = reply["result"]["music"]
        assert music["playing"] == "Halloween"
        assert music["players"][0]["volume"] == 30

        reply = await _ws(client, type=f"{DOMAIN}/music", action="stop")
        assert reply["result"]["music"]["off_tonight"] is True
        assert stop

        # Next colors doesn't start the music again tonight.
        await _ws(client, type=f"{DOMAIN}/press", action="next")
        assert len(play) == 1

        reply = await _ws(client, type=f"{DOMAIN}/music", action="play")
        assert reply["result"]["music"]["off_tonight"] is False
        assert len(play) == 2

        await _ws(client, type=f"{DOMAIN}/music", action="volume", volume=55)
        assert volume[-1].data["volume_level"] == 0.55


async def test_music_needs_players(
    hass: HomeAssistant,
    hass_ws_client,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 15, 0, tzinfo=tz))
    _lights(hass)
    with patch(DARK, return_value=False):
        await _start(hass, _entry())
        client = await _client(hass, hass_ws_client, hass_admin_user)
        reply = await _ws(client, type=f"{DOMAIN}/music", action="play")
        assert not reply["success"]


async def test_try_a_holiday_then_go_back(
    hass: HomeAssistant,
    hass_ws_client,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 12, 0, tzinfo=tz))
    calls = _lights(hass)
    entry = _entry()
    with patch(DARK, return_value=False):
        await _start(hass, entry)
        client = await _client(hass, hass_ws_client, hass_admin_user)
        state = (await _ws(client, type=f"{DOMAIN}/state"))["result"]
        christmas = next(h["id"] for h in state["themes"] if h["name"] == "Christmas")

        reply = await _ws(client, type=f"{DOMAIN}/try", holiday_id=christmas, minutes=2)
        result = reply["result"]
        assert result["trial"]["name"] == "Christmas"
        assert result["running"] is True
        colors = {tuple(call.data["rgb_color"]) for call in calls["on"]}
        assert (255, 0, 0) in colors

        # Daylight doesn't end the trial early.
        await _tick(hass, freezer, datetime(2026, 10, 20, 12, 1, tzinfo=tz))
        assert entry.runtime_data.trial is not None

        # Two minutes later the lights go back to how they were.
        calls["off"].clear()
        await _tick(hass, freezer, datetime(2026, 10, 20, 12, 2, 5, tzinfo=tz))
        controller = entry.runtime_data
        assert controller.trial is None
        assert controller.running is None
        assert calls["off"]
        assert controller.on_at is None
        assert controller.history == []

        # Stop early.
        client = await _client(hass, hass_ws_client, hass_admin_user)
        await _ws(client, type=f"{DOMAIN}/try", holiday_id=christmas)
        reply = await _ws(client, type=f"{DOMAIN}/try/stop")
        assert reply["result"]["trial"] is None
        reply = await _ws(client, type=f"{DOMAIN}/try", holiday_id="nope")
        assert not reply["success"]


async def test_try_while_on_goes_back_to_tonights_show(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 18, 0, tzinfo=tz))
    _lights(hass)
    entry = _entry()
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        controller = entry.runtime_data
        christmas = next(
            h.id for h in controller.holidays.values() if h.name == "Christmas"
        )
        await controller.async_try(christmas, 1)
        assert controller.running.name == "Christmas"
        await _tick(hass, freezer, datetime(2026, 10, 20, 18, 1, 5, tzinfo=tz))
        assert controller.trial is None
        assert controller.running.name == "Halloween"


async def test_admin_only_commands(
    hass: HomeAssistant,
    hass_ws_client,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 20, 15, 0, tzinfo=tz))
    _lights(hass)
    with patch(DARK, return_value=False):
        await _start(hass, _entry())
        client = await _client(hass, hass_ws_client, hass_admin_user)
        hass_admin_user.groups = []
        reply = await _ws(client, type=f"{DOMAIN}/state")
        assert reply["result"]["is_admin"] is False
        for msg in (
            {"type": f"{DOMAIN}/tweaks", "brightness": 50},
            {"type": f"{DOMAIN}/keep_tweaks"},
            {"type": f"{DOMAIN}/try", "holiday_id": "x"},
            {"type": f"{DOMAIN}/try/stop"},
        ):
            reply = await _ws(client, **msg)
            assert reply["error"]["code"] == "unauthorized", msg
        # The everyday controls stay open to everyone.
        reply = await _ws(client, type=f"{DOMAIN}/press", action="start")
        assert reply["success"]


async def test_not_set_up(hass: HomeAssistant, hass_ws_client) -> None:
    entry = _entry()
    _lights(hass)
    await _start(hass, entry)
    await hass.config_entries.async_unload(entry.entry_id)
    client = await hass_ws_client(hass)
    reply = await _ws(client, type=f"{DOMAIN}/state")
    assert reply["error"]["code"] == "not_loaded"
