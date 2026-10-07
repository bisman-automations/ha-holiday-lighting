<p align="center">
  <img src="custom_components/holiday_lighting/brand/icon@2x.png" alt="Holiday Lighting" width="160">
</p>

# Holiday Lighting

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/bisman-automations/ha-holiday-lighting/actions/workflows/validate.yaml/badge.svg)](https://github.com/bisman-automations/ha-holiday-lighting/actions/workflows/validate.yaml)

Home Assistant integration to create holiday color themes and rotate them across your existing lights.

- **Multiple holidays.** Each holiday has its own yearly date range, colors, lights, and rotation speed. Start from built-in presets (Christmas, Halloween, Independence Day, and more) or build your own.
- **Color rotation.** Colors march down your list of lights one step at a time: red on the porch moves to the tree, the tree's green moves to the garage, and so on. Or keep them static.
- **Runs itself every night.** Lights come on when it gets dark (sun elevation, an illuminance sensor, or either), stay on for a set time, and turn off at a hard off time, whichever comes first.
- **Puts things back.** Turning holiday lighting off restores each light's previous state.

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
| Illuminance sensor / threshold | Dark when the sensor reads below the threshold. |
| Stay on for | How long after turning on the lights stay on (default 5 hours). |
| Hard off time | Lights turn off at this time even if the duration hasn't passed (default 11:00 PM). A time before noon means after midnight, e.g. 1:00 AM. |

The lights turn off at whichever comes first, the duration or the hard off time, and stay off until the next evening. Darkness only *starts* the lights, so your own lights brightening a lux sensor won't turn them off early. With neither limit set, they turn off when it's light again.

### Holidays

On the integration page, use **Add holiday** to add more holidays, or the ⋮ menu on a holiday to edit or delete it.

| Field | Notes |
| --- | --- |
| Start / End | `MM-DD`, repeats yearly. Ranges can wrap the new year (`12-31` to `01-01`). |
| Colors | Add as many as you like with the color picker, each with an optional name. Drag to reorder; colors rotate in this order. |
| Lights | Drag to reorder; colors move down the list in this order. Empty uses the default lights. |
| Mode | Rotate or static. |
| Rotation interval | Seconds between steps. |
| Brightness | Optional; empty keeps each light's brightness. |
| Transition | Seconds to fade between colors. |

When holiday ranges overlap, the shorter one wins, so a specific holiday beats a broad season.

> Presets for holidays whose date moves (Easter, Thanksgiving) use a wide window. Edit the dates to match the year.

## Entities

| Entity | Purpose |
| --- | --- |
| `switch.holiday_lighting_enabled` | Arms the nightly schedule. Turning it off restores your lights. |
| `select.holiday_lighting_theme` | **Auto** follows the calendar, or pick a holiday to force it. |
| `sensor.holiday_lighting_status` | `disabled`, `waiting_for_dark`, `on`, `done_for_tonight`, `no_holiday`. |
| `sensor.holiday_lighting_active_holiday` | Showing now, with colors, lights, and the next holiday as attributes. |
| `sensor.holiday_lighting_lights_off_at` | When tonight's lights turn off. |

## Services

| Service | Description |
| --- | --- |
| `holiday_lighting.start` | Turn on now, ignoring darkness. Optional `holiday` name. Off rules still apply. |
| `holiday_lighting.stop` | Turn off and stay off for the rest of tonight. |
| `holiday_lighting.advance` | Move the rotation forward one step. |

## Icon

The integration ships its own icon in `custom_components/holiday_lighting/brand/`, with light and dark versions. Home Assistant 2026.3 and newer shows it automatically; older versions show a generic icon.

## Development

```bash
pip install -r requirements_test.txt
pytest
```

## License

MIT
