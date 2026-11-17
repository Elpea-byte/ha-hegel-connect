[← README](../README.md) · [Reference](REFERENCE.md) · [All pages](README.md)

# Auto standby

> **New in 0.7 (not released yet).** The auto-standby select is not in a release. It is on the `dev` branch; the released version is 0.6.0.

The amplifier can put itself in standby after a while without activity. That is a setting inside the streamer of the amplifier, and *Auto standby* (`select.hegel_h150_auto_standby`, under the device's disabled entities, off until you enable it) shows and changes it: Off, or after 5, 10 or 20 minutes, the choices the amplifier itself offers. The amplifier counts the time itself, so it also works when Home Assistant is not running.

Tried on an H150 (Home Assistant 2026.11, 5 minutes): on the network input without playing it went to standby exactly 5 minutes after the last activity, with Home Assistant doing nothing; while music plays it does not count, and after stopping the 5 minutes start again. Good to know:

- This is not the standby timer in the amplifier's own menu. Which of the two wins when both are on has not been tried.
- The amplifier does not report a change of this setting, so Home Assistant reads it when it connects and every few hours. A change in the Hegel app shows up then.
- Not tried: whether pause counts as idle, whether the setting survives a power cut, and other models. An amplifier that does not have the setting shows the entity as unavailable.
- The [blueprint](blueprints.md) *Standby when idle or nobody is home* is still the way to switch off when everybody has left, or after a time other than 5, 10 or 20 minutes.
