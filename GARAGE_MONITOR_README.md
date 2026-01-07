# Garage Door Monitor with Arduino Nano

A Python script that monitors two IR sensors connected to Arduino Nano via USB to detect garage door state and sends push notifications via ntfy.sh for suspicious activity.

## Features

- 🔄 **Continuous Monitoring**: Periodically checks sensor state via Arduino
- 🌙 **Night Alerts**: Detects suspicious door openings during configured hours (default: 10 PM - 6 AM)
- ⏱️ **Long Open Alerts**: Notifies if door is left open too long (default: 10 minutes)
- 🚪 **Partial Position Detection**: Alerts if door gets stuck in partial position
- 🔔 **Push Notifications**: Uses ntfy.sh for reliable push notifications to your phone
- 🔧 **YAML Configuration**: Easy configuration via config.yaml file
- 🔒 **Debouncing**: Implements sensor debouncing to avoid false triggers (in Arduino)
- 📊 **Smart Notifications**: Prevents spam with minimum intervals between alerts
- 🔁 **Auto-restart**: Can run as systemd service with automatic restart

## Architecture

The system consists of two components:

1. **Arduino Nano**: Reads two IR sensors and sends data via USB serial
2. **Python Script**: Processes sensor data and sends notifications

```
[IR Sensor Open] ──┐
                   ├──> [Arduino Nano] ──USB──> [Python Script] ──> [ntfy.sh]
[IR Sensor Closed]─┘
```

## Requirements

### Hardware
- Arduino Nano (or clone)
- 2x 3-pin IR Obstacle Sensors
- USB cable (Arduino to computer)
- Computer/Server running Linux

### Software
- Python 3
- Arduino IDE or Arduino CLI
- pyserial library
- pyyaml library
- requests library

## Installation

### 1. Install Python Dependencies

```bash
pip3 install pyserial pyyaml requests
```

### 2. Upload Arduino Sketch

#### Option A: Using Arduino CLI (Recommended)

```bash
# Install Arduino CLI
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

# Add to PATH
export PATH="$HOME/bin:$PATH"

# Install Arduino AVR boards
arduino-cli core update-index
arduino-cli core install arduino:avr

# Compile and upload
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328old garage-door-monitor-arduino/
arduino-cli upload --fqbn arduino:avr:nano:cpu=atmega328old --port /dev/ttyUSB0 garage-door-monitor-arduino/
```

#### Option B: Using Arduino Community Edition Extension (VS Code)

1. Install "Arduino Community Edition" extension in VS Code
2. Open `garage-door-monitor-arduino.ino`
3. Select Board: Arduino Nano
4. Select Processor: ATmega328P (Old Bootloader) for clones
5. Select Port: /dev/ttyUSB0 or /dev/ttyACM0
6. Click Upload

### 3. Configure the Monitor

Edit `config.yaml`:

```yaml
arduino:
  port: "/dev/ttyUSB0"  # Your Arduino port
  baud_rate: 9600
  sensor_triggered_state: 1  # 1 = obstacle detected

notifications:
  topic: "your-unique-topic"  # Change this!
  server: "https://ntfy.sh"

alerts:
  enable_night_alerts: true
  suspicious_hours_start: 22  # 10 PM
  suspicious_hours_end: 6     # 6 AM
```

### 4. Test the Setup

```bash
# Test Arduino output
timeout 5 cat /dev/ttyUSB0

# Run Python script
python3 garage_door_monitor_v2.py
```

## Hardware Setup

### IR Sensor Wiring

Each 3-pin IR sensor connects to Arduino:

**Sensor 1 (Fully Open Position):**
- VCC → 5V (Arduino)
- GND → GND (Arduino)
- OUT → D2 (Arduino Digital Pin 2)

**Sensor 2 (Fully Closed Position):**
- VCC → 5V (Arduino)
- GND → GND (Arduino)
- OUT → D3 (Arduino Digital Pin 3)

