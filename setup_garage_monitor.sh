#!/bin/bash

# Setup script for Garage Door Monitor

echo "=== Garage Door Monitor Setup ==="
echo

# Install required Python packages
echo "Installing required Python packages..."
pip3 install requests

# Make the script executable
echo "Making script executable..."
chmod +x garage_door_monitor.py

# Create systemd service (optional)
echo
echo "Creating systemd service file..."
cat > /etc/systemd/system/garage-monitor.service << 'EOF'
[Unit]
Description=Garage Door Monitor
After=network.target

[Service]
Type=simple
User=root
#change to your user and path
WorkingDirectory=/opt/garage-monitor
ExecStart=/usr/bin/python3 /opt/garage-monitor/garage_door_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo
echo "Setup complete!"
echo
echo "Next steps:"
echo "1. Edit the configuration in garage_door_monitor.py (lines 15-30)"
echo "2. Set your NTFY_TOPIC to a unique value"
echo "3. Adjust DOOR_SWITCH_PIN to match your wiring"
echo "4. Test the script: sudo python3 garage_door_monitor.py"
echo
echo "To install as a service:"
echo "  sudo cp /tmp/garage-monitor.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable garage-monitor"
echo "  sudo systemctl start garage-monitor"
echo "  sudo systemctl status garage-monitor"
echo
echo "To subscribe to notifications:"
echo "  1. Install ntfy app on your phone (Android/iOS)"
echo "  2. Subscribe to your topic: https://ntfy.sh/your-garage-topic"
echo "  3. Or use web: https://ntfy.sh/app"
