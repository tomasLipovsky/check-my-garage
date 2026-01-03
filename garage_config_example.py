# Garage Door Monitor Configuration
# Copy this to config.py and adjust values

# GPIO Configuration
# Check your OrangePi PC pinout and adjust accordingly
# Example pins (connector numbering):
# - connector.gpio1p0 = Port PA0
# - connector.gpio1p1 = Port PA1  
# - connector.gpio1p7 = Port PA7
DOOR_SWITCH_PIN = "connector.gpio1p0"

# Ntfy.sh Configuration
# Create your unique topic at https://ntfy.sh
NTFY_TOPIC = "my-unique-garage-topic-12345"
NTFY_SERVER = "https://ntfy.sh"

# Monitoring Settings
CHECK_INTERVAL = 2  # Seconds between GPIO checks
DEBOUNCE_TIME = 1.0  # Seconds to confirm state change

# Alert Configuration
ENABLE_NIGHT_ALERTS = True
SUSPICIOUS_HOURS_START = 22  # 10 PM
SUSPICIOUS_HOURS_END = 6     # 6 AM

ENABLE_LONG_OPEN_ALERTS = True
LONG_OPEN_THRESHOLD = 600  # 10 minutes

# Switch Logic (depends on your wiring)
# If your switch is normally closed (NC): OPEN_STATE = 0
# If your switch is normally open (NO): OPEN_STATE = 1
OPEN_STATE = 1
CLOSED_STATE = 0
