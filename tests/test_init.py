"""End-to-end tests: config flow and a full night of lights."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import voluptuous_serialize
from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.holiday_lighting.const import DOMAIN

LIGHTS = ["light.porch", "light.tree", "light.garage"]
DARK = "custom_components.holiday_lighting.controller.HolidayLightingController.is_dark"


@pytest.fixture
def tz(hass: HomeAssistant):
    return dt_util.get_time_zone(hass.config.time_zone)


async def test_config_flow_creates_presets(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"default_lights": LIGHTS, "presets": ["christmas", "halloween"]},
    )
    assert result["step_id"] == "schedule"

    # Illuminance mode without a sensor is rejected.
    bad = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "use_schedule": True,
            "dark_source": "lux",
            "sun_elevation": -2,
            "lux_threshold": 20,
        },
    )
    assert bad["errors"] == {"lux_sensor": "lux_sensor_required"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "use_schedule": True,
            "dark_source": "sun",
            "sun_elevation": -2,
            "lux_threshold": 20,
            "on_duration": {"hours": 5, "minutes": 0, "seconds": 0},
            "off_time": "23:00:00",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    titles = sorted(s.title for s in entry.subentries.values())
    assert titles == ["Christmas", "Halloween"]
    assert entry.options["default_lights"] == LIGHTS
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("switch.holiday_lighting_enabled").state == "off"
    assert hass.states.get("select.holiday_lighting_theme").attributes["options"] == [
        "Auto",
        "Christmas",
        "Halloween",
    ]


async def test_add_and_edit_holiday_subentry(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "holiday"), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"preset": "independence_day"}
    )
    assert result["step_id"] == "holiday"
    # The form serializes for the frontend, with a sortable picker list for
    # colors and a reorderable light list.
    schema = voluptuous_serialize.convert(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    fields = {field["name"]: field for field in schema}
    colors_field = fields["colors"]["selector"]["object"]
    assert colors_field["multiple"] is True
    assert colors_field["fields"]["color"]["selector"] == {"color_rgb": {}}
    assert fields["lights"]["selector"]["entity"]["reorder"] is True
    # Preset colors come pre-filled as named picker items.
    assert fields["colors"]["default"] == [
        {"name": "Red", "color": [255, 0, 0]},
        {"name": "White", "color": [255, 255, 255]},
        {"name": "Blue", "color": [0, 0, 255]},
    ]

    form = {
        "name": "Christmas",  # duplicate
        "start": "06-28",
        "end": "07-05",
        "colors": [],
        "lights": ["light.garage", "light.porch"],
        "mode": "rotate",
        "interval": 30,
        "transition": 2,
    }
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], form
    )
    assert result["errors"] == {"name": "name_exists", "colors": "colors_required"}

    # Order as the user dragged it, with one unnamed color.
    form |= {
        "name": "Fourth",
        "colors": [
            {"name": "Blue", "color": [0, 0, 255]},
            {"color": [255, 255, 255]},
            {"name": " Red ", "color": [255, 0, 0]},
        ],
    }
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], form
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    sub = next(s for s in entry.subentries.values() if s.title == "Fourth")
    assert sub.data["colors"] == ["#0000FF", "#FFFFFF", "#FF0000"]
    assert sub.data["color_names"] == ["Blue", "#FFFFFF", "Red"]
    assert sub.data["lights"] == ["light.garage", "light.porch"]
    # Entry reloaded, so the select picks up the new holiday.
    assert (
        "Fourth"
        in hass.states.get("select.holiday_lighting_theme").attributes["options"]
    )

    # Editing shows the saved colors, in order, and saves a new order.
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    shown = {
        f["name"]: f
        for f in voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    }
    assert [item["name"] for item in shown["colors"]["default"]] == [
        "Blue",
        "#FFFFFF",
        "Red",
    ]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        form
        | {
            "name": "July 4th",
            "end": "07-04",
            "colors": list(reversed(form["colors"])),
        },
    )
    assert result["reason"] == "reconfigure_successful"
    data = entry.subentries[sub.subentry_id].data
    assert data["end"] == "07-04"
    assert data["colors"] == ["#FF0000", "#FFFFFF", "#0000FF"]


async def test_edit_holiday_saved_by_1_0_0(hass: HomeAssistant) -> None:
    """Holidays saved before color names existed still open for editing."""
    entry = _entry()  # Christmas has colors but no color_names
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    sub_id = next(iter(entry.subentries))
    assert "color_names" not in entry.subentries[sub_id].data
    result = await entry.start_subentry_reconfigure_flow(hass, sub_id)
    shown = {
        f["name"]: f
        for f in voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    }
    assert shown["colors"]["default"] == [
        {"name": "#FF0000", "color": [255, 0, 0]},
        {"name": "#00FF00", "color": [0, 255, 0]},
        {"name": "#FFFFFF", "color": [255, 255, 255]},
    ]


def _entry(**options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Holiday Lighting",
        data={},
        options={
            "default_lights": LIGHTS,
            "use_schedule": True,
            "dark_source": "sun",
            "sun_elevation": -2,
            "lux_threshold": 20,
            "on_duration": {"hours": 5},
            "off_time": "23:00:00",
            **options,
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    "name": "Christmas",
                    "start": "12-01",
                    "end": "12-26",
                    "colors": ["#FF0000", "#00FF00", "#FFFFFF"],
                    "lights": LIGHTS,
                    "mode": "rotate",
                    "interval": 30,
                    "transition": 2,
                },
                subentry_type="holiday",
                title="Christmas",
                unique_id=None,
            )
        ],
    )


async def test_full_night(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """Dark -> on and rotating -> duration ends -> off -> not again tonight."""
    freezer.move_to(datetime(2026, 12, 24, 15, 0, tzinfo=tz))
    for light in LIGHTS:
        hass.states.async_set(light, "off")
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")

    entry = _entry()
    entry.add_to_hass(hass)
    dark = False
    with patch(DARK, side_effect=lambda: dark):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.holiday_lighting_enabled"},
            blocking=True,
        )
        assert (
            hass.states.get("sensor.holiday_lighting_status").state
            == "waiting_for_dark"
        )
        assert not turn_on
        assert (
            hass.states.get("sensor.holiday_lighting_active_holiday").state
            == "Christmas"
        )
        # Before dark: tonight's hard off time.
        off_at = hass.states.get("sensor.holiday_lighting_lights_off_at").state
        assert dt_util.parse_datetime(off_at) == datetime(
            2026, 12, 24, 23, 0, tzinfo=tz
        )

        # Gets dark at 17:30
        dark = True
        freezer.move_to(datetime(2026, 12, 24, 17, 30, tzinfo=tz))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.get("sensor.holiday_lighting_status").state == "on"
        assert (
            hass.states.get("sensor.holiday_lighting_active_holiday").state
            == "Christmas"
        )
        first = {tuple(c.data["rgb_color"]): c.data["entity_id"] for c in turn_on}
        assert first == {
            (255, 0, 0): ["light.porch"],
            (0, 255, 0): ["light.tree"],
            (255, 255, 255): ["light.garage"],
        }
        off_at = hass.states.get("sensor.holiday_lighting_lights_off_at").state
        assert dt_util.parse_datetime(off_at) == datetime(
            2026, 12, 24, 22, 30, tzinfo=tz
        )

        # Rotation after 30s: each color moves one light down.
        turn_on.clear()
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        second = {tuple(c.data["rgb_color"]): c.data["entity_id"] for c in turn_on}
        assert second[(255, 0, 0)] == ["light.tree"]

        # 5 hours later -> off.
        freezer.move_to(datetime(2026, 12, 24, 22, 31, tzinfo=tz))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert sorted(turn_off[-1].data["entity_id"]) == sorted(LIGHTS)
        assert (
            hass.states.get("sensor.holiday_lighting_status").state
            == "done_for_tonight"
        )
        # Done for tonight: still names tonight's holiday, just not showing.
        active = hass.states.get("sensor.holiday_lighting_active_holiday")
        assert active.state == "Christmas"
        assert active.attributes["showing"] is False
        # Done for tonight: tomorrow night's hard off time, not unknown.
        off_at = hass.states.get("sensor.holiday_lighting_lights_off_at").state
        assert dt_util.parse_datetime(off_at) == datetime(
            2026, 12, 25, 23, 0, tzinfo=tz
        )

        # Still dark, still the same night: stays off.
        turn_on.clear()
        freezer.move_to(datetime(2026, 12, 24, 22, 45, tzinfo=tz))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert not turn_on

        # Next evening it comes back.
        freezer.move_to(datetime(2026, 12, 25, 17, 30, tzinfo=tz))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert turn_on
        assert hass.states.get("sensor.holiday_lighting_status").state == "on"
        # Recalculated when the lights turn on: 5 hours from 17:30.
        off_at = hass.states.get("sensor.holiday_lighting_lights_off_at").state
        assert dt_util.parse_datetime(off_at) == datetime(
            2026, 12, 25, 22, 30, tzinfo=tz
        )


async def test_hard_off_time_cuts_duration_short(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 12, 24, 20, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(DARK, return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.holiday_lighting_enabled"},
            blocking=True,
        )
        off_at = hass.states.get("sensor.holiday_lighting_lights_off_at").state
        assert dt_util.parse_datetime(off_at) == datetime(
            2026, 12, 24, 23, 0, tzinfo=tz
        )
        freezer.move_to(datetime(2026, 12, 24, 23, 0, 30, tzinfo=tz))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert turn_off


async def test_disable_restores_previous_state(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 12, 24, 18, 0, tzinfo=tz))
    hass.states.async_set(
        "light.porch",
        "on",
        {"brightness": 120, "color_mode": "color_temp", "color_temp_kelvin": 2700},
    )
    hass.states.async_set("light.tree", "off")
    hass.states.async_set("light.garage", "off")
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(DARK, return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.holiday_lighting_enabled"},
            blocking=True,
        )
        turn_on.clear()
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.holiday_lighting_enabled"},
            blocking=True,
        )
    restored = [c.data for c in turn_on]
    assert restored == [
        {"entity_id": "light.porch", "brightness": 120, "color_temp_kelvin": 2700}
    ]
    assert sorted(c.data["entity_id"] for c in turn_off) == [
        "light.garage",
        "light.tree",
    ]
    assert hass.states.get("sensor.holiday_lighting_status").state == "disabled"


async def test_services(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 7, 1, 13, 0, tzinfo=tz))  # daytime, no holiday
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(DARK, return_value=False):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        await hass.services.async_call(
            DOMAIN, "start", {"holiday": "christmas"}, blocking=True
        )
        assert hass.states.get("sensor.holiday_lighting_status").state == "on"
        assert hass.states.get("select.holiday_lighting_theme").state == "Christmas"
        turn_on.clear()
        await hass.services.async_call(DOMAIN, "advance", {}, blocking=True)
        assert turn_on
        await hass.services.async_call(DOMAIN, "stop", {}, blocking=True)
        assert turn_off
        assert (
            hass.states.get("sensor.holiday_lighting_status").state
            == "done_for_tonight"
        )


# --- 1.2 ----------------------------------------------------------------------

from homeassistant.core import Context, SupportsResponse  # noqa: E402
from homeassistant.helpers import issue_registry as ir  # noqa: E402

from custom_components.holiday_lighting.config_flow import (  # noqa: E402
    _holiday_schema,
    _preset_data,
)
from custom_components.holiday_lighting.diagnostics import (  # noqa: E402
    async_get_config_entry_diagnostics,
)
from custom_components.holiday_lighting.presets import PRESETS  # noqa: E402

HOLIDAY_BASE = {
    "colors": ["#FF0000", "#00FF00", "#FFFFFF"],
    "lights": LIGHTS,
    "mode": "rotate",
    "interval": 30,
    "transition": 2,
}


def _holiday(title: str, **data) -> ConfigSubentryData:
    return ConfigSubentryData(
        data={"name": title, **HOLIDAY_BASE, **data},
        subentry_type="holiday",
        title=title,
        unique_id=None,
    )


def _entry_with(*holidays: ConfigSubentryData, **options) -> MockConfigEntry:
    entry = _entry(**options)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Holiday Lighting",
        data={},
        options=dict(entry.options),
        subentries_data=list(holidays),
    )
    return entry


async def _start(hass, entry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.holiday_lighting_enabled"},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)


async def _tick(hass, freezer, when) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _state(hass, key: str) -> str:
    return hass.states.get(f"sensor.holiday_lighting_{key}").state


async def test_add_custom_kinds(hass: HomeAssistant) -> None:
    """Custom holidays: choose how the dates work, then fill in details."""
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    async def start_custom(kind: str):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "holiday"), context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "custom"}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["menu_options"] == [
            "yearly",
            "nth_weekday",
            "easter",
            "advent",
            "once",
            "calendar",
        ]
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": kind}
        )
        assert result["step_id"] == "holiday"
        return result

    common = {
        "colors": [{"name": "Green", "color": [0, 132, 61]}],
        "mode": "cycle",
        "interval": 20,
        "transition": 1,
    }

    # Nth weekday, with a schedule override
    result = await start_custom("nth_weekday")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        common
        | {
            "name": "Homecoming",
            "week": "last",
            "weekday": "5",
            "month": "10",
            "days_before": 1,
            "days_after": 0,
            "schedule_override": {"all_night": False, "off_time": "01:00:00"},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = result["result"].data if "result" in result else None
    sub = next(s for s in entry.subentries.values() if s.title == "Homecoming")
    assert sub.data["kind"] == "nth_weekday"
    assert (sub.data["week"], sub.data["weekday"], sub.data["month"]) == (-1, 5, 10)
    assert sub.data["off_time"] == "01:00:00"
    assert "schedule_override" not in sub.data
    del data

    # One-time event: end before start is rejected
    result = await start_custom("once")
    bad = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        common
        | {"name": "Party", "start_date": "2026-11-15", "end_date": "2026-11-14"},
    )
    assert bad["errors"] == {"end_date": "end_before_start"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        common
        | {"name": "Party", "start_date": "2026-11-14", "end_date": "2026-11-15"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Calendar
    result = await start_custom("calendar")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        common
        | {"name": "Game Day", "calendar": "calendar.games", "keyword": " Bison "},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    sub = next(s for s in entry.subentries.values() if s.title == "Game Day")
    assert sub.data["keyword"] == "Bison"

    # Reconfigure keeps the kind and shows its fields
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    names = {
        f["name"]
        for f in voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    }
    assert {"calendar", "keyword", "schedule_override"} <= names
    assert "start" not in names


async def test_thanksgiving_preset_moves(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    from custom_components.holiday_lighting.config_flow import _preset_data

    entry = _entry_with(
        _holiday("Thanksgiving", **_preset_data("thanksgiving", LIGHTS))
    )
    async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    freezer.move_to(datetime(2027, 11, 18, 18, 0, tzinfo=tz))  # 1 week before
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        assert _state(hass, "active_holiday") == "Thanksgiving"
    assert _state(hass, "status") == "on"


async def test_calendar_event_tonight(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 12, 5, 17, 0, tzinfo=tz))
    # Load the real calendar component first so it doesn't replace the mock.
    await async_setup_component(hass, "calendar", {})
    calls = async_mock_service(
        hass,
        "calendar",
        "get_events",
        response={
            "calendar.games": {
                "events": [
                    {"summary": "Practice", "start": "x", "end": "y"},
                    {"summary": "NDSU Bison vs UND", "start": "x", "end": "y"},
                ]
            }
        },
        supports_response=SupportsResponse.ONLY,
    )
    turn_on = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26"),
        _holiday(
            "Game Day",
            kind="calendar",
            calendar="calendar.games",
            keyword="bison",
            colors=["#00843D", "#FFC72C"],
        ),
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
    assert _state(hass, "active_holiday") == "Game Day"
    assert calls[0].data["start_date_time"].startswith("2026-12-05T12:00")
    assert calls[0].data["end_date_time"].startswith("2026-12-06T00:00")
    assert {tuple(c.data["rgb_color"]) for c in turn_on} == {
        (0, 132, 61),
        (255, 199, 44),
    }


async def test_calendar_keyword_no_match_falls_back(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 12, 5, 17, 0, tzinfo=tz))
    # Load the real calendar component first so it doesn't replace the mock.
    await async_setup_component(hass, "calendar", {})
    async_mock_service(
        hass,
        "calendar",
        "get_events",
        response={"calendar.games": {"events": [{"summary": "Practice"}]}},
        supports_response=SupportsResponse.ONLY,
    )
    async_mock_service(hass, "light", "turn_on")
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26"),
        _holiday(
            "Game Day", kind="calendar", calendar="calendar.games", keyword="bison"
        ),
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
    assert _state(hass, "active_holiday") == "Christmas"


async def test_holiday_overrides_and_weekend_off_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-23"),
        _holiday(
            "Christmas Eve", kind="yearly", start="12-24", end="12-24", all_night=True
        ),
        _holiday(
            "New Year's", kind="yearly", start="12-31", end="01-01", off_time="01:00:00"
        ),
        on_duration={"hours": 8},
        weekend_off_time="23:59:00",
    )
    with patch(DARK, return_value=True):
        # Friday 2026-12-04: weekend off time
        freezer.move_to(datetime(2026, 12, 4, 17, 0, tzinfo=tz))
        await _start(hass, entry)
        off_at = dt_util.parse_datetime(_state(hass, "lights_off_at"))
        assert off_at == datetime(2026, 12, 4, 23, 59, tzinfo=tz)
        # Monday 2026-12-07: normal 23:00
        await _tick(hass, freezer, datetime(2026, 12, 7, 17, 0, tzinfo=tz))
        off_at = dt_util.parse_datetime(_state(hass, "lights_off_at"))
        assert off_at == datetime(2026, 12, 7, 23, 0, tzinfo=tz)
        # Christmas Eve: all night, no off time
        await _tick(hass, freezer, datetime(2026, 12, 24, 17, 0, tzinfo=tz))
        assert _state(hass, "active_holiday") == "Christmas Eve"
        assert _state(hass, "lights_off_at") == "unknown"
        await _tick(hass, freezer, datetime(2026, 12, 25, 2, 0, tzinfo=tz))
        assert _state(hass, "status") == "on"
    # Gets light: off
    with patch(DARK, return_value=False):
        await _tick(hass, freezer, datetime(2026, 12, 25, 8, 0, tzinfo=tz))
        assert _state(hass, "status") == "done_for_tonight"
    with patch(DARK, return_value=True):
        # New Year's Eve: own off time past midnight, beats the 8h duration
        await _tick(hass, freezer, datetime(2026, 12, 31, 17, 30, tzinfo=tz))
        off_at = dt_util.parse_datetime(_state(hass, "lights_off_at"))
        assert off_at == datetime(2027, 1, 1, 1, 0, tzinfo=tz)


async def test_cycle_and_fade_effects(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 12, 5, 18, 0, tzinfo=tz))
    turn_on = async_mock_service(hass, "light", "turn_on")
    entry = _entry_with(
        _holiday(
            "Christmas",
            kind="yearly",
            start="12-01",
            end="12-26",
            mode="fade",
            interval=20,
        ),
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        assert len(turn_on) == 1
        assert turn_on[0].data["entity_id"] == LIGHTS
        assert turn_on[0].data["rgb_color"] == [255, 0, 0]
        assert turn_on[0].data["transition"] == 20.0
        turn_on.clear()
        freezer.tick(timedelta(seconds=21))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert turn_on[0].data["rgb_color"] == [0, 255, 0]
        assert turn_on[0].data["entity_id"] == LIGHTS


async def test_manual_change_is_left_alone(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """Only light commands from something else count as a manual change."""
    freezer.move_to(datetime(2026, 12, 5, 18, 0, tzinfo=tz))
    for light in LIGHTS:
        hass.states.async_set(light, "off")
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26"),
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        controller = entry.runtime_data
        # A slow light reporting an older color is not a manual change:
        # reported colors are no longer compared.
        freezer.tick(timedelta(seconds=15))
        hass.states.async_set(
            "light.tree", "on", {"rgb_color": (255, 180, 100)}, context=Context()
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert controller.night.overridden == set()

        # Someone turns the porch light off from the app.
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": "light.porch"},
            blocking=True,
            context=Context(user_id="abc"),
        )
        # An automation sets the garage light to warm white.
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": "light.garage", "color_temp_kelvin": 2700},
            blocking=True,
            context=Context(),
        )
        status = hass.states.get("sensor.holiday_lighting_status")
        assert status.attributes["manually_changed"] == ["light.garage", "light.porch"]

        turn_on.clear()
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        touched = {e for c in turn_on for e in c.data["entity_id"]}
        assert touched == {"light.tree"}

        # End of night (schedule): only the light we still control turns off.
        await _tick(hass, freezer, datetime(2026, 12, 5, 23, 1, tzinfo=tz))
        assert turn_off[-1].data["entity_id"] == ["light.tree"]

        # Next night everything is ours again.
        turn_on.clear()
        await _tick(hass, freezer, datetime(2026, 12, 6, 18, 0, tzinfo=tz))
        touched = {e for c in turn_on for e in c.data["entity_id"]}
        assert touched == set(LIGHTS)


async def test_turn_off_button_includes_manual_lights(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """Regression: "Turn off for tonight" left lights marked manual on."""
    freezer.move_to(datetime(2026, 10, 7, 22, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": ["light.tree", "light.garage"], "rgb_color": [255, 255, 255]},
            blocking=True,
            context=Context(user_id="abc"),
        )
        assert entry.runtime_data.night.overridden == {"light.tree", "light.garage"}
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.holiday_lighting_turn_off_for_tonight"},
            blocking=True,
        )
    assert sorted(turn_off[-1].data["entity_id"]) == sorted(LIGHTS)
    assert _state(hass, "status") == "done_for_tonight"


async def test_late_command_cannot_turn_lights_back_on(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """Regression: a slow color step landed after "turn off" and lit a bulb."""
    freezer.move_to(datetime(2026, 10, 7, 22, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        controller = entry.runtime_data
        step_context = controller._our_contexts[-1]  # a color step's command
        await controller.async_force_off()
        turn_off.clear()

        # The slow bulb finally applies that old step: it turns back on.
        hass.states.async_set("light.porch", "on", context=Context(id=step_context))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert [c.data["entity_id"] for c in turn_off] == ["light.porch"]

        # Someone turning a light on themselves is left alone.
        turn_off.clear()
        hass.states.async_set("light.tree", "on", context=Context(user_id="abc"))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert turn_off == []

        # After a minute the guard stops.
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        hass.states.async_set("light.garage", "on", context=Context(id=step_context))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert turn_off == []


async def test_manual_detection_can_be_turned_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 12, 5, 18, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26"),
        respect_manual=False,
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        hass.states.async_set("light.porch", "off", context=Context())
        await hass.async_block_till_done(wait_background_tasks=True)
    status = hass.states.get("sensor.holiday_lighting_status")
    assert status.attributes["manually_changed"] == []


async def test_repairs(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz) -> None:
    freezer.move_to(datetime(2026, 12, 5, 18, 0, tzinfo=tz))
    hass.states.async_set(
        "light.porch", "on", {"supported_color_modes": ["brightness"]}
    )
    hass.states.async_set("light.tree", "on", {"supported_color_modes": ["xy"]})
    hass.states.async_set("light.garage", "unavailable")
    async_mock_service(hass, "light", "turn_on")
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26")
    )
    registry = ir.async_get(hass)
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        sub_id = next(iter(entry.subentries))
        # White-only lights are handled now, so there is no color issue.
        assert registry.async_get_issue(DOMAIN, f"no_color_{sub_id}") is None
        # Unavailable needs two checks in a row.
        assert registry.async_get_issue(DOMAIN, f"lights_unavailable_{sub_id}") is None
        await _tick(hass, freezer, datetime(2026, 12, 5, 18, 1, 30, tzinfo=tz))
        assert registry.async_get_issue(DOMAIN, f"lights_unavailable_{sub_id}")
        # It comes back: cleared.
        hass.states.async_set("light.garage", "on", {"supported_color_modes": ["hs"]})
        await _tick(hass, freezer, datetime(2026, 12, 5, 18, 3, tzinfo=tz))
        assert registry.async_get_issue(DOMAIN, f"lights_unavailable_{sub_id}") is None


async def test_old_no_color_issue_is_cleared(hass: HomeAssistant) -> None:
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26")
    )
    entry.add_to_hass(hass)
    sub_id = next(iter(entry.subentries))
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"no_color_{sub_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="no_color",
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"no_color_{sub_id}") is None


async def test_white_and_color_temp_lights(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """Each kind of light gets something it can show, and isn't flagged as manual."""
    freezer.move_to(datetime(2026, 12, 5, 18, 0, tzinfo=tz))
    hass.states.async_set("light.porch", "off", {"supported_color_modes": ["hs"]})
    hass.states.async_set(
        "light.tree",
        "off",
        {
            "supported_color_modes": ["color_temp"],
            "min_color_temp_kelvin": 2700,
            "max_color_temp_kelvin": 6500,
        },
    )
    hass.states.async_set(
        "light.garage", "off", {"supported_color_modes": ["brightness"]}
    )
    turn_on = async_mock_service(hass, "light", "turn_on")
    entry = _entry_with(
        _holiday(
            "Christmas",
            kind="yearly",
            start="12-01",
            end="12-26",
            colors=["#FF0000", "#0000FF", "#FFFFFF"],
            lights=LIGHTS,
        ),
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
    sent = {c.data["entity_id"][0]: c.data for c in turn_on}
    # Chase step 0: porch red, tree blue, garage white.
    assert sent["light.porch"]["rgb_color"] == [255, 0, 0]
    assert sent["light.tree"]["color_temp_kelvin"] == 6500  # blue -> cool white
    assert "rgb_color" not in sent["light.tree"]
    assert sent["light.garage"]["brightness_pct"] == 100  # white -> full
    assert "rgb_color" not in sent["light.garage"]
    attrs = hass.states.get("sensor.holiday_lighting_active_holiday").attributes
    assert attrs["white_lights"] == ["light.tree", "light.garage"]

    # The tree reports its color temperature (and an rgb_color derived from
    # it, far from blue): reports are not manual changes.
    freezer.tick(timedelta(seconds=15))
    hass.states.async_set(
        "light.tree",
        "on",
        {
            "supported_color_modes": ["color_temp"],
            "color_temp_kelvin": 6500,
            "rgb_color": (255, 249, 253),
        },
        context=Context(),
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data.night.overridden == set()
    # Someone sets it to warm white from the app: that is.
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.tree", "color_temp_kelvin": 2700},
        blocking=True,
        context=Context(user_id="abc"),
    )
    assert entry.runtime_data.night.overridden == {"light.tree"}


async def test_diagnostics(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 12, 5, 18, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26")
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["holidays"][0]["title"] == "Christmas"
    assert diag["state"]["running"] == "Christmas"
    assert diag["state"]["status"] == "on"


async def test_missed_off_time_does_not_skip_tonight(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """If HA misses last night's off time, tonight still runs."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26"),
    )
    with patch(DARK, return_value=True):
        freezer.move_to(datetime(2026, 12, 10, 18, 0, tzinfo=tz))
        await _start(hass, entry)
        assert _state(hass, "status") == "on"
        # Nothing runs until the next evening (HA was down at 23:00).
        turn_on.clear()
        await _tick(hass, freezer, datetime(2026, 12, 11, 18, 0, tzinfo=tz))
        assert turn_off  # last night's lights were turned off
        assert turn_on  # and tonight's came back on
        assert _state(hass, "status") == "on"
        off_at = dt_util.parse_datetime(_state(hass, "lights_off_at"))
        assert off_at == datetime(2026, 12, 11, 23, 0, tzinfo=tz)


async def test_sun_elevation_source(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """Dark detection can read the Sun integration or any elevation sensor."""
    freezer.move_to(datetime(2026, 12, 10, 12, 0, tzinfo=tz))  # midday
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26"),
        sun_source="sun.sun",
    )
    await _start(hass, entry)
    controller = entry.runtime_data
    calculated = controller.current_sun_elevation()  # no entity yet: fallback
    assert calculated > 0

    # The Sun integration's entity: read from its elevation attribute.
    hass.states.async_set("sun.sun", "below_horizon", {"elevation": -38.16})
    assert controller.current_sun_elevation() == -38.16
    assert controller.is_dark()
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 12.5})
    assert not controller.is_dark()

    # Unavailable: falls back to the calculation.
    hass.states.async_set("sun.sun", "unavailable", {})
    assert controller.current_sun_elevation() == pytest.approx(calculated)

    # Any sensor reporting degrees.
    controller.sun_source = "sensor.sun_solar_elevation"
    hass.states.async_set("sensor.sun_solar_elevation", "-3.4")
    assert controller.current_sun_elevation() == -3.4
    assert controller.is_dark()  # below the -2° default
    hass.states.async_set("sensor.sun_solar_elevation", "-1.0")
    assert not controller.is_dark()
    hass.states.async_set("sensor.sun_solar_elevation", "unknown")
    assert controller.current_sun_elevation() == pytest.approx(calculated)

    diagnostics = controller.diagnostics()
    assert diagnostics["sun_source"] == "sensor.sun_solar_elevation"
    assert diagnostics["sun_source_ok"] is False


async def test_options_flow_offers_sun_source(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {
        f["name"]: f
        for f in voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    }
    assert fields["sun_source"]["selector"]["entity"]["domain"] == ["sun", "sensor"]
    options = dict(entry.options) | {"sun_source": "sun.sun"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], options
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["sun_source"] == "sun.sun"


def _frontend_initial(schema: list[dict]) -> dict:
    """Initial form data the way the HA frontend fills it.

    A field's suggested value or default is used as-is; for a section with
    a default, that default wins over the fields inside it.
    """
    data: dict = {}
    for field in schema:
        description = field.get("description") or {}
        if "suggested_value" in description:
            data[field["name"]] = description["suggested_value"]
        elif "default" in field:
            data[field["name"]] = field["default"]
        elif field.get("type") == "expandable":
            data[field["name"]] = _frontend_initial(field["schema"])
    return data


def _frontend_missing(schema: list[dict], data: dict | None, prefix: str = "") -> list:
    """Required fields the frontend would flag as not filled in."""
    missing = []
    for field in schema:
        value = (data or {}).get(field["name"])
        if field.get("type") == "expandable":
            missing += _frontend_missing(
                field["schema"], value, f"{prefix}{field['name']}."
            )
        elif field.get("required") and value in (None, ""):
            missing.append(prefix + field["name"])
    return missing


@pytest.mark.parametrize("preset", list(PRESETS))
def test_preset_form_submits_as_shown(preset: str) -> None:
    """Regression: a hidden required field blocked every holiday form."""
    data = _preset_data(preset, LIGHTS)
    schema = voluptuous_serialize.convert(
        _holiday_schema(data["kind"], data), custom_serializer=cv.custom_serializer
    )
    assert _frontend_missing(schema, _frontend_initial(schema)) == []


@pytest.mark.parametrize(
    ("kind", "user_fields"),
    [
        ("yearly", ["name", "start", "end"]),
        ("nth_weekday", ["name"]),
        ("easter", ["name"]),
        ("once", ["name", "start_date", "end_date"]),
        ("advent", ["name"]),
        ("calendar", ["name", "calendar"]),
    ],
)
def test_custom_form_only_asks_for_user_fields(kind: str, user_fields: list) -> None:
    schema = voluptuous_serialize.convert(
        _holiday_schema(kind, {"lights": LIGHTS}),
        custom_serializer=cv.custom_serializer,
    )
    assert _frontend_missing(schema, _frontend_initial(schema)) == user_fields


def test_edit_form_shows_saved_schedule_override() -> None:
    saved = _preset_data("new_years", LIGHTS) | {"off_time": "01:00:00"}
    schema = voluptuous_serialize.convert(
        _holiday_schema(saved["kind"], saved), custom_serializer=cv.custom_serializer
    )
    assert _frontend_initial(schema)["schedule_override"] == {
        "all_night": False,
        "off_time": "01:00:00",
    }


async def _preset_options(hass: HomeAssistant, entry) -> list[str]:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "holiday"), context={"source": config_entries.SOURCE_USER}
    )
    schema = voluptuous_serialize.convert(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    hass.config_entries.subentries.async_abort(result["flow_id"])
    return schema[0]["selector"]["select"]["options"]


async def test_add_holiday_hides_presets_already_added(hass: HomeAssistant) -> None:
    # "Christmas" was saved before holidays remembered their preset: matched by name.
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    options = await _preset_options(hass, entry)
    assert options[0] == "custom"
    assert "christmas" not in options
    assert "halloween" in options
    assert len(options) == 1 + len(PRESETS) - 1

    # Add Halloween from its preset, renamed: still hidden afterwards.
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "holiday"), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"preset": "halloween"}
    )
    form = _frontend_initial(
        voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], form | {"name": "Spooky Season"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    sub = next(s for s in entry.subentries.values() if s.title == "Spooky Season")
    assert sub.data["preset"] == "halloween"
    assert "halloween" not in await _preset_options(hass, entry)

    # Editing keeps the preset link.
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    form = _frontend_initial(
        voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], form | {"name": "Halloween Night"}
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[sub.subentry_id].data["preset"] == "halloween"
    await hass.async_block_till_done(wait_background_tasks=True)

    # Deleting a holiday makes its preset available again.
    hass.config_entries.async_remove_subentry(entry, sub.subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "halloween" in await _preset_options(hass, entry)


async def test_buttons_and_dashboard_card(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """The example card's entities exist, its template renders, buttons work."""
    import re
    from pathlib import Path

    import yaml
    from homeassistant.helpers.template import Template

    freezer.move_to(datetime(2026, 12, 5, 13, 0, tzinfo=tz))  # daytime
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday(
            "Christmas",
            kind="yearly",
            start="12-01",
            end="12-26",
            color_names=["Red", "Green", "White"],
        ),
        _holiday("New Year's", kind="yearly", start="12-31", end="01-01"),
    )
    with patch(DARK, return_value=False):
        await _start(hass, entry)

        card_file = Path(__file__).parent.parent / "examples" / "dashboard-card.yaml"
        card = card_file.read_text()
        yaml.safe_load(card)
        for entity_id in set(
            re.findall(r"\b(?:switch|select|sensor|button)\.holiday_lighting_\w+", card)
        ):
            assert hass.states.get(entity_id) is not None, entity_id

        markdown = next(
            c for c in yaml.safe_load(card)["cards"] if c["type"] == "markdown"
        )
        rendered = Template(markdown["content"], hass).async_render()
        assert "Next: New Year's, Dec 31" in rendered

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.holiday_lighting_turn_on_now"},
            blocking=True,
        )
        assert _state(hass, "status") == "on"
        rendered = Template(markdown["content"], hass).async_render()
        assert "**Christmas**: Red, Green, White" in rendered
        assert "On, off at" in rendered

        turn_on.clear()
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.holiday_lighting_next_colors"},
            blocking=True,
        )
        assert turn_on

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.holiday_lighting_turn_off_for_tonight"},
            blocking=True,
        )
        assert turn_off
        assert _state(hass, "status") == "done_for_tonight"


