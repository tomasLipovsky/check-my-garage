# Garage Door Monitor for OrangePi PC

A Python script that monitors GPIO switches connected to your OrangePi PC to detect garage door state and sends push notifications via ntfy.sh for suspicious activity.

## Features

- 🔄 **Continuous Monitoring**: Periodically checks GPIO switch state
- 🌙 **Night Alerts**: Detects suspicious door openings during configured hours (default: 10 PM - 6 AM)
- ⏱️ **Long Open Alerts**: Notifies if door is left open too long (default: 10 minutes)
- 🔔 **Push Notifications**: Uses ntfy.sh for reliable push notifications to your phone
- 🔒 **Debouncing**: Implements switch debouncing to avoid false triggers
- 📊 **Smart Notifications**: Prevents spam with minimum intervals between alerts
- 🔁 **Auto-restart**: Can run as systemd service with automatic restart

## Requirements

- OrangePi PC (or compatible board)
- Python 3
- pyA20 GPIO library (already in folder)
- requests library
- GPIO switch(es) connected to your board
- ntfy.sh account (free)

## Installation

1. **Install dependencies:**
   ```bash
   pip3 install requests
   ```

2. **Configure the script:**
   Edit `garage_door_monitor.py` and adjust the configuration section (lines 15-30):
   - `DOOR_SWITCH_PIN`: Set to your GPIO pin (e.g., `connector.gpio1p0`)
   - `NTFY_TOPIC`: Set to your unique ntfy.sh topic
   - `SUSPICIOUS_HOURS_START` and `SUSPICIOUS_HOURS_END`: Set your alert time range
   - `OPEN_STATE` and `CLOSED_STATE`: Adjust based on your switch type (NO/NC)

3. **Run the setup script:**
   ```bash
   chmod +x setup_garage_monitor.sh
   ./setup_garage_monitor.sh
   ```

## GPIO Pin Reference

OrangePi PC GPIO pins (connector notation):
- `connector.gpio1p0` = PA0 (Port A, Pin 0)
- `connector.gpio1p1` = PA1
- `connector.gpio1p7` = PA7
- `connector.gpio2p0` = PC0 (Port C, Pin 0)
- etc.

Refer to your OrangePi PC pinout diagram to identify the physical pin numbers.

## Usage

### Manual Testing

Run the script manually to test:
```bash
sudo python3 garage_door_monitor.py
```

Press `Ctrl+C` to stop.

### Install as System Service

To run automatically on boot:

```bash
# Copy service file
sudo cp /tmp/garage-monitor.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable garage-monitor
sudo systemctl start garage-monitor

# Check status
sudo systemctl status garage-monitor

# View logs
sudo journalctl -u garage-monitor -f
```

### Stop the Service

```bash
sudo systemctl stop garage-monitor
sudo systemctl disable garage-monitor
```

## Notification Setup

### On Your Phone:

1. **Install ntfy app** (available on Android and iOS)
2. **Subscribe to your topic**: 
   - Open the app
   - Tap "+" to add a subscription
   - Enter your topic name (e.g., `your-garage-topic`)

### On Web Browser:

Visit: `https://ntfy.sh/your-garage-topic`

## Notification Types

The script sends different notifications based on events:

- ✅ **Monitor Started**: Confirmation when monitoring begins
- 🚪 **Door Opened**: Normal door opening during regular hours
- 🚨 **Suspicious Activity**: Door opened during suspicious hours (urgent)
- ⚠️ **Door Open Too Long**: Door left open beyond threshold (warning)
- 🔒 **Door Closed**: Door closed confirmation with open duration
- ❌ **Monitor Error**: System error notification (urgent)

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `CHECK_INTERVAL` | 2 seconds | Time between GPIO checks |
| `DEBOUNCE_TIME` | 1.0 seconds | Confirmation delay for state changes |
| `SUSPICIOUS_HOURS_START` | 22 (10 PM) | Start of suspicious time range |
| `SUSPICIOUS_HOURS_END` | 6 (6 AM) | End of suspicious time range |
| `LONG_OPEN_THRESHOLD` | 600 seconds | Time before "too long" alert |
| `OPEN_STATE` | 1 (HIGH) | GPIO value when door is open |
| `min_notification_interval` | 300 seconds | Min time between duplicate alerts |

## Switch Wiring

Typical wiring for a magnetic door switch:

```
GPIO Pin ----[Switch]---- GND

With internal pull-up:
- Door closed: Switch closed → GPIO LOW (0)
- Door open: Switch open → GPIO HIGH (1)
```

Adjust `OPEN_STATE` and `CLOSED_STATE` based on your switch type:
- **Normally Open (NO)**: Open state = 1, Closed state = 0
- **Normally Closed (NC)**: Open state = 0, Closed state = 1

## Troubleshooting

### Script won't run
- Ensure you're running as root: `sudo python3 garage_door_monitor.py`
- Check GPIO library is installed: `cd orangepi_PC_gpio_pyH3-master && sudo python3 setup.py install`

### No notifications received
- Test ntfy.sh: `curl -d "Test message" https://ntfy.sh/your-topic`
- Check internet connectivity
- Verify NTFY_TOPIC is unique and correctly set
- Check phone app is subscribed to correct topic

### False triggers
- Increase `DEBOUNCE_TIME` (e.g., to 2.0 seconds)
- Check switch connections and wiring
- Verify correct pin number and pull-up/down configuration

### GPIO errors
- Verify pin number matches your physical wiring
- Check permissions (must run as root)
- Ensure no other process is using the same GPIO pin

## Security Notes

- Keep your ntfy.sh topic name unique and private
- Consider running your own ntfy.sh server for privacy
- The script must run as root to access GPIO

## License

MIT License - Feel free to modify and use as needed.
