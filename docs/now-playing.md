[← README](../README.md) · [Reference](REFERENCE.md) · [All pages](README.md)

# Now-playing event

> **New in 0.7 (not released yet).** The now-playing event, the Spotify URIs and the blueprint on this page are not in a release. It is on the `dev` branch; the released version is 0.6.0.

`event.hegel_h150_now_playing` is off until you enable it (Settings > Devices & services > Hegel Connect > your amplifier > disabled entities), because every track it fires is stored in the Home Assistant database. It fires once for every new track, so an automation can log or announce what you play without watching the media player's attributes. It fires when the amplifier says "playing", so the quality details are there. It does not fire on pause or resume, nor when the same track plays on (repeat); a track that plays again after another one, or after you stopped, fires again. A track that is already playing when Home Assistant starts is not announced.

The event data has `title`, `artist`, `album`, `service`, `spotify_uri`, `spotify_album_uri`, `spotify_artist_uri`, `spotify_playlist_uri`, `station`, `source`, `audio_quality`, `codec`, `sample_rate`, `bit_depth`, `bitrate` and `is_radio`; a value the amplifier does not report is empty. Write what you play to the logbook:

```yaml
automation:
  - alias: Hegel listening log
    triggers:
      - trigger: state
        entity_id: event.hegel_h150_now_playing
        not_from: [unavailable, unknown]
        not_to: [unavailable, unknown]
    actions:
      - action: logbook.log
        data:
          name: Hegel
          message: >-
            {{ trigger.to_state.attributes.artist }} - {{ trigger.to_state.attributes.title }}
            ({{ trigger.to_state.attributes.audio_quality }})
          entity_id: event.hegel_h150_now_playing
```

The two `not_` lines matter: the event entity goes *unavailable* when the integration reloads and comes back with the time of the last event, which a plain state trigger would log as a new track. (In the automation editor this is the option *Is not* on the state trigger, from Home Assistant 2026.11.) Only the very first event of a new entity is skipped, because it comes from *unknown*. The entity id depends on your Home Assistant language, for example `event.hegel_h150_nu_aan_het_spelen` in Dutch: find yours on the device page (Settings > Devices & services > Hegel Connect > your amplifier).

Home Assistant keeps the recorded events only as long as its recorder does (10 days by default, `purge_keep_days`), and `recorder.purge_entities` removes them earlier. For a longer listening log, let an automation write the tracks somewhere that suits you, or leave the event out of the recorder with `exclude` if you only need the automation to react.

The blueprint [Log or announce what is playing](blueprints.md) does all this for you, including a notification of your own and a filter on audio quality. Scrobbling itself is left to other integrations.

Good to know, from trying it on an H150:

- **Spotify**: the track, album and artist as Spotify URIs (`spotify:track:...`) in `spotify_uri`, `spotify_album_uri`, `spotify_artist_uri` and, when it plays from a playlist, `spotify_playlist_uri` (empty for other services; the media player has the track URI as `media_content_id`). `codec`, `sample_rate`, `bit_depth` and `bitrate` stay empty, because the amplifier does not receive them from Spotify. `audio_quality` is `lossy` (or `lossless` when the amplifier reports Spotify Lossless).
- **Internet radio**: the station is in `station`. The amplifier shows the station name first and the song a moment later, so the event comes with the song; stations send `Artist - Title` as one text, which is split into `artist` and `title` at the first ` - `. A station that never sends a song title gives no events, and a station that updates the title only now and then gives an event per update.
- **Same track again**: a track that plays on (repeat, or back to the start without a break) gives no new event. After a break (another input, the stream moved to a phone and back, or an announcement that interrupted it) the same track starts a new event.
- Tried on an H150 with Spotify, internet radio, pause and resume, next and previous track, switching input, and restarting Home Assistant while music played. Not tried: tracks from a media server (NAS) and other streaming services.

### Play the same Spotify track again

The track URI is enough to start exactly that track again, for example on the Spotify Connect device of the amplifier. This is what an automation with the [SpotifyPlus](https://community.home-assistant.io/t/spotifyplus-integration/698651) integration can do (expected to work: the event attributes were checked on an H150 and the action's name and fields come from community posts, but this exact automation was not tried; check the SpotifyPlus documentation for your version):

```yaml
actions:
  - action: spotifyplus.player_media_play_tracks
    data:
      entity_id: media_player.spotifyplus_your_name   # your SpotifyPlus entity
      uris: "{{ trigger.to_state.attributes.spotify_uri }}"
      device_id: Hegel H150   # the name of the amplifier as a Spotify Connect device
```

The album, artist and playlist URIs can start a whole album, artist or playlist the same way (SpotifyPlus has a separate action for that; not tried). Other services: Hegel Connect has no such ids for them (see the changelog).

