"""End-to-end tests: config flow and a full night of lights."""

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

from custom_components.holiday_lighting.diagnostics import (  # noqa: E402
    async_get_config_entry_diagnostics,
)

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
        # Our own update (our context) is not a manual change.
        controller = entry.runtime_data
        hass.states.async_set(
            "light.tree",
            "on",
            {"rgb_color": (0, 255, 0)},
            context=Context(id=controller._our_contexts[-1]),
        )
        # Someone turns the porch light off by hand.
        hass.states.async_set("light.porch", "off", context=Context())
        await hass.async_block_till_done(wait_background_tasks=True)
        # Someone sets the garage light to a warm white well after our command.
        freezer.tick(timedelta(seconds=15))
        hass.states.async_set(
            "light.garage", "on", {"rgb_color": (255, 180, 100)}, context=Context()
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        status = hass.states.get("sensor.holiday_lighting_status")
        assert status.attributes["manually_changed"] == ["light.garage", "light.porch"]

        turn_on.clear()
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        touched = {e for c in turn_on for e in c.data["entity_id"]}
        assert touched == {"light.tree"}

        # End of night: only the light we still control is turned off.
        await _tick(hass, freezer, datetime(2026, 12, 5, 23, 1, tzinfo=tz))
        assert turn_off[-1].data["entity_id"] == ["light.tree"]

        # Next night everything is ours again.
        turn_on.clear()
        await _tick(hass, freezer, datetime(2026, 12, 6, 18, 0, tzinfo=tz))
        touched = {e for c in turn_on for e in c.data["entity_id"]}
        assert touched == set(LIGHTS)


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
        issue = registry.async_get_issue(DOMAIN, f"no_color_{sub_id}")
        assert issue.translation_placeholders == {
            "holiday": "Christmas",
            "lights": "light.porch",
        }
        # Unavailable needs two checks in a row.
        assert registry.async_get_issue(DOMAIN, f"lights_unavailable_{sub_id}") is None
        await _tick(hass, freezer, datetime(2026, 12, 5, 18, 1, 30, tzinfo=tz))
        assert registry.async_get_issue(DOMAIN, f"lights_unavailable_{sub_id}")
        # It comes back: cleared.
        hass.states.async_set("light.garage", "on", {"supported_color_modes": ["hs"]})
        await _tick(hass, freezer, datetime(2026, 12, 5, 18, 3, tzinfo=tz))
        assert registry.async_get_issue(DOMAIN, f"lights_unavailable_{sub_id}") is None


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
