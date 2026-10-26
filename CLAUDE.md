# Holiday Lighting: notes for Claude and other coding agents

Read this before changing anything in this repo. It describes how the repo is set up and how work is done here.

## What this is

A HACS custom integration (`holiday_lighting`) for Home Assistant. Holidays (date rules, colors, lights, effects, schedule) are config subentries. A controller turns lights on at dark, rotates colors, and turns them off at the earlier of the duration or the hard off time.

- `custom_components/holiday_lighting/controller.py`: state machine (`HolidayLightingController`) and the `Holiday` dataclass.
- `schedule.py`: pure date and schedule helpers with no Home Assistant state. Put date and time logic here so it's easy to test.
- `config_flow.py`: setup, options, and the holiday subentry flow. `presets.py` holds the built-in holidays.
- Platforms: `button.py`, `calendar.py`, `select.py`, `sensor.py`, `switch.py`. `entity.py` is the shared base. `diagnostics.py` is the diagnostics download.
- `const.py` holds config keys and shared constants. Add new keys there.

## Workflow

- Update `README.md` when behavior, entities, buttons, or options change. Its entity table is the public list.
- Check CI with REST, not GraphQL (GraphQL is blocked in some agent environments):
  `gh api "repos/bisman-automations/ha-holiday-lighting/actions/runs?head_sha=$(git rev-parse HEAD)"`
  The workflows are Test (lint, pytest on the oldest and newest Home Assistant) and Validate (hassfest, HACS, standards). When job logs are unavailable, the commit's check-run annotations (`gh api repos/.../commits/<sha>/check-runs`) name the failing rule.

## Checks

Run the shared checks at the end of this file. The `frontend` integration's
requirements are needed for the tests (CI: `core-requirements: frontend`).

`requirements_test_min.txt` runs Home Assistant 2026.2.3 and `requirements_test.txt`
the newest release. Newer Home Assistant versions can break at import time in ways
these tests don't catch. In 1.7.1, `homeassistant.helpers.service` lost a function
that was only found in 2026.10. When a new version is out, check its release notes
and developer blog for removed or moved helpers, and don't import anything the test
environment can't prove exists. The Test workflow's **next** job tries the upcoming
release.

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

<!-- BEGIN bisman-automations shared rules -->
<!-- This block is the same in every bisman-automations repo. Edit it in
     bisman-automations/.github (templates/CLAUDE.shared.md) and copy it to
     every repo; the Validate workflow's "standards" job checks it matches. -->

## Shared rules (every bisman-automations repo)

### Releases

- The version lives in `custom_components/<domain>/manifest.json`. Anything
  else that repeats it is called out in the repo-specific notes below and is
  bumped in the same commit.
