# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.7.4] - 2026-10-09

### Changed

- **Active holiday** never goes to Unknown. When the lights are off (before dark, after the off time, or with holiday lighting disabled), it shows the holiday picked for tonight, or `Default colors` on nights with no holiday. If there's no holiday and no default colors are set, it shows `No holiday`. A new `showing` attribute says whether the lights are on for it.
- The example dashboard card always shows the holiday and its colors, with the status and off time underneath.

## [1.7.3] - 2026-10-09

### Changed

- **Lights off at** always shows the next off time instead of going to Unknown. Before dark it shows tonight's off time. When the lights turn on it's recalculated from the on duration, whichever comes first. After the lights turn off, it moves to the next night's off time. It's only Unknown when holiday lighting is disabled, the schedule is turned off, or the holiday stays on all night.

## [1.7.2] - 2026-10-09

### Fixed

- The integration failed to load on Home Assistant 2026.10 ("cannot import name 'async_extract_referenced_entity_ids'"). Home Assistant moved that helper in 2026.10; Holiday Lighting now uses the new location, which also works on older versions.

## [1.7.1] - 2026-10-08

### Fixed

- **Turn off for tonight** left some lights on. With slow lights, late color reports from earlier steps looked like someone changing the lights by hand, so those lights were marked "Manual" and skipped. Manual changes are now detected from light commands sent by something other than this integration (the app, an automation, a remote, a voice assistant), not from reported colors.
- **Turn off for tonight** now turns off every holiday light, including ones changed by hand. The nightly schedule still leaves those alone.
- Lights could come back on after turning off, when a slow color command reached a bulb late. For a minute after turning off, a light turned back on by one of this integration's own late commands is turned off again.
- **Turn off for tonight** no longer waits behind a color step stuck on slow lights.

### Changed