async def test_status_is_on_while_lights_are_still_responding(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """Regression: diagnostics showed "disabled" while commands were in flight."""
    freezer.move_to(datetime(2026, 10, 7, 20, 47, tzinfo=tz))
    seen: list[str] = []
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
    )

    async def slow_turn_on(call) -> None:
        seen.append(entry.runtime_data.status)

    hass.services.async_register("light", "turn_on", slow_turn_on)
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.holiday_lighting_enabled"},
            blocking=True,
        )
    assert seen and set(seen) == {"on"}


async def test_unresponsive_light_does_not_block_the_controller(
    hass: HomeAssistant,
) -> None:
    """A hung light gives up after the timeout. (No frozen clock: the timeout
    runs on the real event loop clock.)"""
    release = asyncio.Event()

    async def hung_turn_on(call) -> None:
        await release.wait()

    hass.services.async_register("light", "turn_on", hung_turn_on)
    turn_off = async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    controller = entry.runtime_data
    holiday_id = next(iter(entry.subentries))
    with patch(
        "custom_components.holiday_lighting.controller.LIGHT_COMMAND_TIMEOUT", 0.05
    ):
        async with asyncio.timeout(5):  # the test itself must not hang
            await controller.async_force_on(holiday_id)
        # Gave up on the hung light and finished.
        assert controller.status == "on"
        assert not controller._lock.locked()
        assert controller.slow_light_commands >= 1
        # The stop button still works right away.
        async with asyncio.timeout(5):
            await controller.async_force_off()
        assert turn_off
        assert controller.status == "done_for_tonight"
    release.set()
    await hass.async_block_till_done()


