# Roadmap to 1.0

**Plans, not promises.** This is the direction, in the order the maintainer intends to work. Dates are not given, the order can change, and an item can be dropped. Ideas and requests are welcome in [Discussions](../../../discussions/categories/ideas); what is planned is tracked in the [milestones](../../../milestones).

## What 1.0 means

Version 1.0 is the point where Hegel Connect is stable and finished enough that it could be submitted to Home Assistant core as it is: entities, attributes and actions stay as they are (semantic versioning), the documentation is complete, the tests are thorough and the amplifier library is published on its own. Getting into core is a separate step after 1.0, with its own review. It is the goal that sets the quality bar, not something that is promised.

The Home Assistant [integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) is the checklist. [`quality_scale.yaml`](../custom_components/hegel_connect/quality_scale.yaml) keeps an honest list of what is done and what is still open.

## Pace

There is no schedule, and the plan is deliberately not rushed:

- At most one release every three to four weeks, unless a bug needs a fix.
- A version is tried on the maintainer's own amplifier for at least two weeks before it is released.
- Features are bundled: a version comes out when all its items are done and tested, not one by one.
- A breaking change is announced in the release notes one version ahead.
- Every release has something in it that users will notice and enjoy, listed in the table below.

## How work is done

- **Every feature ships with its own tests.** A feature in 0.6 or 0.7 is not finished until its tests are in, written against the fake amplifier that replays a real recording. Version 0.8 is not for catching up on missing tests; it only lifts the overall coverage to 95% or more.
- **Documentation is separate from the versions.** README sections, examples and blueprints can be merged at any time as documentation-only changes, without a release.
- **Breaking changes** are called out as such in the release notes, with what to do about them.

## Versions

