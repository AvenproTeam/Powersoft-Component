"""Constants for the Powersoft integration."""
from __future__ import annotations

DOMAIN = "powersoft"
MANUFACTURER = "Powersoft"

CONF_NUM_CHANNELS = "num_channels"

DEFAULT_PORT = 80
DEFAULT_NUM_CHANNELS = 4  # Quattrocanali
DEFAULT_SCAN_INTERVAL = 5  # seconds
DEFAULT_MODEL = "Amplifier"

# Services
SERVICE_LOAD_SNAPSHOT = "load_snapshot"
SERVICE_SET_MATRIX_GAIN = "set_matrix_gain"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_SNAPSHOT = "snapshot"
ATTR_INPUT = "input"
ATTR_OUTPUT = "output"
ATTR_GAIN = "gain"
