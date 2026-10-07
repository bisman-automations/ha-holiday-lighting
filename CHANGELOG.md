# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/bisman-automations/ha-holiday-lighting/releases/tag/v1.0.0
