#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garage Door Monitor with Arduino Nano
Monitors two switches via Arduino Nano connected via USB and sends notifications via ntfy.sh
"""

import os
import sys
import time
import requests
import logging
import serial
import serial.tools.list_ports
import yaml
from datetime import datetime

# ==================== CONFIGURATION ====================

# Default configuration values (will be overridden by config.yaml)
SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUD_RATE = 9600
SERIAL_TIMEOUT = 2
SENSOR_TRIGGERED_STATE = 1

NTFY_TOPIC = "topic"
NTFY_SERVER = "https://ntfy.sh"

CHECK_INTERVAL = 2
DEBOUNCE_TIME = 1.0

LOG_FILE = "/opt/garage-monitor/garage-monitor.log"
LOG_MAX_SIZE = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5

SUSPICIOUS_HOURS_START = 22
SUSPICIOUS_HOURS_END = 6
ENABLE_NIGHT_ALERTS = True
ENABLE_LONG_OPEN_ALERTS = True
ENABLE_PARTIAL_ALERTS = True
LONG_OPEN_THRESHOLD = 600
PARTIAL_POSITION_THRESHOLD = 30

# Door States
STATE_FULLY_CLOSED = "closed"
STATE_FULLY_OPEN = "open"
STATE_PARTIALLY_OPEN = "partial"
STATE_UNKNOWN = "unknown"

# ==================== LOAD CONFIGURATION ====================

def load_config(config_file='config.yaml'):
    """Load configuration from YAML file"""
    global SERIAL_PORT, SERIAL_BAUD_RATE, SERIAL_TIMEOUT, SENSOR_TRIGGERED_STATE
    global NTFY_TOPIC, NTFY_SERVER, CHECK_INTERVAL, DEBOUNCE_TIME
    global LOG_FILE, LOG_MAX_SIZE, LOG_BACKUP_COUNT
    global SUSPICIOUS_HOURS_START, SUSPICIOUS_HOURS_END
    global ENABLE_NIGHT_ALERTS, ENABLE_LONG_OPEN_ALERTS, ENABLE_PARTIAL_ALERTS
    global LONG_OPEN_THRESHOLD, PARTIAL_POSITION_THRESHOLD
    global min_notification_interval
    
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Arduino settings
        if 'arduino' in config:
            SERIAL_PORT = config['arduino'].get('port', SERIAL_PORT)
            SERIAL_BAUD_RATE = config['arduino'].get('baud_rate', SERIAL_BAUD_RATE)
            SERIAL_TIMEOUT = config['arduino'].get('timeout', SERIAL_TIMEOUT)
            SENSOR_TRIGGERED_STATE = config['arduino'].get('sensor_triggered_state', SENSOR_TRIGGERED_STATE)
        
        # Notification settings
        if 'notifications' in config:
            NTFY_TOPIC = config['notifications'].get('topic', NTFY_TOPIC)
            NTFY_SERVER = config['notifications'].get('server', NTFY_SERVER)
            min_notification_interval = config['notifications'].get('min_interval', 300)
        
        # Monitoring settings
        if 'monitoring' in config:
            CHECK_INTERVAL = config['monitoring'].get('check_interval', CHECK_INTERVAL)
            DEBOUNCE_TIME = config['monitoring'].get('debounce_time', DEBOUNCE_TIME)
        
        # Alert settings
        if 'alerts' in config:
            ENABLE_NIGHT_ALERTS = config['alerts'].get('enable_night_alerts', ENABLE_NIGHT_ALERTS)
            ENABLE_LONG_OPEN_ALERTS = config['alerts'].get('enable_long_open_alerts', ENABLE_LONG_OPEN_ALERTS)
            ENABLE_PARTIAL_ALERTS = config['alerts'].get('enable_partial_alerts', ENABLE_PARTIAL_ALERTS)
            SUSPICIOUS_HOURS_START = config['alerts'].get('suspicious_hours_start', SUSPICIOUS_HOURS_START)
            SUSPICIOUS_HOURS_END = config['alerts'].get('suspicious_hours_end', SUSPICIOUS_HOURS_END)
            LONG_OPEN_THRESHOLD = config['alerts'].get('long_open_threshold', LONG_OPEN_THRESHOLD)
            PARTIAL_POSITION_THRESHOLD = config['alerts'].get('partial_position_threshold', PARTIAL_POSITION_THRESHOLD)
        
        # Logging settings
        if 'logging' in config:
            LOG_FILE = config['logging'].get('log_file', LOG_FILE)
            LOG_MAX_SIZE = config['logging'].get('log_max_size', LOG_MAX_SIZE)
            LOG_BACKUP_COUNT = config['logging'].get('log_backup_count', LOG_BACKUP_COUNT)
        
        print(f"✓ Configuration loaded from {config_file}")
        return True
        
    except FileNotFoundError:
        print(f"⚠ Configuration file {config_file} not found, using defaults")
        return False
    except Exception as e:
        print(f"⚠ Error loading configuration: {e}, using defaults")
        return False

# ==================== GLOBAL STATE ====================

door_state = None  # Current door state
door_opened_at = None  # Timestamp when door was last fully opened
door_partial_at = None  # Timestamp when door entered partial state
last_notification_time = {}  # Track last notification time for each type
min_notification_interval = 300  # Don't spam - minimum 5 minutes between same notifications
logger = None  # Logger instance
serial_connection = None  # Serial connection to Arduino


# ==================== LOGGING SETUP ====================

def setup_logging():
    """Setup logging to file and console"""
    global logger
    
    # Create logger
    logger = logging.getLogger('GarageMonitor')
    logger.setLevel(logging.INFO)
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_SIZE,
        backupCount=LOG_BACKUP_COUNT
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def log_info(message):
    """Log info message"""
    if logger:
        logger.info(message)
    else:
        print(f"[{get_timestamp()}] {message}")


def log_warning(message):
    """Log warning message"""
    if logger:
        logger.warning(message)
    else:
        print(f"[{get_timestamp()}] WARNING: {message}")


def log_error(message):
    """Log error message"""
    if logger:
        logger.error(message)
    else:
        print(f"[{get_timestamp()}] ERROR: {message}")


# ==================== HELPER FUNCTIONS ====================

def send_notification(title, message, priority="default", tags=None):
    """
    Send notification via ntfy.sh
    Priority: min, low, default, high, urgent
    Tags: list of emojis or tag names
    """
    global last_notification_time
    
    # Prevent notification spam
    notification_key = f"{title}:{message}"
    current_time = time.time()
    
    if notification_key in last_notification_time:
        if current_time - last_notification_time[notification_key] < min_notification_interval:
            log_info(f"Skipping notification (too soon): {title}")
            return False
    
    try:
        headers = {
            "Title": title,
            "Priority": priority,
        }
        
        if tags:
            headers["Tags"] = ",".join(tags)
        
        response = requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            last_notification_time[notification_key] = current_time
            log_info(f"✓ Notification sent: {title}")
            return True
        else:
            log_error(f"Failed to send notification: {response.status_code}")
            return False
            
    except Exception as e:
        log_error(f"Error sending notification: {e}")
        return False


def get_timestamp():
    """Get formatted timestamp for logging"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_suspicious_time():
    """Check if current time is during suspicious hours (e.g., night time)"""
    current_hour = datetime.now().hour
    
    if SUSPICIOUS_HOURS_START > SUSPICIOUS_HOURS_END:
        # Range crosses midnight (e.g., 22-6)
        return current_hour >= SUSPICIOUS_HOURS_START or current_hour < SUSPICIOUS_HOURS_END
    else:
        # Range within same day
        return SUSPICIOUS_HOURS_START <= current_hour < SUSPICIOUS_HOURS_END


