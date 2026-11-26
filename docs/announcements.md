[← README](../README.md) · [Reference](REFERENCE.md) · [All pages](README.md)

# Announcements: put the amplifier back afterwards

A spoken message or a doorbell sound on the amplifier interrupts what plays. A scene brings the amplifier back to where it was: Home Assistant stores the power state, input, volume and mute of a media player in a scene and restores them, so Hegel Connect needs nothing extra.

```yaml
sequence:
  - action: scene.create
    data:
      scene_id: hegel_before_announcement
      snapshot_entities:
        - media_player.hegel_h150
  - action: tts.speak
    target:
      entity_id: tts.your_text_to_speech   # your own text-to-speech entity
    data:
      media_player_entity_id: media_player.hegel_h150_cast   # the Cast entity of the amplifier
      message: "Dinner is ready"
  - delay: "00:00:08"   # long enough for the message; or wait until the Cast entity is idle
  - action: scene.turn_on
    target:
      entity_id: scene.hegel_before_announcement
```

What was tried on an H150 (the scene steps; the spoken message itself was not played):

- Input and volume come back, also from standby (the amplifier switches on first). Allow 4 to 8 seconds, from standby the longest.
- Internet radio starts again (live radio cannot continue); Spotify continues at the same place.
- A lower *Maximum volume* wins over the volume in the scene, and mute is restored as it was.
- The now-playing event fires again for the track that continues, because the stream was interrupted.

Playing a link through the DLNA renderer was tried on an H150 (text-to-speech through the built-in *DLNA Digital Media Renderer* integration, which finds the amplifier as a UPnP renderer): the player went to *playing* for 4 seconds and then back to idle. Whether it was audible was not checked. The input stayed *Network* and the volume did not change, but **the radio that played before did not come back**: the amplifier stayed idle, so the scene recipe above is needed there as well. The now-playing event ignores this title.

The amplifier cannot play a link of your own through its local interface (none was found), so the announcement itself goes through the Cast entity of the amplifier. In Home Assistant that entity may be disabled: enable it under the device first.
