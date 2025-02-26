#!/bin/bash

set -e

# Script location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
MONITOR_SCRIPT="$SCRIPT_DIR/server_monitor.py"
LOG_FILE="/var/log/server_monitor.log"

echo "Setting up server monitoring..."

# Install dependencies
echo "Installing required packages..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip

# Install Python dependencies
echo "Installing Python requirements..."
sudo pip3 install psutil requests

# Make script executable
sudo chmod +x "$MONITOR_SCRIPT"

# Create log file and set permissions
sudo touch "$LOG_FILE"
sudo chmod 644 "$LOG_FILE"

# Set up cron job to run every 10 minutes
echo "Setting up cron job..."
CRON_JOB="*/10 * * * * $MONITOR_SCRIPT >> $LOG_FILE 2>&1"
(crontab -l 2>/dev/null || echo "") | grep -v "$MONITOR_SCRIPT" | { cat; echo "$CRON_JOB"; } | crontab -

echo "Testing the script..."
# Run the script in test mode
sudo python3 "$MONITOR_SCRIPT" --test

echo "Setup complete! Server monitoring is now active and will check resources every 10 minutes."
echo "Log file: $LOG_FILE"
echo ""
echo "Remember to update the webhook URL in the script with your Feishu webhook URL."
echo "You can edit it by running: sudo nano $MONITOR_SCRIPT"