async def test_rotation_skips_steps_while_busy(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 10, 7, 20, 47, tzinfo=tz))
    turn_on = async_mock_service(hass, "light", "turn_on")
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        controller = entry.runtime_data
        offset = controller.offset
        turn_on.clear()
        async with controller._lock:  # e.g. the last step is still running
            await controller._async_rotate(dt_util.now())
            await controller._async_rotate(dt_util.now())
        assert controller.offset == offset
        assert controller.skipped_steps == 2
        assert not turn_on
        await controller._async_rotate(dt_util.now())
        assert controller.offset == offset + 1
        assert controller.diagnostics()["skipped_rotation_steps"] == 2


async def test_light_color_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 10, 7, 20, 0, tzinfo=tz))
    hass.states.async_set(
        "light.porch",
        "off",
        {"friendly_name": "Front Porch", "supported_color_modes": ["hs"]},
    )
    hass.states.async_set("light.tree", "off", {"supported_color_modes": ["hs"]})
    hass.states.async_set(
        "light.garage",
        "off",
        {"friendly_name": "Garage", "supported_color_modes": ["color_temp"]},
    )
    async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
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
    porch = "sensor.holiday_lighting_front_porch_color"
    tree = "sensor.holiday_lighting_tree_color"
    garage = "sensor.holiday_lighting_garage_color"
    assert hass.states.get(porch).state == "Off"

    with patch(DARK, return_value=True):
        await _tick(hass, freezer, datetime(2026, 10, 7, 20, 1, tzinfo=tz))
        assert hass.states.get(porch).state == "Orange"
        assert hass.states.get(porch).attributes["hex"] == "#FF6600"
        assert hass.states.get(porch).attributes["holiday"] == "Halloween"
        assert hass.states.get(porch).attributes["shown_as"] == "color"
        assert hass.states.get(tree).state == "Purple"
        # A color-temperature bulb: green shows as neutral white.
        assert hass.states.get(garage).state == "Green"
        assert hass.states.get(garage).attributes["shown_as"] == "4000K white"

        # Next chase step: every color moves one light down.
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.holiday_lighting_next_colors"},
            blocking=True,
        )
        assert hass.states.get(porch).state == "Green"
        assert hass.states.get(tree).state == "Orange"

        # Someone turns the tree off from the app.
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": "light.tree"},
            blocking=True,
            context=Context(user_id="abc"),
        )
        assert hass.states.get(tree).state == "Manual"

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.holiday_lighting_turn_off_for_tonight"},
            blocking=True,
        )
        assert turn_off
        assert hass.states.get(porch).state == "Off"
        assert "hex" not in hass.states.get(porch).attributes


