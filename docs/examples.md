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

Search a radio station by name (new in 0.7) from a script, then start the first result (Home Assistant's own media browser has no search box yet; cards and Assist that use the action can search):

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

Tried on an H150 (Home Assistant 2026.11): about 15 results per search in under a second, and the first result started with `play_media`.

Search podcasts (new in 0.8, not released yet): add `media_filter_classes: [podcast]` to the search. A result is a podcast, not an episode: open it in the media browser (or browse it with `media_player.browse_media`) to its *Episodes*, then play one episode or the whole list. Tried on an H150: the search, opening a podcast and playing its whole episode list. Starting one episode from the media browser was tried too. While an episode plays the amplifier gives a placeholder title (`Title Placeholder Episode ID: ...`); Hegel Connect shows the real title when it knows it, otherwise none.

```yaml
actions:
  - action: media_player.search_media
    target:
      entity_id: media_player.hegel_h150
    data:
      search_query: nieuws
      media_filter_classes: [podcast]
    response_variable: found
```

**By voice (Assist):** Home Assistant's own sentence "play Radio 10 on the Hegel H150" searches with this action and plays the first result; matching radio favorites come first. Say the name Home Assistant knows for the amplifier (the entity is called *Hegel H150*: "the Hegel" was not found), or give the entity an alias under *Settings > Voice assistants > Expose*. Tried on an H150 in text; spoken sentences were not tried.

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