### Arduino Nano Pinout Reference

```
                     Arduino Nano
                   ┌──────────────┐
                   │  USB Port    │
                   └──────────────┘
    ┌────────────────────────────────────────┐
    │ D13                             D12    │
    │ 3V3                             D11    │
    │ REF                             D10    │
    │ A0                              D9     │
    │ A1                              D8     │
    │ A2                              D7     │
    │ A3                              D6     │
    │ A4                              D5     │
    │ A5                              D4     │
    │ A6                              D3  ◄── Closed Sensor OUT
    │ A7                              D2  ◄── Open Sensor OUT
    │ 5V  ◄─── Sensor VCC             GND ◄── Sensor GND
    │ RST                             RST │
    │ GND                             RX0 │
    │ VIN                             TX1 │
    └────────────────────────────────────────┘
```

### IR Sensor Behavior

- **Object detected** (door present) → OUT = LOW (0)
- **No object** (door not there) → OUT = HIGH (1)

### Door Position Logic

| Open Sensor | Closed Sensor | Door State |
|-------------|---------------|------------|
| 1 (object)  | 0 (no object) | Fully Open |
| 0 (no object)| 1 (object)   | Fully Closed|
| 0 (no object)| 0 (no object)| Partially Open|
| 1 (object)  | 1 (object)    | Unknown/Error|

## Configuration (config.yaml)

### Arduino Section
```yaml
arduino:
  port: "/dev/ttyUSB0"        # Serial port (auto-detect if empty)
  baud_rate: 9600             # Must match Arduino sketch
  timeout: 2                  # Serial timeout in seconds
  sensor_triggered_state: 1   # 1 for HIGH when triggered, 0 for LOW
```

### Notifications Section
```yaml
notifications:
  topic: "garage-monitor-xyz"  # Your unique ntfy.sh topic
  server: "https://ntfy.sh"    # Or your own ntfy server
  min_interval: 300            # Min seconds between duplicate alerts
```

### Monitoring Section
```yaml
monitoring:
  check_interval: 2      # Seconds between checks
  debounce_time: 1.0     # Seconds to confirm state change
```

### Alerts Section
```yaml
alerts:
  enable_night_alerts: true
  enable_long_open_alerts: true
  enable_partial_alerts: true
  suspicious_hours_start: 22    # 10 PM
  suspicious_hours_end: 6       # 6 AM
  long_open_threshold: 600      # 10 minutes
  partial_position_threshold: 30 # 30 seconds
```

### Logging Section
```yaml
logging:
  log_file: "/opt/garage-monitor/garage-monitor.log"
  log_max_size: 10485760   # 10 MB
  log_backup_count: 5      # Keep 5 old logs
```

## Usage

### Manual Testing

```bash
# Run the script
python3 garage_door_monitor_v2.py

# Press Ctrl+C to stop
```

### Install as System Service

```bash
# Run setup script
chmod +x setup_garage_monitor.sh
./setup_garage_monitor.sh

# Or manually:
sudo cp garage-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable garage-monitor
sudo systemctl start garage-monitor

# Check status
sudo systemctl status garage-monitor

# View logs
sudo journalctl -u garage-monitor -f
```

## Notification Setup

### On Your Phone

1. Install **ntfy** app (Android/iOS)
2. Subscribe to your topic
3. Test: `curl -d "Test" https://ntfy.sh/your-topic`

### Notification Types

- ✅ **Monitor Started**: System ready
- 🚪 **Door Opened**: Normal opening
- 🚨 **Suspicious Activity**: Night opening (urgent)
- ⚠️ **Door Open Too Long**: Warning after threshold
- ⚠️ **Door Stuck**: Partial position too long
- 🔒 **Door Closed**: Closed confirmation
- ❓ **Unknown State**: Both sensors triggered
- ❌ **Monitor Error**: System error (urgent)

## Troubleshooting

