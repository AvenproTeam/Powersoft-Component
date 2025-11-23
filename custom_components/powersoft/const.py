"""Constants for the Powersoft integration."""

DOMAIN = "powersoft"

# Configuration
DEFAULT_PORT = 80
DEFAULT_UDP_PORT = 8002
DEFAULT_SCAN_INTERVAL = 5  # Reduced to 5 seconds for more responsive updates

# Number of channels for Quattrocanali 8804
NUM_CHANNELS = 4

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
ATTR_SNAPSHOT = "snapshot"

# Services
SERVICE_SET_GAIN = "set_gain"
SERVICE_SET_MUTE = "set_mute"
SERVICE_SET_POLARITY = "set_polarity"
SERVICE_SET_DELAY = "set_delay"
SERVICE_POWER_ON = "power_on"
SERVICE_POWER_OFF = "power_off"
SERVICE_LOAD_SNAPSHOT = "load_snapshot"
SERVICE_SET_MATRIX_GAIN = "set_matrix_gain"

# Powersoft API paths (for reference)
API_BASE_PATH = "/Device/Audio/Presets/Live"
API_OUTPUT_PROCESS = f"{API_BASE_PATH}/OutputProcess/Channels"
API_INPUT_MATRIX = f"{API_BASE_PATH}/InputMatrix/Channels"
API_SNAPSHOTS = f"{API_BASE_PATH}/ReadOnly/SnapshotSlotId"