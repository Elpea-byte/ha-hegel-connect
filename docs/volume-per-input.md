# Maximum volume and volume per input

## Maximum volume

The *Maximum volume* is a setting on the device page (a number entity, so automations can change it). Home Assistant will never make the volume louder than it; the amplifier's own remote and knob are not limited. Lowering the maximum below the current volume brings the volume down to the new maximum at once (not on an input with fixed volume, and not while the amplifier is off). If you turned the amplifier above the limit yourself, *louder* from Home Assistant does nothing and *quieter* goes straight down to the limit, not one step. Volume steps are one point on the amplifier's scale.

## Volume per input

*Volume per input* is optional and does nothing until you enable it. The amplifier only has one *power-on volume* for all inputs; this goes further and is done by Home Assistant. It consists of two entities:

- `number.hegel_h150_start_volume_<input>`, one per input: the volume to set when Home Assistant switches to that input. **0 means off**: the volume is left alone. The slider goes up to your maximum volume.
- `switch.hegel_h150_remember_volume_per_input`: the volume you used last on each input is brought back when you switch to it. A volume is only remembered after you change it on that input; an input where you never touched the volume keeps whatever the amplifier has. Turning the switch off throws the remembered volumes away. A start volume set for an input wins over the remembered one.

Both are switched off by default, so you will not see them on the device page at first. To find them: Settings > Devices & services > Hegel Connect > your amplifier, then open *+ n entities not shown* (or the *Entities* tab with the filter set to show disabled entities), choose the ones you want and enable them. Home Assistant reloads the integration after a short moment.

- **Only when Home Assistant switches the input** (the source list, scripts, automations, the dashboard). Switching with the amplifier's own remote or the Hegel app, or by an app such as Spotify taking the amplifier over, is left alone. The same goes for switching the amplifier on: it keeps the input it had, and the volume is only set when the input is switched afterwards. For a safe volume at power-on, use the amplifier's own *power-on volume* setting in the Hegel Control app.
- The maximum volume always applies. An input with **fixed volume** cannot have a start volume: once you have switched to such an input from Home Assistant, its start volume entity turns *unavailable*.
- If you rename an input in the options, the start volume entity shows the new name after the integration is reloaded.
- **Fixed volume is only learned when you switch to the input.** The amplifier reports whether the volume is fixed for the input that is selected, not for the other inputs, so Hegel Connect cannot read it for all inputs at startup. The start volume entity of such an input looks normal until Home Assistant has switched to it once; from then on it is *unavailable* and a call to it is refused. The binary sensor *Fixed volume* shows it for the current input.
