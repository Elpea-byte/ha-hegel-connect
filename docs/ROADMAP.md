[← README](../README.md) · [Reference](REFERENCE.md) · [All pages](README.md)

# Roadmap to 1.0

**Plans, not promises.** This is the direction, in the order the maintainer intends to work. Dates are not given, the order can change, and an item can be dropped. Ideas and requests are welcome in [Discussions](../../../discussions/categories/ideas); what is planned per version is in the table and the lists below (there are no GitHub milestones yet).

## What 1.0 means

Version 1.0 is the point where Hegel Connect is stable and finished enough that it could be submitted to Home Assistant core as it is: entities, attributes and actions stay as they are (semantic versioning), the documentation is complete, the tests are thorough and the amplifier library is published on its own. Getting into core is a separate step after 1.0, with its own review. It is the goal that sets the quality bar, not something that is promised.

The Home Assistant [integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) is the checklist. [`quality_scale.yaml`](../custom_components/hegel_connect/quality_scale.yaml) keeps an honest list of what is done and what is still open.

## Pace

There is no fixed schedule. The plan follows what is actually done:

- A release comes when all its items are done and tested, on average every two to three weeks (0.5.0 to 0.6.0 took 18 days, 0.6.0 to 0.7.0 took 20); a bug that needs a fix can get its own release.
- A version is used on the maintainer's own amplifier for at least a week before it is released.
- Features are bundled: a version comes out when all its items are done and tested, not one by one.
- A breaking change is announced in the release notes one version ahead.
- Every release has something in it that users will notice and enjoy, listed in the table and lists below.

## How work is done

- **Every feature ships with its own tests.** A feature in 0.6 or 0.7 is not finished until its tests are in, written against the fake amplifier that replays a real recording. Version 0.8 is not for catching up on missing tests; it only lifts the overall coverage to 95% or more.
- **Documentation is separate from the versions.** README sections, examples and blueprints can be merged at any time as documentation-only changes, without a release.
- **Breaking changes** are called out as such in the release notes, with what to do about them.

## Versions

