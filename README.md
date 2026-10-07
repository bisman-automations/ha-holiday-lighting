<p align="center">
  <img src="custom_components/holiday_lighting/brand/icon@2x.png" alt="Holiday Lighting" width="160">
</p>

# Holiday Lighting

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/bisman-automations/ha-holiday-lighting/actions/workflows/validate.yaml/badge.svg)](https://github.com/bisman-automations/ha-holiday-lighting/actions/workflows/validate.yaml)

Home Assistant integration to create holiday color themes and rotate them across your existing lights.

- **Any holiday or event.** Same dates every year, a weekday rule like "4th Thursday of November", days around Easter, a one-time event, or whenever a calendar has a matching event (game days!). Start from presets or build your own.
- **Effects.** Chase colors down your lights, cycle or fade the whole house through them together, twinkle randomly, or hold them static.
- **Runs itself every night.** Lights come on when it gets dark (sun elevation, an illuminance sensor, or either), stay on for a set time, and turn off at a hard off time, whichever comes first. Holidays can set their own schedule, and Friday and Saturday can have a later off time.
- **Plays nice.** If someone changes a light by hand, it's left alone for the rest of the night. Turning holiday lighting off restores each light's previous state.
- **Tells you when something's wrong.** Repairs flag lights that can't show color or have gone unavailable.

## Installation

### HACS

1. In HACS, open the menu → **Custom repositories**.
2. Add `https://github.com/bisman-automations/ha-holiday-lighting` as an **Integration**.
3. Install **Holiday Lighting** and restart Home Assistant.

### Manual

Copy `custom_components/holiday_lighting` into your `config/custom_components` folder and restart.

## Setup

**Settings → Devices & services → Add integration → Holiday Lighting**

1. **Default lights and starter holidays.** Pick the lights to use, in order, and any presets to add.
2. **Nightly schedule.**

| Setting | What it does |
| --- | --- |
| Use nightly schedule | Off: lights run whenever the **Enabled** switch is on. |
| Dark detection | Sun elevation, illuminance sensor, or either. |
| Sun elevation threshold | Dark when the sun is below this angle (default −2°, just after sunset; civil dusk is −6°). |
| Sun elevation source | Optional. Read the elevation from the Sun integration (`sun.sun`) or any sensor reporting degrees. Empty calculates it from your home location. If the entity is unavailable, the calculation is used instead. |
| Illuminance sensor / threshold | Dark when the sensor reads below the threshold. |
| Stay on for | How long after turning on the lights stay on (default 5 hours). |
| Hard off time | Lights turn off at this time even if the duration hasn't passed (default 11:00 PM). A time before noon means after midnight, e.g. 1:00 AM. |
| Weekend hard off time | Optional later off time for Friday and Saturday nights. |
| Respect manual changes | On (default): a light changed by hand is left alone until tomorrow. |

The lights turn off at whichever comes first, the duration or the hard off time, and stay off until the next evening. Darkness only *starts* the lights, so your own lights brightening a lux sensor won't turn them off early. With neither limit set, they turn off when it's light again.

### Holidays

On the integration page, use **Add holiday** to add more holidays, or the ⋮ menu on a holiday to edit or delete it. Start from a preset, or choose **Custom** and pick how the dates work:

| Dates | Example |
| --- | --- |
| Same dates every year | `12-01` to `12-26`. Ranges can wrap the new year (`12-31` to `01-01`). |
| Weekday rule | 4th Thursday of November, last Monday of May. Add days before and after. |
| Around Easter | Easter Sunday, plus days before and after. Calculated every year. |
| One-time event | A start and end date with a year, e.g. a party or graduation. |
| Calendar | Any night a calendar has an event, optionally only events whose title contains a keyword (e.g. `Bison`). |

Presets: New Year's, Valentine's Day, St. Patrick's Day, Easter, Mother's Day, Memorial Day, Independence Day, Labor Day, Halloween, Veterans Day, Thanksgiving, and Christmas. Moving holidays are calculated for each year.

Every holiday also has:

| Field | Notes |
| --- | --- |
| Colors | Add as many as you like with the color picker, each with an optional name. Drag to reorder. |
| Lights | Drag to reorder; chase moves colors down the list in this order. Empty uses the default lights. |
| Mode | **Chase**: colors move one light each step. **Whole-house cycle**: every light shows the same color, stepping through the list. **Whole-house fade**: like cycle, fading slowly into each color over the interval. **Twinkle**: lights pick random colors each step. **Static**: colors stay put. |
| Rotation interval | Seconds between steps. |
| Brightness | Optional; empty keeps each light's brightness. |
| Transition | Seconds to fade between colors. |
| Schedule for this holiday | Optional: stay on all night, or a different duration or hard off time (e.g. New Year's Eve until 1:00 AM). |

**Which holiday shows?** A calendar holiday with a matching event tonight wins. Otherwise, when date ranges overlap, the shorter one wins, so a specific holiday beats a broad season. Calendars are checked for events between noon and midnight, every 15 minutes.

## Entities

| Entity | Purpose |
| --- | --- |
| `switch.holiday_lighting_enabled` | Arms the nightly schedule. Turning it off restores your lights. |
| `select.holiday_lighting_theme` | **Auto** follows the calendar, or pick a holiday to force it. |
| `sensor.holiday_lighting_status` | `disabled`, `waiting_for_dark`, `on`, `done_for_tonight`, `no_holiday`. Attributes include lights changed by hand tonight. |
| `sensor.holiday_lighting_active_holiday` | Showing now, with colors, lights, and the next holiday as attributes. |
| `sensor.holiday_lighting_lights_off_at` | When tonight's lights turn off. |

## Services

| Service | Description |
| --- | --- |
| `holiday_lighting.start` | Turn on now, ignoring darkness. Optional `holiday` name. Off rules still apply. |
| `holiday_lighting.stop` | Turn off and stay off for the rest of tonight. |
| `holiday_lighting.advance` | Move the rotation forward one step. |

## Repairs and diagnostics

- **Repairs** (Settings → System → Repairs) flag a holiday whose lights can't show color, or whose lights are unavailable when it runs. They clear on their own once fixed.
- **Diagnostics**: download from the integration's ⋮ menu to attach to a bug report.

## Icon

The integration ships its own icon in `custom_components/holiday_lighting/brand/`, with light and dark versions. Home Assistant 2026.3 and newer shows it automatically; older versions show a generic icon.

## Development

```bash
pip install -r requirements_test.txt
pytest
```

## License

MIT