- Changes made outside Home Assistant (for example, in a bulb's own app) are no longer detected as manual changes.

## [1.7.0] - 2026-10-07

### Added

- **Schedule calendar** (`calendar.holiday_lighting_schedule`). It shows what will light up each night in Home Assistant's Calendar, with overlaps already resolved and the colors, effect, off time, and number of lights in each event. Nights with no holiday show the default colors, if set.
- The example dashboard card includes a week view of the schedule.

## [1.6.0] - 2026-10-07

### Added

- **Default colors.** A new setting picks colors (for example, white) to show on the default lights on nights with no holiday, on the same schedule. Holidays take over on their dates. Leave it empty to keep the lights off when there's no holiday.
- **A color sensor for each light**, such as "Front Entrance Light color". It shows the color the light is displaying right now, `Off`, or `Manual` if someone changed it by hand, with hex, RGB, how it's shown (in color, as a white, or as a brightness), and the holiday as attributes. Sensors for lights no longer used are removed.
- Diagnostics show whether the integration is busy, how many light commands timed out, and how many rotation steps were skipped.

### Fixed

- Status showed **Disabled** while the lights were still confirming they had turned on. It now shows **On** as soon as the lights are told to turn on.
- A slow or unresponsive light could hold up the integration indefinitely, delaying everything behind it, including turning the lights off at the off time. Light commands now give up after 15 seconds and carry on.
- With a short rotation interval, color steps could pile up behind slow lights. A step is now skipped if the previous one is still running.

## [1.5.0] - 2026-10-07

### Added

- **Relative to Advent** date type: a number of days from the First Sunday of Advent, or the whole season through Christmas Eve. Calculated every year.
- **Liturgical presets:** Advent, Gaudete Sunday, Christ the King, Mardi Gras, Palm Sunday, Ascension (Sunday), and Trinity Sunday.
- **Lights without color now take part.** Color-temperature lights show a matching warm, neutral, or cool white, and dimmable white lights show a brightness for each color. The Active holiday sensor lists them under "Lights shown in white."
- **Buttons:** Turn on now, Next colors, and Turn off for tonight.
- **Dashboard card** in `examples/dashboard-card.yaml`.

### Changed

- When holidays overlap, the one that ends first wins, then the shorter one. Before, only length counted, so a long Advent (up to 28 days) could lose to the Christmas preset on December 1. Every other overlap resolves the same way, except that on December 26 Christmas now beats Kwanzaa.
- Changing a color-temperature light by hand is now recognized as a manual change.

### Removed

- The "lights can't show colors" repair, since those lights are now handled. Existing ones clear on their own.

## [1.4.1] - 2026-10-07

### Changed

- **Add holiday** only lists presets you haven't added yet. A holiday made from a preset stays linked to it even if you rename it; deleting it makes the preset available again.

## [1.4.0] - 2026-10-07

### Added

- **More presets:** Presidents' Day, Earth Day, Cinco de Mayo, Month of the Sacred Heart of Jesus, Father's Day (3rd Sunday of June), Juneteenth, Patriot Day, Día de los Muertos, and Kwanzaa.
- **Catholic feast day presets:** Epiphany, St. Joseph, Annunciation, Divine Mercy Sunday, Pentecost, Corpus Christi, Feast of the Sacred Heart, Immaculate Heart of Mary, Assumption of Mary, All Saints' Day, All Souls' Day, Immaculate Conception, and Our Lady of Guadalupe. Easter-relative feasts are calculated every year.
- **Days from Easter** for "Relative to Easter" holidays, so a custom holiday can be any day around Easter, like Ascension or Trinity Sunday. Existing Easter holidays are unchanged.
- **Open in HACS** and **Add integration** buttons in the README.

## [1.3.1] - 2026-10-07

### Fixed

- Adding or editing a holiday failed with "Not all required fields are filled in." A required switch inside the collapsed **Schedule for this holiday** section started out blank. The section now opens pre-filled and nothing in it is required.
- Editing a holiday now shows its saved schedule override. Before, the section showed empty, and saving cleared the override.

## [1.3.0] - 2026-10-06

### Added

- **Sun elevation source.** Dark detection can read the sun's elevation from the Sun integration (`sun.sun`) or any sensor reporting degrees, instead of calculating it. If the entity is unavailable, it falls back to the calculation.
- The Status sensor and diagnostics show the current sun elevation.

## [1.2.0] - 2026-10-06

### Added

- **New holiday date types.** A weekday rule (e.g. 4th Thursday of November), days around Easter (calculated every year), one-time events with a year, and calendar holidays that turn on any night a calendar has an event, optionally only events whose title contains a keyword.
- **More presets:** Mother's Day, Memorial Day, Labor Day, and Veterans Day.
- **Effects.** Whole-house cycle, whole-house fade, and twinkle, alongside chase and static.
- **Per-holiday schedule.** A holiday can stay on all night or use its own duration or hard off time.
- **Weekend hard off time** for Friday and Saturday nights.
- **Manual changes are respected.** A light changed by hand is left alone for the rest of the night (can be turned off in settings).
- **Repairs** for lights that can't show color or are unavailable.
- **Diagnostics** download.
- **Integration icon,** with light and dark versions (Home Assistant 2026.3+).

### Changed

- Easter and Thanksgiving presets now follow the real date each year instead of a fixed window.
- "Rotate" mode is now called **Chase**. Existing holidays keep working unchanged.

### Fixed

- If Home Assistant missed a night's off time (for example, restarting at 11:00 PM), the lights stayed off the following night. They now turn off as soon as Home Assistant is back and come on as usual the next evening.

## [1.1.0] - 2026-10-06

### Changed

- **Colors** are chosen with a color picker instead of typed. Add as many as you like, give each an optional name, and drag them into the order they rotate in.
- **Lights** can be dragged to reorder, in holidays and in the default lights.

Holidays saved by 1.0.0 keep working and open in the new editor with their colors in the same order.

## [1.0.0] - 2026-10-06

First release.

### Added

- **Holidays.** Add as many holidays as you like, each with a yearly date range (`MM-DD`, can wrap the new year), colors, an ordered list of lights, mode, rotation interval, brightness, and transition. Holidays appear on the integration page with native add, edit, and delete.
- **Presets.** New Year's, Valentine's Day, St. Patrick's Day, Easter, Independence Day, Halloween, Thanksgiving, and Christmas. Pick any during setup or when adding a holiday.
- **Colors.** Enter hex codes or color names, e.g. `red, green, #FFFFFF`.
- **Color rotation.** Each color moves one light down the list every interval, or choose static colors.
- **Overlapping holidays.** When date ranges overlap, the shorter range wins.
- **Nightly schedule.**
  - Lights turn on when it is dark, based on sun elevation, an illuminance sensor, or either.
  - They stay on for a set duration and turn off at a hard off time, whichever comes first. Off times before noon count as after midnight.
  - Once off, lights stay off until the next evening.
  - Darkness only starts the lights; a lux sensor brightening afterward won't turn them off early.
- **Always-on mode.** With the schedule turned off, lights run whenever holiday lighting is enabled.
- **Entities.**
  - `switch.holiday_lighting_enabled` arms holiday lighting.
  - `select.holiday_lighting_theme` chooses Auto or a specific holiday.
  - `sensor.holiday_lighting_status`, `sensor.holiday_lighting_active_holiday`, and `sensor.holiday_lighting_lights_off_at` report what is happening.
- **Services.** `holiday_lighting.start` (optional `holiday`), `holiday_lighting.stop`, and `holiday_lighting.advance`.
- **Restore.** Turning holiday lighting off puts each light back to its previous on/off state, brightness, and color.
- **Resume after restart.** State is saved, so a restart picks up with the same off time.
- **HACS support,** with CI for hassfest, HACS validation, and tests.

### Known limitations

- Easter and Thanksgiving presets use a fixed date window; adjust the dates each year.
- One schedule applies to all holidays.
- Requires Home Assistant 2026.2 or newer.

[Unreleased]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.7.4...HEAD
[1.7.4]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.7.3...v1.7.4
[1.7.3]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.7.2...v1.7.3
[1.7.2]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.7.1...v1.7.2
[1.7.1]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.7.0...v1.7.1
[1.7.0]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.4.1...v1.5.0
[1.4.1]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/bisman-automations/ha-holiday-lighting/releases/tag/v1.0.0