def read_door_state():
    """Read the current state of both door sensors from Arduino via USB"""
    global serial_connection
    
    if not serial_connection or not serial_connection.is_open:
        log_error("Serial connection not available")
        return STATE_UNKNOWN
    
    try:
        # Clear input buffer
        serial_connection.reset_input_buffer()
        
        # Read line from Arduino
        line = serial_connection.readline().decode('utf-8', errors='ignore').strip()
        
        if not line:
            return door_state if door_state else STATE_UNKNOWN
        
        # Check if Arduino sends state directly (e.g., "OPEN", "CLOSED", "PARTIAL")
        line_upper = line.upper()
        if "OPEN" in line_upper and "CLOSED" not in line_upper:
            return STATE_FULLY_OPEN
        elif "CLOSED" in line_upper:
            return STATE_FULLY_CLOSED
        elif "PARTIAL" in line_upper:
            return STATE_PARTIALLY_OPEN
        
        # Parse sensor values format: "open_sensor,closed_sensor" (e.g., "1,0")
        parts = line.split(',')
        if len(parts) >= 2:
            try:
                open_sensor = int(parts[0].strip())
                closed_sensor = int(parts[1].strip())
                
                is_fully_open = (open_sensor == SENSOR_TRIGGERED_STATE)
                is_fully_closed = (closed_sensor == SENSOR_TRIGGERED_STATE)
                
                # Determine door state based on both sensors
                if is_fully_closed and not is_fully_open:
                    return STATE_FULLY_CLOSED
                elif is_fully_open and not is_fully_closed:
                    return STATE_FULLY_OPEN
                elif not is_fully_open and not is_fully_closed:
                    return STATE_PARTIALLY_OPEN
                else:
                    # Both sensors triggered
                    return STATE_UNKNOWN
            except ValueError:
                log_warning(f"Invalid sensor data format: {line}")
                return door_state if door_state else STATE_UNKNOWN
        
        log_warning(f"Unrecognized data from Arduino: {line}")
        return door_state if door_state else STATE_UNKNOWN
        
    except serial.SerialException as e:
        log_error(f"Serial read error: {e}")
        return STATE_UNKNOWN
    except Exception as e:
        log_error(f"Error reading sensor state: {e}")
        return STATE_UNKNOWN


