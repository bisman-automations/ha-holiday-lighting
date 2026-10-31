"""Theme music on Music Assistant speakers while a holiday's lights are on."""

from datetime import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.holiday_lighting.config_flow import (
    SECTION_MUSIC,
    _holiday_schema,
    _normalise_holiday,
)
from custom_components.holiday_lighting.music import music_request
from homeassistant.core import HomeAssistant
from tests.test_init import DARK, _entry_with, _holiday, _start, tz  # noqa: F401

SPEAKERS = ["media_player.porch_speaker", "media_player.yard_speaker"]


def test_music_request() -> None:
    # Blank: a playlist found by the holiday's name.
    assert music_request("Halloween", None) == ("Halloween music", "playlist")
    assert music_request(" Halloween ", "  ") == ("Halloween music", "playlist")
    # A name: searched as a playlist; a link or URI: played as it is.
    assert music_request("Halloween", "Spooky Hits") == ("Spooky Hits", "playlist")
    assert music_request("Halloween", "library://playlist/12") == (
        "library://playlist/12",
        None,
    )


def _services(hass: HomeAssistant):
    return {
        "play": async_mock_service(hass, "music_assistant", "play_media"),
        "volume": async_mock_service(hass, "media_player", "volume_set"),
        "repeat": async_mock_service(hass, "media_player", "repeat_set"),
        "stop": async_mock_service(hass, "media_player", "media_stop"),
    }


async def test_music_plays_while_the_lights_are_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 7, 20, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    calls = _services(hass)
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
        music_players=SPEAKERS,
        music_volume=35,
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        (play,) = calls["play"]
        assert play.data == {
            "entity_id": SPEAKERS,
            "media_id": "Halloween music",
            "media_type": "playlist",
            "enqueue": "replace",
        }
        assert calls["volume"][0].data["volume_level"] == 0.35
        assert calls["repeat"][0].data["repeat"] == "all"
        assert entry.runtime_data.music_error is None

        # Next colors keeps the same holiday: the music isn't restarted.
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.holiday_lighting_next_colors"},
            blocking=True,
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(calls["play"]) == 1

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.holiday_lighting_turn_off_for_tonight"},
            blocking=True,
        )
        await hass.async_block_till_done(wait_background_tasks=True)
    assert calls["stop"][0].data["entity_id"] == SPEAKERS
    assert entry.runtime_data.music_holiday is None


async def test_a_holiday_can_pick_its_music_or_stay_quiet(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 12, 20, 20, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")
    calls = _services(hass)
    entry = _entry_with(
        _holiday(
            "Christmas",
            kind="yearly",
            start="12-01",
            end="12-31",
            music="library://playlist/7",
        ),
        music_players=SPEAKERS,
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
    (play,) = calls["play"]
    assert play.data["media_id"] == "library://playlist/7"
    assert "media_type" not in play.data
    # No volume set: the speakers keep theirs.
    assert calls["volume"] == []


async def test_quiet_holiday_and_no_speakers_play_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 7, 20, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")
    calls = _services(hass)
    entry = _entry_with(
        _holiday(
            "Halloween",
            kind="yearly",
            start="10-01",
            end="10-31",
            music_enabled=False,
        ),
        music_players=SPEAKERS,
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
    assert calls["play"] == []


async def test_without_music_assistant_the_lights_still_run(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    freezer.move_to(datetime(2026, 10, 7, 20, 0, tzinfo=tz))
    turn_on = async_mock_service(hass, "light", "turn_on")
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
        music_players=SPEAKERS,
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
    assert turn_on
    assert entry.runtime_data.music_error == "Music Assistant isn't set up"
    assert entry.runtime_data.diagnostics()["music_error"]


def test_holiday_form_saves_theme_music() -> None:
    schema = _holiday_schema("yearly", {})
    assert SECTION_MUSIC in {str(key) for key in schema.schema}
    form = {
        "name": "Halloween",
        "start": "10-01",
        "end": "10-31",
        "colors": "orange",
        "mode": "rotate",
        "interval": 60,
        "transition": 2,
        SECTION_MUSIC: {"music_enabled": True, "music": "  Spooky Hits "},
    }
    data, errors = _normalise_holiday("yearly", form, set())
    assert not errors
    assert data["music"] == "Spooky Hits"
    assert data["music_enabled"] is True
    assert SECTION_MUSIC not in data
    quiet, _ = _normalise_holiday(
        "yearly", {**form, SECTION_MUSIC: {"music_enabled": False}}, set()
    )
    assert quiet["music_enabled"] is False
    assert "music" not in quiet


async def test_settings_offer_music_speakers_and_volume(hass: HomeAssistant) -> None:
    entry = _entry_with()
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    keys = {str(key) for key in result["data_schema"].schema}
    assert {"music_players", "music_volume"} <= keys
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "use_schedule": True,
            "dark_source": "sun",
            "sun_elevation": -2,
            "lux_threshold": 50,
            "respect_manual": True,
            "music_players": SPEAKERS,
            "music_volume": 40.0,
        },
    )
    assert entry.options["music_players"] == SPEAKERS
    assert entry.options["music_volume"] == 40


async def test_music_already_playing_carries_on_after_a_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz,  # noqa: F811
) -> None:
    """Saving a setting reloads the integration; the song isn't started over."""
    freezer.move_to(datetime(2026, 10, 7, 20, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")
    calls = _services(hass)
    for player in SPEAKERS:
        hass.states.async_set(player, "playing")
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
        music_players=SPEAKERS,
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
    assert calls["play"] == []
    assert entry.runtime_data.music_holiday is not None