async def test_light_color_sensor_removed_with_light(hass: HomeAssistant) -> None:
    from homeassistant.helpers import entity_registry as er

    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
    )
    await _start(hass, entry)
    registry = er.async_get(hass)
    assert registry.async_get("sensor.holiday_lighting_garage_color")
    hass.config_entries.async_update_entry(
        entry, options=dict(entry.options) | {"default_lights": ["light.porch"]}
    )
    sub_id = next(iter(entry.subentries))
    sub = entry.subentries[sub_id]
    hass.config_entries.async_update_subentry(
        entry, sub, data=dict(sub.data) | {"lights": ["light.porch", "light.tree"]}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get("sensor.holiday_lighting_garage_color") is None
    assert registry.async_get("sensor.holiday_lighting_porch_color")


async def test_default_colors_when_no_holiday(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 8, 20, 20, 0, tzinfo=tz))  # no holiday
    turn_on = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
    )
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        assert _state(hass, "status") == "no_holiday"

        # Set white as the default through the settings form.
        turn_on.clear()
        result = await hass.config_entries.options.async_init(entry.entry_id)
        fields = {
            f["name"]: f
            for f in voluptuous_serialize.convert(
                result["data_schema"], custom_serializer=cv.custom_serializer
            )
        }
        assert fields["default_colors"]["selector"]["object"]["multiple"] is True
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            dict(entry.options)
            | {"default_colors": [{"name": "White", "color": [255, 255, 255]}]},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options["default_colors"] == ["#FFFFFF"]
        assert entry.options["default_color_names"] == ["White"]
        await hass.async_block_till_done(wait_background_tasks=True)

        # Saving reloads the integration, which turns the white lights on.
        await _tick(hass, freezer, datetime(2026, 8, 20, 20, 1, tzinfo=tz))
        assert _state(hass, "status") == "on"
        assert _state(hass, "active_holiday") == "Default colors"
        assert {tuple(c.data["rgb_color"]) for c in turn_on} == {(255, 255, 255)}
        assert sorted(e for c in turn_on for e in c.data["entity_id"]) == sorted(LIGHTS)
        assert hass.states.get("sensor.holiday_lighting_porch_color").state == "White"

        # Editing the settings shows the saved default colors.
        result = await hass.config_entries.options.async_init(entry.entry_id)
        fields = {
            f["name"]: f
            for f in voluptuous_serialize.convert(
                result["data_schema"], custom_serializer=cv.custom_serializer
            )
        }
        assert fields["default_colors"]["description"]["suggested_value"] == [
            {"name": "White", "color": [255, 255, 255]}
        ]
        hass.config_entries.options.async_abort(result["flow_id"])

    # On a holiday, the holiday wins over the default.
    with patch(DARK, return_value=False):  # midday
        await _tick(hass, freezer, datetime(2026, 10, 7, 12, 0, tzinfo=tz))
    with patch(DARK, return_value=True):  # evening
        await _tick(hass, freezer, datetime(2026, 10, 7, 20, 0, tzinfo=tz))
        assert _state(hass, "active_holiday") == "Halloween"


