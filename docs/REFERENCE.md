# Reference

Facts about what Hegel Connect creates and does, in one place. For setup and everyday use see the [README](../README.md). Example names are for an amplifier named *Hegel H150*.

## Names and ids

- **Entity ids follow the language of Home Assistant** at the moment the entity is added: in Dutch the now-playing event is `event.hegel_h150_nu_aan_het_spelen`, in English `event.hegel_h150_now_playing`. Find yours on the device page (Settings > Devices & services > Hegel Connect > your amplifier). The translation keys in the table below do not depend on the language.
- **Inputs: use the amplifier's own names, never the shown name.** You can rename an input in the options; the media player then shows your name. Scripts and automations may use either name for `media_player.select_source`, but code and blueprints that compare an input with a fixed text must use the amplifier's own name (the network input is `Network`). The attribute `input_names` maps shown names to the amplifier's names.

## Media player

`media_player.hegel_h150`

| State | Meaning |
| :---- | :---- |
| `off` | The amplifier is in standby, switched off at the mains or not reachable. Tell them apart with `binary_sensor.hegel_h150_network` (on in standby, off when unreachable) |
| `on` | The amplifier is on and an input other than the network input is selected (it cannot tell whether that input plays) |
| `idle`, `playing`, `paused`, `buffering` | Only on the network input. `buffering` is also reported while the amplifier switches to a new track or service |

Volume: `volume_level` is 0 to 1 of the amplifier's range. `volume_raw` and `max_volume` (attributes) are on the amplifier's own scale. Home Assistant never sets a volume above the maximum volume (the number entity); a volume that is already above it because you turned the knob is left alone. Inputs with fixed volume ignore volume changes and refuse them with an error. Volume steps are one point on the amplifier's scale.

Features: next, previous, seek, shuffle, repeat and stop are only offered while the current service allows them (see [streaming services](streaming-services.md)).

| Attribute | Type | Meaning |
| :---- | :---- | :---- |
| `fixed_volume` | bool or null | `true` when the current input uses fixed volume; null until read |
| `can_pause` | bool | `false` while live radio plays: it has no pause, so pause stops it |
| `service` | text or null | Streaming service that plays; null unless the network input plays |
| `media_id` | text or null | Id of what plays (a radio station matches the `id` of a radio favorite); null unless the network input plays |
| `audio_format` | text or null | Codec and format, for example `FLAC · 24-bit/96kHz`; null when not reported or another input plays |
| `volume_raw` | number or null | Volume on the amplifier's scale |
| `media_content_id` (standard attribute) | text or null | While Spotify plays: the track as a Spotify URI (`spotify:track:...`); null for other services |
| `max_volume` | number | The volume ceiling Home Assistant applies, on the amplifier's scale |
| `input_names` | object | Shown input name to the amplifier's own name, for the visible inputs |

`media_player.play_media` takes `media_content_type: hegel_path`. The ids come from the media browser (*Pick media* in the editor): a path on the amplifier, for example `upnp:/uuid:<server>/<album>?itemType=container` or an internet radio path, or `track:<index>:<folder path>` for a track inside a folder (it then plays with the rest of the folder). The browser roots (the top, the favorites folder, media servers and USB) are refused with *not playable*. Ids can change when a media server re-indexes its library. To start a radio favorite use the select instead.

## Entities