| Version | Status | Theme | Done when |
| :---- | :---- | :---- | :---- |
| **0.6** | Released (2026-11-07) | Daily use | Done: see the [release](https://github.com/Elpea-byte/ha-hegel-connect/releases/tag/v0.6.0) and the [changelog](../CHANGELOG.md) |
| **0.7** | Released (2026-11-26) | Features | Done: see the [release](https://github.com/Elpea-byte/ha-hegel-connect/releases/tag/v0.7.0) and the [changelog](../CHANGELOG.md) |
| **0.8** | Planned | Core behaviour and coverage | The CI fails under 95% coverage; the `test-coverage` rule is done; *unavailable* works as announced |
| **0.9** | Planned | Own library and quality | The library is on PyPI and used by the integration; no `todo` left in `quality_scale.yaml` |
| **1.0** | Planned | Stable | Every `quality_scale.yaml` rule done or exempt; coverage 95% or more; [REFERENCE.md](REFERENCE.md) frozen; every "not tested yet" in the [streaming services table](streaming-services.md) tested on an H150 or removed from the claims; no open bug report for six weeks |

### What is in each version

**0.6** (released): optional volume per input and remember volume ([#29](../../../discussions/29)), reconnect on `update_entity` ([#34](../../../discussions/34)), *play* after radio ([#30](../../../discussions/30)), four blueprints ([#31](../../../discussions/31)), fixes.

**0.7** (released), a listening log, an idle timer and finding stations by name:

- **Built:** the now-playing event for listening logs and notifications ([#36](../../../discussions/36)), with a fifth blueprint for it.
- **Built:** Spotify track, album, artist and playlist URIs in the event, and the track URI as `media_content_id`, so an automation can start exactly that track again; tried with SpotifyPlus on an H150; the album and artist URIs were seen in the event when playing from an artist and from an album.
- **Built:** a recipe for putting the amplifier back after an announcement ([#33](../../../discussions/33)); the scene steps were tried on an H150.
- **Built:** the amplifier's own auto-standby as an optional select ([#42](../../../discussions/42)).
- **Built:** a text after setup that asks for a model report for models the maintainer has not tested, and setup that takes a pasted browser address.
- **Built:** hardening of the JSON reading, and the README and `docs/` restructure with [REFERENCE.md](REFERENCE.md).
- **Built:** searching internet radio ([#27](../../../discussions/27)): the action `media_player.search_media` finds stations on the amplifier (Home Assistant's own media browser has no search box yet) (the amplifier has a search form for it: fill in a text, activate, read the result list), and a found station starts like a favorite. Matching favorites come first, so Assist's "play <station> on <amplifier>" (which plays the first search result) starts the favorite; the intent was checked in Home Assistant's source and with a test, not yet by voice. Tried on an H150: searches, no result, several at once, and starting a found station. Open smaller points: only the first page (up to 17) is returned, two stations with the same name (NL and BE) look alike, and the logos load over `http://`.
- **Built:** the auto-standby select is re-read when the connection returns and every 15 minutes, because the amplifier does not report a change of the setting.
- **Built:** a round of review points before the release: receiver device class, `media_channel` and `media_content_type`, pictures over `http://` fetched by Home Assistant, some attributes left out of the recorder, limits that follow the volume range, a start volume entity for hidden inputs too, tasks tied to the config entry, offline-safe diagnostics and fixed-volume sensor, `image_url` in the now-playing event, and more robust blueprints. Tried on an H150 (receiver class, channel and station, picture through Home Assistant, recorder, start volume entities, diagnostics, the event filters and the Qmusic order). Seen again on the final code after a restart, with Qmusic. When the audio power strip switched off at night, the integration logged one warning (*Lost connection*) and was connected again the next morning without a restart. Not seen: how the entities look while the amplifier is gone, https from outside the house, a local https picture, and the version words in a title.

**0.8** (planned), core behaviour and coverage:

- **Built:** entities become *unavailable* when the amplifier cannot be reached at all (network standby stays *off*, the network sensor tells them apart); a **breaking change**, listed as one in the changelog. Checked with automated tests; still to be tried on an H150 (a night with the power strip off).
- **Open:** a repair issue when the amplifier has been unreachable for a long time or its model is not supported (both `exempt` in `quality_scale.yaml` today).
- **Built:** saving the options without `hidden_sources` keeps the hidden inputs instead of showing them again (automated tests).
- **Open:** the *Maximum volume* number recognisable for the blueprint picker, which can only filter on device class or unit (the start volume numbers have neither); this changes an entity, so it is weighed against the dashboards that rely on it and listed as breaking if it is.
- **Open (research):** announcements over DLNA: the amplifier announces itself as a UPnP media renderer, so the built-in DLNA Digital Media Renderer integration may play text-to-speech on it. Tried on an H150: the integration plays a text-to-speech link for a few seconds, the input stays Network and the volume stays, but the radio that played before does not come back, so the scene recipe is still needed (now in [announcements](announcements.md)). Whether the message was audible was not checked. Open: a `play_media` for links in Hegel Connect that restores what played, only if that proves worth it.
- **Open (research):** more amplifier settings as optional entities: a read-only list of the settings (602 rows on an H150) was read. Candidates, to be discussed: the start volume after power-on (mode keep, fixed or limit, with a value), the volume in dB (the amplifier has a table of 101 steps from -120 to 0 dB), and the display brightness. Nothing is built before the discussion.
- **Open:** two blueprints: *switch on from the mains* (plug on, wait for the network sensor, amplifier on, optional input and volume up to the maximum) and *sleep timer* (lower the volume in steps, then standby, restore the volume).
- **Open:** searching podcasts ([#27](../../../discussions/27)), the user feature of this version: it works the same way on the amplifier (the result is a podcast, which opens to its episodes; an episode is a track that starts like a radio item, not tried yet).
- **Open:** larger cover art where the streaming service offers it, only if that can be done reliably.
- **Open (metadata and parsing, from a review; each point checked against the recording and the code):**
  - *The event waits briefly for the stream quality.* In the recording the first `playing` update of a track has no sample rate and the next one has it (events 42 and 43), and the event fires at the first one for anything that is not internet radio, so codec, sample rate and quality can be empty in the event. Plan: if a track has a title but no quality yet, wait about 1.5 seconds for the update that has it, then fire once with what is known (Spotify never reports a codec, so it fires at once; a skip within the wait fires only the new track). To be seen first with a media server and TIDAL or Qobuz on an H150; the recording shows the gap, not yet the effect in the event.
  - *More in the event:* `duration` (known to the media player already) and, only if the amplifier reports it, `channels` (the field is not in the recording yet); the same two as variables in the blueprint. Radio titles that differ only in capitals (`Toto - Pamela` and `TOTO - PAMELA`) count as one track.
  - *One place for the radio and metadata rules*, free of Home Assistant imports so it moves with the library in 0.9: the splitting of `Artist - Title` (also with an en or em dash, and without a station name at the end such as `... | Qmusic`), the Qmusic order rule and the version words, and the filters for what is no song (whole titles only: the station's own slogan, which is in the recording, `reclame`, `nieuws`, `weer`, `verkeer`, `jingle`, `promo`, bare web addresses, and jingles of stations with a short name such as `538 - Nieuws`). The media player's `media_title` and `media_artist` use the same rule (the point above).
  - *A station name is no artist* (from a second review): some stations send only the station and a programme name. Today the event already skips a title equal to the station and a title that starts with the station name (names of 5 or more characters). Not covered: `artist` equal to the station with the programme in `title`, and a short station name (`NPO 2 - Nieuws`). Plan: skip the event then (the station is not a song); not seen on an H150 yet, so built only with a recording of it. Also in the event: `playback_source` (the album or playlist name the service reports; the media player has it already).
  - *Listening time, research only:* an optional second event, `track_finished`, with the seconds listened and the duration, fired on a track change, pause, stop, input change or standby (for Last.fm and ListenBrainz and for skip detection). To be checked first whether position and play time are reliable enough; nothing is built before that.
  - *Other inputs and Spotify Connect, research only:* read real `getData` answers to see whether Coax, Optical or USB report a sample rate, bit depth or codec anywhere, and whether Spotify Connect has more quality or bitrate fields in `activeResource` than `spotifyHifi`.
  - *Cleaning of texts* (HTML entities such as `&amp;`, doubled spaces, placeholder values such as `unknown` or `n/a`): only built after such a text has been seen coming from the amplifier; today nothing in the recording shows it.
  - *The player data:* `serviceID` (more stable than the service name) and the slogan as fields; a cover picture from the other keys a media server uses (`albumArtUri`) once a recording from a NAS shows them; `nominalBitRate` as a second source for the bitrate; more codec names in the lossy and lossless lists, a sample rate shown also without bit depth, and DSD shown as DSD64, DSD128 and so on.
  - *Not planned:* guessing the unit of a bitrate (kbit/s against bit/s) and calling `audio/mp4` lossy from the bitrate. Both are guesses, and the rule of this project is to show only what the amplifier reports. Reconsidered if a recording shows the need.
- **Open:** overall test coverage to 95% or more, with the CI floor raised to match, and `pip-audit` in the CI. The tests for the client should cover timeouts, the size limit, broken JSON, HTTP errors, a lost queue, IPv6 and the search form.
- **Open:** two buttons: *Reconnect* (diagnostic, calls the reconnect that `homeassistant.update_entity` triggers today) and *Refresh radio favorites* (config, so a new favorite shows up without waiting for the six-hour timer). Disabled by default is not needed for a button nobody presses by accident, but it is decided with the entity rules.
- **Built:** *play* after *stop* also resumes a station that was found by search or browsing, not only a favorite: the path is bound to the station once it plays (automated tests).
- **Open:** the saved copy of the inputs, volume range and firmware moves from the config entry to Home Assistant's `Store`, with a one-time migration; and after a start without the amplifier that data is read again when it comes back (today the saved copy stays until the next restart).
- **Open:** the media player's `media_title` for internet radio stays the raw text (`Run - SNOW PATROL`) without `media_artist`, while the now-playing event splits it. Split it there too, so cards show artist and title; a visible change for dashboards, so weighed first and noted in the release notes.
- **Open:** reading the independent values at start and reconnect in parallel (`asyncio.gather`), if the amplifier copes with it; to be tried on an H150 first.
- **Open:** switching input waits for the amplifier's own confirmation instead of a fixed pause, and a failed switch (the input did not stick after three tries) becomes an error instead of a log line. Both need the power-on case on a real amplifier: it jumps back to Network within a second there, which is why the pause is there.
- **Built:** the start volume entities show a renamed input's new name: renaming reloads the integration once (automated tests). **Not planned:** a clash between an input and the field *hidden inputs*; the input names come from the amplifier (XLR, RCA, ...), none is called like that.
- **Open (research):** whether the queue can be cancelled on unload instead of just dropped.
- **Open (from a look at other integrations, each point to be tried on an H150 first):**
  - *Fast volume changes:* a slider or knob that goes from 20 to 45 can queue many `setData` calls one behind the other (`PARALLEL_UPDATES = 1` on the media player). Plan: while a volume call is on its way, keep only the last requested value and send that next, so the volume does not lag behind. First measure how many calls a dashboard slider and a knob really send; it may be less of a problem than it sounds.
  - *Empty lists after a start:* **built for the radio favorites** (read again after 45 seconds, up to three times, the last good list kept; automated tests); open for the auto-standby choices. If the radio favorites or the auto-standby choices fail while the amplifier is still starting (it answers before its cloud part is ready), read them again after 30 to 60 seconds, without a reload, and keep the last good list when a later read fails. Goes together with the saved-copy point above.
  - *A push connection that went quiet:* the long poll can answer with an empty list while the subscription is gone, so `connected` stays true and the states freeze. Research first whether this happens on an H150 at all (a router change, a firmware hiccup); if it does, a command that changes a value but is not followed by a push event within a few seconds forces one fresh read and a new subscription.
  - *The play queue ("up next"), research only:* check with the browser's developer tools on `/webclient/` whether `playlists:pq/getitems` returns the coming tracks during a NAS, USB, Qobuz or TIDAL playlist. If it does, an attribute or an action follows later (0.9 or after).
- **Open:** four blueprints that people will use: *TV or HT bypass follows the TV* (amplifier on and to the TV input when the TV starts; back to standby only if it is still on that input), *announcement with restore* (the recipe in [announcements](announcements.md) as a script blueprint, with a wait instead of a fixed pause), plus the two above (*switch on from the mains*, *sleep timer*).

**0.9** (planned), own library and quality:

- **Open:** `api.py` becomes a separate Python package in its own repository, published on PyPI from GitHub Actions (trusted publishing), with its own tests; the integration requires it in `manifest.json`. The split is decided with the open questions below.
- **Open:** every rule in `quality_scale.yaml` is done or exempt.
- **Open:** typed models in the library instead of the raw player dictionary, and a small core (power, volume, input, push) with browse, search and settings as extensions, so a first core pull request with only the media player stays small.
- **Open:** in the library, a small catalogue of settings (path, value type, check) with one generic read and one generic write, so each new `settings:/` entity is a line instead of new code, and the push loop with its reconnect and a `watch()` or callback interface inside the library, so `coordinator.py` stays thin. Both are part of the split above.
- **Open (research):** the amplifier's MAC address as a device connection, if the web API gives it; checked first against how it works together with Google Cast and DLNA entries of the same device.
- **Open:** a configurable volume step (1, 2 or 5 percent per press) in the options.
- **Open:** three more blueprints: *rotary knob or buttons* (turn = volume, click = play/pause, double click = next, long press = standby or input), *plug off after standby* (switch the plug off safely after a time in standby, within a time window) and *turntable or CD player on power* (switch to the analog input when a plug measures power).

**1.0** (planned): entities, attributes and actions frozen, documentation final, release notes say what is stable.

1.0 does not wait for other people. It was tested on an H150 and confirmed by a user on an H200. The other models are listed in the supported-models table as soon as someone confirms them, and until then they stay "expected to work".

**What "supported" means at 1.0:** for the H150 and the H200, what the README and REFERENCE.md say is tested or confirmed. For the H400 and H600 it means *expected to behave like the H150* (Hegel groups them for home automation), nothing more: a bug found there is fixed from a report with the diagnostics file, but nothing is guaranteed. The table says *tested*, *confirmed* or *expected* per model, and that is not changed without a report.

**Getting reports for the H400 and H600:** a post on the Home Assistant forum asking for them, the [model report](https://github.com/Elpea-byte/ha-hegel-connect/issues/new?template=model_report.yml) link at the top of the README (it is there), and a link to it in the text after a successful setup (built for 0.7: other models than the H150 get it there).

**Considered and not planned for now:** hiding volume or play and pause from the media player's features when the volume is fixed or another input is on. Today the call is refused with a message that says why (and `can_pause`, `fixed_volume` explain it), which is more useful than a missing button; features that come and go with the state also make cards flicker. Reconsidered if a reviewer asks for it.

## Documentation track (no release needed)

Merged as documentation-only changes whenever they are ready, independent of the versions above:

- **Done:** ready-made blueprints with import buttons ([#31](../../../discussions/31)), five of them now.
- **Done:** the README is shorter and follows a new user's order, with long sections in `docs/`, and [REFERENCE.md](REFERENCE.md) lists states, entities, attributes and errors, checked by a test.
- **Open:** a test plan per service on the H150, so the "not tested yet" cells in the [streaming services table](streaming-services.md) get tested or removed: TIDAL and Qobuz Connect, AirPlay, Google Cast, a USB stick, and a media server (NAS) for the now-playing event.
- **Open:** a dashboard example with a screenshot ([#32](../../../discussions/32)): plain tile cards, a radio favorites grid with logos and the audio-quality badge.
- **Open:** a short guide for Music Assistant: power, input and volume through Hegel Connect, the music over AirPlay, Cast or DLNA. Not tried on an H150 yet, so it is written as a plan until it is.
- **Open:** a listening-quality overview recipe with `history_stats`: how much you listen in Hi-Res, lossless or lossy, and per streaming service ([#37](../../../discussions/37)).
- **Done:** *Which entity or attribute to use in a trigger* ([#28](../../../discussions/28)), in [REFERENCE.md](REFERENCE.md). It replaces the idea of device triggers and conditions: Home Assistant no longer accepts new device automations and points to entity triggers, and our states and attributes are already available as such, so nothing is built for it. The one case a plain state change cannot cover, a new track with all its details, is handled by the now-playing event (built in 0.7).

## After 1.0: Home Assistant core

- A new core integration normally starts with one platform per pull request, so the media player would go first and the sensors, number, select and binary sensor follow.
- Core uses its own translation process: the English `strings.json` goes in, other languages come through Home Assistant's translation tool, so the separate language files of this repository do not move along as they are.
- Documentation lives on home-assistant.io, not in the README.
- All of this is checked against the then-current developer documentation before a pull request is opened.

## Open questions before core

These are questions, not decisions. They decide where 0.9 and 1.0 aim, so they are researched first and answered with the Home Assistant developers before any core work starts.

1. **Core already has a `hegel` integration** for the IP-control models (H95, H120, H190, H190V, H390, H590 and Röst, TCP port 50001, push updates): see its [documentation](https://www.home-assistant.io/integrations/hegel/). Hegel Connect is for the streaming platform (H150, H200, H400, H600), which talks through a web API instead. Would core accept a second, separate Hegel integration, or ask for one integration with two protocols? This decides the domain name, the library name and whether 0.9 to 1.0 are aimed right. **Found (read on 2026-11-17), each marked as fact or interpretation:**

- *Fact:* core groups several integrations under one brand in `homeassistant/brands/*.json`: [`yamaha.json`](https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/brands/yamaha.json) lists `yamaha` and `yamaha_musiccast`; [`denon.json`](https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/brands/denon.json) lists `denon`, `denonavr`, `denon_rs232` and `heos`; [`lg.json`](https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/brands/lg.json) lists `lg_infrared`, `lg_netcast`, `lg_soundbar`, `lg_thinq`, `lg_tv_rs232` and `webostv`. There is no `hegel.json` ([404](https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/brands/hegel.json)): the core `hegel` integration stands alone.
- *Fact:* `heos` has its own domain and its own code owner, separate from `denonavr` ([HEOS documentation](https://home-assistant.io/integrations/heos)); users run both ([forum thread](https://community.home-assistant.io/t/denon-vs-heos-integrations/531245)).
- *Fact:* a community thread reports that the built-in `hegel` integration does not work with an H200 ([thread](https://community.home-assistant.io/t/hegel-h200-integration-not-workign/1024645), user-reported), which fits two different protocols.
- *Fact:* the developer documentation on [brands](https://developers.home-assistant.io/docs/creating_integration_brand) says brand images live in the brands repository, one folder per integration domain; it does not say how a second integration of a brand is judged.
- *Interpretation:* because core already keeps several integrations of one brand side by side when the products or protocols differ (Yamaha, Denon, LG), a second, separate Hegel integration for the streaming platform looks plausible, under the same brand file as `hegel`. This is not confirmed by anything a reviewer wrote.
- *Not found:* the pull requests that added `yamaha_musiccast`, `denonavr` and `webostv`, and what reviewers said about a separate domain. The searches only turned up [core pull request 9258](https://github.com/home-assistant/core/pull/9258) (the MusicCast work, where a contributor noted that a part of it would better be a separate pull request) and [home-assistant.io pull request 3295](https://github.com/home-assistant/home-assistant.io/pull/3295) (its documentation), not a discussion of domains. The history of `homeassistant/components/yamaha_musiccast`, `denonavr` and `webostv` on GitHub is the next thing to read.
- *Interpretation:* the domain name matters more than it looks. `hegel_connect` is a custom domain; a core domain would be chosen with the reviewers, and the library would need a name that does not clash with the other Hegel integrations (for example the community `hegel_streaming`).

**Question to ask (drafted, not posted):**

> Hi! I maintain Hegel Connect, a custom integration (domain `hegel_connect`) for Hegel's streaming amplifiers (H150, H200, H400, H600). It talks to the amplifier's local web API with a push event queue; the library has no Home Assistant imports and is meant to go to PyPI. Core already has a `hegel` integration, but it is for the older IP-control models (H95, H120, H190, H190V, H390, H590 and Röst) and uses a different protocol (TCP 50001); the streaming models do not answer it. I see that core keeps several integrations of one brand side by side in `homeassistant/brands` (for example `yamaha` with `yamaha_musiccast`, and `denon` with `denonavr` and `heos`). Before I spend time on a core submission: would you accept a second, separate integration for the Hegel streaming platform next to `hegel`, listed under the same brand, or would you rather have one `hegel` integration with two protocols? And is there a naming rule for the domain and the library that I should follow?

2. **A core pull request needs the library on PyPI and one platform first.** The [contributing guide](https://developers.home-assistant.io/docs/core/integration/contributing_to_core) asks for the communication logic in an external library and for new integrations to be small, with a single platform; the quality scale rule *dependency transparency* (see `quality_scale.yaml`) is about the library's own repository and releases. Is `api.py` (810 lines, including browse and radio) split so that a media-player-only first pull request is possible? **Today:** no. The client mixes power, volume, playback, browse, favorites and settings (auto standby). **Next step:** decide the split while moving `api.py` into its own package in 0.9, so the library already has a small core and the optional parts can follow in later releases.

## Help wanted

- **Model reports** for the H400 and H600 (the H200 was confirmed in [#17](../../../issues/17)), also when everything works: [send one](../../../issues/new?template=model_report.yml). Confirmed models are added to the supported-models table.
- Translations and bug reports: see [CONTRIBUTING.md](../CONTRIBUTING.md).
