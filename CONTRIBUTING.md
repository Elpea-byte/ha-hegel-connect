# Contributing

Thanks for helping out! The most useful contributions right now:

1. **Model reports** for the H200, H400 and H600 ([open one](../../issues/new?template=model_report.yml)). Also when everything works.
2. **Bug reports** with the diagnostics file (Settings > Devices & services > Hegel Connect > ⋮ > *Download diagnostics*). The file contains no IP address or device ids.
3. **Translations**: copy `custom_components/hegel_connect/translations/en.json` to `<language>.json` and translate the values. A test checks that every language has the same keys and placeholders.

## Code

```bash
pip install -r requirements_test.txt
ruff check
ruff format        # CI runs "ruff format --check": format before you push
pytest
```

- Keep `api.py` free of Home Assistant imports.
- Never commit IP addresses, serial numbers or other personal data (also not in test fixtures).
- One topic per pull request; describe on which amplifier you tested.
- Open pull requests against the `dev` branch.

## Branches and releases

- `dev`: day-to-day work, tested on the maintainer's own amplifier first. Changes are listed under *Unreleased* in the changelog.
- `main`: only what has been tested; updated from `dev` with a pull request.
- Releases are made from `main` and bundle several changes. HACS offers releases only, so pushes to `dev` or `main` never reach users by themselves. Bug fixes can get their own patch release; larger changes may first ship as a pre-release (for example `v0.3.0b1`).