async def test_schedule_calendar(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """The calendar shows what each night will display, overlaps resolved."""
    from custom_components.holiday_lighting.presets import PRESETS

    freezer.move_to(datetime(2026, 10, 7, 12, 0, tzinfo=tz))
    async_mock_service(hass, "light", "turn_on")

    def preset(key, **extra):
        data = {k: v for k, v in PRESETS[key].items()} | extra
        return _holiday(data["name"], **data)

    entry = _entry_with(
        preset("halloween"),
        preset("all_saints"),
        preset("all_souls"),
        preset("veterans_day"),
        preset("thanksgiving", days_before=5, days_after=2),
        preset("christ_the_king"),
        preset("advent"),
        preset("gaudete_sunday"),
        preset("immaculate_conception"),
        preset("guadalupe"),
        preset("christmas"),
        default_colors=["#FFFFFF"],
        default_color_names=["White"],
    )
    await _start(hass, entry)
    state = hass.states.get("calendar.holiday_lighting_schedule")
    assert state.state == "on"  # an all-day event covers today
    assert state.attributes["message"] == "Halloween"

    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": "calendar.holiday_lighting_schedule",
            "start_date_time": "2026-10-25T00:00:00",
            "end_date_time": "2027-01-01T00:00:00",
        },
        blocking=True,
        return_response=True,
    )
    events = response["calendar.holiday_lighting_schedule"]["events"]
    got = [(e["summary"], e["start"], e["end"]) for e in events]
    assert got == [
        ("Halloween", "2026-10-01", "2026-11-01"),
        ("All Saints' Day", "2026-11-01", "2026-11-02"),
        ("All Souls' Day", "2026-11-02", "2026-11-03"),
        ("Default colors", "2026-11-03", "2026-11-08"),
        ("Veterans Day", "2026-11-08", "2026-11-12"),
        ("Default colors", "2026-11-12", "2026-11-21"),
        ("Thanksgiving", "2026-11-21", "2026-11-22"),
        ("Christ the King", "2026-11-22", "2026-11-23"),
        ("Thanksgiving", "2026-11-23", "2026-11-29"),
        ("Advent", "2026-11-29", "2026-12-08"),
        ("Immaculate Conception", "2026-12-08", "2026-12-09"),
        ("Advent", "2026-12-09", "2026-12-12"),
        ("Our Lady of Guadalupe", "2026-12-12", "2026-12-13"),
        ("Gaudete Sunday", "2026-12-13", "2026-12-14"),
        ("Advent", "2026-12-14", "2026-12-25"),
        ("Christmas", "2026-12-25", "2026-12-27"),
        ("Default colors", "2026-12-27", "2027-01-01"),
    ]
    advent = next(e for e in events if e["summary"] == "Advent")
    assert "Colors: Purple, Purple, Purple, Rose" in advent["description"]
    assert "Effect: Chase, every 30s" in advent["description"]
    assert "Off at 11:00 PM" in advent["description"]


