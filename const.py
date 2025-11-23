"""Constants for the Powersoft integration."""

DOMAIN = "powersoft"

# Configuration
DEFAULT_PORT = 80
DEFAULT_UDP_PORT = 8002
DEFAULT_SCAN_INTERVAL = 10

# Attributes
ATTR_CHANNEL = "channel"
ATTR_GAIN = "gain"
ATTR_MUTE = "mute"
ATTR_POLARITY = "polarity"
ATTR_DELAY = "delay"
ATTR_TEMPERATURE = "temperature"
ATTR_IMPEDANCE = "impedance"
ATTR_VOLTAGE = "voltage"
ATTR_CURRENT = "current"
ATTR_POWER = "power"
ATTR_CLIP = "clip"
ATTR_SIGNAL_PRESENT = "signal_present"
ATTR_ALARM = "alarm"
ATTR_MODEL = "model"
ATTR_SERIAL = "serial"
ATTR_FIRMWARE = "firmware"

# Services
SERVICE_SET_GAIN = "set_gain"
SERVICE_SET_MUTE = "set_mute"
SERVICE_SET_POLARITY = "set_polarity"
SERVICE_SET_DELAY = "set_delay"
SERVICE_POWER_ON = "power_on"
SERVICE_POWER_OFF = "power_off"
SERVICE_LOAD_SNAPSHOT = "load_snapshot"

# API Endpoints
ENDPOINT_STATUS = "/status"
ENDPOINT_CONTROL = "/control"
ENDPOINT_CHANNELS = "/channels"
ENDPOINT_SYSTEM = "/system"
ENDPOINT_SNAPSHOTS = "/snapshots"