- Versions follow [Semantic Versioning](https://semver.org): patch for fixes,
  translations, docs and CI; minor for new features, options or entities;
  major when something users rely on is removed or renamed (entities,
  services, events, options) or setup has to be redone.
- Check what is released before choosing a version:
  `git ls-remote --tags origin | awk -F/ '{print $3}' | sort -V | tail -1`
  (`sort -V`: plain sorting puts `v1.10.0` before `v1.9.0`). Never add
  changes to a released version. If the manifest version has no tag yet,
  add to its CHANGELOG section instead of bumping again.
- Every push to `main` ships as a release. In the same push: bump the
  manifest version, and add a dated `## [X.Y.Z] - YYYY-MM-DD` section to
  `CHANGELOG.md` (Keep a Changelog: Added, Changed, Deprecated, Removed,
  Fixed, Security) with its compare link at the bottom. Small follow-ups can
  collect under `## [Unreleased]` first; move them into the version section
  when you bump.
- Ask Donavan before every push. Push fast-forward only: never force-push,
  rebase or amend anything already pushed, or rewrite history in any other
  way. Rewriting history orphans the release tags (it broke drafting in
  ha-button-actions).
- Pushing to `main` runs **Draft release**, which creates or refreshes a
  draft `vX.Y.Z` with that version's CHANGELOG section as the notes, the
  commits since the last release and `<domain>.zip`. **Donavan publishes
  the draft himself**, and publishing creates the tag. Never create or push
  tags, publish releases, or edit published releases.
- Publishing runs **Release check**: the tag must match the manifest version
  and the CHANGELOG, and be on `main`. If it fails, fix it with a new patch
  release, not by moving the tag.

### Commits

- Author commits as `Donavan Becker <donavan.becker@icloud.com>` (set
  `git config user.name` / `user.email` in the clone). HACS's
  default-repository check needs the submitter to have a fair share of the
  commits. Credit an AI assistant with a `Co-Authored-By:` trailer if you
  like, never as the author.
- Subject lines are plain, imperative and say what changed for the user
  ("Show Pico remotes as unavailable when Lutron isn't running"). No
  `fix:`/`feat:` prefixes. Release commits are "Release X.Y.Z".
- Commit and push only when asked.

### CI (shared workflows)

- `.github/workflows/` holds four thin callers of the reusable workflows in
  [bisman-automations/.github](https://github.com/bisman-automations/.github):
  `test.yml` (lint, frontend, pytest on the oldest supported and the newest
  Home Assistant, plus the upcoming one as information only), `validate.yml`
  (hassfest, HACS, standards), `draft-release.yml` and `release-check.yml`.
  Don't add jobs to the callers. Use the shared workflow's inputs, or change
  the shared workflow so every repo gets the improvement.
- `requirements_test.txt` leaves `pytest-homeassistant-custom-component`
  unpinned (newest Home Assistant) and pins ruff (and mypy where used).
  `requirements_test_min.txt` pins the harness release for the minimum in
  `hacs.json`: the newest harness release of that month. CI fails if they
  drift apart.
- Raising the minimum Home Assistant means changing, together: `hacs.json`,
  `requirements_test_min.txt`, `python-min` in `test.yml` (3.13 up to
  2026.2, 3.14 from 2026.3), the README's Home Assistant badge, and a
  CHANGELOG entry.
- Home Assistant 2026.3 and newer need Python 3.14 (3.14.2+).
- The published hassfest rejects `categories` in `manifest.json` and Pillow
  in `requirements`. Leave both out.
- Dependabot (`.github/dependabot.yml`) proposes action and pinned-tool
  updates weekly. It ignores the test harness on purpose.
- Test and Validate also run every Thursday, the day after Home Assistant's
  betas come out. The **next** test job (newest pre-release harness) is
  information only: when it fails, fix the cause before that release ships.

### Before saying work is done

Run from the repo root, in a Python 3.14 venv with `requirements_test.txt`
installed:

```
ruff check .
ruff format --check .
pytest
```

Also run `node --test tests/*.mjs` when the repo has Node tests, mypy when
the repo-specific notes list it, and the tests in a second venv with
`requirements_test_min.txt` when a change could behave differently on the
oldest supported Home Assistant. The standards check (also in CI) is
`python <path to bisman-automations/.github>/scripts/check_repo.py .`.

### Code and docs

- Support every Home Assistant from the `hacs.json` minimum to the newest
  release. Check for deprecations in the newest release and the beta.
- Keep entity IDs, unique IDs, service names and event names stable. When
  one has to change, migrate it and say so under Changed in the CHANGELOG.
- `strings.json` and `translations/en.json` hold the same keys. Home
  Assistant reads only `translations/`, so change both in the same commit.
- Never put personal details in the repo (README, CHANGELOG, code, tests,
  screenshots): no names, addresses, account or device identifiers, or real
  entity IDs. Use placeholders such as `light.living_room`.
- `README.md` is user documentation with the standard header (badges, HACS
  and "add integration" My buttons) and sections Installation, Setup, ...,
  Troubleshooting, Development, License. Use plain language and show names,
  not entity IDs, wherever the UI does.
<!-- END bisman-automations shared rules -->
