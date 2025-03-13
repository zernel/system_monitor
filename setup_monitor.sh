#!/bin/bash

set -e

# Script location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
MONITOR_SCRIPT="$SCRIPT_DIR/server_monitor.py"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
ENV_FILE="$SCRIPT_DIR/.env"
LOG_FILE="/var/log/server_monitor.log"

echo "Setting up server monitoring..."

# Install dependencies
echo "Installing required packages..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip

# Install Python dependencies
echo "Installing Python requirements..."
sudo pip3 install psutil requests python-dotenv

# Make script executable
sudo chmod +x "$MONITOR_SCRIPT"

# Create log file and set permissions
sudo touch "$LOG_FILE"
sudo chmod 644 "$LOG_FILE"

# Create .env file if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating .env file from template..."
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "Please edit $ENV_FILE to set at least one notification webhook URL:"
    echo "vim $ENV_FILE"
    read -p "Press Enter to continue after editing the .env file..."
else
    echo "Using existing .env file."
fi

# Set up cron job to run every 30 minutes with environment flag
echo "Setting up cron job..."
CRON_JOB="*/30 * * * * cd $SCRIPT_DIR && RUNNING_FROM_CRON=true python3 $MONITOR_SCRIPT >> $LOG_FILE 2>&1"
(crontab -l 2>/dev/null || echo "") | grep -v "$MONITOR_SCRIPT" | { cat; echo "$CRON_JOB"; } | crontab -

# Check if any webhook URL is configured
if ! grep -q -E "^(FEISHU|SLACK|MATTERMOST)_WEBHOOK_URL=.+" "$ENV_FILE" || grep -q "your-webhook-token-here" "$ENV_FILE"; then
    echo "WARNING: You need to configure at least one notification webhook URL in $ENV_FILE"
    echo "Please edit the file and update the webhook URL for Feishu, Slack, or Mattermost."
else
    echo "Testing the script..."
    # Run the script in test mode
    sudo python3 "$MONITOR_SCRIPT" --test
fi

echo "Setup complete! Server monitoring is now active and will check resources every 30 minutes."
echo "Log file: $LOG_FILE"
echo "Environment configuration: $ENV_FILE"
echo ""
echo "You can edit the environment settings anytime by running: vim $ENV_FILE"
