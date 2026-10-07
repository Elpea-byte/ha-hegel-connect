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
| `media_player.py`, `sensor.py`, `binary_sensor.py`, `number.py` | Entities. |
| `quality_scale.yaml` | Honest self-assessment against the Home Assistant quality scale. |

## Checks (all must pass; CI runs them on every push)

```bash
pip install -r requirements_test.txt
ruff check . && ruff format --check .
mypy custom_components/hegel_connect          # strict
pytest --cov=custom_components.hegel_connect  # total floor in pyproject.toml
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
- Claims in the README must be facts that were tested, or clearly marked as expected.
