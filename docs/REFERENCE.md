# Reference

## Entities

For an amplifier named *Hegel H150*:

| Entity | |
| :---- | :---- |
| `media_player.hegel_h150` | Power, volume, mute, input, playback, now playing, media browser, and eight extra attributes (below) |
| `sensor.hegel_h150_audio_quality` | Hi-Res, CD quality, Lossless, Lossy, DSD (while the streamer plays) |
| `sensor.hegel_h150_streaming_service` | The service that plays (TIDAL, Spotify, radio, ...) |
| `sensor.hegel_h150_codec`, `_sample_rate`, `_bit_depth`, `_bitrate` | Stream details, when the service reports them (kept in history, no long-term statistics) |
| `event.hegel_h150_now_playing` | Optional, off until you enable it: fires `track_changed` when a new track starts, with title, artist, album, service, input, audio quality, codec, sample rate, bit depth, bitrate and whether it is radio. For listening logs, scrobbling and notifications |
| `select.hegel_h150_radio_favorite` | The radio favorites as options; choosing one starts that station, and it shows the favorite that is playing (unknown when something else plays) |
| `sensor.hegel_h150_radio_favorites` | Number of radio favorites; the list (title, icon, path) as attribute, for custom dashboard cards that show the station logos |
| `select.hegel_h150_auto_standby` | Optional, off until you enable it: the amplifier's own auto-standby after 5, 10 or 20 minutes without activity (or off), configuration |
| `number.hegel_h150_maximum_volume` | Volume ceiling for Home Assistant (configuration) |
| `number.hegel_h150_start_volume_<input>` | Optional, off until you enable it: the volume to set when Home Assistant switches to that input (0 = leave the volume alone) |
| `switch.hegel_h150_remember_volume_per_input` | Optional, off until you enable it: switching to an input returns to the volume it had last |
| `binary_sensor.hegel_h150_network` | On while the amplifier answers, standby included (diagnostic) |
| `binary_sensor.hegel_h150_fixed_volume` | On when the current input uses fixed volume (diagnostic) |

Extra attributes of the media player:

| Attribute | Meaning |
| :---- | :---- |
| `fixed_volume` | `true` when the current input uses fixed volume (the volume cannot be set), otherwise `false` |
| `can_pause` | `false` while live radio plays: it has no pause, so pause stops it |
| `service` | The streaming service that plays (TIDAL, Spotify, radio, ...); empty unless the network input plays |
| `media_id` | Id of what plays, for example a radio station; it matches the `id` of a radio favorite; empty unless the network input plays |
| `audio_format` | Codec and format as text, for example `FLAC · 24-bit/96kHz`; empty when the service does not report it or another input plays |
| `volume_raw` | The volume on the amplifier's own scale (`volume_level` is 0 to 1) |
| `max_volume` | The volume ceiling Home Assistant applies, on the amplifier's own scale |
| `input_names` | The inputs you see (shown name to the amplifier's own name), so cards can keep icons for renamed inputs |

Entity ids follow your Home Assistant language when they are added; the names above are the English ones, and your own ids are on the device page (Settings > Devices & services > Hegel Connect > your amplifier). Home Assistant 2026.11 shows entity names together with their device and area; existing entity ids stay as they are.