async def test_schedule_calendar_without_default(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    freezer.move_to(datetime(2026, 8, 1, 12, 0, tzinfo=tz))
    entry = _entry_with(
        _holiday("Halloween", kind="yearly", start="10-01", end="10-31"),
    )
    await _start(hass, entry)
    state = hass.states.get("calendar.holiday_lighting_schedule")
    assert state.state == "off"
    assert state.attributes["message"] == "Halloween"  # the next event
    assert state.attributes["start_time"].startswith("2026-10-01")


async def test_default_colors_tonight_button(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tz
) -> None:
    """The button swaps the holiday for the default colors until tomorrow."""
    from homeassistant.exceptions import ServiceValidationError

    freezer.move_to(datetime(2026, 12, 5, 18, 0, tzinfo=tz))
    turn_on = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26"),
        default_colors=["#FFFFFF"],
        default_color_names=["White"],
    )
    button = "button.holiday_lighting_use_default_colors_tonight"
    with patch(DARK, return_value=True):
        await _start(hass, entry)
        assert _state(hass, "active_holiday") == "Christmas"
        assert (
            hass.states.get("calendar.holiday_lighting_schedule")
            .attributes["message"]
            .startswith("Christmas")
        )

        turn_on.clear()
        await hass.services.async_call(
            "button", "press", {"entity_id": button}, blocking=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        # Switched right away, and every sensor follows.
        assert _state(hass, "status") == "on"
        assert _state(hass, "active_holiday") == "Default colors"
        assert {tuple(c.data["rgb_color"]) for c in turn_on} == {(255, 255, 255)}
        assert hass.states.get("sensor.holiday_lighting_porch_color").state == "White"
        assert (
            hass.states.get("calendar.holiday_lighting_schedule")
            .attributes["message"]
            .startswith("Default colors")
        )

        # Still tonight after midnight.
        await _tick(hass, freezer, datetime(2026, 12, 6, 0, 30, tzinfo=tz))
        assert _state(hass, "active_holiday") == "Default colors"

    # Next day: back to the holiday, before and after dark.
    with patch(DARK, return_value=False):
        await _tick(hass, freezer, datetime(2026, 12, 6, 13, 0, tzinfo=tz))
        assert _state(hass, "active_holiday") == "Christmas"
        assert (
            hass.states.get("calendar.holiday_lighting_schedule")
            .attributes["message"]
            .startswith("Christmas")
        )
    with patch(DARK, return_value=True):
        await _tick(hass, freezer, datetime(2026, 12, 6, 18, 0, tzinfo=tz))
        assert _state(hass, "status") == "on"
        assert _state(hass, "active_holiday") == "Christmas"

        # Picking a theme takes over from the button.
        await hass.services.async_call(
            "button", "press", {"entity_id": button}, blocking=True
        )
        assert _state(hass, "active_holiday") == "Default colors"
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": "select.holiday_lighting_theme", "option": "Christmas"},
            blocking=True,
        )
        assert _state(hass, "active_holiday") == "Christmas"

    # Without default colors the button is unavailable and the action errors.
    await hass.config_entries.async_unload(entry.entry_id)
    plain = _entry_with(
        _holiday("Christmas", kind="yearly", start="12-01", end="12-26")
    )
    with patch(DARK, return_value=True):
        await _start(hass, plain)
    assert hass.states.get(button).state == "unavailable"
    with pytest.raises(ServiceValidationError):
        await plain.runtime_data.async_use_default_tonight()
