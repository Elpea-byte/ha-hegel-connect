[← README](../README.md) · [Reference](REFERENCE.md) · [All pages](README.md)

# Examples

Quieter in the evening:

```yaml
automation:
  - alias: Hegel volume limit at night
    triggers:
      - trigger: time
        at: "22:00:00"
    actions:
      - action: number.set_value
        target:
          entity_id: number.hegel_h150_maximum_volume
        data:
          value: 40
```

Start a radio favorite by name (the options follow the favorites in the Hegel Control app):

```yaml
action: select.select_option
target:
  entity_id: select.hegel_h150_radio_favorite
data:
  option: "Qmusic"
```

To start a station from a button or a dashboard card, use the select above. The attributes of the radio favorites sensor (title, icon and path of each station) are meant for custom cards that show the logos; such a card can start a station with the same `select.select_option` call.

Play an album from your NAS from a script or button. In the script editor, add the action *Media player: Play media*, choose the Hegel and click *Pick media*: you browse the same folders as in the media browser. The result looks like this (the id comes from your media server; if the server re-indexes your library it can change):

```yaml
action: media_player.play_media
target:
  entity_id: media_player.hegel_h150
data:
  media_content_type: hegel_path
  media_content_id: "upnp:/uuid:<server>/<album>?itemType=container"
```

Search a radio station by name (new in 0.7, not released yet) from a script, then start the first result; in the media browser the same search box finds stations:

```yaml
actions:
  - action: media_player.search_media
    target:
      entity_id: media_player.hegel_h150
    data:
      search_query: Radio 10
    response_variable: found
  - action: media_player.play_media
    target:
      entity_id: media_player.hegel_h150
    data:
      media_content_type: hegel_path
      media_content_id: "{{ found['media_player.hegel_h150'].result[0].media_content_id }}"
```

The field names of the result follow the Home Assistant version; not tried on an H150 yet. Searching podcasts is planned.

Reconnect at once when the amplifier was unplugged or switched off at the mains. Home Assistant normally notices within a minute (it retries after 5, 10, 20, 40 and then every 60 seconds); the standard action `homeassistant.update_entity` on any Hegel Connect entity makes it retry now:

```yaml
action: homeassistant.update_entity
target:
  entity_id: media_player.hegel_h150
```

It only helps once the amplifier answers on the network again: right after power-on it needs a little time to start (about 20 to 45 seconds on an H150), and a call that comes too early fails quietly while the normal retries carry on. If the amplifier hangs on a smart plug, wait for it to start and then ask for the connection (expected to work; the single call was tried on an H150 at the moment the amplifier answered). The delay is a starting point, so adjust it to your amplifier; the blueprint *Smart plug: reconnect at once* does this with a loop:

```yaml
triggers:
  - trigger: state
    entity_id: switch.audio_plug   # your own plug
    to: "on"
actions:
  - delay: "00:00:45"
  - action: homeassistant.update_entity
    target:
      entity_id: media_player.hegel_h150
```

