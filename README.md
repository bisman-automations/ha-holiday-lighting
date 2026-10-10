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
- **Plays nice.** If someone changes a light from the app, an automation, a remote, or a voice assistant, it's left alone for the rest of the night. Turning holiday lighting off restores each light's previous state.
- **Default colors for every other night.** Pick colors (like white) to show on nights with no holiday, on the same schedule.
- **A schedule calendar.** See what will light up on any night in Home Assistant's Calendar.
- **See every light.** A sensor for each light shows the color it's displaying right now.
- **Works with any light.** Color bulbs show the colors; white and color-temperature bulbs follow along with matching brightness or warm and cool whites.
- **Tells you when something's wrong.** Repairs flag lights that have gone unavailable.

## Installation

### HACS

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bisman-automations&repository=ha-holiday-lighting&category=integration)

Or add it by hand:

1. In HACS, open the menu → **Custom repositories**.
2. Add `https://github.com/bisman-automations/ha-holiday-lighting` as an **Integration**.
3. Install **Holiday Lighting** and restart Home Assistant.

### Manual

Copy `custom_components/holiday_lighting` into your `config/custom_components` folder and restart.

## Setup

[![Open your Home Assistant instance and start setting up Holiday Lighting.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=holiday_lighting)

Or go to **Settings → Devices & services → Add integration → Holiday Lighting**.

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
| Respect manual changes | On (default): a light someone changes through Home Assistant (the app, an automation, a remote, a voice assistant) is left alone until tomorrow. Changes made outside Home Assistant, like a bulb's own app, aren't detected. **Turn off for tonight** still turns off every holiday light. |

The lights turn off at whichever comes first, the duration or the hard off time, and stay off until the next evening. Darkness only *starts* the lights, so your own lights brightening a lux sensor won't turn them off early. With neither limit set, they turn off when it's light again.

### Holidays

On the integration page, use **Add holiday** to add more holidays, or the ⋮ menu on a holiday to edit or delete it. Start from a preset, or choose **Custom** and pick how the dates work:

| Dates | Example |
| --- | --- |
| Same dates every year | `12-01` to `12-26`. Ranges can wrap the new year (`12-31` to `01-01`). |
| Weekday rule | 4th Thursday of November, last Monday of May. Add days before and after. |
| Relative to Easter | A number of days from Easter Sunday (e.g. 49 for Pentecost), plus days before and after. Calculated every year. |
| Relative to Advent | A number of days from the First Sunday of Advent (e.g. -7 for Christ the King), plus days before and after, or through Christmas Eve. Calculated every year. |
| One-time event | A start and end date with a year, e.g. a party or graduation. |
| Calendar | Any night a calendar has an event, optionally only events whose title contains a keyword (e.g. `Bison`). |

Presets: New Year's, Presidents' Day, Valentine's Day, St. Patrick's Day, Easter, Earth Day, Cinco de Mayo, Mother's Day, Memorial Day, Month of the Sacred Heart of Jesus, Father's Day, Juneteenth, Independence Day, Labor Day, Patriot Day, Halloween, Día de los Muertos, Veterans Day, Thanksgiving, Christmas, and Kwanzaa.

Catholic feast days and seasons: Epiphany, Mardi Gras, St. Joseph, Annunciation, Palm Sunday, Divine Mercy Sunday, Ascension (Sunday), Pentecost, Trinity Sunday, Corpus Christi (Sunday), Feast of the Sacred Heart, Immaculate Heart of Mary, Assumption of Mary, All Saints' Day, All Souls' Day, Christ the King, Advent (through Christmas Eve), Gaudete Sunday, Immaculate Conception, and Our Lady of Guadalupe.

Ascension and Corpus Christi use the Sunday observance. For Thursday, edit the holiday's days from Easter to 39 or 60.

Moving holidays and feasts are calculated for each year.

Holidays on the lunar or Hebrew calendars (Lunar New Year, Hanukkah, Diwali, Ramadan) aren't presets yet. Add them as a one-time event each year, or as a calendar holiday using a holiday calendar.

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

**Which holiday shows?** A calendar holiday with a matching event tonight wins. Otherwise, when date ranges overlap, the one that ends first wins, then the shorter one. A feast day inside a season takes over for its day, and a season that runs into a holiday finishes first: Advent runs through Christmas Eve, then Christmas takes over. Calendars are checked for events between noon and midnight, every 15 minutes.

## Entities

| Entity | Purpose |
| --- | --- |
| `switch.holiday_lighting_enabled` | Arms the nightly schedule. Turning it off restores your lights. |
| `select.holiday_lighting_theme` | **Auto** follows the calendar, or pick a holiday to force it. |
| `sensor.holiday_lighting_status` | `disabled`, `waiting_for_dark`, `on`, `done_for_tonight`, `no_holiday`. Attributes include lights changed by hand tonight. |
| `sensor.holiday_lighting_active_holiday` | The holiday showing now, or the one picked for tonight (`Default colors` on nights with no holiday, or `No holiday` if default colors aren't set). Attributes: colors, lights, `showing` (whether the lights are on for it), and the next holiday. |
| `sensor.holiday_lighting_lights_off_at` | When the lights turn off next. Before dark, tonight's off time; once the lights are on, recalculated with the on duration; after they turn off, the next night's off time. Unknown only when holiday lighting is disabled, the schedule is off, or the holiday stays on all night. |
| `sensor.holiday_lighting_<light>_color` | One per light: the color it's showing now (e.g. `Orange`), `Off`, or `Manual` if changed by hand. Attributes: hex, RGB, how it's shown, and the holiday. |
| `calendar.holiday_lighting_schedule` | What each night will show. See [Schedule calendar](#schedule-calendar). |
| `button.holiday_lighting_turn_on_now` | Turn on now, ignoring darkness. Off rules still apply. |
| `button.holiday_lighting_next_colors` | Move the colors forward one step. |
| `button.holiday_lighting_turn_off_for_tonight` | Turn off and stay off for the rest of tonight. |

## Services

| Service | Description |
| --- | --- |
| `holiday_lighting.start` | Turn on now, ignoring darkness. Optional `holiday` name. Off rules still apply. |
| `holiday_lighting.stop` | Turn off and stay off for the rest of tonight. |
| `holiday_lighting.advance` | Move the rotation forward one step. |

## Schedule calendar

`calendar.holiday_lighting_schedule` shows what will light up each night, using the same rules that pick the lights, so overlaps are already resolved. For example, Advent runs through Christmas Eve, broken up by Immaculate Conception and Gaudete Sunday. Each event's details list the colors, effect, off time, and number of lights. Nights with no holiday show **Default colors** if you've set them, or nothing if not.

Find it in the **Calendar** panel in the sidebar, or add a Calendar card to a dashboard. Calendar holidays only appear for tonight, since they depend on events that are checked each evening. A theme picked with the Theme select isn't shown; the calendar shows the automatic schedule.

## Default colors

In the integration's settings, **Default colors** are shown on your default lights on nights with no holiday, on the same dark-to-off schedule. For example, pick white to light the front of the house every night, with holidays taking over on their dates. Leave it empty to keep the lights off on non-holiday nights. The Active holiday sensor shows **Default colors** while they're on.

## Lights without color

Every light in a holiday does something it can show:

| Light | What it shows |
| --- | --- |
| Color | The holiday colors. |
| Color temperature | A matching white: warm for reds, oranges, golds, and pinks; neutral for whites and greens; cool for blues and purples. |
| Dimmable white | A brightness for each color (white brightest, blue dimmest), so chase and cycle still visibly move. |
| On/off | On. |

The Active holiday sensor lists these under **Lights shown in white**.

## Light color sensors and history

Each light's color sensor changes on every color step. With a short rotation interval, that's frequent, so the details (hex, RGB, holiday) are kept out of history. To leave the sensors out of history entirely, add this to `configuration.yaml`:

```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.holiday_lighting_*_color
```

## Dashboard card

[`examples/dashboard-card.yaml`](examples/dashboard-card.yaml) is a ready-made card using only built-in cards: the Enabled switch, tonight's holiday and colors, when the lights turn off, the next holiday, a theme picker, and On / Next / Off buttons. In a dashboard, choose **Edit → Add card → Manual** and paste it in.

## Repairs and diagnostics

- **Repairs** (Settings → System → Repairs) flag a holiday whose lights are unavailable when it runs. They clear on their own once fixed.
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
