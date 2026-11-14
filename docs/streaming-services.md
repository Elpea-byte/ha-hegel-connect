# What each streaming service allows

The amplifier reports per service which controls work; Hegel Connect follows it, so buttons that would fail are not offered. Tested on the H150; "not tested yet" means what the code expects, not what was seen. Pause and play with Qobuz Connect were confirmed by a user on an H200.

| Source | Format shown | Next / previous | Stop | Seek | Shuffle / repeat |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Spotify Connect | Service and quality only (Spotify sends no codec or bitrate) | No: the amplifier refuses it | Not offered (to keep the session with your phone) | No | No |
| Internet radio | Codec, bit depth, sample rate, bitrate | No | Offered | No | No |
| Media server (UPnP/DLNA, e.g. FLAC from a NAS) | Codec, bit depth, sample rate, bitrate | Yes (tested) | Offered (not tested yet) | Yes (tested) | Yes (tested, also follows changes made in the Hegel app) |
| TIDAL / Qobuz Connect | Not tested yet | Not tested yet | Offered (not tested yet) | Not tested yet | Not tested yet |
| AirPlay (e.g. Apple Music) | AirPlay's own label, like the Hegel web client (not tested yet) | Not tested yet | Offered (not tested yet) | Not tested yet | Not tested yet |
| Google Cast (e.g. YouTube Music) | Not tested yet | Not tested yet | Offered (not tested yet) | Not tested yet | Not tested yet |

With Spotify Connect, *play* after *pause* uses Spotify's own resume action; on the H150 a plain play command was refused there and stopped the session. Other services resume the way the Hegel web client does.

Live internet radio has no pause: *pause* stops the station, like the Hegel web client. After a stop there is nothing to resume, so start the station again from the media browser or a favorite. The media player's `can_pause` attribute is `false` while radio plays, so a card can show a stop button instead of pause.
