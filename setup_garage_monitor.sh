#!/bin/bash

# Setup script for Garage Door Monitor

echo "=== Garage Door Monitor Setup ==="
echo

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo "Error: config.yaml not found in current directory"
    exit 1
fi

# Read configuration from YAML
WORKING_DIR=$(grep -A 3 "^service:" config.yaml | grep "working_directory:" | sed 's/.*: *"\(.*\)"/\1/')
PYTHON_SCRIPT=$(grep -A 3 "^service:" config.yaml | grep "python_script:" | sed 's/.*: *"\(.*\)"/\1/')
SERVICE_USER=$(grep -A 3 "^service:" config.yaml | grep "user:" | sed 's/.*: *"\(.*\)"/\1/')

# Use defaults if not found in config
WORKING_DIR=${WORKING_DIR:-/opt/garage-monitor}
PYTHON_SCRIPT=${PYTHON_SCRIPT:-garage_door_monitor_v2.py}
SERVICE_USER=${SERVICE_USER:-root}

echo "Configuration from config.yaml:"
echo "  Working Directory: $WORKING_DIR"
echo "  Python Script: $PYTHON_SCRIPT"
echo "  Service User: $SERVICE_USER"
echo

# Install required Python packages
echo "Installing required Python packages..."
pip3 install requests
pip3 install pyserial
pip3 install pyyaml

# Make the script executable
echo "Making script executable..."
chmod +x $PYTHON_SCRIPT

# Create systemd service
echo
echo "Creating systemd service file..."
cat > /tmp/garage-monitor.service << EOF
[Unit]
Description=Garage Door Monitor
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$WORKING_DIR
ExecStart=/usr/bin/python3 $WORKING_DIR/$PYTHON_SCRIPT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo
echo "✓ Setup complete!"
echo
echo "Next steps:"
echo "1. Edit config.yaml to set your ntfy.sh topic and Arduino port"
echo "2. Upload Arduino sketch to your Arduino Nano"
echo "3. Test the script: python3 $PYTHON_SCRIPT"
echo
echo "To install as a service:"
echo "  sudo cp /tmp/garage-monitor.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable garage-monitor"
echo "  sudo systemctl start garage-monitor"
echo "  sudo systemctl status garage-monitor"
echo
echo "To view logs:"
echo "  sudo journalctl -u garage-monitor -f"
echo
echo "To subscribe to notifications:"
echo "  1. Install ntfy app on your phone (Android/iOS)"
echo "  2. Subscribe to your topic from config.yaml"
echo "  3. Or use web: https://ntfy.sh/app"
