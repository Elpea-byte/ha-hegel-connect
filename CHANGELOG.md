# Changelog

All notable changes are listed here. Versions follow [semantic versioning](https://semver.org/).

## [Unreleased]

Changes on the `dev` branch that are not in a release yet.

### Added
- Seeking within a track (media player `media_seek`), where the amplifier allows it: tracks from a media server or USB. Not for Spotify Connect or radio, like the Hegel web client.

## [0.3.3] - 2026-10-07

### Fixed
- Icon: no tile behind the knob any more, so it no longer shows as a white square in the integrations list on dark themes; light and dark variants now match other integrations.

## [0.3.2] - 2026-10-07

### Changed
- New icon in a calm black, white and grey style, with a variant for dark themes.
- Shorter, calmer texts when adding the amplifier (all six languages).

### Added
- Media player: `media_playlist` shows what the track plays from (a playlist or album), when the service reports it.

## [0.3.1] - 2026-10-07

### Changed
- Codec, sample rate, bit depth and bitrate sensors are on by default again: owners of a hi-fi amplifier want to see them. This reverts the change in 0.3.0.
- Sample rate, bit depth and bitrate no longer keep long-term statistics (an average sample rate means nothing). Their history is kept as before. Home Assistant may offer to delete the old statistics under *Developer tools > Statistics*; that is safe.

## [0.3.0] - 2026-10-07

### Fixed
- A manually entered IPv6 address now works: it is put in square brackets in URLs (it may also be typed as `[address]`). Discovery still uses IPv4 only.

### Changed
- Dependabot opens its pull requests against `dev`.
- Codec, sample rate, bit depth and bitrate sensors are disabled by default on new installs (enable them on the device page). Existing installs keep their current setting. Audio quality and streaming service stay on.

### Added
- Issue template for feature requests.
- `quality_scale.yaml`: honest self-assessment against Home Assistant's integration quality scale.
- CI: strict type check (mypy), coverage report with a floor, and 100% coverage required for the config flow.
- README: how to remove the integration, and a note on the built-in Hegel integration's discovery.
- README: "At a glance" summary and a plain-language disclaimer.
- `AGENTS.md` with checks and rules for AI coding agents.

## [0.2.1] - 2026-10-06

### Fixed
- Options: after an error (duplicate name) the form keeps what you typed instead of showing the stored values again.
- Options: a stored hidden input that the amplifier no longer has no longer breaks the form.
- Wrong input from the user (unknown input, fixed volume, item that cannot be played) is now reported as a service validation error instead of a general error.

### Tests
- The back-off test patches only the coordinator's own wait, not `asyncio.sleep` everywhere.
- Options keep typed input after an error and skip stale hidden inputs; an unknown input is a user error.

## [0.2.0] - 2026-10-06

### Added
- Options: hide inputs you do not use and give inputs your own name (shown in the source list and on dashboards; the amplifier's own names keep working in automations). Changes apply at once, without a reload.
- Attribute `input_names` (shown name -> amplifier name), so custom cards can keep icons for renamed inputs.

### Tests
- The back-off test now drives the listener itself with a failing poll and checks the waits (5, 10, 20, 40, 60 s); without back-off it fails.
- Options: hiding and renaming inputs, and refusing duplicate names.

## [0.1.2] - 2026-10-06

### Fixed
- Back-off when the event queue keeps failing now really works: the counter is only reset after a poll that succeeded.
- Play: the Spotify resume is only tried when the streaming service is unknown, not for other services.

### Documentation
- Known limitations (input named "Network", unauthenticated local API); CONTRIBUTING mentions `ruff format`.

## [0.1.1] - 2026-10-06

### Fixed
- Discovery: a new address announced over mDNS is only used after the device at that address confirms it is the same amplifier.
- The push listener can no longer stop on an unexpected answer; it logs it and reconnects. Backs off when the event queue keeps getting lost.
- Manual setup and reconfigure check the model and the amplifier's id (reconfigure refuses a different amplifier); no more IP address as fallback id.
- Radio favorites are also refreshed after starting while the amplifier was off at the mains.
- No double reload after reconfigure; `max_volume` attribute follows the number entity right away.
- Diagnostics also hide stream and artwork URLs (they can point to a NAS on your network).

### Added
- Error messages in all six languages; H200 in the Google Cast discovery.

## [0.1.0] - 2026-10-06

First release. Tested on the H150; H200, H400 and H600 are expected to work.

### Added
- Local push control: power, volume (with a maximum), mute, inputs, play/pause, next/previous and stop where the streaming service allows it.
- Now playing with artwork, track position and streaming format sensors (quality, codec, sample rate, bit depth, bitrate, service).
- Spotify Connect: play resumes the session instead of breaking it.
- Media browser: radio favorites, internet radio, media servers (UPnP/DLNA), USB stick and recently played. Albums play as a whole, like in the Hegel web client.
- Radio favorites sensor, network sensor and fixed-volume (home theater bypass) sensor.
- Automatic discovery, the same way the Hegel Control app finds the amplifier; older Hegel models are recognised during setup and pointed to the built-in integration.
- Diagnostics without IP address or device ids.
- English, Dutch, Norwegian (Bokmål), German, French and Spanish.

[Unreleased]: ../../compare/v0.3.3...dev
[0.3.3]: ../../compare/v0.3.2...v0.3.3
[0.3.2]: ../../compare/v0.3.1...v0.3.2
[0.3.1]: ../../compare/v0.3.0...v0.3.1
[0.3.0]: ../../compare/v0.2.1...v0.3.0
[0.2.1]: ../../compare/v0.2.0...v0.2.1
[0.2.0]: ../../compare/v0.1.2...v0.2.0
[0.1.2]: ../../compare/v0.1.1...v0.1.2
[0.1.1]: ../../compare/v0.1.0...v0.1.1
[0.1.0]: ../../releases/tag/v0.1.0
