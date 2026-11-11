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
| `docs/ROADMAP.md` | Plan towards 1.0; keep it in step with what is built. |
| `quality_scale.yaml` | Honest self-assessment against the Home Assistant quality scale. |

## Checks (all must pass; CI runs them on every push)

```bash
pip install -r requirements_test.txt
ruff check . && ruff format --check .
mypy custom_components/hegel_connect          # strict
pytest --cov=custom_components.hegel_connect  # total floor in pyproject.toml
yamllint --strict -c .yamllint.yaml blueprints/
coverage report --include="custom_components/hegel_connect/config_flow.py" --fail-under=100
```

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
