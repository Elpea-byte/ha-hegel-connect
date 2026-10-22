# Roadmap to 1.0

**Plans, not promises.** This is the direction, in the order the maintainer intends to work. Dates are not given, the order can change, and an item can be dropped. Ideas and requests are welcome in [Discussions](../../../discussions/categories/ideas); what is planned is tracked in the [milestones](../../../milestones).

## What 1.0 means

Version 1.0 is the point where Hegel Connect is stable and finished enough that it could be submitted to Home Assistant core as it is: entities, attributes and actions stay as they are (semantic versioning), the documentation is complete, the tests are thorough and the amplifier library is published on its own. Getting into core is a separate step after 1.0, with its own review. It is the goal that sets the quality bar, not something that is promised.

The Home Assistant [integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) is the checklist. [`quality_scale.yaml`](../custom_components/hegel_connect/quality_scale.yaml) keeps an honest list of what is done and what is still open.

## How work is done

- **Every feature ships with its own tests.** A feature in 0.6 or 0.7 is not finished until its tests are in, written against the fake amplifier that replays a real recording. Version 0.8 is not for catching up on missing tests; it only lifts the overall coverage to 95% or more.
- **Documentation is separate from the versions.** README sections, examples and blueprints can be merged at any time as documentation-only changes, without a release.
- **Breaking changes** are called out as such in the release notes, with what to do about them.

## Versions

| Version | Theme | What | Done when |
| :---- | :---- | :---- | :---- |
| **0.6** | Daily use | Reconnect at once on `homeassistant.update_entity` ([#34](../../../discussions/34)); optional start volume per input ([#29](../../../discussions/29)); *play* after stopping live radio restarts the last favorite ([#30](../../../discussions/30)) | Each has tests and is tried on an H150; README and changelog updated |
| **0.7** | Features | Restore volume and input after an announcement ([#33](../../../discussions/33)): a documented recipe first, code only if the amplifier can play a URL; then searching internet radio and podcasts ([#27](../../../discussions/27)) as the last feature. If #27 turns out too big it moves to after 1.0 | Each has tests and is tried on an H150 |
| **0.8** | Core behaviour and coverage | Entities become *unavailable* when the amplifier cannot be reached at all (network standby stays *off*, the network sensor tells them apart); this is a **breaking change** and is listed as one in the release notes. Overall test coverage to 95% or more, with the CI floor raised to match. `pip-audit` in the CI | CI fails under 95%; the `test-coverage` rule is done |
| **0.9** | Own library and quality | `api.py` becomes a separate Python package in its own repository, published on PyPI from GitHub Actions (trusted publishing), with its own tests; the integration requires it in `manifest.json`. Every rule in `quality_scale.yaml` is done or exempt | The package is on PyPI and used by the integration; no `todo` left |
| **1.0** | Stable | Entities, attributes and actions frozen; documentation final; release notes say what is stable | Six weeks in a row without open bugs |

1.0 does not wait for other people. It was tested on an H150. The other models are listed in the supported-models table as soon as someone confirms them, and until then they stay "expected to work".

## Documentation track (no release needed)

Merged as documentation-only changes whenever they are ready, independent of the versions above:

- Ready-made blueprints with import buttons ([#31](../../../discussions/31)).
- A dashboard example with a screenshot ([#32](../../../discussions/32)).
- A short README section, *Triggers: which entity and attribute to use*. It replaces the idea of device triggers and conditions ([#28](../../../discussions/28)): Home Assistant no longer accepts new device automations and points to entity triggers, and our states and attributes are already available as such, so nothing is built for it.

## After 1.0: Home Assistant core

- A new core integration normally starts with one platform per pull request, so the media player would go first and the sensors, number, select and binary sensor follow.
- Core uses its own translation process: the English `strings.json` goes in, other languages come through Home Assistant's translation tool, so the separate language files of this repository do not move along as they are.
- Documentation lives on home-assistant.io, not in the README.
- All of this is checked against the then-current developer documentation before a pull request is opened.

## Help wanted

- **Model reports** for the H200, H400 and H600, also when everything works: [send one](../../../issues/new?template=model_report.yml). Confirmed models are added to the supported-models table.
- Translations and bug reports: see [CONTRIBUTING.md](../CONTRIBUTING.md).
