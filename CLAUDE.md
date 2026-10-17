# Holiday Lighting: notes for Claude

Read this before changing anything in this repo. It describes how the repo is set up and how work is done here.

## What this is

A HACS custom integration (`holiday_lighting`) for Home Assistant. Holidays (date rules, colors, lights, effects, schedule) are config subentries. A controller turns lights on at dark, rotates colors, and turns them off at the earlier of the duration or the hard off time.

- `custom_components/holiday_lighting/controller.py`: state machine (`HolidayLightingController`) and the `Holiday` dataclass.
- `schedule.py`: pure date and schedule helpers with no Home Assistant state. Put date and time logic here so it's easy to test.
- `config_flow.py`: setup, options, and the holiday subentry flow. `presets.py` holds the built-in holidays.
- Platforms: `button.py`, `calendar.py`, `select.py`, `sensor.py`, `switch.py`. `entity.py` is the shared base. `diagnostics.py` is the diagnostics download.
- `const.py` holds config keys and shared constants. Add new keys there.

## Workflow

- Work and push straight to `main`. The owner tags releases himself (`vX.Y.Z`). Don't tag or create releases.
- Every user-visible change bumps `version` in `custom_components/holiday_lighting/manifest.json` and adds a `CHANGELOG.md` entry under a new version heading (Keep a Changelog: `Added`, `Changed`, `Fixed`, `Removed`), plus the compare link at the bottom. Patch for fixes and small tweaks, minor for new features.
- Update `README.md` when behavior, entities, buttons, or options change. Its entity table is the public list.
- Commit with the owner's git identity and the Claude trailers. Use the identity from the owner's git config, not one written into the repo:
  ```
  git -c user.name="<owner name>" -c user.email="<owner email>" commit -m "..."
  ```
  End the message with `Co-Authored-By: Claude <model> <noreply@anthropic.com>` and the `Claude-Session:` line.
- Push with `git fetch origin main && git rebase FETCH_HEAD && git push origin HEAD:main`. Another workflow (draft release) also commits to `main` sometimes, so a plain push can be rejected. Rebase; never force-push.
- Check CI with REST, not GraphQL (GraphQL is blocked in this environment):
  `gh api "repos/bisman-automations/ha-holiday-lighting/actions/runs?head_sha=$(git rev-parse HEAD)"`
  The jobs are hassfest, HACS validation, and pytest. Job logs may be unavailable; the commit's check-run annotations (`gh api repos/.../commits/<sha>/check-runs`) name the failing rule.

## Checks before every commit

```
ruff format custom_components tests
ruff check --select E,F,I,B,UP --ignore E501 custom_components tests
pytest -q
```

The local test environment runs Home Assistant 2026.2.3 (`pytest-homeassistant-custom-component`). Newer Home Assistant versions can break at import time in ways these tests don't catch. In 1.7.1, `homeassistant.helpers.service` lost a function that was only found in 2026.10. When a new version is out, check its release notes and developer blog for removed or moved helpers, and don't import anything the test environment can't prove exists.

## Conventions

- **Translations:** `strings.json` and `translations/en.json` must match. Edit both. Entity names live under `entity.<platform>.<key>.name`. Icons live in `icons.json`.
- **Entity ids:** `sensor.holiday_lighting_<key>`, `button.holiday_lighting_<key>`, and so on. Tests look entities up by these ids.
- **Schedule logic:** date and time math goes in `schedule.py` and is tested in `tests/test_schedule.py`. State and service behavior go in `controller.py` and are tested in `tests/test_init.py`.
- **Test helpers:** freeze time with the `freezer` fixture and the `tz` fixture. Patch darkness with `DARK` (`is_dark`), not the sun. Helpers: `_entry`, `_entry_with`, `_holiday`, `_start`, `_tick`, `_state`.
- **Light commands:** go through the controller's timeout-wrapped helper (15 s). Our own calls carry our context, so manual-change detection ignores them.
- **Manifest dependencies:** hassfest requires any integration you import to be listed in `dependencies`. Don't import another integration's module unless it's declared there. `logbook` isn't declared, so Activity entries are written by firing the `logbook_entry` event directly.
- **Docs and privacy:** never put account numbers, addresses, service IDs, email addresses, or other account-specific details in README, CHANGELOG, or any repo file. Use placeholders.

## Things that already bit us

- `ObjectSelector` field selectors must be dict form: `{"color_rgb": {}}`, not `ColorRGBSelector()`.
- Collapsible `section()` schemas: the frontend fills a section from its default, so the default must carry the current values, and nothing inside it may be required.
- Deprecated Home Assistant helpers: `get_astral_location` was replaced with `astral` directly (1.8.1). `TargetSelectorData` is removed in 2026.12, so use `TargetSelection`.
- Dates: `MM-DD` for yearly holidays. `first_sunday_of_advent` and `easter_sunday` are computed per year. Noon is the boundary that decides which night a time belongs to (`night_of`).
- Overlap rule: a calendar holiday with a matching event tonight wins. Otherwise the window that ends first wins, then the shorter one.
- Default colors: a synthetic `Holiday` with id `default`. "Use default colors tonight" sets `default_night`, which the sensors and calendar read through `_selected_holiday`.
- Calendar titles: `Holiday Lights: <name>`, and `Holiday Lights for Tonight: <name>` for the event that covers tonight.
- Lights on at / Lights off at are timestamp sensors. Each has a live value and a predicted value (`next_on`, `next_off`) before the lights change.
- Activity: a holiday start writes one entry per light. Color steps aren't logged, so the Activity list doesn't fill up during a show.
- Entities must never raise. A raised exception in a Home Assistant entity breaks its platform.

## Open items

Check the repo's open issues and the owner's latest messages for current work. Don't treat an item from an older note as still open.
