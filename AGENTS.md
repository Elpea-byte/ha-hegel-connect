# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.

## What this is

Hegel Connect: a Home Assistant custom integration (domain `hegel_connect`) for Hegel
H150/H200/H400/H600 streaming amplifiers, using the amplifier's local web API with push
updates. Code lives in `custom_components/hegel_connect/`.

| File | Role |
| :---- | :---- |
| `api.py` | Async HTTP client for the amplifier. No Home Assistant imports. |
| `coordinator.py` | Push listener (event queue), state, back-off, cached static data. |
| `config_flow.py` | User setup, discovery (mDNS, SSDP, Cast), reconfigure, options. |
| `entity.py` | Base entity (device info). |
| `media_player.py`, `sensor.py`, `binary_sensor.py`, `event.py`, `number.py`, `select.py`, `switch.py` | Entities. `event.py` holds the now-playing event. `number.py` and `switch.py` also hold the optional volume-per-input entities, and `select.py` the optional auto-standby (all disabled by default). |
| `diagnostics.py` | Diagnostics download (addresses and ids are redacted). |
| `blueprints/automation/hegel_connect/` | Ready-made blueprints, imported by users through the README buttons. |
| `docs/REFERENCE.md` | States, entities, attributes and errors in tables; a test checks it against `strings.json` and the media player. |
| `docs/*.md` | Longer guides (now playing, volume per input, auto standby, announcements, blueprints, streaming services, examples); the README links to them. |
| `docs/ROADMAP.md` | Plan towards 1.0; keep it in step with what is built. |
| `quality_scale.yaml` | Honest self-assessment against the Home Assistant quality scale. |

## Setup and checks (all must pass; CI runs them on every push)

Python 3.14 (what the CI uses and what the current Home Assistant needs). On Windows, in PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements_test.txt
```

Home Assistant's test tools install fine on Windows; if a package refuses to build there, use WSL or a Linux container instead. The checks:

```bash
pip install -r requirements_test.txt
ruff check . && ruff format --check .
mypy custom_components/hegel_connect          # strict
pytest --cov=custom_components.hegel_connect  # total floor in pyproject.toml
yamllint --strict -c .yamllint.yaml blueprints/
coverage report --include="custom_components/hegel_connect/config_flow.py" --fail-under=100
```

## Definition of done for a new entity or option

- [ ] Code, with `_attr_translation_key` and a unique id; `has_entity_name` stays on.
- [ ] Texts in `strings.json` **and** the six files in `translations/` (en, nl, nb, de, fr, es), icon in `icons.json`.
- [ ] Optional or noticeable for existing setups: **disabled by default** (`_attr_entity_registry_enabled_default = False`).
- [ ] A test against the `FakeHegel` fixture, including the failure case (the amplifier refuses, the setting is missing).
- [ ] `docs/REFERENCE.md` (table row, states), the README or a page in `docs/`, `CHANGELOG.md` under *Unreleased*.
- [ ] `quality_scale.yaml` and `docs/ROADMAP.md` still say what is true.
- [ ] Claims in the docs separate what was tried on a real amplifier from what only ran in automated tests.

## Extending the recording

`tests/fixtures/h150_session.json` is a recording of a real H150: answers to `getData` and `getRows` (`snap`, `rows`) and the events of the queue (`events`). To add a case, record the amplifier's own answers (for example with the browser's developer tools on `http://<address>/webclient/`) and paste them in, after removing everything personal: the unique id and `systemMemberId` become `00000000-0000-0000-0000-000000000000`, IP addresses become `192.0.2.x`, host names and account names become neutral text, and cloud ids in paths (Airable, Spotify) become placeholders. Search the file for digits-and-dots and for `@` before you commit. The `FakeHegel` class in `tests/conftest.py` replays it; never contact a real device from a test.

## Releases (short)

`dev` is for day-to-day work; `main` only gets tested code, through a pull request from `dev`. A release bundles several changes: raise `version` in `custom_components/hegel_connect/manifest.json`, rename *Unreleased* in `CHANGELOG.md` to the version with the date (and add an empty *Unreleased* above it plus the compare links), merge `dev` into `main`, then create the GitHub release `vX.Y.Z` on the merge commit of `main`. HACS and the Marketplace only offer releases. The release notes say what was tried on a real amplifier.

## Rules

- Open pull requests against `dev`; `main` only receives tested code from `dev`.
- Add an entry under *Unreleased* in `CHANGELOG.md` for user-visible changes.
- Keep `api.py` free of Home Assistant imports.
- Never commit IP addresses, serial numbers, unique ids or other personal data, also not in test fixtures.
- User-facing text goes through `strings.json` and all files in `translations/` (en, nl, nb, de, fr, es); `tests/test_translations.py` checks they match.
- Errors shown to users are translated (`translation_domain`/`translation_key`); wrong user input raises `ServiceValidationError`.
- Tests replay a real H150 recording through the `FakeHegel` fixture in `tests/conftest.py`; do not contact real devices in tests.
- Claims in the README, CHANGELOG and release notes must be facts that were tested, or clearly marked as expected. Say what was tried on a real amplifier and what only ran in automated tests.
- Optional features are off by default: a new setting or entity must not change anything for existing setups (see the volume-per-input entities, disabled until enabled).
- The user may give an input an own name in the options. Code and blueprints must keep working with the amplifier's own names (`source_name_for`), and must not compare with the shown name.
- The maximum volume always applies to volumes that Home Assistant sets, and inputs with fixed volume are never given a volume.
- Blueprints: English text, `source_url` pointing at the file on `main`, a `homeassistant: min_version`, entity selectors filtered on `integration: hegel_connect`. A new or renamed blueprint needs its inputs in `tests/test_blueprints.py` and a My Home Assistant import button in the README (the test checks both).
- Changes to the entities or attributes the Home Assistant dashboards rely on are breaking: say so in the CHANGELOG.
- Local reports and notes (`Testverslag-*.md`, `Release-*.md`, `CLAUDE.local.md`) are not committed.
