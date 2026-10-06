# Contributing

Thanks for helping out! The most useful contributions right now:

1. **Model reports** for the H200, H400 and H600 ([open one](../../issues/new?template=model_report.yml)). Also when everything works.
2. **Bug reports** with the diagnostics file (Settings > Devices & services > Hegel Connect > ⋮ > *Download diagnostics*). The file contains no IP address or device ids.
3. **Translations**: copy `custom_components/hegel_connect/translations/en.json` to `<language>.json` and translate the values. A test checks that every language has the same keys and placeholders.

## Code

```bash
pip install -r requirements_test.txt
ruff check
pytest
```

- Keep `api.py` free of Home Assistant imports.
- Never commit IP addresses, serial numbers or other personal data (also not in test fixtures).
- One topic per pull request; describe on which amplifier you tested.
