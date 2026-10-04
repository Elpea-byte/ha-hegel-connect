"""Constants for Hegel Connect."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "hegel_connect"
MANUFACTURER = "Hegel"

# Kept here (not in __init__.py) so adding a platform only touches this file.
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SENSOR]

# Models on the StreamUnlimited platform. Other brands (e.g. Onkyo) announce the
# same mDNS service, so discovery only accepts these.
SUPPORTED_MODELS = ("H150", "H400", "H600")

# Older models (IP control on TCP 50001) are served by the built-in integration.
CORE_HEGEL_URL = "https://www.home-assistant.io/integrations/hegel/"

CONF_MAX_VOLUME = "max_volume"
# Saved in the config entry: inputs, volume range and firmware, so the
# integration can start while the amplifier is off at the mains.
CACHE_KEY = "cache"
DEFAULT_MAX_VOLUME = 100

# Push: how long the amplifier keeps a poll request open, and the wait after errors.
POLL_TIMEOUT = 30
BACKOFF_START = 5
BACKOFF_MAX = 60

# Source switching: wait for the amplifier to be on, then verify the input stuck.
POWER_ON_WAIT = 15
SOURCE_VERIFY_WAIT = 4
SOURCE_ATTEMPTS = 3
