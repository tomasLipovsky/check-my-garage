#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garage Door Monitor for OrangePi PC
Monitors two GPIO switches representing garage door positions and sends notifications via ntfy.sh
"""

import os
import sys
import time
import requests
import logging
from datetime import datetime
from pyA20.gpio import gpio
from pyA20.gpio import connector

# ==================== CONFIGURATION ====================

# GPIO Pin Configuration (adjust based on your wiring)
# Two sensors: one triggers when fully open, one when fully closed
FULLY_OPEN_SENSOR_PIN = connector.gpio1p0    # Sensor at fully open position
FULLY_CLOSED_SENSOR_PIN = connector.gpio1p1  # Sensor at fully closed position

# Ntfy.sh Configuration
NTFY_TOPIC = "check-my-garage-tli-2026-orca"  # Change this to your unique topic
NTFY_SERVER = "https://ntfy.sh"  # Use your own server if you have one

# Monitoring Configuration
CHECK_INTERVAL = 2  # Seconds between checks
DEBOUNCE_TIME = 1.0  # Seconds to wait before confirming state change

# Logging Configuration
LOG_FILE = "/home/tomas/Documents/Rodina/Tomas/development/check-my-garage/garage-monitor.log"
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5  # Keep 5 backup files

# Suspicious Activity Detection
SUSPICIOUS_HOURS_START = 22  # 10 PM
SUSPICIOUS_HOURS_END = 6     # 6 AM
ENABLE_NIGHT_ALERTS = True
ENABLE_LONG_OPEN_ALERTS = True
ENABLE_PARTIAL_ALERTS = True  # Alert if door stops in partial position
LONG_OPEN_THRESHOLD = 600    # 10 minutes in seconds
PARTIAL_POSITION_THRESHOLD = 30  # Alert if door stuck partially open for 30 seconds

# Sensor Configuration (adjust based on your switch wiring)
# Set to 1 if sensor is HIGH when triggered, 0 if LOW when triggered
SENSOR_TRIGGERED_STATE = 1  # GPIO HIGH (1) when sensor is triggered

# Door States
STATE_FULLY_CLOSED = "closed"
STATE_FULLY_OPEN = "open"
STATE_PARTIALLY_OPEN = "partial"
STATE_UNKNOWN = "unknown"

# ==================== GLOBAL STATE ====================

door_state = None  # Current door state
door_opened_at = None  # Timestamp when door was last fully opened
door_partial_at = None  # Timestamp when door entered partial state
last_notification_time = {}  # Track last notification time for each type
min_notification_interval = 300  # Don't spam - minimum 5 minutes between same notifications
logger = None  # Logger instance


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
    """Read the current state of both door sensors with debouncing"""
    # Read multiple times to debounce
    open_readings = []
    closed_readings = []
    
    for _ in range(3):
        open_reading = gpio.input(FULLY_OPEN_SENSOR_PIN)
        closed_reading = gpio.input(FULLY_CLOSED_SENSOR_PIN)
        open_readings.append(open_reading)
        closed_readings.append(closed_reading)
        time.sleep(0.1)
    
    # Use majority vote for stability
    is_fully_open = max(set(open_readings), key=open_readings.count) == SENSOR_TRIGGERED_STATE
    is_fully_closed = max(set(closed_readings), key=closed_readings.count) == SENSOR_TRIGGERED_STATE
    
    # Determine door state based on both sensors
    if is_fully_closed and not is_fully_open:
        return STATE_FULLY_CLOSED
    elif is_fully_open and not is_fully_closed:
        return STATE_FULLY_OPEN
    elif not is_fully_open and not is_fully_closed:
        return STATE_PARTIALLY_OPEN
    else:
        # Both sensors triggered - this shouldn't happen, likely wiring issue
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
    
    if ENABLE_NIGHT_ALERTS and is_suspicious_time():
        send_notification(
            "🚨 Podezřelá aktivita v garáži",
            f"Garážová vrata byla plně otevřena v {time_str} (neobvyklá doba)",
            priority="urgent",
            tags=["rotating_light", "warning"]
        )
    else:
        send_notification(
            "🚪 Garážová vrata otevřena",
            f"Garážová vrata dosáhla plně otevřené pozice v {time_str}",
            priority="default",
            tags=["door", "unlock"]
        )


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
    else:
        duration_str = ""
    
    send_notification(
        "🔒 Garážová vrata zavřena",
        f"Garážová vrata dosáhla plně zavřené pozice v {time_str}{duration_str}",
        priority="low",
        tags=["door", "lock"]
    )
    
    door_opened_at = None
    door_partial_at = None


def handle_door_partially_open():
    """Handle door in partial position"""
    global door_partial_at
    
    if door_partial_at is None:
        door_partial_at = time.time()
    
    time_str = datetime.now().strftime("%H:%M")
    
    send_notification(
        "⏸️ Garážová vrata částečně otevřena",
        f"Garážová vrata jsou v částečně otevřené pozici v {time_str}",
        priority="default",
        tags=["pause_button", "door"]
    )


def handle_door_unknown():
    """Handle unknown door state (both sensors triggered)"""
    send_notification(
        "❓ Neznámý stav garážových vrat",
        "Oba senzory jsou aktivní - možný problém s kabeláží",
        priority="high",
        tags=["question", "warning"]
    )


def monitor_loop():
    """Main monitoring loop"""
    global door_state
    
    log_info("Starting garage door monitor...")
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
        "Systém monitorování garážových vrat je nyní aktivní (režim 2 senzorů)",
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
        gpio.cleanup()
        log_info("GPIO cleanup completed")


# ==================== MAIN ====================

def main():
    """Main entry point"""
    
    # Check if running as root
    if not os.geteuid() == 0:
        sys.exit('ERROR: This script must be run as root (use sudo)')
    
    # Setup logging first
    setup_logging()
    log_info("=" * 60)
    log_info("Garage Door Monitor Starting")
    log_info("=" * 60)
    
    # Initialize GPIO
    log_info("Initializing GPIO...")
    gpio.init()
    
    # Configure both sensor pins as inputs with pull-up resistors
    gpio.setcfg(FULLY_OPEN_SENSOR_PIN, gpio.INPUT)
    gpio.pullup(FULLY_OPEN_SENSOR_PIN, gpio.PULLUP)
    
    gpio.setcfg(FULLY_CLOSED_SENSOR_PIN, gpio.INPUT)
    gpio.pullup(FULLY_CLOSED_SENSOR_PIN, gpio.PULLUP)
    
    log_info("GPIO initialized successfully")
    log_info("  - Fully open sensor: PIN configured")
    log_info("  - Fully closed sensor: PIN configured")
    log_info("")
    
    # Start monitoring
    monitor_loop()


if __name__ == "__main__":
    main()