def check_long_open():
    """Check if door has been open for too long"""
    global door_opened_at
    
    if door_opened_at and ENABLE_LONG_OPEN_ALERTS:
        open_duration = time.time() - door_opened_at
        if open_duration >= LONG_OPEN_THRESHOLD:
            minutes = int(open_duration / 60)
            send_notification(
                "⚠️ Garážová vrata otevřená příliš dlouho",
                f"Garážová vrata jsou plně otevřená již {minutes} minut!",
                priority="high",
                tags=["warning", "clock"]
            )
            # Reset to avoid repeated notifications
            door_opened_at = time.time()


def check_partial_position():
    """Check if door has been in partial position for too long"""
    global door_partial_at
    
    if door_partial_at and ENABLE_PARTIAL_ALERTS:
        partial_duration = time.time() - door_partial_at
        if partial_duration >= PARTIAL_POSITION_THRESHOLD:
            seconds = int(partial_duration)
            send_notification(
                "⚠️ Garážová vrata zaseknutá",
                f"Garážová vrata jsou částečně otevřená již {seconds} sekund!",
                priority="high",
                tags=["warning", "door"]
            )
            # Reset to avoid repeated notifications
            door_partial_at = time.time()


def handle_door_fully_opened():
    """Handle door fully opened event"""
    global door_opened_at, door_partial_at
    
    door_opened_at = time.time()
    door_partial_at = None
    time_str = datetime.now().strftime("%H:%M")
    
    # Only send notification if it's suspicious time
    if ENABLE_NIGHT_ALERTS and is_suspicious_time():
        send_notification(
            "🚨 Podezřelá aktivita v garáži",
            f"Garážová vrata byla plně otevřena v {time_str} (neobvyklá doba)",
            priority="urgent",
            tags=["rotating_light", "warning"]
        )
    else:
        log_info(f"Door opened at {time_str} (normal hours, no notification)")


def handle_door_fully_closed():
    """Handle door fully closed event"""
    global door_opened_at, door_partial_at
    
    time_str = datetime.now().strftime("%H:%M")
    
    # Calculate how long it was not closed
    if door_opened_at:
        open_duration = time.time() - door_opened_at
        minutes = int(open_duration / 60)
        seconds = int(open_duration % 60)
        
        if minutes > 0:
            duration_str = f" (byla otevřená {minutes}m {seconds}s)"
        else:
            duration_str = f" (byla otevřená {seconds}s)"
        
        log_info(f"Door closed at {time_str}{duration_str}")
    else:
        log_info(f"Door closed at {time_str}")
    
    door_opened_at = None
    door_partial_at = None


def handle_door_partially_open():
    """Handle door in partial position"""
    global door_partial_at
    
    if door_partial_at is None:
        door_partial_at = time.time()
    
    time_str = datetime.now().strftime("%H:%M")
    log_info(f"Door partially open at {time_str}")


def handle_door_unknown():
    """Handle unknown door state (both sensors triggered)"""
    log_warning("Both sensors triggered - possible wiring issue")
    send_notification(
        "❓ Neznámý stav garážových vrat",
        "Oba senzory jsou aktivní - možný problém s kabeláží",
        priority="high",
        tags=["question", "warning"]
    )


def find_arduino_port():
    """Auto-detect Arduino Nano USB port"""
    log_info("Searching for Arduino Nano...")
    
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Check for Arduino Nano (common VID:PID combinations)
        # Arduino Nano: 2341:0043, 1a86:7523 (CH340), 0403:6001 (FTDI)
        if port.vid and port.pid:
            vid_pid = f"{port.vid:04x}:{port.pid:04x}"
            log_info(f"  Found device: {port.device} ({vid_pid}) - {port.description}")
            
            # Common Arduino identifiers
            if ("Arduino" in port.description or 
                "CH340" in port.description or
                "FTDI" in port.description or
                vid_pid in ["2341:0043", "1a86:7523", "0403:6001"]):
                log_info(f"  ✓ Arduino detected at {port.device}")
                return port.device
    
    log_warning("Arduino not found, available ports:")
    for port in ports:
        log_warning(f"  - {port.device}: {port.description}")
    
    return None


