# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-06

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

[Unreleased]: https://github.com/bisman-automations/ha-holiday-lighting/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/bisman-automations/ha-holiday-lighting/releases/tag/v0.1.0
