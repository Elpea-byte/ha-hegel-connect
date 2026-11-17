# Contributing

Thanks for helping out! The most useful contributions right now:

1. **Model reports** for the H400 and H600 ([open one](../../issues/new?template=model_report.yml)); the H200 is confirmed. Also when everything works.
2. **Bug reports** with the diagnostics file (Settings > Devices & services > Hegel Connect > ⋮ > *Download diagnostics*). The file contains no IP address or device ids.
3. **Ideas** go in [Discussions](../../discussions/categories/ideas), where others can vote and comment. Issues are for bugs and model reports.
4. **Translations**: copy `custom_components/hegel_connect/translations/en.json` to `<language>.json` and translate the values. A test checks that every language has the same keys and placeholders.

## Code

```bash
pip install -r requirements_test.txt
ruff check .
ruff format .                                # CI runs "ruff format --check": format before you push
mypy custom_components/hegel_connect         # strict
pytest --cov=custom_components.hegel_connect # the total floor is in pyproject.toml
coverage report --include="custom_components/hegel_connect/config_flow.py" --fail-under=100
yamllint --strict -c .yamllint.yaml blueprints/
```

Python 3.14. On Windows run the tests in WSL or a Linux container: `pytest` does not start on native Windows (see [AGENTS.md](AGENTS.md)). A new entity or option follows the checklist *Definition of done* there: texts in all six languages, disabled by default when optional, a test, the reference page and the changelog.

- Keep `api.py` free of Home Assistant imports.
- Never commit IP addresses, serial numbers or other personal data (also not in test fixtures).
- One topic per pull request; describe on which amplifier you tested.
- Open pull requests against the `dev` branch.

## Branches and releases

- `dev`: day-to-day work, tested on the maintainer's own amplifier first. Changes are listed under *Unreleased* in the changelog.
- `main`: only what has been tested; updated from `dev` with a pull request.
- Releases are made from `main` and bundle several changes. HACS and the Marketplace offer releases only, so pushes to `dev` or `main` never reach users by themselves. Bug fixes can get their own patch release; larger changes may first ship as a pre-release (for example `v0.3.0b1`).
