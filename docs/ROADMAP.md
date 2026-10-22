# Roadmap to 1.0

**Plans, not promises.** This is the direction, in the order the maintainer intends to work. Dates are not given, the order can change, and an item can be dropped. Ideas and requests are welcome in [Discussions](../../../discussions/categories/ideas); what is planned is tracked in the [milestones](../../../milestones).

## What 1.0 means

Version 1.0 is the point where Hegel Connect is stable and finished enough that it could be submitted to Home Assistant core as it is: entities, attributes and actions stay as they are (semantic versioning), the documentation is complete, the tests are thorough and the amplifier library is published on its own. Getting into core is a separate step after 1.0, with its own review. It is the goal that sets the quality bar, not something that is promised.

The Home Assistant [integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) is the checklist. [`quality_scale.yaml`](../custom_components/hegel_connect/quality_scale.yaml) keeps an honest list of what is done and what is still open.

## Versions

| Version | Theme | What | Done when |
| :---- | :---- | :---- | :---- |
| **0.6** | Daily use | Reconnect at once on `homeassistant.update_entity` ([#34](../../../discussions/34)); optional start volume per input ([#29](../../../discussions/29)); *play* after stopping live radio restarts the last favorite ([#30](../../../discussions/30)) | Tried on an H150; tests, README and changelog updated |
| **0.7** | Tests | Client and coordinator tests against recorded amplifier answers, coverage from about 83% to 95% or more; the CI floor goes up with it | CI fails under 95%; the `test-coverage` rule is done |
| **0.8** | Own library | `api.py` becomes a separate Python package in its own repository, published on PyPI from GitHub Actions (trusted publishing), with its own tests; the integration requires it in `manifest.json` | The package is on PyPI and used by the integration; the `dependency-transparency` rule is done |
| **0.9** | Core quality | Entities become *unavailable* when the amplifier cannot be reached at all (network standby stays *off*, the network sensor tells them apart); every rule in `quality_scale.yaml` is done or exempt; H200, H400 and H600 confirmed or honestly documented; a period of daily use without open bugs | No `todo` left; no open bugs |
| **1.0** | Stable | Entities, attributes and actions frozen; documentation final; release notes say what is stable | The 0.9 conditions held for a while |

A step that changes behaviour for existing users, such as the *unavailable* change in 0.9, is listed in the changelog as a breaking change with what to do about it.

## After 1.0: Home Assistant core

- A new core integration normally starts with one platform per pull request, so the media player would go first and the sensors, number, select and binary sensor follow.
- Core uses its own translation process: the English `strings.json` goes in, other languages come through Home Assistant's translation tool, so the separate language files of this repository do not move along as they are.
- Documentation lives on home-assistant.io, not in the README.
- All of this is checked against the then-current developer documentation before a pull request is opened.

## Not on the way to 1.0

Useful, but not needed for 1.0 and not planned in order: searching internet radio and podcasts ([#27](../../../discussions/27)), device triggers and conditions ([#28](../../../discussions/28)), ready-made blueprints ([#31](../../../discussions/31)), a dashboard example in the README ([#32](../../../discussions/32)) and restoring volume and input after an announcement ([#33](../../../discussions/33)). Device triggers fit core well and may move up after 0.7. Blueprints and dashboard examples do not belong in core.

## Help wanted

- **Model reports** for the H200, H400 and H600, also when everything works: [send one](../../../issues/new?template=model_report.yml). Confirmed models are what lets 1.0 say more than "expected to work".
- Translations and bug reports: see [CONTRIBUTING.md](../CONTRIBUTING.md).