| Version | Status | Theme | What | Nice for users | Done when |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **0.6** | Released (2026-11-07) | Daily use | Optional volume per input, reconnect on `update_entity`, *play* after radio, four blueprints, fixes. See the [release](https://github.com/Elpea-byte/ha-hegel-connect/releases/tag/v0.6.0) and the [changelog](../CHANGELOG.md) | Volume starts where you want it, the play button works after radio | Done |
| **0.7** | In progress | Features | Built on `dev`, with tests, tried on an H150: the now-playing event ([#36](../../../discussions/36)), a recipe for restoring the amplifier after an announcement ([#33](../../../discussions/33)), the amplifier's own auto-standby as an optional select ([#42](../../../discussions/42)), a fifth blueprint for the now-playing event, and hardening of the JSON reading. **Open:** searching internet radio ([#27](../../../discussions/27)); the amplifier has a search form for it, being researched. If #27 turns out too big it moves to after 1.0 | A listening log of what you play and in which quality; choose how long the amplifier may sit idle; finding a station by typing its name | #27 built or moved, and 0.7 released |
| **0.8** | Planned | Core behaviour and coverage | Entities become *unavailable* when the amplifier cannot be reached at all (network standby stays *off*, the network sensor tells them apart); this is a **breaking change** and is listed as one in the release notes. Larger cover art where the streaming service offers it, only if that can be done reliably. Overall test coverage to 95% or more, with the CI floor raised to match. `pip-audit` in the CI. Make the *Maximum volume* number recognisable for the blueprint picker, which can only filter on device class or unit (the start volume numbers have neither, so the night blueprint list shows all of them); this changes an entity, so it is weighed against the dashboards that rely on it and listed as breaking if it is | Bigger album art; a clear signal when the amplifier is really gone | CI fails under 95%; the `test-coverage` rule is done |
| **0.9** | Planned | Own library and quality | `api.py` becomes a separate Python package in its own repository, published on PyPI from GitHub Actions (trusted publishing), with its own tests; the integration requires it in `manifest.json`. Every rule in `quality_scale.yaml` is done or exempt | Mostly under the hood; the documentation track below is announced with it | The package is on PyPI and used by the integration; no `todo` left |
| **1.0** | Planned | Stable | Entities, attributes and actions frozen; documentation final; release notes say what is stable | A stable base to build on | Six weeks in a row without open bugs |

1.0 does not wait for other people. It was tested on an H150. The other models are listed in the supported-models table as soon as someone confirms them, and until then they stay "expected to work".

## Documentation track (no release needed)

Merged as documentation-only changes whenever they are ready, independent of the versions above:

- **Done:** ready-made blueprints with import buttons ([#31](../../../discussions/31)), five of them now.
- **Open:** a dashboard example with a screenshot ([#32](../../../discussions/32)).
- **Open:** a listening-quality overview recipe with `history_stats`: how much you listen in Hi-Res, lossless or lossy, and per streaming service ([#37](../../../discussions/37)).
- **Open:** a short section, *Triggers: which entity and attribute to use* ([#28](../../../discussions/28)), which will be part of a reference page. It replaces the idea of device triggers and conditions: Home Assistant no longer accepts new device automations and points to entity triggers, and our states and attributes are already available as such, so nothing is built for it. The one case a plain state change cannot cover, a new track with all its details, is handled by the now-playing event (built in 0.7).

## After 1.0: Home Assistant core

- A new core integration normally starts with one platform per pull request, so the media player would go first and the sensors, number, select and binary sensor follow.
- Core uses its own translation process: the English `strings.json` goes in, other languages come through Home Assistant's translation tool, so the separate language files of this repository do not move along as they are.
- Documentation lives on home-assistant.io, not in the README.
- All of this is checked against the then-current developer documentation before a pull request is opened.

## Open questions before core

These are questions, not decisions. They decide where 0.9 and 1.0 aim, so they are researched first and answered with the Home Assistant developers before any core work starts.

1. **Core already has a `hegel` integration** for the IP-control models (H95, H120, H190, H190V, H390, H590 and Röst, TCP port 50001, push updates): see its [documentation](https://www.home-assistant.io/integrations/hegel/). Hegel Connect is for the streaming platform (H150, H200, H400, H600), which talks through a web API instead. Would core accept a second, separate Hegel integration, or ask for one integration with two protocols? This decides the domain name, the library name and whether 0.9 to 1.0 are aimed right. **Found so far:** nothing that answers it. A community thread reports that the built-in integration does not work with an H200 ([thread](https://community.home-assistant.io/t/hegel-h200-integration-not-workign/1024645), user-reported), which fits two different protocols. General threads treat several integrations for one device as normal ([thread](https://community.home-assistant.io/t/integrating-different-protocol-devices-in-ha/682902)), and the architecture repository has a discussion about overlap between brands ([discussion 734](https://github.com/home-assistant/architecture/discussions/734)). The precedents to look at (`yamaha` and `yamaha_musiccast`, `denon` and `denonavr`, `heos`) were not found documented with a reason in the searches so far. **Next step:** read those integrations' pages and history, and ask in the architecture discussions.
2. **A core pull request needs the library on PyPI and one platform first.** The [contributing guide](https://developers.home-assistant.io/docs/core/integration/contributing_to_core) asks for the communication logic in an external library and for new integrations to be small, with a single platform; the quality scale rule *dependency transparency* (see `quality_scale.yaml`) is about the library's own repository and releases. Is `api.py` (810 lines, including browse and radio) split so that a media-player-only first pull request is possible? **Today:** no. The client mixes power, volume, playback, browse, favorites and settings (auto standby). **Next step:** decide the split while moving `api.py` into its own package in 0.9, so the library already has a small core and the optional parts can follow in later releases.

## Help wanted

- **Model reports** for the H400 and H600 (the H200 was confirmed in [#17](../../../issues/17)), also when everything works: [send one](../../../issues/new?template=model_report.yml). Confirmed models are added to the supported-models table.
- Translations and bug reports: see [CONTRIBUTING.md](../CONTRIBUTING.md).
