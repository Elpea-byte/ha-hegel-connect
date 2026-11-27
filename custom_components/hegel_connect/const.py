"""Constants for Hegel Connect."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "hegel_connect"
MANUFACTURER = "Hegel"

# Kept here (not in __init__.py) so adding a platform only touches this file.
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Models on the StreamUnlimited platform. Other brands (e.g. Onkyo) announce the
# same mDNS service, so discovery only accepts these.
SUPPORTED_MODELS = ("H150", "H200", "H400", "H600")

# Older models (IP control on TCP 50001) are served by the built-in integration.
CORE_HEGEL_URL = "https://www.home-assistant.io/integrations/hegel/"

# Shown after setup for a model the maintainer has not tested (everything but the H150).
README_OPTIONAL_URL = "https://github.com/Elpea-byte/ha-hegel-connect#first-steps"
MODEL_REPORT_URL = "https://github.com/Elpea-byte/ha-hegel-connect/issues/new?template=model_report.yml"
TESTED_MODEL = "H150"

CONF_MAX_VOLUME = "max_volume"
# Options: inputs hidden from the source list (by index, as text) and own names
# for inputs ({index: name}). The amplifier's own names stay in use internally.
CONF_HIDDEN_SOURCES = "hidden_sources"
CONF_SOURCE_NAMES = "source_names"
# Saved in the config entry: inputs, volume range and firmware, so the
# integration can start while the amplifier is off at the mains.
CACHE_KEY = "cache"
DEFAULT_MAX_VOLUME = 100
# Saved volumes per input ("remember volume"), kept in the Home Assistant storage.
VOLUMES_STORAGE_VERSION = 1
VOLUMES_SAVE_DELAY = 10

# Push: how long the amplifier keeps a poll request open, and the wait after errors.
POLL_TIMEOUT = 30
# Radio favorites only change in the Hegel Control app: re-read now and then.
FAVORITES_INTERVAL = timedelta(hours=6)
# An empty or failed read of the favorites is tried again this often, this many seconds apart
# (the amplifier can answer before its cloud part is ready, just after power-on).
FAVORITES_RETRIES = 3
# A repair issue when the amplifier has not answered this long (longer than a night or weekend without power).
UNREACHABLE_ISSUE_AFTER = timedelta(hours=24)
FAVORITES_RETRY_DELAY = 45
# Stations started from Home Assistant by path that play can restart after a stop.
RADIO_PATHS_KEPT = 20
# The amplifier does not report a change of its auto-standby setting: read it again now and then (one small read).
AUTO_STANDBY_INTERVAL = timedelta(minutes=15)
BACKOFF_START = 5
BACKOFF_MAX = 60

# Source switching: wait for the amplifier to be on, then verify the input stuck.
POWER_ON_WAIT = 15
SOURCE_VERIFY_WAIT = 4
SOURCE_ATTEMPTS = 3