| Entity | Translation key | On by default | Category | States and values |
| :---- | :---- | :---- | :---- | :---- |
| `media_player.hegel_h150` | (the device name) | yes | | see above |
| `sensor.hegel_h150_audio_quality` | `audio_quality` | yes | | `hi_res`, `cd`, `lossless`, `lossy`, `dsd`; `unknown` unless the built-in streamer plays or is paused |
| `sensor.hegel_h150_codec` | `codec` | yes | | codec name, for example `FLAC`; `unknown` when not reported |
| `sensor.hegel_h150_sample_rate` | `sample_rate` | yes | | kHz |
| `sensor.hegel_h150_bit_depth` | `bit_depth` | yes | | bit |
| `sensor.hegel_h150_bitrate` | `bitrate` | yes | | kbit/s |
| `sensor.hegel_h150_streaming_service` | `streaming_service` | yes | | text, for example `Spotify` |
| `sensor.hegel_h150_radio_favorites` | `radio_favorites` | yes | | number of favorites; attribute `favorites` is the list (title, icon, path, id) |
| `select.hegel_h150_radio_favorite` | `radio_favorite` | yes | | options are the radio favorites; the playing favorite, `unknown` when something else plays |
| `number.hegel_h150_maximum_volume` | `max_volume` | yes | config | 1 to 100, the volume ceiling for Home Assistant |
| `binary_sensor.hegel_h150_network` | `network` | yes | diagnostic | `on` while the amplifier answers (standby included), `off` when it does not |
| `binary_sensor.hegel_h150_fixed_volume` | `fixed_volume` | yes | diagnostic | `on` when the current input uses fixed volume |
| `number.hegel_h150_start_volume_<input>` | `start_volume` | no | config | 0 (off) up to the maximum volume; `unavailable` on an input with fixed volume |
| `switch.hegel_h150_remember_volume_per_input` | `remember_volume` | no | config | `on` or `off` |
| `select.hegel_h150_auto_standby` | `auto_standby` | no | config | `off`, `5_min`, `10_min`, `20_min` (the amplifier's own list); `unavailable` while not connected or when the amplifier does not have the setting |
| `event.hegel_h150_now_playing` | `now_playing` | no | | event type `track_changed`, see below |

The sensors and the media player are not `unavailable` when the amplifier cannot be reached: they show `unknown` or `off` (a planned change, see the [roadmap](ROADMAP.md)). The optional entities are enabled under the device page's disabled entities.

### The now-playing event

Event type `track_changed`, with the attributes `title`, `artist`, `album`, `service`, `spotify_uri`, `spotify_album_uri`, `spotify_artist_uri`, `spotify_playlist_uri` (Spotify only, otherwise null; the playlist only when it plays from one), `station`, `source` (the shown input name), `audio_quality`, `codec`, `sample_rate`, `bit_depth`, `bitrate` and `is_radio`. A value the amplifier does not report is null. Details and examples: [now playing](now-playing.md).

## Which entity or attribute to use in a trigger

| You want to react to | Use |
| :---- | :---- |
| A new track, with all its details | The now-playing event (a state trigger with `not_from` and `not_to` set to `unavailable` and `unknown`) |
| Play, pause, stop | The state of the media player |
| The input changed | The `source` attribute of the media player (the shown name) |
| The volume changed | `volume_level` or `volume_raw` of the media player |
| Quality of what plays | `sensor.hegel_h150_audio_quality` |
| Standby or gone | The media player is `off` in both cases; `binary_sensor.hegel_h150_network` is `on` in standby and `off` when gone |
| A radio station started | The state of `select.hegel_h150_radio_favorite` |

Home Assistant no longer accepts new device triggers and conditions and points to entity triggers, so Hegel Connect does not add any.

## Errors

Errors you can see in the interface and in `service` calls have a translated message. The keys are in `strings.json` under `exceptions`.

| Key | When |
| :---- | :---- |
| `command_failed` | The amplifier did not accept a command or could not be reached; the amplifier's own message is included |
| `fixed_volume` | A volume is set while the current input uses fixed volume |
| `not_playable` | `play_media` was given one of the browser roots (the top, favorites, media servers, USB) instead of a station, album or track |
| `unknown_media` | `play_media` was given a track id that is not valid |
| `browse_failed` | A folder of the media browser could not be opened on the amplifier |
| `unknown_source` | `select_source` was given an input the amplifier does not have |
| `play_mode_not_allowed` | A shuffle and repeat combination that the amplifier does not allow for what plays now |
| `nothing_to_resume` | *Play* when there is nothing to resume: another input is selected, the amplifier is in standby, or nothing has played |
| `fixed_volume_input` | A start volume is set (directly on the entity) for an input that has fixed volume |
