# Changelog

All notable changes are listed here. Versions follow [semantic versioning](https://semver.org/).

## [Unreleased]

### Added
- H200 listed as supported model (expected to work, not tested yet).
- Norwegian (Bokmål), German, French and Spanish translations.
- Radio favorites sensor; favorites play the same way as in the Hegel web client.
- Streaming format sensors (quality, codec, sample rate, bit depth, bitrate, service), track position, network sensor, maximum volume.
- Discovery via `_sues800device._tcp` (like the Hegel Control app), SSDP and Google Cast; older Hegel models are recognised during setup.

### Fixed
- Spotify Connect: play resumes the session instead of breaking it; next/previous only shown when the service allows it.
