# Hegel Connect for Home Assistant

> **Unofficial community integration.** Not affiliated with, endorsed or supported by Hegel Music Systems AS. Hegel is a trademark of its owner.

Local-push integration for **Hegel H150, H400 and H600** streaming amplifiers. It talks to the amplifier over your own network, the same way the amplifier's built-in web app does. No cloud, no account, and no polling: changes made on the amplifier, with its remote or in the Hegel Control app show up in Home Assistant within a second.

## Which integration for my Hegel?

Hegel has two generations of network amplifiers, controlled in different ways:

| Generation | Models | How it is controlled | Use |
| :---- | :---- | :---- | :---- |
| **Streaming generation** | H150, H400, H600 | Built-in streamer with a web API (the same one the Hegel Control app and the amplifier's web page use) | **Hegel Connect** (this integration) |
| **IP control generation** | Röst, H95, H120, H190, H190V, H390, H590 | Hegel IP control protocol on TCP port 50001 | The built-in [Hegel integration](https://www.home-assistant.io/integrations/hegel/) in Home Assistant |

Quick check: if `http://<amplifier-address>/webclient/` opens a Hegel page, the amplifier belongs to the streaming generation. If you try to add an older amplifier to Hegel Connect, setup recognises it (it answers a read-only IP control status query) and points you to the built-in integration.

## Supported models

| Model | Status |
| :---- | :---- |
| H150 | ✅ Tested by the maintainer |
| H400 | 🟡 Expected to work, not tested yet |
| H600 | 🟡 Expected to work, not tested yet |

The H150, H400 and H600 share the same software platform (they are supported by the same Hegel Control app). If you own an H400 or H600, please [send a model report](../../issues/new?template=model_report.yml), even if everything works. It takes five minutes and helps everyone.

## Features

- **Power** on and network standby
- **Volume** (set and step) and **mute**, with an optional maximum volume
- **Inputs**: read from the amplifier, so every model shows its own inputs
- **Reliable input switching**: waits until the amplifier is on, pauses a running stream and checks the input sticks (the amplifier otherwise jumps back to Network after power-on)
- **Now playing** for the built-in streamer: title, artist, album, cover art, service (Spotify, AirPlay, Google Cast, TIDAL, internet radio, ...)
- **Play, pause, next, previous**
- **Media browser**: your internet radio favorites, all internet radio, and recently played
- **Fixed volume** indicator: shows when the current input is set to home theater bypass (volume changes are then ignored by the amplifier)
- **Stream format sensors**: audio quality (Hi-Res, CD, Lossless, Lossy, DSD), codec, sample rate, bit depth, bitrate, streaming service; track length and position
- **Network sensor**: tells standby (still on the network) and switched off at the mains apart; the media player then shows off instead of unavailable
- **Diagnostics** download without IP address or device ids

## Installation

### HACS (recommended)

1. HACS > ⋮ > *Custom repositories* > add `https://github.com/Elpea-byte/ha-hegel-connect`, type *Integration*.
2. Search for **Hegel Connect** and download it.
3. Restart Home Assistant.

### Manual

Copy `custom_components/hegel_connect` to the `custom_components` folder of your Home Assistant configuration and restart.

## Configuration

The amplifier is **discovered automatically**, the same way the Hegel Control app finds it (mDNS service `_sues800device._tcp`), with UPnP/DLNA and Google Cast as backups. Home Assistant then shows it under Settings > Devices & services > *Discovered*; click *Add*.

Not discovered (other subnet/VLAN, multicast blocked)? Add it by hand: *Add integration* > **Hegel Connect** > enter the IP address.

A fixed IP address (DHCP reservation in your router) is still recommended. If the address does change, Home Assistant picks up the new one by itself the next time it sees the amplifier on the network.

**Maximum volume** is a setting on the device page (a number entity, so automations can change it, e.g. lower in the evening). Home Assistant will never set the volume above it; the amplifier's own remote is not limited.

The amplifier stays reachable in network standby, so it can be switched on from Home Assistant. If it is disconnected from mains, the integration reconnects automatically when it is back.

## Troubleshooting

Enable debug logging and reproduce the problem:

```yaml
logger:
  default: warning
  logs:
    custom_components.hegel_connect: debug
```

Then open an [issue](../../issues/new/choose) with the log and the diagnostics file (Settings > Devices & services > Hegel Connect > ⋮ > *Download diagnostics*).

## Known limitations

- *Play* after *pause* is passed to the streaming service; with Spotify Connect, resuming is most reliable from the Spotify app.
- Radio favorites are managed in the Hegel Control app; Home Assistant shows and plays them.

## Related projects

[hegel-home-assistant](https://github.com/zerostorypoints/hegel-home-assistant) (`hegel_streaming`, MIT) targets the same amplifiers through the same local API. Matching discovery on the `manufacturer`/`uuid` TXT records and reading the id from `systemmanager:systemMember` were inspired by it.

## Development

The client in `custom_components/hegel_connect/api.py` has no Home Assistant dependencies and may move to its own package later. Tests replay a real H150 recording (`tests/fixtures/h150_session.json`):

```bash
pip install -r requirements_test.txt
pytest
```

## License

MIT