def init_serial_connection():
    """Initialize serial connection to Arduino"""
    global serial_connection
    
    # Determine serial port
    port = SERIAL_PORT
    if not port or port == "":
        port = find_arduino_port()
        if not port:
            log_error("Could not find Arduino. Please specify SERIAL_PORT manually.")
            return False
    
    try:
        log_info(f"Connecting to Arduino on {port} at {SERIAL_BAUD_RATE} baud...")
        serial_connection = serial.Serial(
            port=port,
            baudrate=SERIAL_BAUD_RATE,
            timeout=SERIAL_TIMEOUT,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE
        )
        
        # Wait for Arduino to reset and stabilize
        log_info("Waiting for Arduino to initialize...")
        time.sleep(2)
        
        # Clear any startup data
        serial_connection.reset_input_buffer()
        
        log_info("✓ Serial connection established")
        return True
        
    except serial.SerialException as e:
        log_error(f"Failed to open serial port {port}: {e}")
        return False
    except Exception as e:
        log_error(f"Error initializing serial connection: {e}")
        return False


def monitor_loop():
    """Main monitoring loop"""
    global door_state
    
    log_info("Starting garage door monitor...")
    log_info(f"  - Serial port: {SERIAL_PORT if SERIAL_PORT else 'Auto-detect'}")
    log_info(f"  - Baud rate: {SERIAL_BAUD_RATE}")
    log_info(f"  - Check interval: {CHECK_INTERVAL}s")
    log_info(f"  - Suspicious hours: {SUSPICIOUS_HOURS_START}:00 - {SUSPICIOUS_HOURS_END}:00")
    log_info(f"  - Long open threshold: {LONG_OPEN_THRESHOLD}s")
    log_info(f"  - Partial position threshold: {PARTIAL_POSITION_THRESHOLD}s")
    log_info(f"  - Ntfy topic: {NTFY_TOPIC}")
    log_info(f"  - Log file: {LOG_FILE}")
    log_info("")
    
    # Send startup notification
    send_notification(
        "✅ Monitor garáže spuštěn",
        "Systém monitorování garážových vrat je nyní aktivní (Arduino USB režim)",
        priority="low",
        tags=["white_check_mark"]
    )
    
    try:
        while True:
            current_state = read_door_state()
            
            # State change detection
            if door_state is None:
                # First reading - initialize state
                door_state = current_state
                state_desc = {
                    STATE_FULLY_CLOSED: "PLNĚ ZAVŘENÁ",
                    STATE_FULLY_OPEN: "PLNĚ OTEVŘENÁ",
                    STATE_PARTIALLY_OPEN: "ČÁSTEČNĚ OTEVŘENÁ",
                    STATE_UNKNOWN: "NEZNÁMÝ"
                }
                log_info(f"Initial state: Door is {state_desc.get(current_state, 'NEZNÁMÝ')}")
                
            elif current_state != door_state:
                # State changed - wait for debounce
                time.sleep(DEBOUNCE_TIME)
                
                # Verify state change
                confirmed_state = read_door_state()
                if confirmed_state != door_state:
                    old_state = door_state
                    door_state = confirmed_state
                    
                    if door_state == STATE_FULLY_OPEN:
                        log_info("🚪 Door FULLY OPENED")
                        handle_door_fully_opened()
                    elif door_state == STATE_FULLY_CLOSED:
                        log_info("🔒 Door FULLY CLOSED")
                        handle_door_fully_closed()
                    elif door_state == STATE_PARTIALLY_OPEN:
                        log_info("⏸️  Door PARTIALLY OPEN")
                        handle_door_partially_open()
                    elif door_state == STATE_UNKNOWN:
                        log_warning("❓ Door state UNKNOWN")
                        handle_door_unknown()
            
            # Check if door has been open too long
            if door_state == STATE_FULLY_OPEN:
                check_long_open()
            
            # Check if door has been partially open too long
            if door_state == STATE_PARTIALLY_OPEN:
                check_partial_position()
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        log_info("Monitoring stopped by user")
    except Exception as e:
        log_error(f"Error: {e}")
        send_notification(
            "❌ Chyba monitoru garáže",
            f"Monitorování zastaveno kvůli chybě: {str(e)}",
            priority="urgent",
            tags=["x", "warning"]
        )
    finally:
        if serial_connection and serial_connection.is_open:
            serial_connection.close()
            log_info("Serial connection closed")


# ==================== MAIN ====================

def main():
    """Main entry point"""
    
    # Load configuration first
    load_config()
    
    # Setup logging
    setup_logging()
    log_info("=" * 60)
    log_info("Garage Door Monitor Starting (Arduino USB Mode)")
    log_info("=" * 60)
    
    # Initialize serial connection to Arduino
    if not init_serial_connection():
        log_error("Failed to initialize serial connection")
        sys.exit(1)
    
    log_info("")
    
    # Start monitoring
    monitor_loop()


if __name__ == "__main__":
    main()