### Arduino Not Found

```bash
# List USB devices
ls -la /dev/ttyUSB* /dev/ttyACM*

# Check dmesg
dmesg | grep -i tty | tail -10

# Fix brltty conflict (common with Arduino clones)
sudo systemctl stop brltty-udev.service
sudo systemctl mask brltty-udev.service
sudo systemctl disable brltty.service
```

### Permission Denied on Serial Port

```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Logout and login again for changes to take effect
```

### Script Won't Start

```bash
# Check Python dependencies
pip3 list | grep -E "pyserial|pyyaml|requests"

# Test Arduino connection
timeout 5 cat /dev/ttyUSB0

# Check config file
cat config.yaml
```

### No Notifications Received

```bash
# Test ntfy.sh manually
curl -d "Test message" https://ntfy.sh/your-topic

# Check internet connectivity
ping -c 3 ntfy.sh

# Verify topic in config.yaml
grep topic config.yaml
```

### False Triggers

- Adjust sensor position and angle
- Increase `debounce_time` in config.yaml
- Check sensor power supply (stable 5V)
- Verify wiring connections

### Both Sensors Triggered (Unknown State)

- Sensors too close together
- Door blocking both sensors simultaneously
- Check sensor placement and adjust positions

### Arduino Clone Upload Issues

- Try "Old Bootloader" processor setting
- If that fails, try "New Bootloader"
- Use slower baud rate: `-b 57600` flag with avrdude
- Check USB cable quality

## Project Files

```
check-my-garage/
├── config.yaml                          # Configuration file
├── garage_door_monitor_v2.py           # Main Python script (Arduino version)
├── garage_door_monitor.py              # Original OrangePi version
├── garage-door-monitor-arduino/
│   └── garage-door-monitor-arduino.ino # Arduino sketch
├── setup_garage_monitor.sh             # Setup script
├── GARAGE_MONITOR_README.md            # This file
└── garage_config_example.py            # Old config example
```

## Arduino Sketch Details

The Arduino sketch (`garage-door-monitor-arduino.ino`):

- Reads two digital pins (D2, D3) with debouncing
- Sends sensor states via serial: `"open,closed\n"` format
- Example output: `1,0` (open detected, closed not detected)
- Updates every 500ms
- Built-in LED blinks on state changes
- Startup: LED flashes 3 times

### Serial Protocol

**Format:** `open_value,closed_value\n`

**Examples:**
- `1,0` → Open sensor triggered, closed not triggered
- `0,1` → Open sensor not triggered, closed triggered  
- `0,0` → Neither sensor triggered (door in between)
- `1,1` → Both sensors triggered (error/misconfiguration)

## Advanced Configuration

### Using Custom ntfy.sh Server

Edit `config.yaml`:
```yaml
notifications:
  server: "https://your-ntfy-server.com"
  topic: "your-topic"
```

### Adjusting Sensor Sensitivity

In Arduino sketch, modify:
```cpp
const int DEBOUNCE_READS = 5;      // More reads = more stable
const int DEBOUNCE_DELAY = 10;     // Longer delay = more filtering
```

### Custom Alert Times

```yaml
alerts:
  suspicious_hours_start: 20  # 8 PM
  suspicious_hours_end: 8     # 8 AM
```

### Logging to Custom Location

```yaml
logging:
  log_file: "/home/user/logs/garage.log"
```

## Security & Privacy

- Keep ntfy.sh topic unique and private
- Consider self-hosting ntfy.sh server
- Use authentication if running on public network
- Arduino USB connection is local (not exposed to network)
- Log files may contain timestamps of door activity

## Future Improvements

- [ ] Web dashboard for monitoring
- [ ] Multiple door support
- [ ] Integration with Home Assistant
- [ ] Email notifications
- [ ] Door open/close statistics
- [ ] Mobile app integration

## License

MIT License - Feel free to modify and use as needed.
