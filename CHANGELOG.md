# Changelog

All notable changes are listed here. Versions follow [semantic versioning](https://semver.org/).

## [Unreleased]

Changes on the `dev` branch that are not in a release yet.

## [0.7.0] - 2026-11-26

Requires Home Assistant 2025.4 or newer (searching needs a newer one; older versions just do not offer it). Nothing needs to be done after updating: the new entities (the now-playing event, auto standby, the extra start volumes) are disabled until you enable them. Two small things you can notice are listed under *Changed*: the media type of the media player and the attributes that are no longer in the history. Version 0.8 will make the entities *unavailable* when the amplifier cannot be reached (announced under *Changed*).

### Added
- Now-playing event ([#36](https://github.com/Elpea-byte/ha-hegel-connect/discussions/36)): `event.<name>_now_playing` fires `track_changed` when a new track starts, with title, artist, album, service, input, audio quality, codec, sample rate, bit depth, bitrate and `is_radio`. Pause, resume and a repeating track do not fire it, and a track already playing at startup is not announced. Internet radio waits for the song (the station name alone is not a track) and splits `Artist - Title` into artist and title, with the station in `station`. Disabled until you enable it, because every track is stored in the Home Assistant database; nothing existing changes. Tried on an H150 with Spotify and internet radio; not with a media server.

- Auto standby ([#42](https://github.com/Elpea-byte/ha-hegel-connect/discussions/42)): `select.<name>_auto_standby` shows and changes the amplifier's own idle timer (off, or 5, 10 or 20 minutes without activity; the choices come from the amplifier). Disabled until you enable it, so nothing changes for existing setups. Tried on an H150: with 5 minutes it went to standby by itself after exactly 5 minutes idle on the network input, not while music played. Not tried: how it works together with the standby timer in the amplifier's own menu, pause, a power cut, and other models.

- A fifth blueprint, *Log or announce what is playing*, for the now-playing event: it writes each new track to the logbook and runs an action of your own (for example a notification) if you choose one. Optional filters on audio quality and on internet radio. Nothing is sent unless you choose an action. Valid as a blueprint and as an automation in the tests; its trigger and filters are run in a test as well. Not yet tried on Home Assistant with a real amplifier.
- Spotify tracks can be started again: while Spotify plays, the media player's `media_content_id` is the track URI (`spotify:track:...`), and the now-playing event has `spotify_uri`, `spotify_album_uri`, `spotify_artist_uri` and `spotify_playlist_uri` (the playlist it plays from, if any; null for other services). The track URI is also what tells two tracks with the same title apart for the event. Radio is unchanged (`media_id`). Tried on an H150 playing Spotify, including starting the same track and the playlist again with SpotifyPlus 1.0.225. Played from an artist and from an album on the same amplifier: the event carried the album and artist URIs (the album URI changed with the album), and `spotify_playlist_uri` stayed empty because neither is a playlist; the media player's `media_playlist` then shows the name of the artist's *Popular* list or of the album. Starting the album or artist URI again was not tried. Other services (TIDAL, Qobuz, AirPlay, UPnP) were not looked at on a real amplifier, nothing was built for them.

### Added (search)
- Search internet radio from the media browser ([#27](https://github.com/Elpea-byte/ha-hegel-connect/discussions/27)): the action `media_player.search_media` finds stations on the amplifier (up to 17 per search), and a found station starts like a favorite. Home Assistant 2026.11's own media browser has no search box yet, so it is used by cards, scripts and Assist; versions of Home Assistant without the action just do not offer it. Tried on an H150: searches, a search with no result, several at once, and starting a found station. Podcasts are planned for 0.8.
- Search puts matching radio favorites first, then all radio. Home Assistant's Assist ("play Qmusic on the amplifier", intent `HassMediaSearchAndPlay`) searches with `media_player.search_media` and plays the first result, so a spoken name now starts the favorite. Tried on an H150 with Assist (text): "play Radio 10 on the Hegel H150" started the favorite. Assist needs the name or an alias of the entity: "the Hegel" was not found for the entity *Hegel H150*.
- The amplifier keeps every search form until it loses power, so a search now reuses its form instead of making a new one each time. Tried on an H150: seven searches made one form, and after the amplifier lost power the next search worked again with a new form.
- The media browser no longer shows the *Search* folder of the radio section (it opened an empty page); seen on an H150.
- The now-playing event ignores what is not a song: the titles `commercial-in`, `commercial-out` and `Ad break` that some stations send around their commercials, station jingles that start with the station name (such as `Qmusic nieuws`), and an announcement played through the DLNA renderer (`Home Assistant` or `UPnP Renderer` on *Media Servers*). Seen on an H150 on Qmusic (`commercial-in`, `-out`, `Ad break` and `Qmusic nieuws` gave no event, in 25 minutes) and on Radio 10; the DLNA title is covered by tests only.
- Internet radio titles: Qmusic sends `Title - ARTIST` where most stations send `Artist - Title`. When only the second part is in capitals the event takes it as the artist, so `Take Me Back - KYGO & MAX MCNOWN` gives artist KYGO & MAX MCNOWN. Seen on an H150: four Qmusic songs and five Radio 10 songs came out in the right order (the order was wrong before); other stations unchanged. A title ending in `LIVE`, `REMIX` or `EDIT` is covered by tests only.

### Changed
- **Announcement for 0.8 (breaking):** when the amplifier cannot be reached at all (switched off at the mains, network down), its entities will become *unavailable* instead of showing *off*. Standby stays *off*, and the *Network* binary sensor keeps telling the two apart. Automations that test for `off` should also look at `unavailable`; the blueprints already do (see below).
- The media player is now a receiver (`device_class: receiver`) and reports `media_content_type: channel` and `media_channel` (the station) while internet radio plays, `music` for other network streams, and nothing on other inputs. Before it always said `music`. Seen on an H150 with Qmusic and Radio 10 (`channel` and the station while playing, `music` after stop, nothing in standby).
- Pictures that come over plain `http://` (radio logos, a NAS) are now fetched by Home Assistant instead of by the browser, so they also show on an https page (Nabu Casa, your own certificate) and outside the house. Only `https://` pictures on a public address still go straight to the browser (not https on a local address or name). Seen on an H150 with the radio logos: the picture comes through Home Assistant (200, PNG). Not tried over https from outside the house, and the local-address rule is covered by tests only.
- Attributes that only repeat or rarely change (`input_names`, `fixed_volume`, `max_volume`, `can_pause`, `volume_raw`) are no longer stored in the Home Assistant database. They are still on the entity; only their history is gone. Seen on an H150: the rows from before the restart have them, the rows after it do not.
- The *Maximum volume* number and the start volumes follow the volume range of the amplifier instead of a fixed 100; a saved or default 100 is shown as the top of the range, not above it (seen on an H150: top 100, value 70; a range below 100 is covered by tests only, no model with one is known). There is now a start volume entity for every input, also the hidden ones (all disabled until you enable them), so unhiding an input later finds it. Seen on an H150: nine entities for nine inputs, five of them hidden ones.
- The *Fixed volume* sensor is *unknown* while the amplifier does not answer, instead of keeping the last value. The diagnostics file no longer waits for a timeout when the amplifier is gone and lists a few more settings (`max_volume`, `remember_volume`, `fixed_inputs`, `favorites_count`, `started_offline`).
- Blueprints: the amplifier being *unavailable* or *unknown* now counts as not on in *Radio at a time* and *Standby when idle*; *Reconnect after the smart plug* also starts when the plug comes back from *unavailable*; *Log or announce what is playing* has the cover picture and the Spotify URIs as variables for your action.
- The now-playing event also has `image_url` (the cover or station logo, for example for a notification). A title ending in a capitalised version word (`LIVE`, `REMIX`, `EDIT` ...) is no longer taken for an artist.
- The diagnostics file now also lists the model, firmware, volume range, the auto-standby choices of the amplifier and the features of the media player, so a model report shows what the amplifier offers. Nothing that identifies the amplifier or its owner is added. Seen on an H150: no address, id or account name in the file.
- The text after setup now links to the README section that explains how to enable the optional entities.
- The automated tests also run against Home Assistant 2025.4, the oldest supported version.
- The auto-standby select is read again every 15 minutes (before: every 6 hours), because the amplifier does not report a change of the setting; a change in the Hegel app shows up within a quarter of an hour. One small read each time, and only while the entity is enabled.
- The auto-standby select no longer shows its old value for a moment when the connection returns; it stays unavailable until the amplifier has answered (seen on an H150 as 36 ms).
- After setup a text says that optional entities are off until you enable them, and for a model the maintainer has not tested (everything but the H150) it asks for a [model report](https://github.com/Elpea-byte/ha-hegel-connect/issues/new?template=model_report.yml). All six languages; tested with the fake amplifier, not seen in the interface yet.
- Setup: you can paste the address from your browser (for example `http://192.168.1.50/webclient/`); only the host (and an explicit port) is used, in setup and when changing the address. The error *Cannot reach the amplifier* now says how to check it (open the address followed by `/webclient/` in a browser), changing the address has a description, and the discovery confirmation shows the model. All six languages. Tested with the fake amplifier. An empty address (for example only `http://`) is refused with a clear message (before, it said the amplifier could not be reached). A port is kept for IPv4 and IPv6 alike (`[addr]:port`). IPv6 addresses typed by hand put brackets in the request URL (checked on the URL only, not with a real IPv6 amplifier); discovery stays IPv4-only.

### Fixed
- Answers with an integer of more than 19 digits are refused as invalid JSON instead of causing repeated errors. A normal answer is not affected (the largest integer in the recording of an H150 has 16 digits).
- A new internet radio search no longer makes a second search form when the amplifier does not answer at all.
- The saved volumes of "remember volume per input" are removed when you remove the integration from Home Assistant, instead of staying behind in its storage.
- "Remember volume per input" no longer saves a volume under an input the amplifier does not list.

These three were only checked with automated tests, not on a real amplifier.

### Documentation
- Roadmap, open question 1 before core: what core's brand files and documentation show about a second integration of one brand (Yamaha, Denon, LG), marked as fact or interpretation. No decision is made.
- The roadmap table is one line per version, with the items as a list per version below it (built, open), including the Spotify URIs and the text after setup.
- `docs/REFERENCE.md` now also has a table of the actions (what works and when it is refused), the standard attributes of the media player that dashboards use, and the attributes of the radio favorites sensor. A test checks that every key of the now-playing event is listed.
- Pages and README lines about features that are not released yet say so (*New in 0.7, not released yet*), and a test fails when such a marker names a version the manifest has reached, so the markers go with the release.
- New `docs/REFERENCE.md`: media player states, volume, every entity with its translation key, default and states, all attributes, `play_media` ids, every translated error, the rule about the amplifier's own input names, and which entity or attribute to use in a trigger ([#28](https://github.com/Elpea-byte/ha-hegel-connect/discussions/28)).
- README: the troubleshooting section lists the usual symptoms with cause and fix (not discovered, cannot reach, does not look like a Hegel, entity ids, Spotify controls, start volume, inputs not known, empty now playing). Two entries come from the code and were not tried on a real amplifier; they say so.
- The README is shorter and follows the order of a new user: is it for my model, install, set up, first steps, troubleshooting, features. The long sections moved to pages in `docs/` (now playing, volume per input, auto standby, announcements, blueprints, streaming services, examples, reference). Links in the README are absolute, so they also work where HACS and the Marketplace show the README (not checked there).
- README: the now-playing example no longer logs the previous track again when the integration reloads. The event entity goes *unavailable* and comes back with the time of the last event, so the example (and the new blueprint) ignore a change from or to *unavailable* or *unknown* (`not_from` and `not_to`). The README also says that entity ids follow the language of Home Assistant and where to find them, and that it was tried on Home Assistant 2026.11.
- README: how to put the amplifier back after an announcement with a scene ([#33](https://github.com/Elpea-byte/ha-hegel-connect/discussions/33)), tried on an H150 apart from the spoken message itself, and what to expect from the now-playing event per service.
- README: the install section leads with searching for *Hegel Connect* in HACS or the Marketplace now that it is in the HACS default list; the custom repository steps stay as the fallback. The platforms row lists `select`, `switch` and `event`.

## [0.6.0] - 2026-11-07

Requires Home Assistant 2025.4 or newer. Nothing needs to be done after updating: the new volume entities are disabled until you enable them.

### Added
- Four blueprints with import buttons ([#31](https://github.com/Elpea-byte/ha-hegel-connect/discussions/31)): reconnect after a smart plug turns on, radio favorite at a set time, standby when idle or nobody is home, and a lower maximum volume at night. They are checked in the tests (valid blueprint and automation, README buttons) and with yamllint in the CI.
- Optional volume per input ([#29](https://github.com/Elpea-byte/ha-hegel-connect/discussions/29)): a *Start volume* number for each input (0 = leave the volume alone) and a *Remember volume per input* switch. Both are disabled until you enable them, so nothing changes for existing setups. They apply when Home Assistant switches the input and stay within the maximum volume. An input with fixed volume is learned when you switch to it, and its start volume entity then turns unavailable. Turning the switch off clears the remembered volumes. The range of the start volume follows the maximum volume.

### Fixed
- The start volume entity of an input with fixed volume refuses a value with a clear, translated error (Home Assistant itself already skips service calls to it while it is unavailable).
- *Play* no longer pulls music over from another device or switches the amplifier away from the input it is on: it only resumes on the network input. On any other input, or in standby, it answers that there is nothing to resume. This also applies to resuming Spotify and live radio ([#30](https://github.com/Elpea-byte/ha-hegel-connect/discussions/30)).
- Lowering the *Maximum volume* below the current volume now brings the volume down at once, instead of leaving it above the new maximum until the next volume command.
- *Play* after you stopped live radio starts the same favorite again, instead of answering that there is nothing to resume (live radio cannot pause, so stopping is all there is). Only when radio was the last thing played and the station is one of your favorites ([#30](https://github.com/Elpea-byte/ha-hegel-connect/discussions/30)).
- *Volume up* from Home Assistant no longer turns the amplifier down when it is already above the maximum volume (for example after you turned the knob): *louder* now does nothing there, and *quieter* still goes down to the limit.
- The stream sensors (audio quality, bitrate, streaming service and the others) show what the amplifier reports while a track is starting, instead of going empty until it says "playing". Values it does not report yet stay empty.

### Changed
- Requires Home Assistant 2025.4 or newer (the old minimum of 2025.2 never worked: the integration cannot load there).
- `homeassistant.update_entity` on any Hegel Connect entity now makes a waiting connection retry at once and starts the back-off over, instead of waiting up to 60 seconds. Nothing changes while the connection is healthy.

### Development
- `AGENTS.md` and `CONTRIBUTING.md` describe the new files, the yamllint check and the rules for blueprints, optional features and renamed inputs.
- Minimum Home Assistant version in `hacs.json` is now 2025.4.0 (was 2025.2.0). The old value was never tested: 2025.2 cannot load the integration (`AddConfigEntryEntitiesCallback` is missing there). The full test suite passes on 2025.4.4.
- The manifest names a category (Speakers & audio), so the Marketplace can show Hegel Connect under it.

### Documentation
- README: that fixed volume is only learned when you switch to the input; where to find the optional (disabled) entities, that *0 = off*, when the volume is set and when not, the smart-plug example for `update_entity` and the start-up time of the amplifier.
- README: a note for the options (hide and rename inputs): saved through the API or a script, `hidden_sources` must be sent again, or hidden inputs show up again. The form in the interface fills it in.
- The "Maximum volume entity" field of the night blueprint says to pick the maximum volume, not a start volume (the list shows all numbers of the integration).
- README: installation steps for the Marketplace of Home Assistant 2026.11, next to HACS (which it replaces from that version).
- New [docs/ROADMAP.md](docs/ROADMAP.md): the direction towards 1.0 (plans, not promises).
- README: a note not to install Hegel Connect together with the similar `hegel_streaming` integration for the same amplifier (both would be offered by discovery).
- Ideas and feature requests now go in GitHub Discussions (Ideas) instead of issues, so the issue list (and the counter HACS shows) only holds bugs and model reports. The "Feature request" issue form is replaced by a link to Discussions.
- The README has "My Home Assistant" buttons: one to open the repository in HACS, one that asks to set up the integration, to enter the address by hand (usually not needed, because the amplifier is discovered automatically). Both were tried on a Home Assistant instance.
- The README now shows the radio favorite select as the one way to start a station; the older `play_media` example with a template on the favorites sensor is gone (it still works).

## [0.5.0] - 2026-10-20

### Added
- Radio favorite select (`select.<name>_radio_favorite`): choose one of the amplifier's radio favorites from a list to start it, in automations, scripts, voice assistants and dashboard cards. It shows the favorite that is playing, and keeps the station you chose selected while the amplifier switches to it (no flicker to unknown). The list follows the favorites in the Hegel Control app (#14).

### Fixed
- A number that is too large for Python (such as `1e999`) in an answer from the amplifier is skipped like other odd values, instead of restarting the push connection. A media id with a character like a superscript two instead of a digit now gives the normal "unknown media" error.
- A device answering with a non-finite number (such as 1e999) is now refused as invalid JSON instead of causing repeated errors.

### Documentation
- H200 confirmed working by a user (#17): status, artwork, track info and pause/play, also with Qobuz Connect.
- Tested on Home Assistant 2026.10.

### Security
- Discovery only connects to an IP address: the address in the _sues800device announcement is used only when it is an IPv4 address that the announcement came from, and a UPnP (SSDP) announcement with a host name or a broken address is ignored. Before, a device on your network could announce a different target for Home Assistant to contact. Manual setup is unchanged.
- Answers from the amplifier are read in chunks and refused above 8 MiB (a normal answer is a few KB), so a faulty or fake device cannot fill Home Assistant's memory.

### Development
- Tests now run on Python 3.14 against Home Assistant 2026.10 (pytest-homeassistant-custom-component 0.13.373, pytest-cov 7.1.0), with mypy 2.4.0. No change for users.
- The GitHub workflows run with read-only repository permissions, and every action is pinned to a commit (Dependabot keeps them current).

## [0.4.1] - 2026-10-08

### Fixed
- Play after pause no longer fails with "Directory is empty" (Qobuz Connect, media servers and other services, #17). Hegel Connect now resumes the way the Hegel web client does: by sending pause again, which the amplifier treats as a toggle. Spotify Connect keeps its own resume action.
- Play while nothing is paused now explains that there is nothing to resume, instead of sending a command that the amplifier refuses.
- Internet radio: pause gave an error (the amplifier has no pause for live radio and answered "Control is not supported"). Pause and play/pause now stop the station, like the Hegel web client; other services keep a real pause. New attribute `can_pause` tells cards when to show a stop button instead of pause.
- Media browser: placeholder rows of the amplifier (such as an empty media server list) are no longer shown as playable items.

## [0.4.0] - 2026-10-07

### Added
- Shuffle and repeat (`shuffle_set`, `repeat_set`), where the amplifier allows them (media server, USB), using the same play modes as the Hegel web client.
- Seeking within a track (media player `media_seek`), where the amplifier allows it: tracks from a media server or USB. Not for Spotify Connect or radio, like the Hegel web client.

### Fixed
- At a track change the position starts at 0 at once; before, the new track briefly showed the old track's position, so progress bars ran backwards.

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

[Unreleased]: ../../compare/v0.7.0...dev
[0.7.0]: ../../compare/v0.6.0...v0.7.0
[0.6.0]: ../../compare/v0.5.0...v0.6.0
[0.5.0]: ../../compare/v0.4.1...v0.5.0
[0.4.1]: ../../compare/v0.4.0...v0.4.1
[0.4.0]: ../../compare/v0.3.3...v0.4.0
[0.3.3]: ../../compare/v0.3.2...v0.3.3
[0.3.2]: ../../compare/v0.3.1...v0.3.2
[0.3.1]: ../../compare/v0.3.0...v0.3.1
[0.3.0]: ../../compare/v0.2.1...v0.3.0
[0.2.1]: ../../compare/v0.2.0...v0.2.1
[0.2.0]: ../../compare/v0.1.2...v0.2.0
[0.1.2]: ../../compare/v0.1.1...v0.1.2
[0.1.1]: ../../compare/v0.1.0...v0.1.1
[0.1.0]: ../../releases/tag/v0.1.0
