"""Constants for Hegel Connect."""

from __future__ import annotations

DOMAIN = "hegel_connect"
MANUFACTURER = "Hegel"

CONF_MAX_VOLUME = "max_volume"
DEFAULT_MAX_VOLUME = 100

# Push: how long the amplifier keeps a poll request open, and the wait after errors.
POLL_TIMEOUT = 30
BACKOFF_START = 5
BACKOFF_MAX = 60

# Source switching: wait for the amplifier to be on, then verify the input stuck.
POWER_ON_WAIT = 15
SOURCE_VERIFY_WAIT = 4
SOURCE_ATTEMPTS = 3
